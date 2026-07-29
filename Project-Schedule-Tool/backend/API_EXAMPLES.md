# API Usage Examples

## Simple Text Generation (Using Defaults)

The easiest way to use the API - just provide a prompt and let it use the default model:

```bash
curl -X POST 'http://localhost:8000/generate' \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "What are the three laws of robotics?"
  }'
```

## Text Generation with Custom Max Tokens

Control the response length:

```bash
curl -X POST 'http://localhost:8000/generate' \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Explain quantum computing",
    "max_tokens": 5000
  }'
```

## Specify a Different Model

If you have multiple models enabled:

```bash
curl -X POST 'http://localhost:8000/generate' \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Hello World",
    "model": "anthropic--claude-4.8-opus"
  }'
```

## Task Analysis

Analyze a task description for project planning:

```bash
curl -X POST 'http://localhost:8000/analyze/task' \
  -H 'Content-Type: application/json' \
  -d '{
    "task_description": "Implement user authentication with OAuth 2.0",
    "context": {
      "project_type": "web_app",
      "tech_stack": "React, FastAPI"
    }
  }'
```

## Project Optimization

Get AI-powered optimization suggestions:

```bash
curl -X POST 'http://localhost:8000/optimize/project' \
  -H 'Content-Type: application/json' \
  -d '{
    "project_data": {
      "tasks": [
        {"name": "Design UI", "duration": 5},
        {"name": "Implement Backend", "duration": 10},
        {"name": "Testing", "duration": 5}
      ],
      "total_duration": 20
    },
    "optimization_goals": ["reduce_timeline", "optimize_resources"]
  }'
```

## Natural Language Query

Ask questions about your project:

```bash
curl -X POST 'http://localhost:8000/query' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What are the best practices for project scheduling?",
    "context": {
      "project_size": "medium",
      "team_size": 5
    }
  }'
```

## List Available Models

See all enabled AI models:

```bash
curl -X GET 'http://localhost:8000/models'
```

## Get Default Model

Check which model is currently set as default:

```bash
curl -X GET 'http://localhost:8000/models/default'
```

## Health Check

Check if the API is running:

```bash
curl -X GET 'http://localhost:8000/health'
```

## Run All Tests

Use the automated test script:

```bash
cd backend
./test_api.sh
```

## Common Parameters

### For `/generate` endpoint:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `prompt` | string | Yes | - | The input prompt/question |
| `model` | string | No | Default model | Specific model to use (leave empty for default) |
| `provider` | string | No | Default provider | Provider to use (leave empty for default) |
| `max_tokens` | integer | No | 25000 | Maximum tokens to generate |

### Response Format:

```json
{
  "success": true,
  "response": { ... },
  "error": null,
  "model_used": "anthropic--claude-4.8-opus",
  "provider_used": "sap_ai_core",
  "timestamp": "2026-07-29T12:00:00.000000"
}
```

## Error Handling

If there's an error, you'll get:

```json
{
  "success": false,
  "response": null,
  "error": "Error message here",
  "model_used": null,
  "provider_used": null,
  "timestamp": "2026-07-29T12:00:00.000000"
}
```

## Tips

1. **Always use JSON format** for request bodies
2. **Omit optional parameters** to use defaults (recommended for most cases)
3. **Check `/docs`** for interactive API documentation at http://localhost:8000/docs
4. **Max tokens default is 25000** - adjust only if you need shorter responses
5. **Provider and model auto-select** from config.json when not specified
