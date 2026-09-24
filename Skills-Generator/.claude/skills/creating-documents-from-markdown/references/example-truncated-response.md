# Example: empty, length-truncated completion saved in place of a SKILL.md

This payload was written into a SKILL.md file in place of the skill content. Two problems combined here:

- The response has `finish_reason: "length"`, empty `content`, and a thinking block that holds only a signature. The thinking budget used up `max_tokens`.
- The saved file is itself cut off in the middle of the `signature` string.

Only the start of the original `signature` value is kept below. The value is opaque and has no diagnostic use.

```json
{
  "id": "chatcmpl-23360168-255c-48e7-abce-148cd226ad46",
  "created": 1790263239,
  "model": "claude-opus-5-5",
  "object": "chat.completion",
  "choices": [
    {
      "finish_reason": "length",
      "index": 0,
      "message": {
        "content": "",
        "role": "assistant",
        "reasoning_content": "",
        "thinking_blocks": [
          {
            "type": "thinking",
            "thinking": "",
            "signature": "CAQSk8cCChIIEhABGAI4AUIIdGhpbmtpbmcS...
```

**Diagnosis:** The reasoning or thinking budget used all of the output tokens, so no visible content was produced. The pipeline then wrote the raw response object to disk instead of the content field, and the write was also truncated.

**Fix:**
- Ensure `thinking_budget < max_tokens`, with enough headroom for the answer.
- Write `choices[0].message.content` rather than the raw response object.
- Reject the output when `content` is empty or `finish_reason == "length"`.
