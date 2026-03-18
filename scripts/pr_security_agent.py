import os
import sys

# The dangerous functions we want our agent to look for
DANGEROUS_CALLS = ['os.system', 'subprocess', 'eval', 'exec', 'os.popen']
# The safeguard we require if they use a dangerous function
SAFEGUARD = 'input('

def scan_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"❌ REJECTED: Could not read file '{filepath}' ({e}). Treating as failed security check.")
        return False

    # Check if any dangerous calls exist in the code
    found_danger = [call for call in DANGEROUS_CALLS if call in content]

    if found_danger:
        # If danger is found, check if they included a Human-In-The-Loop prompt
        if SAFEGUARD not in content:
            print(f"🚨 ALERT: '{filepath}' contains dangerous calls: {found_danger}")
            print(f"❌ REJECTED: No Human-in-the-Loop safeguard (like `input()`) detected.")
            return False
        else:
            print(f"⚠️ WARNING: '{filepath}' contains {found_danger}, but HITL safeguard `input()` was found. Manual review still recommended.")
            return True

    return True

def main():
    print("🤖 Security Agent waking up... Scanning implementations folder...")
    # Determine the implementations directory:
    # - If a directory is provided as the first CLI argument, use that.
    # - Otherwise, default to the 'implementations' directory next to this script.
    if len(sys.argv) > 1:
        implementations_dir = sys.argv[1]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        implementations_dir = os.path.join(script_dir, 'implementations')

    if not os.path.isdir(implementations_dir):
        print(f"🛑 ERROR: Implementations directory '{implementations_dir}' does not exist.")
        sys.exit(1)

    all_safe = True
    
    # Walk through all files in the implementations folder
    for root, _, files in os.walk(implementations_dir):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if not scan_file(filepath):
                    all_safe = False

    if not all_safe:
        print("\n🛑 SECURITY CHECK FAILED. Agent is blocking this Pull Request.")
        sys.exit(1)  # Exit with non-zero status to signal a failed security check to the calling CI system
    else:
        print("\n✅ SECURITY CHECK PASSED. No autonomous destructive commands found.")
        sys.exit(0)  # Exit with zero status to signal a successful security check to the calling CI system

if __name__ == "__main__":
    main()
