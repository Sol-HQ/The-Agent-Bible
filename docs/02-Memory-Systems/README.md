# 02 - Memory Systems: The Soul of an Agent

> *"Without memory, an agent is just a goldfish."*

An agent that forgets everything the moment a conversation ends is not an agent—it is a very expensive lookup table. This chapter explores how we give agents a persistent, retrievable "soul."

---

## 🧠 The Memory Hierarchy

Agent memory is best understood as a hierarchy of three layers, each serving a different time horizon:

### 1. In-Context Memory (Short-Term)
This is the agent's **active working memory**—the raw content of the current conversation passed to the LLM as the `messages` list. It is fast and requires no infrastructure, but it is:
* **Limited** by the model's context window (e.g., 128k tokens for GPT-4o).
* **Ephemeral**—it disappears the moment the session ends.

### 2. External Memory via RAG (Long-Term)
**Retrieval-Augmented Generation (RAG)** is the most important long-term memory pattern. Instead of cramming everything into the context window, the agent stores knowledge in a **Vector Database** (e.g., Chroma, Pinecone, Weaviate) and retrieves only the most relevant chunks on demand.

**The RAG Loop:**
1. **Ingest:** Split documents into chunks and embed them as vectors.
2. **Store:** Write the vectors and their source text to a vector DB.
3. **Retrieve:** At query time, embed the user's question and find the top-K nearest vectors.
4. **Augment:** Inject the retrieved chunks into the prompt as additional context.
5. **Generate:** The LLM answers using both its training knowledge and the retrieved context.

### 3. Parametric Memory (Frozen)
This is the knowledge "baked into" the LLM's weights during training. It cannot be updated without fine-tuning. It is the baseline that RAG augments.

---

## 🗄️ Vector Databases 101

| Database | Hosting | Best For |
|----------|---------|----------|
| **Chroma** | Local / Self-hosted | Prototyping, local dev |
| **Pinecone** | Managed Cloud | Production at scale |
| **Weaviate** | Self-hosted / Cloud | Hybrid search (keyword + vector) |
| **Qdrant** | Self-hosted / Cloud | High-performance Rust core |
| **pgvector** | PostgreSQL extension | Teams already using Postgres |

---

## 🔒 Security Note

Vector databases often store sensitive business documents. When building RAG systems:
* Apply **access controls** at the chunk level if users have different permission tiers.
* **Sanitize** retrieved chunks before injecting them into the prompt to prevent **indirect prompt injection** (where a malicious document manipulates the agent).

---

## 💻 Implementation

See [`/implementations/memory-persistent/`](../../implementations/memory-persistent/) for a working example of a ReAct agent augmented with a local Chroma vector store.

**Next up:** [Chapter 03 - Tooling & Action](../03-Tooling-and-Action/README.md)
