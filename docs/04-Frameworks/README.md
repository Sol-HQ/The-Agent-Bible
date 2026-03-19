# 04 - Frameworks: Choosing Your Weapon

> *"A framework is a map. Useful to navigate, but don't confuse the map for the territory."*

Once you understand the raw primitives—the ReAct loop, memory, tools—you can reach for a framework to accelerate development. This chapter surveys the dominant agent frameworks and helps you choose the right one for your use case.

---

## 🗺️ The Landscape

The agent framework ecosystem is moving fast. Here is the current state of the major players:

| Framework | Maintainer | Best For | Key Strength |
|-----------|------------|----------|--------------|
| **LangChain** | LangChain Inc. | Rapid prototyping, broad integrations | Largest ecosystem, most tutorials |
| **LangGraph** | LangChain Inc. | Stateful, multi-step agents | Graph-based control flow |
| **CrewAI** | CrewAI | Multi-agent teams / "crews" | Role-based agent collaboration |
| **AutoGen** | Microsoft Research | Research & conversational multi-agent | Flexible agent conversation patterns |
| **Semantic Kernel** | Microsoft | Enterprise .NET / Python | Deep Azure/Microsoft integration |
| **Haystack** | deepset | RAG pipelines | Production-grade document retrieval |
| **Raw API** | You | Learning, custom control | Full transparency, no magic |

---

## 🔬 Framework Deep Dives

### LangChain
LangChain popularized the "chain" abstraction—composing LLM calls, tools, and memory into pipelines. It offers the most pre-built integrations (100+ vector stores, LLMs, and tools) but has been criticized for abstraction complexity ("magic" that is hard to debug).

**When to use:** You need to connect many different data sources quickly and don't mind learning the abstraction layer.

### LangGraph
An extension of LangChain that models agent workflows as directed graphs (nodes + edges). Each node is an agent step; edges define transitions based on state. This gives you precise control over loops, branches, and error recovery.

**When to use:** You are building complex, stateful agents where control flow needs to be explicit and debuggable.

### CrewAI
CrewAI frames multi-agent work as a "crew" of specialized agents each with a **Role**, **Goal**, and **Backstory**. Agents are assigned **Tasks** and collaborate sequentially or in parallel.

**When to use:** Your problem decomposes naturally into parallel specialised sub-tasks (e.g., a "Researcher" + "Writer" + "Editor" crew for content generation).

### Raw API (The Bible Approach)
For learning and for maximum control, the implementations in this repository use the raw OpenAI API directly. This means:
* Zero hidden magic—you see every prompt and every response.
* Easy to understand what the agent is actually doing.
* Portable: the patterns translate to any LLM provider.

---

## ⚖️ Framework Selection Guide

```
Is your agent a one-off research prototype?
  → Raw API or LangChain

Do you need precise, debuggable control flow?
  → LangGraph

Do you need multiple specialized agents collaborating?
  → CrewAI or AutoGen

Is this a production RAG pipeline?
  → Haystack

Are you building in a Microsoft/Azure environment?
  → Semantic Kernel
```

---

## 🛡️ A Note on Framework Security

When adopting a framework, audit its defaults:
* Does it allow agents to make web requests without HITL approval?
* Does it log tool inputs/outputs? (Important for audit trails.)
* Does it support sandboxed code execution, or does it run `exec()` directly?

The principles from [Chapter 03 - Tooling & Action](../03-Tooling-and-Action/README.md) and [Chapter 05 - Ethics & Governance](../05-Ethics-Governance/README.md) apply regardless of which framework you use.

---

**Next up:** [Chapter 05 - Ethics & Governance](../05-Ethics-Governance/README.md)
