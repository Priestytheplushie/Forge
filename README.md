# Forge

Forge is an experimental Python IDE featuring live object introspection and Git tooling. Unstable, abandoned, **not recommended for daily use**.

> [!WARNING]
> **ABANDONED / DEPRECATED**  
> This project is **experimental**, structurally fragile, and no longer maintained. It is preserved here strictly as a portfolio piece and an architectural experiment. **Do not use this as your daily driver.**

<p align="center">
  <img src="assets/screenshot.png" alt="Forge IDE Screenshot" width="100%">
</p>

## What was this?
Forge was an attempt to build a custom Python IDE from scratch using `PySide6` (Qt).

Forge included `PyForge`, an experimental introspection library and agent. `PyForge` was designed to hook into a running Python script over a local TCP socket, scrape Python's garbage collector (`gc.get_objects()`) to find live class instances, and let you inspect or rewrite variables directly in memory without restarting your program. 

It also attempted to bundle: 
- An LSP client connected to `basedpyright` for autocompletion and diagnostics. 
- An automated refactoring pipeline chaining `Ruff`, `Black`, and `pyupgrade`. 
- A full Git client with visual branch, rebase, and merge conflict views.
- Local snapshot history saving every file edit to a hidden directory.
- A real terminal powered by `xterm.js`.
- Best in class code editing with `Monaco Editor`.

Forge was meant to be the de facto IDE which could do it all, the "swiss army knife" of code editors. It had stuff from `VS Code`, `GitKraken`, and even unique stuff like `PyForge`. However, it turns out trying to do what teams of thousands of devs do as a solo developer leads to some... compromises.

## A retrospective on Forge
To explain **where Forge went wrong**, I think it's fair to have a second look. As I'm writing this, it's `September 8th, 2026`, almost a full year after Forge was abandoned. Taking a step back and analyzing what worked and what didn't can help us all learn, which is really what Forge was to me: an experiment and a learning experience. 

> [!NOTE]
> If you just want to install Forge and run it for yourself, you can skip to the "Running It" section.

### The Origin of "Forge"
"Forge", the name, was not originally an **IDE** at all. It was an **AI Agent CLI** developed by me around `Early 2025`, which was about `1-2 months` before **Forge** the IDE began development. I'll refer to it as **Forge-Agent** from now on. This CLI was originally meant to be an Autonomous AI Agent. It had a sleek UI with `rich`, and it even had a `tkinter` GUI for something called `Agent Requests`, which was a rip-off of Pull Requests from GitHub. The reason I'm sharing this is because this was what motivated the **Forge IDE's motto**: "Your AI Collaborative Partner". The original vision for Forge was to use AI, but as we'll see... that dream never happened. 

