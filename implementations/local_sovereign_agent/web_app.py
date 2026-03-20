import os
import sqlite3
import json
import time
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import subprocess
import glob
import matplotlib.pyplot as plt
import io

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "agent_memory.db")
MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "deepseek-r1:7b")
OLLAMA_BASE = os.getenv("OPENAI_BASE_URL", os.getenv("OLLAMA_URL", "http://localhost:11434/v1"))

# Import package-local brain index
from implementations.local_sovereign_agent import brain_index

# ensure brain-material exists and begin indexing in background
brain_index.ensure_dirs()
try:
    import threading
    t = threading.Thread(target=brain_index.index_all_files, daemon=True)
    t.start()
except Exception:
    pass

# --- 🧠 BACKEND: SQLite memory helpers ---
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS facts (fact TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

def get_memory_df():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        df = pd.read_sql_query("SELECT timestamp, fact FROM facts ORDER BY timestamp DESC", conn)
    except Exception:
        df = pd.DataFrame(columns=["timestamp", "fact"])
    conn.close()
    return df

def save_fact(fact: str):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("INSERT INTO facts (fact) VALUES (?)", (fact,))
    conn.commit()
    conn.close()

# --- Model calling utilities ---
def call_local_model_with_requests(messages, model=None):
    url = f"{OLLAMA_BASE}/chat/completions"
    m = model or MODEL_NAME
    payload = {"model": m, "messages": messages}
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        # Provide clearer guidance when Ollama responds with a server error
        status = getattr(e.response, 'status_code', '')
        err_text = f"[Local model error] HTTP {status} - {e}\n"
        # try to parse structured JSON errors for friendlier guidance
        try:
            j = e.response.json()
            # common Ollama error format: {"error": {"message": "..."}}
            msg = None
            if isinstance(j, dict):
                if 'error' in j and isinstance(j['error'], dict):
                    msg = j['error'].get('message')
                elif 'message' in j:
                    msg = j.get('message')
            if msg:
                err_text += msg + "\n"
                # detect common memory error and suggest smaller models
                if 'requires more system memory' in msg or 'more system memory' in msg:
                    err_text += "Suggestion: the chosen model needs more RAM than is available. Try importing or pulling a smaller model (for example: 'llama3.2:3b') or free system memory.\n"
        except Exception:
            try:
                err_text += e.response.text
            except Exception:
                pass
        return err_text
    except Exception as e:
        return f"[Local model error] {e}"

    if isinstance(data, dict):
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if isinstance(choice, dict) and "message" in choice:
                return choice["message"].get("content", "")
            if isinstance(choice, dict) and "text" in choice:
                return choice.get("text", "")
        if "result" in data:
            return data.get("result")
        if "output" in data:
            return data.get("output")
    return json.dumps(data)

def call_local_model(messages, model=None):
    try:
        return call_local_model_with_requests(messages, model=model)
    except Exception as e:
        return f"[Local model error] {e}"

def get_ollama_models():
    """Return a list of model names available from the local Ollama runtime.
    Returns: list of names, empty list when none, or None on connection error.
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE}/models", timeout=3)
        resp.raise_for_status()
        data = resp.json()
        models = []
        if isinstance(data, dict):
            d = data.get("data")
            if not d:
                return []
            for item in d:
                if isinstance(item, dict):
                    if "name" in item:
                        models.append(item["name"])
                    elif "id" in item:
                        models.append(item["id"])
                    else:
                        models.append(str(item))
                else:
                    models.append(str(item))
            return models
        return []
    except Exception:
        return None

# --- UI: Streamlit app ---
st.set_page_config(page_title="The Agent Bible — Local Sovereign Agent", layout="wide")

with st.sidebar:
    st.title("💾 Memory Bank — Local")
    st.info("Persistent facts (local SQLite). The agent will save facts here when instructed.")
    init_db()
    memory_df = get_memory_df()
    if not memory_df.empty:
        st.dataframe(memory_df, use_container_width=True, hide_index=True)
    else:
        st.write("No facts remembered yet.")

    if st.button("🗑️ Clear Long-Term Memory"):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM facts")
        conn.commit()
        conn.close()
        st.experimental_rerun()

    st.markdown("---")
    st.header("Stealth Status")
    try:
        status = brain_index.get_status()
        st.write(f"Vault documents: {status.get('count', 0)}")
        last = status.get('last_index')
        if last:
            st.write(f"Last indexed: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last))}")
        else:
            st.write("Last indexed: never")
        vault_count = status.get('count', 0)
        mem_count = len(memory_df) if not memory_df.empty else 0
        fig, ax = plt.subplots(figsize=(2.5, 1.5))
        bars = ax.bar(['Vault', 'Memory'], [vault_count, mem_count], color=['#4b8bbe', '#ffd43b'])
        ax.set_ylabel('Count')
        ax.set_title('Agent Stats')
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{int(height)}', xy=(bar.get_x() + bar.get_width() / 2, height), xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png")
        st.image(buf.getvalue(), width=180)
        plt.close(fig)
    except Exception as e:
        st.write("Vault status: error")

    # --- Local LLM status (Ollama) ---
    try:
        models = get_ollama_models()
        if models is None:
            st.warning(f"Ollama unreachable at {OLLAMA_BASE}. Start Ollama to enable local inference.")
        elif len(models) == 0:
            st.warning("No local models loaded into Ollama.")
            st.caption("Place a model archive into implementations/local_sovereign_agent/models/ and run import_model.sh, or try pulling a public model.")
            c1, c2 = st.columns([1,1])
            with c1:
                if st.button("Attempt pull: llama3.2:3b"):
                    with st.spinner("Pulling model (may take long)..."):
                        try:
                            out = subprocess.run(["ollama","pull","llama3.2:3b"], capture_output=True, text=True, timeout=7200)
                            st.text(out.stdout + "\n" + out.stderr)
                        except Exception as e:
                            st.error(f"Pull failed: {e}")
            with c2:
                if st.button("Import local model (see README)"):
                    st.info("Place model archive in implementations/local_sovereign_agent/models/ and run import_model.sh from a shell")
        else:
            st.write(f"Local models: {', '.join(models)}")
    except Exception:
        st.write("Model check: error")

    st.markdown("**Upload to Vault**")
    uploaded = st.file_uploader("Drop text/markdown/html files to add to the vault", accept_multiple_files=True, type=['txt','md','html','htm'])
    if uploaded:
        for up in uploaded:
            safe_name = f"{int(time.time())}_{up.name.replace(' ', '_')}"
            out_path = os.path.join(BASE_DIR, 'brain-material', safe_name)
            try:
                content = up.getvalue()
                if isinstance(content, bytes):
                    content = content.decode('utf-8', errors='ignore')
                with open(out_path, 'w', encoding='utf-8') as fh:
                    fh.write(content)
                try:
                    brain_index.index_file(out_path)
                    st.success(f"Saved & indexed: {safe_name}")
                except Exception:
                    st.warning(f"Saved but indexing failed for: {safe_name}")
            except Exception as e:
                st.error(f"Failed to save {up.name}: {e}")

st.title("🤖 Agent Bible — Local Sovereign Dashboard")
st.markdown("---")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg.get("role", "user")):
        st.markdown(msg.get("content", ""))

SYSTEM_PROMPT = """
You are the DeepSeek Sovereign Agent (local). Prioritize data sovereignty, privacy, and high integrity.
Persist explicit, user-approved facts into the local SQLite `agent_memory.db` when required.
If you learn a new fact that should be stored to long-term memory, append a line exactly like:

SAVE_FACT: <the fact>

at the end of your assistant reply. Otherwise do not output SAVE_FACT.
"""

models = get_ollama_models()
if models is None:
    st.error(f"Cannot reach Ollama at {OLLAMA_BASE}. Start Ollama to enable local inference.")
elif len(models) == 0:
    st.info("No local model loaded. Upload/import a model or use the sidebar actions to pull/import one.")
else:
    active_model = MODEL_NAME if MODEL_NAME in models else models[0]
    if prompt := st.chat_input("Ask your local agent to remember something or solve a problem..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        model_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in st.session_state.messages:
            model_messages.append(m)

        with st.spinner("Local agent is thinking..."):
            reply = call_local_model(model_messages, model=active_model)

            if isinstance(reply, str) and "SAVE_FACT:" in reply:
                try:
                    new_fact = reply.split("SAVE_FACT:", 1)[1].strip().splitlines()[0]
                    if new_fact:
                        save_fact(new_fact)
                        reply = reply.replace(f"SAVE_FACT: {new_fact}", "✅ *Fact Memorized*")
                except Exception:
                    pass

            with st.chat_message("assistant"):
                st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
