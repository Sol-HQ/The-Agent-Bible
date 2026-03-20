# Local Sovereign Agent — Quick Setup

This folder contains a local-first agent implementation that runs against a local LLM (Ollama) and a local "vault" for RAG.

Quick notes:

- Drop a local model archive or unpacked model directory into `implementations/local-sovereign-agent/models/` or `implementations/local_sovereign_agent/models/` and use the **Import** button in the Streamlit UI or run `import_model.sh` to register it with Ollama.
- The default `requirements.txt` is deliberately lightweight. If you want full RAG/embedding features, install `requirements-full.txt`:

```bash
python3 -m pip install -r implementations/local_sovereign_agent/requirements-full.txt
```

- To prefetch the embedding model for offline use:

```bash
python3 scripts/prefetch_embeddings.py
```

- If disk space is constrained, free caches before installing heavy packages:

```bash
python3 -m pip cache purge
rm -rf ~/.cache/huggingface ~/.cache/pip /tmp/*
```

- Use `setup_and_run.sh` to automate install/start steps; it will avoid a full install when disk is low.

## UI & Agent Presence
- Streamlit UI launches at http://localhost:8080
- Sidebar shows agent memory, vault stats, upload widget, and model status
- Agent presence/status is visible in chat and sidebar
- Graphs: disk usage, vault document count, last index time

## Data Storage
- Vault: `brain-material/` (indexed docs, embeddings, vector DB)
- Memory: `agent_memory.db` (SQLite)
- Models: `models/` (Ollama model archives)

## Git Hygiene
- `.gitignore` includes `brain-material/` and `models/` to avoid pushing large/private files
- Use Git LFS for large model files if needed

## Extending
- Add new models to `models/` and run `import_model.sh`
- Export memory or vault for Supabase integration

---
For more, see `web_app_local.py`, `brain_index.py`, and `setup_and_run.sh`.

Security & privacy:
- `brain-material/` and `models/` are git-ignored; binary model artifacts should not be committed to the repository.
