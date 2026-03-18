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
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Maximum file size accepted for scanning (1 MiB). Files larger than this
# are rejected to prevent DoS via enormous inputs.
# ---------------------------------------------------------------------------
_MAX_FILE_BYTES: int = 1 * 1024 * 1024  # 1 MiB

# ---------------------------------------------------------------------------
# Calls considered "dangerous" when no HITL guard is present.
# ---------------------------------------------------------------------------
_DANGEROUS_CALLS: dict[tuple[str | None, str], str] = {
    # os module — shell execution
    ("os", "system"): "os.system",
    ("os", "popen"): "os.popen",
    # os module — exec* family
    ("os", "execv"): "os.execv",
    ("os", "execve"): "os.execve",
    ("os", "execvp"): "os.execvp",
    ("os", "execvpe"): "os.execvpe",
    ("os", "execl"): "os.execl",
    ("os", "execle"): "os.execle",
    ("os", "execlp"): "os.execlp",
    ("os", "execlpe"): "os.execlpe",
    # os module — spawn* family
    ("os", "spawnl"): "os.spawnl",
    ("os", "spawnle"): "os.spawnle",
    ("os", "spawnlp"): "os.spawnlp",
    ("os", "spawnlpe"): "os.spawnlpe",
    ("os", "spawnv"): "os.spawnv",
    ("os", "spawnve"): "os.spawnve",
    ("os", "spawnvp"): "os.spawnvp",
    ("os", "spawnvpe"): "os.spawnvpe",
    # subprocess module
    ("subprocess", "run"): "subprocess.run",
    ("subprocess", "call"): "subprocess.call",
    ("subprocess", "check_call"): "subprocess.check_call",
    ("subprocess", "check_output"): "subprocess.check_output",
    ("subprocess", "Popen"): "subprocess.Popen",
    ("subprocess", "getoutput"): "subprocess.getoutput",
    ("subprocess", "getstatusoutput"): "subprocess.getstatusoutput",
    # importlib — dynamic module loading can be used to import os/subprocess
    ("importlib", "import_module"): "importlib.import_module",
    # builtins module — dynamic code execution via the builtins object
    ("builtins", "eval"): "builtins.eval",
    ("builtins", "exec"): "builtins.exec",
    ("builtins", "compile"): "builtins.compile",
    # Built-in builtins (unqualified)
    (None, "eval"): "eval",
    (None, "exec"): "exec",
    (None, "__import__"): "__import__",
    (None, "compile"): "compile",
}

# ---------------------------------------------------------------------------
# The set of dangerous module names (used for getattr-bypass detection).
# ---------------------------------------------------------------------------
_DANGEROUS_MODULES: frozenset[str] = frozenset(
    mod for (mod, _) in _DANGEROUS_CALLS if mod is not None
)


def _collect_import_info(tree: ast.AST) -> tuple[dict[str, str], dict[str, str]]:
    """Return (module_aliases, imported_dangerous).

    module_aliases   : local_name -> canonical_module_name
    imported_dangerous: local_name -> human-readable label
    """
    module_aliases: dict[str, str] = {}
    imported_dangerous: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(".")[0]
                if module_name in _DANGEROUS_MODULES:
                    local_name = alias.asname or module_name
                    module_aliases[local_name] = module_name
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
    """Return a human-readable label if *node* is a dangerous call, else None.

    Handles four patterns:
      1. Bare name:            eval(...)
      2. Attribute access:     os.system(...)  /  alias.system(...)
      3. Direct from-import:   system(...)  (via imported_dangerous)
      4. getattr bypass:       getattr(os, 'system')(...)
    """
    func = node.func

    if isinstance(func, ast.Name):
        # Pattern 1: builtin dangerous name  (eval, exec, __import__, compile)
        builtin_label = _DANGEROUS_CALLS.get((None, func.id))
        if builtin_label is not None:
            return builtin_label

        # Pattern 4: getattr(module, 'func_name') bypass
        #   getattr(os, 'system')  or  getattr(os, some_var)
        if func.id == "getattr" and len(node.args) >= 2:
            obj_arg = node.args[0]
            method_arg = node.args[1]
            if isinstance(obj_arg, ast.Name):
                module_name = module_aliases.get(obj_arg.id, obj_arg.id)
                if module_name in _DANGEROUS_MODULES:
                    # Second arg is a string literal — check against known functions
                    if isinstance(method_arg, ast.Constant) and isinstance(
                        method_arg.value, str
                    ):
                        label = _DANGEROUS_CALLS.get((module_name, method_arg.value))
                        if label:
                            return label
                    # Second arg is not a literal — flag conservatively
                    return f"getattr({module_name}, <dynamic>)"

        # Pattern 3: dangerous name imported via `from module import func [as alias]`
        return imported_dangerous.get(func.id)

    # Pattern 2: attribute call  (obj.method)
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        base_name = func.value.id
        module_name = module_aliases.get(base_name, base_name)
        return _DANGEROUS_CALLS.get((module_name, func.attr))

    return None


