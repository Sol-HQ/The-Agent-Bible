"""
Copy of brain_index utilities adapted for package `implementations.local_sovereign_agent`.
"""
import os
import json
import time
import logging
from pathlib import Path
import uuid

try:
    import chromadb
    from chromadb.config import Settings
except Exception:
    chromadb = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

import numpy as np

logging.basicConfig(level=logging.INFO)
_embed_model = None

BASE_DIR = os.path.dirname(__file__)
BRAIN_DIR = os.path.join(BASE_DIR, "brain-material")
CHROMA_DIR = os.path.join(BRAIN_DIR, "chroma_db")
INDEX_META = os.path.join(BRAIN_DIR, "indexed_files.json")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
EMBED_LOCAL_DIR = os.getenv("EMBED_LOCAL_DIR", os.path.join(BRAIN_DIR, "embed_model"))

def ensure_dirs():
    os.makedirs(BRAIN_DIR, exist_ok=True)
    os.makedirs(CHROMA_DIR, exist_ok=True)

def load_embed_model():
    global _embed_model
    if _embed_model is not None:
        return _embed_model
    if SentenceTransformer is None:
        logging.info("sentence-transformers not installed — using lightweight fallback embeddings")

        class FallbackEmbedModel:
            def __init__(self, dim=384):
                self.dim = dim

            def _text_to_vec(self, text):
                import hashlib, math
                vec = [0.0] * self.dim
                if not text:
                    return vec
                for token in str(text).split():
                    h = hashlib.sha256(token.encode('utf-8')).digest()
                    idx = int.from_bytes(h[:4], 'little') % self.dim
                    vec[idx] += 1.0
                norm = math.sqrt(sum(x * x for x in vec))
                if norm > 0:
                    vec = [x / norm for x in vec]
                return vec

            def encode(self, texts, show_progress_bar=False, convert_to_numpy=True):
                if isinstance(texts, str):
                    texts = [texts]
                arr = [self._text_to_vec(t) for t in texts]
                import numpy as _np
                return _np.array(arr, dtype=float)

        _embed_model = FallbackEmbedModel()
        return _embed_model

    if os.path.exists(EMBED_LOCAL_DIR):
        logging.info(f"Loading embedding model from local directory: {EMBED_LOCAL_DIR}")
        try:
            _embed_model = SentenceTransformer(EMBED_LOCAL_DIR)
            return _embed_model
        except Exception:
            logging.warning("Failed to load local embedding model; falling back to remote name")

    logging.info(f"Loading embedding model {EMBED_MODEL_NAME} (may download on first run)")
    _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model

def init_chroma():
    if chromadb is None:
        return None, None
    client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=CHROMA_DIR))
    collection = client.get_or_create_collection(name="vault")
    return client, collection

LOCAL_INDEX_FILE = os.path.join(BRAIN_DIR, "local_index.json")

def _load_local_index():
    if not os.path.exists(LOCAL_INDEX_FILE):
        return []
    try:
        with open(LOCAL_INDEX_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []

def _save_local_index(items):
    with open(LOCAL_INDEX_FILE, "w", encoding="utf-8") as fh:
        json.dump(items, fh)

def _chunk_text(text, chunk_size=1000, overlap=200):
    if not text:
        return []
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk.strip())
        start = end - overlap
    return [c for c in chunks if c]

def _load_index_meta():
    if not os.path.exists(INDEX_META):
        return {}
    try:
        with open(INDEX_META, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}

def _save_index_meta(meta):
    with open(INDEX_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)

def index_file(file_path, client=None, collection=None, embed_model=None, chunk_size=1000, overlap=200):
    ensure_dirs()
    if client is None or collection is None:
        client, collection = init_chroma()
    if embed_model is None:
        embed_model = load_embed_model()

    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        logging.warning(f"File not found for indexing: {file_path}")
        return 0

    with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
        text = fh.read()

    chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return 0

    embeddings = embed_model.encode(chunks, show_progress_bar=False, convert_to_numpy=True)
    ids = []
    metadatas = []
    for i, chunk in enumerate(chunks):
        uid = f"{uuid.uuid4()}"
        ids.append(uid)
        metadatas.append({"source": os.path.basename(file_path), "chunk_index": i})

    if client is not None and collection is not None:
        try:
            collection.add(ids=ids, documents=chunks, embeddings=embeddings.tolist(), metadatas=metadatas)
            client.persist()
        except Exception as e:
            logging.exception("Failed to add to chroma collection: %s", e)
            return 0
    else:
        items = _load_local_index()
        for i, chunk in enumerate(chunks):
            items.append({
                "id": ids[i],
                "document": chunk,
                "metadata": metadatas[i],
                "embedding": embeddings[i].tolist()
            })
        _save_local_index(items)

    meta = _load_index_meta()
    rel = os.path.relpath(file_path, BRAIN_DIR)
    meta[rel] = os.path.getmtime(file_path)
    _save_index_meta(meta)
    logging.info(f"Indexed {file_path}: {len(chunks)} chunks")
    return len(chunks)

