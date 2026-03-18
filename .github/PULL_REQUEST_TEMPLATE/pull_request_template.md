## Description

<!-- What did you change and why? Link the relevant Issue if one exists. -->

Closes #<!-- issue number, e.g. 42 -->

---

## Type of Change

<!-- Check all that apply. -->

- [ ] 📖 Docs update (`/docs`)
- [ ] 💻 New implementation (`/implementations`)
- [ ] 🤖 Automation / CI (`/scripts` or `/.github`)
- [ ] 🐛 Bug fix
- [ ] 🔧 Chore / repo hygiene

---

## Safety Checklist (required for `/implementations` PRs)

> The security scanner will fail this PR automatically if any of the items
> below are not satisfied. Please verify before submitting.

- [ ] **No autonomous destructive commands** — my agent does **not** call
  `os.system`, `subprocess`, `eval`, `exec`, or similar without user approval.
- [ ] **Human-in-the-Loop safeguard present** — every dangerous operation is
  gated behind an `input()` confirmation that lets a human approve or abort.
- [ ] **Minimal dependencies** — I included a scoped `requirements.txt` (or
  `package.json`) that lists only what this example needs.
- [ ] **Tested locally** — I ran the code and confirmed it works as described.

*If your implementation intentionally omits an `input()` guard, explain why
below and tag a maintainer for manual review.*

---

## Testing

<!-- How did you verify your changes? Paste output, screenshots, or test runs. -->

---

## Additional Notes

<!-- Anything else reviewers should know? -->
