"""Test Azure OpenAI configuration."""
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# Load configuration
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

print("=" * 60)
print("Azure OpenAI Configuration Test")
print("=" * 60)
print(f"Endpoint: {endpoint}")
print(f"Deployment: {deployment}")
print(f"API Version: {api_version}")
print(f"API Key: {'*' * 20}{api_key[-4:] if len(api_key) > 4 else '(empty)'}")
print("=" * 60)

# Test the configuration
url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
headers = {"api-key": api_key, "Content-Type": "application/json"}

payload = {
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say 'Configuration test successful!' if you can read this."}
    ],
    "max_completion_tokens": 50,
}

print("\nTesting API call...")
print(f"URL: {url}\n")

try:
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            result = data["choices"][0]["message"]["content"]
            print(f"✓ SUCCESS: {result}")
        else:
            print(f"✗ FAILED")
            print(f"Response: {resp.text}")
            
            # Common error messages
            if resp.status_code == 404:
                print("\n⚠️  Error 404: The deployment name might be incorrect.")
                print(f"   Current deployment: '{deployment}'")
                print("   Common deployment names: gpt-4, gpt-4-turbo, gpt-4o, gpt-35-turbo")
            elif resp.status_code == 401:
                print("\n⚠️  Error 401: API key is invalid or expired.")
            elif resp.status_code == 429:
                print("\n⚠️  Error 429: Rate limit exceeded or quota depleted.")
                
except Exception as e:
    print(f"✗ ERROR: {type(e).__name__}: {str(e)}")

print("=" * 60)
