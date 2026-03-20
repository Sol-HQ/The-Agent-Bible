import os
import sqlite3
import json
import time
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import sys

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "agent_memory.db")
MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "deepseek-r1:7b")
OLLAMA_BASE = os.getenv("OPENAI_BASE_URL", os.getenv("OLLAMA_URL", "http://localhost:11434/v1"))

# Import local brain index utilities from the same folder
sys.path.insert(0, BASE_DIR)
import brain_index
import subprocess
import glob
import matplotlib.pyplot as plt
import io

# ensure brain-material exists and begin indexing in background
brain_index.ensure_dirs()
try:
    # run indexing in background so UI loads quickly
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

def call_local_model_with_requests(messages):
    url = f"{OLLAMA_BASE}/chat/completions"
    payload = {"model": MODEL_NAME, "messages": messages}
    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    # flexible parsing for OpenAI-style or Ollama responses
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

def call_local_model(messages):
    try:
        return call_local_model_with_requests(messages)
    except Exception as e:
        return f"[Local model error] {e}"

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
        # Small visible graph: vault doc count and memory facts
        vault_count = status.get('count', 0)
        mem_count = len(memory_df) if not memory_df.empty else 0
        fig, ax = plt.subplots(figsize=(2.5, 1.5))
        bars = ax.bar(['Vault', 'Memory'], [vault_count, mem_count], color=['#4b8bbe', '#ffd43b'])
        ax.set_ylabel('Count')
        ax.set_title('Agent Stats')
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{int(height)}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=8)
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png")
        st.image(buf.getvalue(), width=180)
        plt.close(fig)
    except Exception as e:
        st.write("Vault status: error")

    # Check whether Ollama has any models loaded; offer an import button
    try:
        mresp = requests.get(f"{OLLAMA_BASE}/v1/models", timeout=2)
        mresp.raise_for_status()
        mdata = mresp.json()
        models_list = mdata.get("data") or []
        if not models_list:
            st.warning("No LLM models appear loaded in Ollama. The agent cannot generate responses until a model is available.")
            if st.button("Attempt import from 'models/' folder"):
                model_folder = os.path.join(BASE_DIR, "models")
                candidates = glob.glob(os.path.join(model_folder, "*"))
                if candidates:
                    sh = os.path.join(BASE_DIR, "import_model.sh")
                    if os.path.exists(sh):
                        try:
                            with st.spinner("Running import... check server logs for details"):
                                subprocess.run([sh, candidates[0]], check=True)
                            st.success("Import command executed. Refresh after Ollama finishes importing.")
                        except subprocess.CalledProcessError as e:
                            st.error(f"Import failed: {e}")
                    else:
                        st.error("import_model.sh not found in this folder.")
                else:
                    st.info("No files found in 'models/' — drop a model archive there and try again.")
        else:
            try:
                loaded = ", ".join([m.get('id', str(m)) for m in models_list])
            except Exception:
                loaded = str(models_list)
            st.write(f"Loaded models: {loaded}")
    except Exception:
        st.write("Could not query Ollama models.")

    # File upload into the stealth vault
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
                # index immediately
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

# Display chat history
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

if prompt := st.chat_input("Ask your local agent to remember something or solve a problem..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build the messages for the model
    model_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in st.session_state.messages:
        model_messages.append(m)

    with st.spinner("Local agent is thinking..."):
        reply = call_local_model(model_messages)

        # Handle SAVE_FACT marker
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
