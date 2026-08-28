# Data Model

## Session

```json
{
  "session_id": "sess_...",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "title": "Conversation title",
  "messages": [],
  "attachment_ids": []
}
```

## Message

```json
{
  "id": "msg_...",
  "role": "user | assistant | system",
  "content": "Markdown/text",
  "created_at": "ISO-8601 timestamp",
  "attachments": [
    {
      "attachment_id": "att_...",
      "filename": "document.pdf"
    }
  ]
}
```

## Attachment

```json
{
  "attachment_id": "att_...",
  "filename": "document.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 123456,
  "created_at": "ISO-8601 timestamp",
  "stored_path": "...",
  "content_markdown_path": "...",
  "status": "uploaded | processing | ready | failed"
}
```

## IDs

Generate all IDs server-side.

Recommended:

```python
uuid.uuid4()
```

Prefix IDs to make their purpose obvious:

```text
sess_<uuid>
msg_<uuid>
att_<uuid>
```

## Time

Store timestamps as ISO-8601.

Prefer timezone-aware UTC internally:

```text
2026-08-27T04:10:00Z
```

The UI can render them in the user's local timezone.

## Session title

Version 1 can derive the title from the first user message.

Example:

```text
"Help me understand this Databricks pipeline"
```

becomes:

```text
"Help me understand this Databricks..."
```

A model-generated title can be added later.

## History references

The session ID is the primary reference for conversation history.

Attachment IDs are the primary references for uploaded content.

Message IDs are the primary references for individual messages.

Do not use filenames as primary identifiers.
