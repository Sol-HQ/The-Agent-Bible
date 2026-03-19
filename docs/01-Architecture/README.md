# 01 - Architecture: The Agentic Triforce

To build a true agent, you aren't just writing code; you are designing a cognitive loop. While a standard script follows a linear path ($A \rightarrow B \rightarrow C$), an agent operates in a circle.

---

## 🏗️ The Core Loop: ReAct

The most common architecture for modern agents is the **ReAct** (Reasoning + Acting) pattern. This is what we used in our first implementation.

1. **Thought:** The LLM analyzes the task and "thinks" about what it needs.
2. **Action:** The LLM selects a tool to use (Web Search, Code Exec, API call).
3. **Observation:** The system provides the output of that tool back to the LLM.
4. **Repeat:** The LLM updates its plan based on what it just learned.

---

## 🔺 The Triforce of Agency

Every autonomous system in this Bible is built on these three pillars:

### 1. Perception & Reasoning (The Brain)
This is the LLM itself. It’s not just for "chatting"; it’s for **Planning**. 
* **Zero-Shot:** Doing it in one go.
* **Chain-of-Thought (CoT):** Forcing the model to explain its steps.

### 2. Memory (The Soul)
Without memory, an agent is just a goldfish.
* **Short-Term:** The current conversation history (Context Window).
* **Long-Term:** A Vector Database (like Chroma or Pinecone) where the agent "remembers" things from days or weeks ago using RAG (Retrieval-Augmented Generation).

### 3. Action (The Hands)
This is where the agent touches the real world.
* **Tools/Plugins:** Functions the agent can call.
* **Sandboxing:** The most critical part of the Bible. Hands must stay in the "Quarantine" unless a human allows them out.

---

## 🛡️ Architecture & Security

The "Cline Hack" happened because the **Perception** pillar was fed poisoned data that overrode the **Reasoning** pillar. In the next chapters, we will learn how to build "Guardrails" between these pillars.

**Next up:** [Chapter 02 - Memory & RAG](../02-Memory-Systems/README.md)
