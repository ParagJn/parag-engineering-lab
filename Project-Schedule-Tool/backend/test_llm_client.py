"""
Test script for Universal LLM Client

This script demonstrates how to use the LLM client and tests its functionality.
Run this to verify your configuration is correct.

Usage:
    python test_llm_client.py
"""

import os
import sys
import json
from llm_client import UniversalLLMClient, LLMClientError


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_initialization():
    """Test client initialization"""
    print_section("1. Testing Client Initialization")
    
    try:
        client = UniversalLLMClient(config_path="config.json")
        print("✅ Client initialized successfully")
        return client
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        sys.exit(1)


def test_list_models(client: UniversalLLMClient):
    """Test listing available models"""
    print_section("2. Testing List Models")
    
    try:
        models = client.list_available_models()
        print(f"Found {len(models)} available model(s):\n")
        
        for model in models:
            print(f"  Provider: {model['provider']}")
            print(f"  Model: {model['model_name']}")
            print(f"  Default: {model['is_default']}")
            print(f"  Capabilities: {', '.join(model['capabilities'])}")
            print(f"  Max Tokens: {model['max_tokens']}")
            print()
        
        if len(models) == 0:
            print("⚠️  No models are enabled. Please enable at least one model in config.json")
            return False
        
        print("✅ Model listing successful")
        return True
        
    except Exception as e:
        print(f"❌ Failed to list models: {e}")
        return False


def test_default_model(client: UniversalLLMClient):
    """Test getting default model"""
    print_section("3. Testing Default Model Configuration")
    
    try:
        provider, model = client.get_default_model()
        print(f"Default Provider: {provider}")
        print(f"Default Model: {model}")
        print("✅ Default model configuration retrieved")
        return True
    except Exception as e:
        print(f"❌ Failed to get default model: {e}")
        return False


def test_simple_generation(client: UniversalLLMClient):
    """Test simple text generation"""
    print_section("4. Testing Simple Text Generation")
    
    prompt = "What are the three laws of robotics? Be concise."
    print(f"Prompt: {prompt}\n")
    
    try:
        print("Sending request to LLM...")
        response = client.generate(
            prompt=prompt,
            max_tokens=500
        )
        
        print("\n✅ Generation successful!")
        print("\nResponse structure:")
        print(json.dumps(response, indent=2)[:500] + "...")
        
        return True
        
    except LLMClientError as e:
        print(f"❌ LLM Client Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_task_analysis_prompt(client: UniversalLLMClient):
    """Test a task analysis prompt (typical use case)"""
    print_section("5. Testing Task Analysis Use Case")
    
    prompt = """Analyze this task and provide a structured breakdown:

Task: Implement user authentication system with OAuth 2.0

Please provide:
1. Estimated effort in person-days (min, max, likely)
2. Key dependencies or prerequisites
3. Potential risks or challenges

Keep the response concise."""
    
    print(f"Prompt: {prompt[:100]}...\n")
    
    try:
        print("Sending request to LLM...")
        response = client.generate(
            prompt=prompt,
            max_tokens=1000
        )
        
        print("\n✅ Task analysis successful!")
        print("\nResponse preview:")
        response_str = json.dumps(response, indent=2)
        print(response_str[:300] + "..." if len(response_str) > 300 else response_str)
        
        return True
        
    except LLMClientError as e:
        print(f"❌ LLM Client Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_token_caching(client: UniversalLLMClient):
    """Test that token caching works (SAP only)"""
    print_section("6. Testing Token Caching (SAP AI Core)")
    
    # Check if SAP is the default provider
    provider, _ = client.get_default_model()
    if provider != "sap_ai_core":
        print("ℹ️  Skipping token caching test (not using SAP AI Core)")
        return True
    
    try:
        print("Making first request...")
        client.generate(prompt="Hello", max_tokens=10)
        
        print("Making second request (should use cached token)...")
        client.generate(prompt="Hello again", max_tokens=10)
        
        print("✅ Token caching working (check logs for 'cached' message)")
        return True
        
    except Exception as e:
        print(f"❌ Token caching test failed: {e}")
        return False


def test_error_handling(client: UniversalLLMClient):
    """Test error handling with invalid configuration"""
    print_section("7. Testing Error Handling")
    
    try:
        print("Testing with non-existent model...")
        client.generate(
            prompt="Test",
            model="non-existent-model",
            max_tokens=10
        )
        print("❌ Should have raised an error")
        return False
        
    except LLMClientError as e:
        print(f"✅ Error correctly caught: {e}")
        return True
    except Exception as e:
        print(f"⚠️  Unexpected error type: {e}")
        return True


def main():
    """Run all tests"""
    print("""
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║          Universal LLM Client - Test Suite                        ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    # Check environment
    print("Checking environment variables...")
    sap_client_id = os.getenv("SAP_CLIENT_ID")
    sap_client_secret = os.getenv("SAP_CLIENT_SECRET")
    
    if not sap_client_id or not sap_client_secret:
        print("\n⚠️  Warning: SAP credentials not found in environment")
        print("Make sure to set SAP_CLIENT_ID and SAP_CLIENT_SECRET")
        print("You can load them from .env file or set them manually\n")
    else:
        print("✅ SAP credentials found in environment\n")
    
    # Run tests
    results = {}
    
    client = test_initialization()
    results["Initialization"] = True
    
    results["List Models"] = test_list_models(client)
    results["Default Model"] = test_default_model(client)
    results["Simple Generation"] = test_simple_generation(client)
    results["Task Analysis"] = test_task_analysis_prompt(client)
    results["Token Caching"] = test_token_caching(client)
    results["Error Handling"] = test_error_handling(client)
    
    # Summary
    print_section("Test Summary")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n{'='*70}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'='*70}\n")
    
    if passed == total:
        print("🎉 All tests passed! The LLM client is ready to use.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Please check the configuration.")
        sys.exit(1)


if __name__ == "__main__":
    # Load environment variables if .env file exists
    try:
        from dotenv import load_dotenv
        if os.path.exists(".env"):
            load_dotenv()
            print("📝 Loaded environment variables from .env file\n")
    except ImportError:
        print("💡 Tip: Install python-dotenv to auto-load .env file\n")
    
    main()
