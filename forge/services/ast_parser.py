import ast
from lsprotocol import types


class OutlineVisitor(ast.NodeVisitor):
    """A dedicated visitor to get only high-level symbols for the outline view."""

    def __init__(self):
        self.symbols = []
        self.current_scope = self.symbols

    def visit_FunctionDef(self, node):
        self.current_scope.append(
            {
                "name": node.name,
                "lineno": node.lineno,
                "end_lineno": getattr(node, "end_lineno", node.lineno),
                "type": "method",
                "children": [],
            }
        )

    def visit_ClassDef(self, node):
        class_symbol = {
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": getattr(node, "end_lineno", node.lineno),
            "type": "class",
            "children": [],
        }
        self.current_scope.append(class_symbol)
        previous_scope = self.current_scope
        self.current_scope = class_symbol["children"]
        self.generic_visit(node)
        self.current_scope = previous_scope


class CompletionVisitor(ast.NodeVisitor):
    """A dedicated visitor to get all relevant symbols for autocompletion."""

    def __init__(self, cursor_line):
        self.completions = []
        self.cursor_line = cursor_line
        self.scope_stack = []

    def visit(self, node):
        self.scope_stack.append(node)
        super().visit(node)
        self.scope_stack.pop()

    def visit_Import(self, node):
        for alias in node.names:
            self.completions.append(
                {"label": alias.name, "kind": types.CompletionItemKind.Module}
            )

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.completions.append(
                {"label": alias.name, "kind": types.CompletionItemKind.Variable}
            )

    def visit_FunctionDef(self, node):
        self.completions.append(
            {"label": node.name, "kind": types.CompletionItemKind.Function}
        )
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)
        if start_line <= self.cursor_line <= end_line:
            for arg in node.args.args:
                if arg.arg != "self":
                    self.completions.append(
                        {"label": arg.arg, "kind": types.CompletionItemKind.Variable}
                    )
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.completions.append(
            {"label": node.name, "kind": types.CompletionItemKind.Class}
        )
        self.generic_visit(node)

    def visit_Assign(self, node):

        is_global = len(self.scope_stack) > 1 and isinstance(
            self.scope_stack[-2], ast.Module
        )

        if is_global:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.completions.append(
                        {"label": target.id, "kind": types.CompletionItemKind.Variable}
                    )

        in_function_scope = False
        for scope_node in reversed(self.scope_stack):
            if isinstance(scope_node, ast.FunctionDef):
                start_line = scope_node.lineno
                end_line = getattr(scope_node, "end_lineno", start_line)
                if (
                    start_line <= self.cursor_line <= end_line
                    and node.lineno < self.cursor_line
                ):
                    in_function_scope = True
                break

        if in_function_scope:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.completions.append(
                        {"label": target.id, "kind": types.CompletionItemKind.Variable}
                    )


class ASTParser:
    def get_symbols(self, source_code):
        try:
            tree = ast.parse(source_code, feature_version=(3, 9))
            for node in ast.walk(tree):
                if hasattr(node, "body") and isinstance(node.body, list) and node.body:
                    node.end_lineno = getattr(
                        node.body[-1], "end_lineno", node.body[-1].lineno
                    )
                elif hasattr(node, "lineno"):
                    node.end_lineno = node.lineno
            visitor = OutlineVisitor()
            visitor.visit(tree)
            return visitor.symbols
        except (SyntaxError, ValueError):
            return []

    def get_completions(self, source_code, line):
        try:
            tree = ast.parse(source_code, feature_version=(3, 9))
            for node in ast.walk(tree):
                if hasattr(node, "body") and isinstance(node.body, list) and node.body:
                    node.end_lineno = getattr(
                        node.body[-1], "end_lineno", node.body[-1].lineno
                    )
                elif hasattr(node, "lineno"):
                    node.end_lineno = node.lineno
            visitor = CompletionVisitor(cursor_line=line)
            visitor.visit(tree)
            return list({v["label"]: v for v in visitor.completions}.values())
        except (SyntaxError, ValueError):
            return []
