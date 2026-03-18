# Basic ReAct Agent

This is a bare-bones implementation of a **ReAct (Reasoning + Acting)** agent. It demonstrates the core loop of autonomous behavior: Thought -> Action -> Pause -> Observation.

## How it works
The agent is instructed to stop generating text (PAUSE) when it wants to take an action. The Python script then parses the action, executes a local Python tool, and feeds the result back to the LLM as an Observation.

## Safety First
This agent features a powerful but dangerous tool (`execute_python`). In accordance with the rules of The Agent Bible, a **Human-In-The-Loop (HITL)** safeguard (`input()`) is hardcoded right before the execution step to prevent autonomous destruction.

## How to run
1. Ensure you have Python 3.10+ installed.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
