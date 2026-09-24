---
name: creating-documents-from-markdown
description: Diagnoses LLM chat-completion responses that come back empty, truncated, or malformed, such as JSON with finish_reason "length", empty message content, empty reasoning_content, or thinking blocks that hold only a signature. Explains the likely cause and recommends concrete fixes. Use when a model or API call returns no usable text, when generated files contain raw API response JSON instead of the expected content, or when output stops mid-way.
when_to_use: Example requests include "why is my completion content empty?", "the model returned finish_reason length with nothing in it", "my generated SKILL.md is just a JSON blob", "reasoning ate all my tokens", and "the response JSON is cut off and won't parse".
argument-hint: "[response-file]"
arguments: [response_file]
allowed-tools: Read Grep Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# Diagnosing truncated or empty chat completions

Use this skill when an LLM API response has no usable output, or when a raw response payload was written somewhere real content was expected. A common example is a generated file that holds a `chat.completion` JSON object instead of the document it should contain.

## Inputs

- `$response_file`: path to the saved response or the affected file. If no path is given, ask for one or use the JSON pasted in the conversation.

## Workflow

1. **Inspect the payload.**
   Run:
   ```
   python3 ${CLAUDE_SKILL_DIR}/scripts/inspect_completion.py "$response_file"
   ```
   The script also accepts truncated or invalid JSON. It falls back to regex extraction and reports:
   - `finish_reason`
   - the lengths of `content` and `reasoning_content`
   - the number of thinking blocks, and whether each one holds text or only a signature
   - the `usage` token counts, if present
   - whether the payload itself was cut off

2. **Classify the failure.** Use the table below.

   | Symptom | Likely cause | Fix |
   |---|---|---|
   | `finish_reason: "length"`, empty `content`, thinking block with only a `signature` | The reasoning or thinking budget used up all of `max_tokens` before any visible output was produced | Raise `max_tokens`, or lower the thinking budget or reasoning effort so that `budget < max_tokens`, leaving room for the answer |
   | `finish_reason: "length"`, partial `content` | The output was longer than `max_tokens` | Raise `max_tokens`, request shorter output, or split the task into chunks or continuation calls |
   | The payload JSON itself is cut off (for example, an unterminated `signature` string) | The file writer or log truncated the saved response, or the stream ended early | Save the full response, check the streaming or accumulation code, and retry |
   | The whole response object was written into an output file | The pipeline wrote `response` instead of `response.choices[0].message.content` | Extract the content field, and validate that it is non-empty before writing |
   | `finish_reason: "stop"` but empty `content` | Content filtering, or the prompt ended in a way that elicits no text | Check the provider's safety or filter fields, and adjust the prompt |
   | `finish_reason: "tool_calls"` | The model wanted to call a tool, and no text is expected | Handle the tool call, then continue the loop |

3. **Report.** State the following:
   - the diagnosis, with evidence quoted from the payload
   - the root cause
   - a minimal code or config fix

4. **Recover the intended artifact, if applicable.** If the payload was written into a file that should hold real content (for example, a SKILL.md), say that nothing usable can be recovered from an empty `content` field. The generation has to be re-run with the fix applied. Do not invent the missing content.

## Guardrails

- Never print or try to decode `signature` values. They are opaque and carry no recoverable text.
- Do not claim what the model "would have said". Empty content means no output was produced.
- Also recommend a pipeline check that fails fast when `content` is empty or `finish_reason == "length"`.

## Reference

See `references/example-truncated-response.md` for a real example of this failure mode.
