"""
This module contains the built-in tooltip database for Python keywords.

This serves as the fallback data source for the application's tooltip provider,
offering helpful information when the Language Server Protocol (LSP) does not
provide a hover result for a specific language keyword.
"""

PYTHON_KEYWORD_TOOLTIPS = {
    "if": "Performs a conditional check. The following block of code will execute only if the condition is true.",
    "elif": "Else if. A subsequent conditional check that runs only if the preceding 'if' or 'elif' conditions were false.",
    "else": "Executes a block of code if all preceding 'if' and 'elif' conditions were false.",
    "for": "Loops over the items of a sequence (like a list or string), executing a block of code for each item.",
    "while": "Continuously executes a block of code as long as a given condition is true.",
    "break": "Immediately exits the innermost 'for' or 'while' loop.",
    "continue": "Skips the rest of the current iteration of a loop and proceeds to the next one.",
    "pass": "A null operation. When the statement is executed, nothing happens. It is useful as a placeholder.",
    "match": "Starts a structural pattern matching block, similar to a switch statement in other languages. (Python 3.10+)",
    "case": "A pattern within a 'match' block. If the pattern matches the subject, its code block is executed.",
    "def": "Defines a function. A function is a reusable block of code that performs a specific task.",
    "class": "Defines a class. A class is a blueprint for creating objects (instances).",
    "return": "Exits a function and optionally passes a value back to the caller.",
    "yield": "Pauses a generator function and returns a value to the caller, saving the state for the next call.",
    "lambda": "Creates a small, anonymous function on a single line.",
    "self": "A conventional name for the first argument of a method in a class, representing the instance of the object itself.",
    "import": "Brings a module into the current scope, allowing you to use its functions, classes, and variables.",
    "from": "Used with 'import' to bring specific parts of a module into the current scope.",
    "as": "Used to create an alias for a module or object when importing.",
    "try": "Specifies a block of code to be tested for errors while it is being executed.",
    "except": "Catches and handles specific exceptions (errors) that occurred in the 'try' block.",
    "finally": "Specifies a block of code that will be executed regardless of whether an error occurred in the 'try' block.",
    "raise": "Used to raise an exception (error) manually.",
    "assert": "Tests a condition, and if the condition is false, it raises an AssertionError.",
    "global": "Declares that a variable inside a function is global (i.e., its value is in the main scope).",
    "nonlocal": "Declares that a variable inside a nested function refers to a variable in the enclosing function.",
    "del": "Deletes an object, variable, or item from a list or dictionary.",
    "with": "Used to wrap the execution of a block of code with methods defined by a context manager. Often used for file I/O.",
    "async": "Declares a function as an asynchronous coroutine.",
    "await": "Pauses the execution of an async function to wait for an awaitable object (like a coroutine) to complete.",
}
