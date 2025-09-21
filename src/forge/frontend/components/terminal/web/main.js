

let term;
let bridge;
const fitAddon = new FitAddon.FitAddon();

console.log("main.js: Script started.");

term = new Terminal({
    cursorBlink: true,
    convertEol: true,
    theme: { 
        background: '#1e1e1e', 
        foreground: '#cccccc' 
    }
});
term.loadAddon(fitAddon);
term.open(document.getElementById('terminal'));
console.log("main.js: Terminal created and opened.");

new QWebChannel(qt.webChannelTransport, function (channel) {
    console.log("main.js: QWebChannel connection established.");
    bridge = channel.objects.bridge;

    term.onData(data => {
        bridge.receive_data_from_js(data);
    });

    if (bridge) {
        console.log("main.js: Bridge object found. Calling js_loaded.");
        bridge.js_loaded();
    } else {
        console.error("main.js: Bridge object NOT found.");
    }
});

function write_to_terminal(data) {
    if (term) {
        term.write(data);
    }
}


function clear_terminal() {
    if (term) {
        term.clear();
    }
}

function resize_terminal() {
    if (term && bridge) {
        fitAddon.fit();
        bridge.resize_pty(term.cols, term.rows);
    }
}

function request_initial_size() {
    console.log("main.js: request_initial_size() called by Python.");
    if (term && bridge) {
        fitAddon.fit();
        const size = [term.cols, term.rows];
        console.log("main.js: Calculated initial size:", size, ". Calling receive_initial_size slot.");
        bridge.receive_initial_size(size[0], size[1]);
    } else {
        console.warn("main.js: request_initial_size() called before bridge was ready.");
    }
}