After **Forge-Agent**, I worked on many small projects, like [PriestyCode](https://github.com/Priestytheplushie/PriestyCode), which was a `tkinter` IDE. That then became the very first **Forge IDE**, which was made using `customtkinter` (which is on the `tkinter` branch of this repository). This IDE was not good—very incomplete and buggy. However, it sparked an interest in me for building IDEs, which is when I discovered `PySide6`, and boy, was I motivated... 

After the discovery of `PySide6`, I began working on the `Forge` we know today. But I was kind of weird and ambitious, and decided that I would use the `Monaco` editor because I didn't like `tk.text` and was scared of `QPlainTextEdit`, as they seemed similar. This became a rabbit hole, which is what shaped Forge today.

With this history, you know where the AI motto came from and a brief history of my endeavors in making IDEs. With that, we can look into Forge's design choices, starting with... 

### The Good 
Before we get into all the broken, underdeveloped codebase, I think we should look at the **positive** stuff Forge has, starting with the concept / idea. While not a good idea in general due to scope creep (we'll get to that later), the original concept of a hyper-focused "AI-powered" IDE seemed promising, and if you look at all the other features like `PyForge`, they were good ideas—just with flaws. Also, while `PyForge` is nowhere near suited for production, it was a creative idea, and the UI for PyForge inside Forge was pretty nice. Finally, it was also a miracle that it even ran, because with all the stuff I dumped into it, it still kind of works, which is crazy. But with these good things came a truckload of bugs, technical debt, and poor architecture, which made Forge borderline unusable. So let's talk about the bad...  

### Web Tech in Python
This was the biggest flaw in `Forge`, hands down. I wanted a modern text editor, so I decided to use `Monaco` because I heard that using `QPlainTextEdit` would lead to a bad time. I wanted a terminal, and after dealing with trying to mock a terminal in [PriestyCode](https://github.com/Priestytheplushie/PriestyCode), I decided to use `xterm.js` and use a real `pty` / pseudoterminal. 

The core problem with web tech in Python is communication between the languages. You have to use `QWebChannel`, which is basically like the two languages shouting at each other through a Discord group DM, with Python trying to hold it all together. This especially failed because of differences between the languages: **JavaScript is weakly typed**, **Python is strongly typed**. This caused a lot of `TypeError`s to appear, especially on startup for `Monaco`, leading to the creation of `RecoverableWebEnginePage`, which just shows how unstable it was. It basically turned simple stuff like moving the cursor, getting autocomplete from LSPs, and saving a file into complicated tasks with race conditions, bugs, and render crashes. Not to mention performance takes a massive tank because of the bridge. **If you want web tech, use Electron**. End of story.

### PyForge: Brilliant Idea, Horrible Execution 
PyForge tried to treat Python runtimes like dynamic game engines where you can hot-patch code in real time. This creates massive problems, security risks, and is very experimental in nature. For PyForge to work, it needed to...

#### Monkey Patching
PyForge had to **monkey patch** the `__new__` method on classes to track new object creation for the Object Tree. This is terrible for many reasons. Firstly, monkey patching in general is an **anti-pattern**, especially on core libraries or built-ins, because it can create major issues and incompatibilities. It also degrades performance because you know that my code was unoptimized. It could also create security risks, and a whole other list of issues. Monkey patching is a **last resort**, not a core feature.

#### Traversing the Garbage 
PyForge wanted to create a tree of all objects in your app so you can manipulate them, which seems fine enough, but the problem is it used `gc.get_objects()`, which literally grabs every object in the Garbage Collector. This is bad because of performance: loading all these objects in the Object Tree lagged, even with lazy loading. And more importantly, it gave us... well, garbage. It's the Garbage Collector, so most of the stuff you found with PyForge was practically useless. PyForge suffered from having very little filtering, meaning that it mostly just displayed garbage in `[All Live Instances]`, which is really bad UX and not even useful.

#### Hot Reloading 
PyForge decided that `hot reloading` is the solution to everything, when it's not... Firstly, it broke on the entry point file, requiring sketchy fixes in order for it to work. Secondly, it relied on a `master.pfscript`, which was hot reloaded constantly. This is bad because hot reloading existing modules is dangerous and can create issues like memory leaks. The ability to hot reload every file sounds cool on paper, but again, it's dangerous. Loading **new modules** is genuinely useful if you need something like a utility, but hot reloading is just risky and should probably be avoided.

#### Conclusion
Overall, `PyForge` was an innovative idea with terrible execution. I haven't even scratched the surface of all the issues and dangers of using it, but the concept was solid. Looking back, Forge would have been completely fine without it, but I'm glad it was included. It was a nice "gimmick", but not practical for real-time debugging or serious development.

> [!CAUTION]
> **DO NOT USE PYFORGE ON SCRIPTS YOU CARE ABOUT**: Do not run `PyForge` on long-running scripts like web servers, games, or anything you care about, because it's very unstable and insecure and could lead to corruption, data loss, and other bugs. 

### The "AI" was fake
The core vision of Forge was "Your AI Collaborative Partner", but looking at Forge, there is **zero AI involved**. There is no OpenAI API, no Claude, no Gemini, no Ollama, no nothing. It was the heart of the Forge brand, and yet it never happened due to **scope creep**, which is a shame because what even is Forge without AI? Just some random IDE with random features. The IDE is just a poorly built IDE with "AI" stamped everywhere that did absolutely nothing.

### Over-engineering & Scope Creep
This was the real killer. Instead of building a solid text editor, I decided I would make the next `VS Code`, `GitKraken`, and debugger all in Python, as a solo developer, and as a hobby project. This is the definition of **scope creep**, because I missed out on the main appeal of Forge: the AI. 

The result of this ever-growing scope can be seen inside `main_controller.py`, which is impossible to maintain and stabilize. It's also a shame because I had an internal `roadmap.md`, but after a while I just ignored it and built random stuff, which just leads to scope creep. What I learned is that you need to stick with the scope; you can't just keep adding stuff before a release. I'm still... not good at this, for example [PriestyAI](https://github.com/Priestytheplushie/PriestyAI), which went through a complete rewrite before it even became a public GitHub repository. 

### Conclusion 
In conclusion, `Forge` failed due to being a high-scoped hobby project. It was inevitably going to break down, as 1 developer can't maintain 3 enterprise-scale apps alone. It also took risks—big ones—and used experimental, shady "hacks" in order to work properly, which is not great. While `Forge` may have been a failure, it did teach me a lot about software development and architecture, which I am thankful for, meaning it wasn't a waste to develop. 

Forge is like a "Jack of all trades", as the old saying goes...
> "...a Jack of all trades, and in truth, master of none."

Forge tries to do everything, but by doing that, it masters nothing, making it fundamentally a worse choice for an IDE than something like `VS Code`. Do not use Forge; use it as a learning tool and an **example of what NOT to do**. 

## Running It 
Forge is relatively easy to run, requiring installing `requirements.txt` and the `basedpyright` language server via npm. I was kind of dumb and included both `xterm.js` and `Monaco` locally, so no install is needed for those, but they may be outdated.

```bash
# Clone the repo 
git clone https://github.com/Priestytheplushie/Forge.git 
cd Forge 

# Install the language server for LSP features
npm install -g basedpyright

# Set up virtual environment 
python -m venv .venv 

# Activate virtual environment
# On Linux / macOS:
source .venv/bin/activate 
# On Windows: 
.venv\Scripts\activate 

# Install Python dependencies 
pip install -r requirements.txt 

# Run Forge 
python src/forge/main.py
```

## Development 
I think it's clear from the retrospective and big warning that this repo is not going to be developed further. Pull Requests and Issues have been disabled, and this is mainly just an educational and demonstrational repository. You're free to use it as an example (of what **not** to do) and even run it if you like, but do not expect any updates.

## License 
MIT (see [LICENSE.md](LICENSE.md)). Third-party notices in [NOTICE.md](NOTICE.md).