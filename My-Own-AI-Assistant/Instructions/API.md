# API Contract

Base path:

```text
/api
```

## POST /sessions

Creates a session.

### Response

```json
{
  "session_id": "sess_01...",
  "created_at": "2026-08-27T09:30:00+05:30",
  "title": "New conversation"
}
```

## GET /sessions

Returns sessions ordered by most recently updated.

### Response

```json
[
  {
    "session_id": "sess_01...",
    "title": "Working on Python",
    "created_at": "...",
    "updated_at": "..."
  }
]
```

## GET /sessions/{session_id}

Returns the full session.

## DELETE /sessions/{session_id}

Deletes a session.

Deletion should be explicit and should not occur automatically.

## POST /sessions/{session_id}/messages

### Request

```json
{
  "content": "Explain this code",
  "attachment_ids": [
    "att_123"
  ]
}
```

### Response

```json
{
  "session_id": "sess_01...",
  "message": {
    "id": "msg_...",
    "role": "assistant",
    "content": "## Explanation\n...",
    "created_at": "..."
  }
}
```

## POST /sessions/{session_id}/attachments

Use `multipart/form-data`.

### Response

```json
{
  "attachment_id": "att_123",
  "filename": "example.pdf",
  "mime_type": "application/pdf",
  "markdown_available": true
}
```

## GET /sessions/{session_id}/attachments/{attachment_id}

Returns attachment metadata.

Do not expose arbitrary filesystem paths.

## Health endpoint

Implement:

```text
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

## API principles

- Pydantic request/response models
- Consistent error responses
- Async endpoints where I/O benefits
- No model-provider details exposed to frontend
- No API keys returned by any endpoint
