#!/usr/bin/env python3
"""Inspect a (possibly truncated) chat-completion response and summarize failure signals."""
import json
import re
import sys


def regex_fallback(text):
    info = {"parsed": False}
    m = re.search(r'"finish_reason"\s*:\s*"([^"]*)"', text)
    info["finish_reason"] = m.group(1) if m else None
    m = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    info["content_len"] = len(m.group(1)) if m else None
    m = re.search(r'"reasoning_content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    info["reasoning_len"] = len(m.group(1)) if m else None
    blocks = re.findall(r'"type"\s*:\s*"thinking"', text)
    thinking_texts = re.findall(r'"thinking"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    info["thinking_blocks"] = len(blocks)
    info["thinking_text_lens"] = [len(t) for t in thinking_texts]
    info["has_signature"] = '"signature"' in text
    info["usage"] = None
    return info


def structured(data):
    info = {"parsed": True}
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message", {}) or {}
    info["finish_reason"] = choice.get("finish_reason")
    info["content_len"] = len(msg.get("content") or "")
    info["reasoning_len"] = len(msg.get("reasoning_content") or "")
    blocks = msg.get("thinking_blocks") or []
    info["thinking_blocks"] = len(blocks)
    info["thinking_text_lens"] = [len(b.get("thinking") or "") for b in blocks]
    info["has_signature"] = any("signature" in b for b in blocks)
    info["usage"] = data.get("usage")
    return info


def main():
    if len(sys.argv) < 2:
        print("usage: inspect_completion.py <response-file>", file=sys.stderr)
        sys.exit(2)
    text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    try:
        info = structured(json.loads(text))
        info["payload_truncated"] = False
    except json.JSONDecodeError:
        info = regex_fallback(text)
        info["payload_truncated"] = True

    for k, v in info.items():
        print(f"{k}: {v}")

    print("\nsignals:")
    if info.get("payload_truncated"):
        print("- payload is not valid JSON (likely truncated on write or stream)")
    if info.get("finish_reason") == "length":
        print("- finish_reason=length: output hit max_tokens")
    if info.get("content_len") == 0:
        print("- content is empty: no visible output produced")
    if info.get("has_signature") and all(n == 0 for n in info.get("thinking_text_lens", [])):
        print("- thinking blocks contain only signatures: reasoning likely consumed the budget")


if __name__ == "__main__":
    main()
