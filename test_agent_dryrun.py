import os
import sys
import argparse
from dotenv import load_dotenv
from agent import GeminiShoppingAgent

load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="Test Gemini Commerce Assistant Agent")
    parser.add_argument("--api-key", help="Gemini API Key (otherwise reads GEMINI_API_KEY env var)")
    parser.add_argument("--query", default="Recommend some breakfast options. Make sure they are peanut-free.", help="Test query for the agent")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: Please specify a Gemini API Key using --api-key or set the GEMINI_API_KEY environment variable.")
        sys.exit(1)

    print("🚀 Initializing Gemini Commerce Assistant...")
    agent = GeminiShoppingAgent(api_key=api_key)

    session_id = "test-session-101"
    print(f"💬 Session ID: {session_id}")
    print(f"👤 User query: {args.query}")
    print("⏳ Running agent (this will invoke search tools)...")

    response = agent.send_message(args.query, session_id=session_id)

    if response["success"]:
        print("\n✨ [AGENT RESPONSE] ✨")
        print(response["text"])
        print("\n🔍 [TOOL EXECUTION TRACE] 🔍")
        print(response["thoughts"] if response["thoughts"] else "No tools were called.")
    else:
        print("\n❌ [AGENT FAILURE] ❌")
        print(response["text"])

if __name__ == "__main__":
    main()