def _find_dangerous_calls(tree: ast.AST) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    module_aliases, imported_dangerous = _collect_import_info(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            label = _call_label(node, module_aliases, imported_dangerous)
            if label:
                results.append((node.lineno, label))
    return results


def _has_hitl_before(tree: ast.AST, max_lineno: int) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "input":
                if getattr(node, "lineno", 0) <= max_lineno:
                    return True
    return False


def scan_file(filepath: str) -> list[dict]:
    path = Path(filepath)

    # ------------------------------------------------------------------
    # Basic path-safety checks  (run BEFORE the existence check so that
    # crafted paths like ../../etc/passwd.py are rejected even if the
    # file does not exist on disk.)
    # ------------------------------------------------------------------

    # Reject directory traversal — the absolute path must stay inside CWD.
    # os.path.abspath collapses ".." components without following symlinks
    # (symlinks are rejected separately below).
    cwd = Path.cwd().resolve()
    try:
        abs_path = Path(os.path.abspath(filepath))
        abs_path.relative_to(cwd)
    except ValueError:
        print(
            f"[ERROR] Path traversal detected — file is outside the project root: {filepath}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Reject symlinks — they can point to sensitive files outside the repo.
    if path.is_symlink():
        print(f"[ERROR] Symlink not allowed: {filepath}", file=sys.stderr)
        sys.exit(2)

    if not path.exists() or path.suffix.lower() != ".py":
        return []

    # Reject oversized files to prevent DoS / memory exhaustion.
    file_size = path.stat().st_size
    if file_size > _MAX_FILE_BYTES:
        print(
            f"[ERROR] File exceeds size limit ({file_size} > {_MAX_FILE_BYTES} bytes): {filepath}",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=filepath)
    except Exception as exc:
        print(f"[ERROR] Cannot process {filepath}: {exc}", file=sys.stderr)
        sys.exit(2)

    source_lines = source.splitlines()
    violations: list[dict] = []

    for lineno, label in _find_dangerous_calls(tree):
        if not _has_hitl_before(tree, lineno):
            code = source_lines[lineno - 1].strip() if lineno <= len(source_lines) else ""
            violations.append({
                "file": filepath,
                "line": lineno,
                "code": code,
                "label": label,
            })

    return violations


def main() -> None:
    files = sys.argv[1:]
    if not files:
        print("[INFO] No files provided to scan. Nothing to do — passing.")
        sys.exit(0)

    all_violations: list[dict] = []
    for filepath in files:
        all_violations.extend(scan_file(filepath))

    if all_violations:
        print(f"\n🚨 SECURITY SCAN FAILED — {len(all_violations)} violation(s) found.\n")
        for v in all_violations:
            print(f"  File    : {v['file']}\n  Line    : {v['line']}\n  Pattern : {v['label']}\n  Code    : {v['code']}\n")
        print("❌ Add an input() confirmation *before* every dangerous operation.")
        sys.exit(1)

    print(f"✅ Security scan passed — no violations found in {len(files)} file(s).")
    sys.exit(0)


if __name__ == "__main__":
    main()