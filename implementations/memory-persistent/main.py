import os
import sqlite3
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- DATABASE LOGIC (THE "BRAIN STEM") ---
def init_db():
    conn = sqlite3.connect('agent_memory.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS facts 
                 (id INTEGER PRIMARY KEY, fact TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_fact(fact):
    conn = sqlite3.connect('agent_memory.db')
    c = conn.cursor()
    c.execute("INSERT INTO facts (fact) VALUES (?)", (fact,))
    conn.commit()
    conn.close()

def get_all_facts():
    conn = sqlite3.connect('agent_memory.db')
    c = conn.cursor()
    c.execute("SELECT fact FROM facts")
    facts = [row[0] for row in c.fetchall()]
    conn.close()
    return facts

# --- AGENT LOGIC ---
def run_memory_agent(user_input):
    # This reaches out to the cloud computer's .env for your key
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    init_db()
    
    # Recall everything we know about the user
    past_facts = get_all_facts()
    memory_context = "\n".join([f"- {f}" for f in past_facts])
    
    system_prompt = f"""
    You are a Memory Agent. You remember details about the user to be more helpful.
    
    FACTS YOU CURRENTLY REMEMBER ABOUT THE USER:
    {memory_context if memory_context else "No facts remembered yet."}
    
    INSTRUCTION: If the user tells you something new and important about themselves (like a name, 
    a preference, or a goal), respond with the phrase 'SAVE_FACT: ' followed by the fact.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}]
    )
    
    reply = response.choices[0].message.content
    
    # Check if the AI wants to "commit" something to long-term memory
    if "SAVE_FACT:" in reply:
        fact_to_save = reply.split("SAVE_FACT:")[1].strip()
        save_fact(fact_to_save)
        print(f"💾 [MEMORY STORED]: {fact_to_save}")
        
    print(f"\n🤖 Agent: {reply}")

if __name__ == "__main__":
    print("Memory Agent Active. Type 'quit' to exit.")
    while True:
        user_msg = input("\n🧑‍💻 You: ")
        if user_msg.lower() == 'quit': break
        run_memory_agent(user_msg)
