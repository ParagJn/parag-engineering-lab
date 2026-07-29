# Project Schedule Tool - Backend

AI-powered backend for the Project Schedule Tool, providing intelligent project planning and optimization capabilities.

## Overview

This FastAPI-based backend integrates with multiple LLM providers to add intelligence to project scheduling and planning. It features a reusable, provider-agnostic LLM client that can work with SAP AI Core, OpenAI, Google Gemini, Azure OpenAI, and Anthropic models.

## Features

- 🤖 **Universal LLM Integration**: Support for multiple AI providers through a unified interface
- 🔄 **Automatic Token Management**: OAuth 2.0 token caching and refresh for SAP AI Core
- 🎯 **Task Analysis**: AI-powered task breakdown, effort estimation, and dependency identification
- 📊 **Project Optimization**: Intelligent suggestions for resource allocation and timeline optimization
- 💬 **Natural Language Queries**: Ask questions about your project in plain English
- 🔌 **RESTful API**: Clean, well-documented API endpoints
- 🔒 **Configurable Security**: CORS support for frontend integration
- 📝 **Comprehensive Logging**: Detailed logging for debugging and monitoring

## Architecture

```
backend/
├── main.py              # FastAPI application and endpoints
├── llm_client.py        # Universal LLM client (reusable)
├── config.json          # Model configuration
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (not in git)
├── .env.example         # Example environment configuration
├── start.sh             # Unix/Mac startup script
├── start.bat            # Windows startup script
└── README.md            # This file
```

## Prerequisites

- Python 3.9 or higher
- Virtual environment (recommended)
- API credentials for at least one LLM provider

## Setup Instructions

### 1. Virtual Environment

The project uses a shared virtual environment at `/Users/paragjain/dev-works/myenv`.

If you need to create a new virtual environment:

```bash
python3 -m venv /path/to/venv
source /path/to/venv/bin/activate  # On Unix/Mac
# or
/path/to/venv/Scripts/activate  # On Windows
```

### 2. Install Dependencies

```bash
# Activate virtual environment
source /Users/paragjain/dev-works/myenv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the example environment file and update with your credentials:

```bash
cp .env.example .env
```

Edit `.env` and add your API credentials:

```bash
# SAP AI Core (default provider)
SAP_CLIENT_ID=your_client_id
SAP_CLIENT_SECRET=your_client_secret

# Optional: Other providers
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
ANTHROPIC_API_KEY=your_anthropic_key
```

### 4. Configure Models

Edit `config.json` to enable/disable models and providers:

```json
{
  "models": {
    "sap_ai_core": {
      "enabled": true,
      "models": [
        {
          "name": "anthropic--claude-4.8-opus",
          "enabled": true,
          "default": true
        }
      ]
    }
  }
}
```

## Running the Backend

### Using the Unified Startup Script (Recommended)

The easiest way to run both the backend and frontend is to use the unified startup script from the **project root**:

```bash
cd ..  # Go to project root
./start.sh
```

This will start both services automatically:
- Backend API at `http://localhost:8000`
- Frontend at `http://localhost:5173`

### Running Backend Only (Manual Start)

If you want to run only the backend:

```bash
# Activate virtual environment
source /Users/paragjain/dev-works/myenv/bin/activate

# Navigate to backend directory
cd backend

# Start the server
python main.py
```

The server will start at `http://localhost:8000`

## API Documentation

Once the server is running, visit:

- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## API Endpoints

### Health & Info

- `GET /` - Root endpoint with API information
- `GET /health` - Health check

### Models

- `GET /models` - List all available models
- `GET /models/default` - Get default model configuration

### AI Generation

- `POST /generate` - Generic text generation
  ```json
  {
    "prompt": "Your prompt here",
    "model": "anthropic--claude-4.8-opus",
    "max_tokens": 5000
  }
  ```

### Task Analysis

- `POST /analyze/task` - Analyze a task description
  ```json
  {
    "task_description": "Implement user authentication",
    "context": {
      "project_type": "web_app",
      "tech_stack": "React, Node.js"
    }
  }
  ```

### Project Optimization

- `POST /optimize/project` - Get optimization suggestions
  ```json
  {
    "project_data": {
      "tasks": [...],
      "resources": [...],
      "timeline": "..."
    },
    "optimization_goals": [
      "reduce_timeline",
      "optimize_resources"
    ]
  }
  ```

### Natural Language Queries

- `POST /query` - Ask questions in natural language
  ```json
  {
    "query": "What are the critical path tasks?",
    "context": { ... }
  }
  ```

## LLM Client Usage

The `llm_client.py` module can be used standalone in other projects:

```python
from llm_client import UniversalLLMClient

# Initialize client
client = UniversalLLMClient(config_path="config.json")

# List available models
models = client.list_available_models()

# Generate text
response = client.generate(
    prompt="Explain quantum computing",
    model="anthropic--claude-4.8-opus",
    max_tokens=2000
)

print(response)
```

## Configuration Reference

### config.json Structure

```json
{
  "models": {
    "provider_key": {
      "provider": "sap|openai|google|azure|anthropic",
      "enabled": true|false,
      "models": [
        {
          "name": "model-name",
          "enabled": true|false,
          "default": true|false,
          "max_tokens": 25000
        }
      ],
      "auth": {
        "type": "oauth2|api_key",
        "api_base_url": "https://...",
        ...
      }
    }
  },
  "settings": {
    "default_provider": "sap_ai_core",
    "default_model": "anthropic--claude-4.8-opus",
    "retry_attempts": 3,
    "timeout_seconds": 120
  }
}
```

## Adding New Providers

To add a new AI provider:

1. Add provider configuration to `config.json`
2. Implement provider-specific request method in `llm_client.py`
3. Update the routing logic in `_make_request_with_retry()`

Example:

```python
def _make_request_new_provider(
    self,
    provider_config: Dict,
    model_config: Dict,
    prompt: str,
    **kwargs
) -> Dict:
    """Make API request to new provider"""
    # Implementation here
    pass
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black .
flake8 .
mypy .
```

### Development Mode

For auto-reload during development:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Troubleshooting

### Common Issues

**1. LLM Client not initialized**
- Check that `config.json` exists
- Verify environment variables are set correctly
- Check logs for initialization errors

**2. Authentication errors**
- Verify API credentials in `.env`
- Check token expiration (SAP tokens expire after ~1 hour)
- Ensure correct OAuth URL for SAP AI Core

**3. CORS errors**
- Update `ALLOWED_ORIGINS` in `.env`
- Add your frontend URL to the CORS middleware

**4. Model not found**
- Check that the model is enabled in `config.json`
- Verify the model name matches exactly
- Check provider is enabled

### Logs

Logs include:
- Request/response details (configurable)
- Authentication status
- Error messages with stack traces

Set log level in `config.json`:
```json
{
  "settings": {
    "logging": {
      "level": "DEBUG",  // INFO, WARNING, ERROR
      "log_requests": true,
      "log_responses": false
    }
  }
}
```

## Production Deployment

For production deployment:

1. Set `RELOAD=false` in `.env`
2. Use a production ASGI server (uvicorn with workers)
3. Set up proper logging and monitoring
4. Configure rate limiting
5. Use HTTPS
6. Set proper CORS origins
7. Use environment variables for all secrets

Example production command:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## License

[Your License Here]

## Support

For issues or questions, please contact [Your Contact Info]

---

**Note**: This backend is designed to be reusable across multiple projects. The `llm_client.py` module can be extracted and used in any Python project requiring LLM integration.
