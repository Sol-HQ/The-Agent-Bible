import os
import re
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables (like OPENAI_API_KEY) from a .env file
load_dotenv()

# ---------------------------------------------------------------------------
# 1. THE TOOLS (The Agent's Hands)
# ---------------------------------------------------------------------------
def execute_python(code: str) -> str:
    """A tool that executes Python code. This is inherently dangerous."""
    print(f"\n🤖 [AGENT WANTS TO EXECUTE CODE]:\n{code}\n")
    
    # HITL SAFEGUARD: This input() call ensures we pass the PR Security Scanner!
    approval = input("🛡️ Human-in-the-Loop: Allow execution? (y/n): ")
    
    if approval.lower() != 'y':
        return "System Observation: The human denied this action."
    
    try:
        # We capture the output of the executed code using a simple dictionary
        local_scope = {}
        exec(code, {}, local_scope)
        return f"System Observation: Code executed. Local scope variables: {local_scope}"
    except Exception as e:
        return f"System Observation: Execution failed with error: {e}"

# ---------------------------------------------------------------------------
# 2. THE SYSTEM PROMPT (The Agent's Brain)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
You are a ReAct (Reasoning and Acting) AI Agent. 
Your goal is to answer the user's question or complete their task.

You run in a loop of THOUGHT, ACTION, PAUSE, OBSERVATION.
At the end of the loop you output an ANSWER.

1. THOUGHT: Explain your reasoning step-by-step.
2. ACTION: Choose exactly one tool to use. 
3. PAUSE: Stop generating text and wait for the system to return an OBSERVATION.
4. OBSERVATION: The system will provide the result of your action.

Available Tools:
- execute_python: Provide a string of Python code to execute. Useful for math or logic.

Example Session:
User: What is 234 * 892?
THOUGHT: I need to multiply two large numbers. I will use the execute_python tool.
ACTION: execute_python: result = 234 * 892
PAUSE

System OBSERVATION: Code executed. Local scope variables: {'result': 208728}

THOUGHT: I have the result.
ANSWER: The answer is 208,728.
"""

# ---------------------------------------------------------------------------
# 3. THE EXECUTION LOOP (The Agent's Heartbeat)
# ---------------------------------------------------------------------------
def run_agent(user_query: str):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query}
    ]
    
    print(f"\n🧑‍💻 User: {user_query}")
    
    # The Agent Loop: Allow the agent to think and act up to 5 times
    for step in range(5):
        response = client.chat.completions.create(
            model="gpt-4o", # Or gpt-3.5-turbo if you want to save pennies
            messages=messages,
            stop=["PAUSE"] # The LLM will stop generating when it types PAUSE
        )
        
        reply = response.choices[0].message.content.strip()
        print(f"\n{reply}")
        messages.append({"role": "assistant", "content": reply})
        
        # Did the agent output an ANSWER? We are done!
        if "ANSWER:" in reply:
            break
            
        # Did the agent output an ACTION? We need to run the tool!
        action_match = re.search(r"ACTION:\s*execute_python:\s*(.*)", reply, re.IGNORECASE)
        
        if action_match:
            code_to_run = action_match.group(1).strip()
            # Run the tool (which triggers our HITL input)
            observation = execute_python(code_to_run)
            print(f"🖥️ {observation}")
            # Feed the observation back to the LLM
            messages.append({"role": "user", "content": observation})
        else:
            # If the agent didn't output an action or an answer, nudge it.
            messages.append({"role": "user", "content": "System: You did not output an ACTION or an ANSWER. Please continue."})

if __name__ == "__main__":
    print("Welcome to the Basic ReAct Agent from The Agent Bible.")
    query = input("What would you like me to do? ")
    run_agent(query)
