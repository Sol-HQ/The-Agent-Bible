#!/usr/bin/env python3
"""
Download and cache the sentence-transformers embedding model locally.
Usage: python3 scripts/prefetch_embeddings.py
Environment:
- EMBED_MODEL_NAME: optional HF model id (default 'sentence-transformers/all-MiniLM-L6-v2')
- EMBED_LOCAL_DIR: optional local path to save model
"""
import os
from pathlib import Path
import sys

MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
BASE = Path(__file__).resolve().parents[1]
BRAIN_DIR = BASE / "implementations" / "local_sovereign_agent" / "brain-material"
LOCAL_DIR = os.getenv("EMBED_LOCAL_DIR", str(BRAIN_DIR / "embed_model"))

def main():
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        print("sentence-transformers not installed. Run 'pip install sentence-transformers'")
        raise

    print(f"Downloading embedding model '{MODEL_NAME}' into local dir: {LOCAL_DIR}")
    Path(LOCAL_DIR).mkdir(parents=True, exist_ok=True)
    model = SentenceTransformer(MODEL_NAME)
    try:
        model.save(LOCAL_DIR)
        print("Saved embedding model to:", LOCAL_DIR)
    except Exception:
        # Some SentenceTransformer versions use save_pretrained
        try:
            model.save_pretrained(LOCAL_DIR)
            print("Saved embedding model (save_pretrained) to:", LOCAL_DIR)
        except Exception as e:
            print("Failed to save model locally:", e)
            raise

if __name__ == "__main__":
    main()
