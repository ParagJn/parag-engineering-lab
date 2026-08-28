"""
Test script for IBM ICA client.
Interactive chat session with token tracking.
"""

import os
import sys

from dotenv import load_dotenv

from ibm_ica_client import IBMICAClient, IBMICAConfigError, IBMICAError


def main() -> int:
    """Run interactive chat session."""
    load_dotenv()

    # Load configuration from environment
    api_key = (os.getenv("IBM_ICA_API_KEY") or "").strip()
    model_id = (os.getenv("IBM_ICA_MODEL_ID") or "").strip() or "claude-sonnet-5"
    endpoint = (
        os.getenv("IBM_ICA_endpoint") or os.getenv("IBM_ICA_ENDPOINT") or ""
    ).strip()

    # Validate required variables
    missing = []
    if not api_key:
        missing.append("IBM_ICA_API_KEY")
    if not endpoint:
        missing.append("IBM_ICA_endpoint (or IBM_ICA_ENDPOINT)")

    if missing:
        print(
            "Missing required environment variables:", ", ".join(missing), file=sys.stderr
        )
        print("\nSet these in your .env file:", file=sys.stderr)
        print("IBM_ICA_API_KEY=your_key_here", file=sys.stderr)
        print("IBM_ICA_ENDPOINT=https://your-ibm-ica-url", file=sys.stderr)
        print("IBM_ICA_MODEL_ID=claude-sonnet-5  # optional", file=sys.stderr)
        return 1

    # Initialize client
    try:
        client = IBMICAClient(endpoint=endpoint, api_key=api_key, model_id=model_id)
    except IBMICAConfigError as err:
        print(f"Configuration error: {err}", file=sys.stderr)
        return 1

    print(f"Endpoint: {client.endpoint}")
    print(f"Model:    {client.model_id}")
    print(f"SSL Mode: {'INSECURE (testing only)' if client.insecure_tls else 'VERIFIED'}")
    print("\nCandidate endpoints:")
    for url in client.candidate_urls:
        print(f"  • {url}")

    # Initialize conversation
    messages = [{"role": "system", "content": "You are a concise assistant."}]
    session_prompt_tokens = 0
    session_completion_tokens = 0
    session_total_tokens = 0

    print("\n" + "=" * 60)
    print("Interactive chat started. Press Ctrl+C to exit.")
    print("=" * 60)

    while True:
        try:
            user_prompt = input("\n🧑 You: ").strip()
        except KeyboardInterrupt:
            print("\n\nExiting chat. Goodbye!")
            return 0
        except EOFError:
            print("\n\nInput closed. Exiting chat.")
            return 0

        if not user_prompt:
            print("⚠️  Please enter a prompt.")
            continue

        # Add user message
        messages.append({"role": "user", "content": user_prompt})

        try:
            # Send chat request
            result = client.chat(messages, max_tokens=100000)
            reply = result["text"]
            
            print(f"\n🤖 Assistant: {reply}")

            # Extract token usage
            prompt_tokens = result["prompt_tokens"]
            completion_tokens = result["completion_tokens"]
            total_tokens = result["total_tokens"]
            estimated = result["estimated"]

            # Update session totals
            session_prompt_tokens += prompt_tokens
            session_completion_tokens += completion_tokens
            session_total_tokens += total_tokens

            # Display token usage
            estimate_note = " (estimated)" if estimated else ""
            print(f"\n📊 Tokens this turn{estimate_note}:")
            print(f"   Input: {prompt_tokens:,} | Output: {completion_tokens:,} | Total: {total_tokens:,}")
            print(f"\n📈 Session totals:")
            print(
                f"   Input: {session_prompt_tokens:,} | "
                f"Output: {session_completion_tokens:,} | "
                f"Total: {session_total_tokens:,}"
            )

            # Add assistant response to conversation
            messages.append({"role": "assistant", "content": reply})

        except IBMICAError as err:
            print(f"\n❌ Chat request failed: {err}", file=sys.stderr)
            # Remove failed user turn from context
            if messages and messages[-1].get("role") == "user":
                messages.pop()


if __name__ == "__main__":
    sys.exit(main())