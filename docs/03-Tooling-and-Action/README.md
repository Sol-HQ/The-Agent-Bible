# 03 - Tooling & Action: The Hands of an Agent

> *"A brain without hands is just philosophy. Tools are what make an agent real."*

Perception and reasoning are worthless without the ability to act. This chapter covers how agents are equipped with **Tools**—the functions they can call to interact with the outside world—and the safety architecture that must surround them.

---

## 🔧 What is a Tool?

In the context of LLM agents, a **Tool** (also called a "function," "plugin," or "action") is a Python function (or API endpoint) that the LLM can request to be executed on its behalf.

The agent does not run the tool itself; it declares its intent in a structured format (e.g., JSON), and the surrounding framework executes the actual call and feeds the result back as an "Observation."

```
Agent: ACTION: web_search("latest LLM papers")
System: OBSERVATION: [{"title": "ReAct: ...", "url": "..."}]
```

---

## 🗂️ The Tool Taxonomy

### Tier 1 — Read-Only (Lowest Risk)
These tools only retrieve information; they cannot modify state.
* `web_search(query)` — Search the internet.
* `read_file(path)` — Read a file from disk.
* `query_database(sql)` — Run a SELECT query.

### Tier 2 — Write / Side-Effect (Medium Risk)
These tools modify state but in controlled, reversible ways.
* `write_file(path, content)` — Write or overwrite a file.
* `send_email(to, subject, body)` — Send an email.
* `create_github_issue(title, body)` — Create an issue on GitHub.

### Tier 3 — Execution (Highest Risk)
These tools run arbitrary code or shell commands. They are the most powerful and most dangerous.
* `execute_python(code)` — Run a Python snippet.
* `run_shell(command)` — Execute a terminal command.
* `browser_navigate(url)` — Control a headless browser.

**Rule:** Every Tier 3 tool **must** have a Human-in-the-Loop (HITL) safeguard.

---

## 🛡️ HITL Safeguards in Practice

As demonstrated in [`/implementations/basic-react-agent/main.py`](../../implementations/basic-react-agent/main.py), the safeguard pattern is simple:

```python
def execute_python(code: str) -> str:
    print(f"\n🤖 [AGENT WANTS TO EXECUTE]:\n{code}\n")
    # The critical line — a human must approve before execution
    approval = input("🛡️ Human-in-the-Loop: Allow execution? (y/n): ")
    if approval.lower() != 'y':
        return "Action denied by human operator."
    # ... execute
```

This pattern is enforced by the PR Security Agent (`scripts/pr_security_agent.py`), which will **block any PR** that introduces Tier 3 tool calls without a preceding `input()` guard.

---

## 🔌 Tool Definition Standards

Modern frameworks (LangChain, OpenAI Functions, Anthropic Tool Use) define tools as JSON schemas that are passed to the LLM in the system prompt. The LLM then returns a structured JSON call.

**Example OpenAI Tool Definition:**
```json
{
  "type": "function",
  "function": {
    "name": "web_search",
    "description": "Search the web for current information on a topic.",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {"type": "string", "description": "The search query."}
      },
      "required": ["query"]
    }
  }
}
```

---

**Next up:** [Chapter 04 - Frameworks](../04-Frameworks/README.md)
