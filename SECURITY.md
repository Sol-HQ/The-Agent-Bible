# Security Policy

## Reporting a Vulnerability

The Agent Bible takes security seriously. If you discover a security vulnerability in any of the code implementations, agent scripts, or CI/CD workflows in this repository, **please do not open a public GitHub Issue.**

Instead, report it privately using one of the following methods:

1. **GitHub Private Security Advisory:** Navigate to the repository's [Security tab](../../security/advisories/new) and open a private advisory.
2. **Direct Contact:** Reach out to the maintainers via the contact information listed in the repository profile.

### What to Include in Your Report

Please provide as much of the following information as possible to help us understand and reproduce the issue:

* **Type of vulnerability** (e.g., Prompt Injection, Unsafe Code Execution, Credential Leak)
* **File(s) affected** (e.g., `scripts/pr_security_agent.py`, `implementations/basic-react-agent/main.py`)
* **Steps to reproduce** the vulnerability
* **Proof-of-concept** or exploit code (if available)
* **Potential impact** — what could an attacker do by exploiting this?

---

## Our Response Process

1. We will acknowledge receipt of your report within **72 hours**.
2. We will investigate and validate the issue.
3. We will patch the vulnerability and push a fix, typically within **14 days** for critical issues.
4. After the patch is merged, we will publicly disclose the vulnerability (if appropriate) and credit you in the release notes.

---

## Security Architecture

### HITL (Human-in-the-Loop) Safeguards

Any agent code in `implementations/` that touches the filesystem, terminal, or browser **must** include an `input()` confirmation gate before executing a destructive or irreversible action. This is enforced automatically by the [`pr_security_agent.py`](./scripts/pr_security_agent.py) AST scanner on every Pull Request.

### AST-Based Scanning

The PR security scanner uses Python's `ast` module to detect calls to dangerous built-ins (`exec`, `eval`, `os.system`, `subprocess.run`, etc.) without a preceding `input()` guard. This prevents dangerous code from being merged even if it is hidden inside obfuscated strings or comments.

### Secrets Management

* `.env` files are excluded from version control via `.gitignore`.
* An `.env.example` file is provided to document required environment variables without exposing real values.
* Never hard-code API keys, tokens, or credentials in implementation files.

---

## Scope

This security policy covers:

| Component | In Scope |
|-----------|----------|
| `implementations/` — agent code examples | ✅ Yes |
| `scripts/` — automation and scanner scripts | ✅ Yes |
| `.github/workflows/` — CI/CD pipeline | ✅ Yes |
| `docs/` — documentation files | ⚠️ Limited (content accuracy, not execution) |

---

> *"The greatest vulnerability in an autonomous system is its willingness to be helpful to a stranger."*
> — The Agent Bible, Chapter 05
