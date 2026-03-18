#!/usr/bin/env python3
"""
PR Security Agent
=================
Scans Python files under `implementations/` for dangerous shell/exec commands
that lack a Human-in-the-Loop (HITL) safeguard (i.e. an ``input()`` call).

The scanner uses the Python ``ast`` module so that patterns inside comments,
docstrings, and string literals are **never** flagged as violations.

HITL detection is scope-aware: an ``input()`` call is only accepted as a guard
when it appears at a strictly earlier line number within the **same function**
(or at module level) as the dangerous call.  An ``input()`` in an unrelated
function, or anywhere *after* the dangerous call, is not considered a guard.

Import aliases are fully resolved:
  * ``import os as o; o.system(...)``           → flagged
  * ``from subprocess import run; run(...)``    → flagged
  * ``from subprocess import run as r; r(...)`` → flagged

Usage
-----
    python scripts/pr_security_agent.py <file1.py> [file2.py ...]

Exit codes
----------
  0 — All scanned files passed.
  1 — One or more files contain a dangerous pattern without a scoped input() guard.
  2 — Unexpected runtime error (e.g. file unreadable or unparseable).
"""

import ast
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Calls considered "dangerous" when no HITL guard is present.
#
# Format: mapping from (module_or_None, function_name) → human-readable label.
#   - (None, "eval")          matches bare   eval(...)
#   - ("os", "system")        matches        os.system(...)
#   - ("subprocess", "run")   matches        subprocess.run(...)
# ---------------------------------------------------------------------------
_DANGEROUS_CALLS: dict[tuple[str | None, str], str] = {
    # os module
    ("os", "system"): "os.system",
    ("os", "popen"): "os.popen",
    ("os", "execv"): "os.execv",
    ("os", "execve"): "os.execve",
    ("os", "execvp"): "os.execvp",
    ("os", "execvpe"): "os.execvpe",
    ("os", "execl"): "os.execl",
    ("os", "execle"): "os.execle",
    ("os", "execlp"): "os.execlp",
    ("os", "execlpe"): "os.execlpe",
    # subprocess module
    ("subprocess", "run"): "subprocess.run",
    ("subprocess", "call"): "subprocess.call",
    ("subprocess", "check_call"): "subprocess.check_call",
    ("subprocess", "check_output"): "subprocess.check_output",
    ("subprocess", "Popen"): "subprocess.Popen",
    # Built-in builtins
    (None, "eval"): "eval",
    (None, "exec"): "exec",
    (None, "__import__"): "__import__",
    (None, "compile"): "compile",
}


def _collect_import_info(tree: ast.AST) -> tuple[dict[str, str], dict[str, str]]:
    """Collect simple import/alias information for dangerous modules/functions.

    Returns:
        module_aliases: maps local module names (including aliases) to
            canonical module names used in _DANGEROUS_CALLS, e.g. {"o": "os"}.
        imported_dangerous: maps locally imported function names (including
            aliases) to their human-readable danger label, e.g.
            {"run": "subprocess.run", "r": "subprocess.run"}.
    """
    module_aliases: dict[str, str] = {}
    imported_dangerous: dict[str, str] = {}

    dangerous_modules = {mod for (mod, _) in _DANGEROUS_CALLS.keys() if mod is not None}

    for node in ast.walk(tree):
        # import os as o
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(".")[0]
                if module_name in dangerous_modules:
                    local_name = alias.asname or module_name
                    module_aliases[local_name] = module_name

        # from subprocess import run as r
        elif isinstance(node, ast.ImportFrom):
            if not node.module:
                continue
            base_module = node.module.split(".")[0]
            for alias in node.names:
                imported_name = alias.name
                local_name = alias.asname or imported_name
                label = _DANGEROUS_CALLS.get((base_module, imported_name))
                if label:
                    imported_dangerous[local_name] = label

    return module_aliases, imported_dangerous


def _call_label(
    node: ast.Call,
    module_aliases: dict[str, str],
    imported_dangerous: dict[str, str],
) -> str | None:
    """Return a danger label for an AST Call node, or None if it is safe."""
    func = node.func

    # Bare name: eval(...), exec(...), from-imported dangerous functions, etc.
    if isinstance(func, ast.Name):
        # Built-in dangerous calls (module is None in _DANGEROUS_CALLS)
        builtin_label = _DANGEROUS_CALLS.get((None, func.id))
        if builtin_label is not None:
            return builtin_label

        # Dangerous functions imported via "from module import name"
        return imported_dangerous.get(func.id)

    # Attribute access: os.system(...), subprocess.run(...), including aliases
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        base_name = func.value.id
        # Resolve module alias if present (e.g. o -> os)
        module_name = module_aliases.get(base_name, base_name)
        return _DANGEROUS_CALLS.get((module_name, func.attr))

    return None