def index_all_files():
    ensure_dirs()
    client, collection = init_chroma()
    embed_model = load_embed_model()
    meta = _load_index_meta()
    files = [p for p in Path(BRAIN_DIR).glob("**/*") if p.is_file()]
    total_indexed = 0
    for p in files:
        if str(p).startswith(CHROMA_DIR):
            continue
        if os.path.basename(str(p)) == os.path.basename(INDEX_META):
            continue
        rel = os.path.relpath(str(p), BRAIN_DIR)
        mtime = os.path.getmtime(str(p))
        if meta.get(rel) and meta.get(rel) >= mtime:
            continue
        if client is not None and collection is not None:
            try:
                collection.delete(where={"source": os.path.basename(str(p))})
            except Exception:
                pass
        else:
            items = _load_local_index()
            items = [it for it in items if it.get("metadata", {}).get("source") != os.path.basename(str(p))]
            _save_local_index(items)

        total_indexed += index_file(str(p), client=client, collection=collection, embed_model=embed_model)
    logging.info(f"Indexing complete. Total chunks indexed: {total_indexed}")
    return total_indexed

def query_vault(query_text, top_k=4):
    ensure_dirs()
    client, collection = init_chroma()
    embed_model = load_embed_model()
    q_emb = embed_model.encode([query_text], convert_to_numpy=True)[0].tolist()
    if client is not None and collection is not None:
        try:
            results = collection.query(query_embeddings=[q_emb], n_results=top_k, include=["documents", "metadatas", "ids", "distances"])
        except Exception as e:
            logging.exception("Chroma query failed: %s", e)
            return []
        hits = []
        if not results or "ids" not in results:
            return hits
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0] if results.get("distances") else [None]*len(ids)
        for i in range(len(ids)):
            hits.append({"id": ids[i], "document": docs[i], "metadata": metadatas[i], "distance": distances[i]})
        return hits

    items = _load_local_index()
    if not items:
        return []
    import math
    def cosine(a, b):
        num = sum(x * y for x, y in zip(a, b))
        da = math.sqrt(sum(x * x for x in a))
        db = math.sqrt(sum(x * x for x in b))
        if da == 0 or db == 0:
            return 0.0
        return num / (da * db)

    scored = []
    for it in items:
        emb = it.get("embedding")
        if not emb:
            continue
        score = cosine(q_emb, emb)
        scored.append((score, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    hits = []
    for score, it in scored[:top_k]:
        hits.append({"id": it.get("id"), "document": it.get("document"), "metadata": it.get("metadata"), "distance": 1.0 - score})
    return hits

def get_status():
    ensure_dirs()
    client, collection = init_chroma()
    if client is None or collection is None:
        items = _load_local_index()
        count = len(items)
    else:
        try:
            count = collection.count()
        except Exception:
            try:
                res = collection.get(include=["ids"])
                count = len(res.get("ids", []))
            except Exception:
                count = 0
    meta = _load_index_meta()
    last_index = max(meta.values()) if meta else None
    return {"count": count, "last_index": last_index}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", action="store_true", help="Index all files in brain-material")
    parser.add_argument("--reindex", action="store_true", help="Clear and reindex")
    args = parser.parse_args()
    ensure_dirs()
    if args.reindex:
        client, collection = init_chroma()
        try:
            client.delete_collection(name="vault")
        except Exception:
            pass
    if args.index or args.reindex:
        if args.reindex:
            client, collection = init_chroma()
            if client is None:
                try:
                    os.remove(LOCAL_INDEX_FILE)
                except Exception:
                    pass
            else:
                try:
                    client.delete_collection(name="vault")
                except Exception:
                    pass
        index_all_files()
    else:
        print(get_status())
