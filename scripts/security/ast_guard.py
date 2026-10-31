"""
scripts/security/ast_guard.py

Static AST Taint Analysis and Security Guardrails for Polyglot Code Evaluation.
Supports:
- Python (via native ast.parse and NodeVisitor)
- TypeScript / JavaScript (via static lexical and regex AST heuristics)
- PHP (via static token screening)
- SQL (via lexical statement parser)
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class SecurityViolation:
    """Represents a detected security violation in analyzed code."""
    category: str
    message: str
    lineno: Optional[int] = None
    node_type: Optional[str] = None


@dataclass
class AstSecurityReport:
    """Consolidated security analysis report for a code snippet."""
    is_safe: bool
    violations: List[SecurityViolation] = field(default_factory=list)
    language: str = "python"


class PythonSecurityVisitor(ast.NodeVisitor):
    """AST visitor that checks for dangerous Python nodes and patterns."""

    FORBIDDEN_MODULES: Set[str] = {
        "os", "sys", "subprocess", "shutil", "socket", "urllib", "requests",
        "http", "ctypes", "posix", "nt", "importlib", "pickle", "shelve",
        "webbrowser", "winreg", "pty", "commands", "cgi", "cgitb"
    }

    FORBIDDEN_CALLS: Set[str] = {
        "eval", "exec", "open", "compile", "breakpoint", "input",
        "__import__", "exit", "quit"
    }

    FORBIDDEN_ATTRIBUTES: Set[str] = {
        "__builtins__", "__subclasses__", "__bases__", "__class__",
        "__globals__", "__code__", "__closure__", "system", "popen",
        "spawn", "fork", "kill", "eval", "exec", "open"
    }

    def __init__(self) -> None:
        super().__init__()
        self.violations: List[SecurityViolation] = []

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in ("__builtins__", "globals", "locals", "vars"):
            self.violations.append(
                SecurityViolation(
                    category="reflection_escape",
                    message=f"Direct access to reflection namespace or variable '{node.id}' is prohibited.",
                    lineno=node.lineno,
                    node_type="Name"
                )
            )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_mod = alias.name.split(".")[0]
            if root_mod in self.FORBIDDEN_MODULES:
                self.violations.append(
                    SecurityViolation(
                        category="forbidden_import",
                        message=f"Import of forbidden module '{alias.name}' is prohibited.",
                        lineno=node.lineno,
                        node_type="Import"
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root_mod = node.module.split(".")[0]
            if root_mod in self.FORBIDDEN_MODULES:
                self.violations.append(
                    SecurityViolation(
                        category="forbidden_import",
                        message=f"Import from forbidden module '{node.module}' is prohibited.",
                        lineno=node.lineno,
                        node_type="ImportFrom"
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct calls (e.g. eval(), exec(), open())
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.FORBIDDEN_CALLS:
                self.violations.append(
                    SecurityViolation(
                        category="forbidden_call",
                        message=f"Direct call to dangerous builtin function '{func_name}' is prohibited.",
                        lineno=node.lineno,
                        node_type="Call"
                    )
                )
            elif func_name in ("getattr", "setattr", "delattr"):
                # Check if second argument is a forbidden attribute string literal
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                    attr_val = node.args[1].value
                    if attr_val in self.FORBIDDEN_ATTRIBUTES:
                        self.violations.append(
                            SecurityViolation(
                                category="reflection_escape",
                                message=f"Dynamic reflection accessing forbidden attribute '{attr_val}' is prohibited.",
                                lineno=node.lineno,
                                node_type="Call"
                            )
                        )

        # Check method calls (e.g. os.system(), Path.unlink())
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in ("unlink", "rmdir", "remove", "system", "popen", "spawn"):
                self.violations.append(
                    SecurityViolation(
                        category="forbidden_call",
                        message=f"Call to destructive filesystem or process method '{attr_name}' is prohibited.",
                        lineno=node.lineno,
                        node_type="Call"
                    )
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in self.FORBIDDEN_ATTRIBUTES:
            self.violations.append(
                SecurityViolation(
                    category="dunder_access",
                    message=f"Access to sensitive internal attribute '{node.attr}' is prohibited.",
                    lineno=node.lineno,
                    node_type="Attribute"
                )
            )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        # Check dictionary lookups for __builtins__
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            if node.slice.value in ("__builtins__", "os", "subprocess"):
                self.violations.append(
                    SecurityViolation(
                        category="reflection_escape",
                        message=f"Subscript lookup of forbidden key '{node.slice.value}' is prohibited.",
                        lineno=node.lineno,
                        node_type="Subscript"
                    )
                )
        self.generic_visit(node)


class AstSecurityGuard:
    """Consolidated security validator across all supported languages."""

    def check_python(self, code: str) -> AstSecurityReport:
        """Analyzes Python code via AST parsing."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return AstSecurityReport(
                is_safe=False,
                violations=[
                    SecurityViolation(
                        category="syntax_error",
                        message=f"Python syntax error: {e}",
                        lineno=e.lineno
                    )
                ],
                language="python"
            )

        visitor = PythonSecurityVisitor()
        visitor.visit(tree)
        is_safe = len(visitor.violations) == 0
        return AstSecurityReport(is_safe=is_safe, violations=visitor.violations, language="python")

    def check_typescript(self, code: str) -> AstSecurityReport:
        """Analyzes TypeScript / JavaScript code via static heuristics."""
        violations: List[SecurityViolation] = []

        patterns = [
            (r"require\s*\(\s*['\"](fs|child_process|net|http|https|os|process|dns)['\"]\s*\)", "forbidden_import", "Forbidden Node.js module import"),
            (r"import\s+.*from\s+['\"](fs|child_process|net|http|https|os|process|dns)['\"]", "forbidden_import", "Forbidden ESM module import"),
            (r"fetch\s*\(", "network_call", "Unauthorized network fetch call"),
            (r"process\.(exit|kill|env|binding)", "process_manipulation", "Host process manipulation"),
            (r"eval\s*\(", "forbidden_call", "Dynamic eval execution"),
            (r"Function\s*\(", "forbidden_call", "Dynamic Function constructor execution"),
        ]

        for pattern, category, msg in patterns:
            if re.search(pattern, code):
                violations.append(SecurityViolation(category=category, message=msg))

        return AstSecurityReport(is_safe=len(violations) == 0, violations=violations, language="typescript")

    def check_php(self, code: str) -> AstSecurityReport:
        """Analyzes PHP code via static token screening."""
        violations: List[SecurityViolation] = []

        patterns = [
            (r"\b(system|exec|passthru|shell_exec|popen|proc_open|pcntl_exec)\s*\(", "forbidden_call", "Host command execution function"),
            (r"\bfile_get_contents\s*\(\s*['\"]https?://", "network_call", "Unauthorized outbound HTTP request"),
            (r"\b(curl_init|curl_exec)\s*\(", "network_call", "Unauthorized cURL network request"),
            (r"\beval\s*\(", "forbidden_call", "Dynamic evaluation construct"),
            (r"\bassert\s*\(\s*['\"]", "forbidden_call", "Dynamic code assertion via string evaluation"),
            (r"\b(unlink|rmdir)\s*\(", "forbidden_call", "Destructive filesystem operation"),
        ]

        for pattern, category, msg in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                violations.append(SecurityViolation(category=category, message=msg))

        return AstSecurityReport(is_safe=len(violations) == 0, violations=violations, language="php")

    def check_sql(self, code: str) -> AstSecurityReport:
        """Analyzes SQL queries for prohibited administrative and DDL commands."""
        violations: List[SecurityViolation] = []

        # Remove single line and multi-line comments
        clean_sql = re.sub(r"--.*", "", code)
        clean_sql = re.sub(r"/\*.*?\*/", "", clean_sql, flags=re.DOTALL)

        patterns = [
            (r"\bDROP\s+(DATABASE|SCHEMA|TABLE|USER|ROLE)\b", "forbidden_ddl", "Destructive DROP DDL command"),
            (r"\bALTER\s+(DATABASE|SYSTEM)\b", "forbidden_ddl", "System ALTER command"),
            (r"\bTRUNCATE\s+TABLE\b", "forbidden_ddl", "Destructive TRUNCATE command"),
            (r"\bSHUTDOWN\b", "admin_command", "Database SHUTDOWN command"),
            (r"\bATTACH\s+(DATABASE\s+)?", "forbidden_call", "Database ATTACH file operation"),
            (r"\bDETACH\s+(DATABASE\s+)?", "forbidden_call", "Database DETACH operation"),
            (r"\bxp_cmdshell\b", "forbidden_call", "xp_cmdshell shell execution"),
            (r"\bLOAD_EXTENSION\b", "forbidden_call", "External library load operation"),
        ]

        for pattern, category, msg in patterns:
            if re.search(pattern, clean_sql, re.IGNORECASE):
                violations.append(SecurityViolation(category=category, message=msg))

        return AstSecurityReport(is_safe=len(violations) == 0, violations=violations, language="sql")