class _ScopeAwareScanner(ast.NodeVisitor):
    """Walk the AST scope-by-scope to find dangerous calls that lack a
    preceding ``input()`` guard within the same function (or module-level)
    scope.

    A dangerous call is considered guarded only when an ``input()`` call
    appears at a strictly earlier line number **in the same scope**.  An
    ``input()`` call in a *different* function, or anywhere after the
    dangerous call, does **not** count.
    """

    def __init__(
        self,
        module_aliases: dict[str, str],
        imported_dangerous: dict[str, str],
    ) -> None:
        self._module_aliases = module_aliases
        self._imported_dangerous = imported_dangerous
        self.violations: list[tuple[int, str]] = []
        # Each entry in the stack holds the input() line-numbers seen so far
        # in that scope.  The bottom entry is the module-level scope.
        self._input_stack: list[list[int]] = [[]]

    # ------------------------------------------------------------------
    # Scope management
    # ------------------------------------------------------------------

    def _push_scope(self) -> None:
        self._input_stack.append([])

    def _pop_scope(self) -> None:
        self._input_stack.pop()

    def _record_input(self, lineno: int) -> None:
        self._input_stack[-1].append(lineno)

    def _has_prior_input(self, lineno: int) -> bool:
        """Return True if any ``input()`` was seen at an earlier line in the
        current scope."""
        return any(il < lineno for il in self._input_stack[-1])

    # ------------------------------------------------------------------
    # Visitors
    # ------------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Each function body gets its own independent scope.
        self._push_scope()
        self.generic_visit(node)
        self._pop_scope()

    # AsyncFunctionDef uses the same logic as FunctionDef.
    # The type: ignore suppresses mypy's complaint that the two method
    # signatures differ slightly in their node type annotations.
    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func

        # Record input() before checking for dangerous calls.  When both
        # share the same line number (e.g. os.system(input("cmd?"))), the
        # strictly-less-than comparison in _has_prior_input means the
        # inner input() does *not* count as a guard — which is the
        # intended behaviour: the argument provides the command, not a
        # prior human confirmation.
        if isinstance(func, ast.Name) and func.id == "input":
            self._record_input(node.lineno)

        label = _call_label(node, self._module_aliases, self._imported_dangerous)
        if label and not self._has_prior_input(node.lineno):
            self.violations.append((node.lineno, label))

        self.generic_visit(node)


def scan_file(filepath: str) -> list[dict]:
    """Scan a single Python file and return a list of violation dicts.

    Each violation dict has keys: ``file``, ``line``, ``code``, ``label``.
    An empty list means the file passed the check.
    """
    path = Path(filepath)

    if not path.exists():
        print(f"[WARNING] File not found, skipping: {filepath}", file=sys.stderr)
        return []

    if path.suffix.lower() != ".py":
        return []

    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[ERROR] Cannot read {filepath}: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        print(
            f"[ERROR] Cannot parse {filepath} (SyntaxError: {exc}). "
            "Falling back to failure to be conservative.",
            file=sys.stderr,
        )
        sys.exit(2)

    module_aliases, imported_dangerous = _collect_import_info(tree)
    scanner = _ScopeAwareScanner(module_aliases, imported_dangerous)
    scanner.visit(tree)

    source_lines = source.splitlines()
    violations: list[dict] = []

    for lineno, label in scanner.violations:
        code = source_lines[lineno - 1].strip() if lineno <= len(source_lines) else ""
        violations.append(
            {
                "file": filepath,
                "line": lineno,
                "code": code,
                "label": label,
            }
        )

    return violations


def main() -> None:
    files = sys.argv[1:]

    if not files:
        print("[INFO] No files provided to scan. Nothing to do — passing.")
        sys.exit(0)

    all_violations: list[dict] = []
    scanned = 0

    for filepath in files:
        violations = scan_file(filepath)
        all_violations.extend(violations)
        scanned += 1

    if all_violations:
        print(
            f"\n🚨  SECURITY SCAN FAILED — {len(all_violations)} violation(s) "
            f"across {scanned} file(s).\n"
        )
        for v in all_violations:
            print(f"  File    : {v['file']}")
            print(f"  Line    : {v['line']}")
            print(f"  Pattern : {v['label']}")
            print(f"  Code    : {v['code']}")
            print()
        print(
            "❌  Dangerous command(s) found without a Human-in-the-Loop safeguard.\n"
            "   Add an input() confirmation *before* every dangerous operation.\n"
            "   See CONTRIBUTING.md §'Safety First' for guidance."
        )
        sys.exit(1)

    print(
        f"✅  Security scan passed — {scanned} file(s) scanned, "
        "no violations found."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()

