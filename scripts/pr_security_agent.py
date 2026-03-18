#!/usr/bin/env python3
"""
PR Security Agent
=================
Scans Python files under `implementations/` for dangerous shell/exec commands
that lack a Human-in-the-Loop (HITL) safeguard (i.e. an ``input()`` call).

The scanner uses the Python ``ast`` module so that patterns inside comments,
docstrings, and string literals are **never** flagged as violations.

Usage
-----
    python scripts/pr_security_agent.py <file1.py> [file2.py ...]

Exit codes
----------
  0 — All scanned files passed.
  1 — One or more files contain a dangerous pattern without an input() guard.
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


def _call_label(node: ast.Call) -> str | None:
    """Return a danger label for an AST Call node, or None if it is safe."""
    func = node.func

    # Bare name: eval(...), exec(...), etc.
    if isinstance(func, ast.Name):
        return _DANGEROUS_CALLS.get((None, func.id))

    # Attribute access: os.system(...), subprocess.run(...), etc.
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name):
            return _DANGEROUS_CALLS.get((func.value.id, func.attr))

    return None


def _find_dangerous_calls(tree: ast.AST) -> list[tuple[int, str]]:
    """Walk the AST and return (lineno, label) for every dangerous Call."""
    results: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            label = _call_label(node)
            if label:
                results.append((node.lineno, label))
    return results


def _has_hitl(tree: ast.AST) -> bool:
    """Return True if the AST contains at least one bare ``input(...)`` call.

    Only actual Call nodes are checked — ``input`` in comments or strings
    does **not** count.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "input":
                return True
    return False


def scan_file(filepath: str) -> list[dict]:
    """Scan a single Python file and return a list of violation dicts.

    Each violation dict has keys: ``file``, ``line``, ``label``.
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

    # Fast-path: a file that already has an input() call anywhere passes.
    if _has_hitl(tree):
        return []

    source_lines = source.splitlines()
    violations: list[dict] = []

    for lineno, label in _find_dangerous_calls(tree):
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
