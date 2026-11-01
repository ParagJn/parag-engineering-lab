"""Deliberate breaks for S10 (the guardrail scanner and where it is enforced).

Run:  cd backend && python -u -m scripts.mutation_check scripts/mutants/s10_guardrails.py
Every one of these should make the test suite FAIL. One that does not is a hole in the tests.
"""
SCAN = "app/guardrails/scan.py"
CHECKS = "app/agents/checks.py"
RUNTIME = "app/agents/runtime.py"
REPOS = "app/repos.py"
HUMAN = "app/review/human.py"
SERVICE = "app/review/service.py"
CONTEXT = "app/context/store.py"
RUNNER = "app/run/runner.py"
MAIN = "app/main.py"
CONFIG = "app/config.py"

MUTANTS = [
    # --- the rules
    ("a private key header is not found", SCAN, 'collect("private_key", _PRIVATE_KEY, gate="PRIVATE KEY" in text)', "pass"),
    ("a cloud key is one character too strict", SCAN, r'_AWS = re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Za-z0-9])")', r'_AWS = re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA)[A-Z0-9]{17}(?![A-Za-z0-9])")'),
    ("a temporary cloud key is not found", SCAN, "(?:AKIA|ASIA)[A-Z0-9]{16}", "(?:AKIA)[A-Z0-9]{16}"),
    ("a short code-hosting token is accepted", SCAN, "gh[pousr]_[A-Za-z0-9]{30,255}", "gh[pousr]_[A-Za-z0-9]{3,255}"),
    ("a fine-grained code-hosting token is missed", SCAN, "|github_pat_[A-Za-z0-9_]{22,255})", ")"),
    ("a chat token is missed", SCAN, 'collect("slack_token", _SLACK, gate="xox" in text)', "pass"),
    ("a restricted payment key is missed", SCAN, "[sr]k_live_", "sk_live_"),
    ("a cloud API key is missed", SCAN, 'collect("google_api_key", _GOOGLE, gate="AIza" in text)', "pass"),
    ("a login token is missed", SCAN, 'collect("jwt", _JWT, gate="eyJ" in text)', "pass"),
    ("a password in a web address is missed", SCAN, 'if "url_password" in names and "://" in text:', "if False:"),
    ("a placeholder web password is flagged", SCAN, "if m and not _placeholder_password(m.group(2)):", "if m:"),
    ("the configured credentials are not checked", SCAN, 'if "configured_credential" in names:\n            self._configured(text, out, limit)', "pass"),
    ("a very short configured value matches", SCAN, "            if len(secret) < MIN_SECRET_CHARS:\n                continue", "            if not secret:\n                continue"),
    ("a configured host name is case sensitive", SCAN, 'if secret.lower().startswith(("http://", "https://")):', "if False:"),
    ("the secret list is read once", SCAN, "for secret in dict.fromkeys(s.strip() for s in self._secrets() if s and s.strip()):", "for secret in dict.fromkeys(s.strip() for s in tuple(self._secrets())[:0] if s and s.strip()):"),
    ("a credential value is not judged at all", SCAN, "accept=lambda m: _looks_like_secret_value(m.group(1))", "accept=lambda m: True"),
    ("a self-labelled stand-in is a credential", SCAN, '"todo", "<", ">", "${", "{{", "%(", "insert", "replace", "test", "fake", "demo", "secret",', '"todo", "<", ">", "${", "{{", "%(", "insert", "replace",'),
    ("a low-entropy value is a credential", SCAN, "    return _entropy(value) >= 3.0", "    return True"),
    ("an item ID is a credential", SCAN, ' or "://" in value or _ID_LIKE.fullmatch(value):', ' or "://" in value:'),
    ("code in a value is a credential", SCAN, "    if any(c in _CODE_CHARS for c in value):\n        return False\n", ""),
    ("a one-character-type value is a credential", SCAN, "    if kinds < 2:\n        return False\n", ""),
    ("a reserved example domain is flagged", SCAN, "accept=lambda m: not _reserved_domain(m.group(1)) and not _is_git_remote(text, m)", "accept=lambda m: not _is_git_remote(text, m)"),
    ("a git remote is flagged as an email", SCAN, "accept=lambda m: not _reserved_domain(m.group(1)) and not _is_git_remote(text, m)", "accept=lambda m: not _reserved_domain(m.group(1))"),
    ("every reserved top-level name is flagged", SCAN, '_RESERVED_DOMAIN_SUFFIXES = (".example", ".invalid", ".test", ".localhost", ".local")', "_RESERVED_DOMAIN_SUFFIXES = ()"),
    ("a phone number needs no length check", SCAN, "accept=lambda m: 8 <= sum(c.isdigit() for c in m.group(0)) <= 15)", "accept=lambda m: True)"),
    ("a grouped phone form is missed", SCAN, "            collect(\"phone\", _PHONE_GROUPED)\n", ""),
    ("a card number needs no checksum", SCAN, "len(set(digits)) > 1 and _luhn(digits)", "len(set(digits)) > 1"),
    ("a repeated-digit run is a card", SCAN, "len(set(digits)) > 1 and _luhn(digits)", "_luhn(digits)"),
    ("the Luhn check is wrong", SCAN, "        total += d\n        flip = not flip", "        total += d + 1\n        flip = not flip"),
    ("a bank account needs no checksum", SCAN, "    return int(number) % 97 == 1", "    return True"),
    ("an unknown country is a bank account", SCAN, "or compact[:2] not in _IBAN_COUNTRIES:", ":"),
    # --- results
    ("a finding reports the wrong line", SCAN, "located = [(bisect_right(starts, s), e - s, r) for s, e, r in spans]", "located = [(bisect_right(starts, s) + 1, e - s, r) for s, e, r in spans]"),
    ("a heading is taken from below the value", SCAN, "        while cursor < line:                         # headings strictly BEFORE this line", "        while cursor <= line:                        # headings strictly BEFORE this line"),
    ("a heading holding a value is copied", SCAN, "heading = HEADING_REMOVED if cursor in on_finding_line else title[:MAX_HEADING_CHARS]", "heading = title[:MAX_HEADING_CHARS]"),
    ("a section heading holding a value is copied", SCAN, "    return HEADING_REMOVED if scanner.scan(heading) else heading[:MAX_HEADING_CHARS]", "    return heading[:MAX_HEADING_CHARS]"),
    ("headings are not cut", SCAN, "heading = HEADING_REMOVED if cursor in on_finding_line else title[:MAX_HEADING_CHARS]", "heading = HEADING_REMOVED if cursor in on_finding_line else title"),
    ("findings are not capped", SCAN, "_findings(text, spans[:MAX_FINDINGS])", "_findings(text, spans)"),
    ("findings are not in order", SCAN, "spans = _merge_overlaps(sorted(spans))", "spans = _merge_overlaps(spans)"),
    ("the same digits count twice", SCAN, "        if out and out[-1][2] == span[2] and span[0] < out[-1][1]:", "        if False:"),
    ("a token is also reported as a generic assignment", SCAN, 'weaker = rule == "credential_assignment" or BY_NAME[rule].klass == PERSONAL', "weaker = False"),
    ("section scans restart the line count", SCAN, "            offset += text.count(\"\\n\") + 1", "            offset += 0"),
    ("the description names the value", SCAN, '    where = f"line {finding.line}" + (f", under \'{finding.heading}\'" if finding.heading else "")', '    where = f"line {finding.line}" + (f", under \'{finding.heading}\' (length {finding.length})" if finding.heading else "")'),
    ("a personal-data finding is a problem", SCAN, "return [describe(f) for f in self.scan(text) if f.klass == SECRET]", "return [describe(f) for f in self.scan(text)]"),
    # --- switching rules off
    ("a disabled rule keeps firing", SCAN, "return [r for r in RULES if r.name not in self.disabled and (only is None or r.name in only)]", "return [r for r in RULES if (only is None or r.name in only)]"),
    ("an unknown rule name is accepted", SCAN, "    if unknown:\n        raise ValueError(f\"unknown guardrail rule(s)", "    if False:\n        raise ValueError(f\"unknown guardrail rule(s)"),
    ("your own key can be switched off", SCAN, "    if locked:\n        raise ValueError(f\"guardrail rule(s)", "    if False:\n        raise ValueError(f\"guardrail rule(s)"),
    ("a private key can be switched off", SCAN, 'Rule("private_key", SECRET, "a private key", always_on=True),', 'Rule("private_key", SECRET, "a private key"),'),
    ("the setting is not checked at start-up", CONFIG, "        parse_disabled(value)   # raises", "        pass   # raises"),
    ("the scanner ignores the setting", SCAN, "return cls(settings.secret_values, settings.guardrails_disabled)", "return cls(settings.secret_values, ())"),
    # --- enforcement
    ("an agent's secret is not a problem", CHECKS, "        problems = (scanner.problems(body) + problems)[:MAX_PROBLEMS]", "        pass"),
    ("a secret problem can be cut off the list", CHECKS, "        problems = (scanner.problems(body) + problems)[:MAX_PROBLEMS]", "        problems = (problems + scanner.problems(body))[:MAX_PROBLEMS]"),
    ("the runtime does not scan", RUNTIME, "check_body(body, skill, prompt.allowed, item_ctx, result.finish_reason, scanner), body", "check_body(body, skill, prompt.allowed, item_ctx, result.finish_reason, None), body"),
    ("the runtime passes no scanner to its check", RUNTIME, "self._check(result, skill, prompt, item_ctx, self.scanner)", "self._check(result, skill, prompt, item_ctx)"),
    ("findings are not kept with the version", RUNTIME, '            "guardrails": flags,\n', ""),
    ("the flag count is always zero", RUNTIME, "links=len(links), flags=len(flags),", "links=len(links), flags=0,"),
    ("a person's secret is accepted", HUMAN, "problems = check_body(body, skill, upstream_ids | resolved, item_ctx, scanner=self.runtime.scanner)", "problems = check_body(body, skill, upstream_ids | resolved, item_ctx)"),
    ("a person's flags are not kept", HUMAN, '            "guardrails": [f.as_dict() for f in self.runtime.scanner.scan(body)],\n', ""),
    ("the approval record forgets the flags", HUMAN, '"built_on_changed": stale_built, "guardrail_flags": flagged,', '"built_on_changed": stale_built, "guardrail_flags": {},'),
    ("the approval record counts secrets as flags", HUMAN, 'found = [f for f in (record or {}).get("guardrails", []) if f.get("class") == "personal"]', 'found = [f for f in (record or {}).get("guardrails", [])]'),
    ("a review's secret is stored", SERVICE, "        problems = (self.runtime.scanner.problems(text) + problems)[:MAX_PROBLEMS]", "        pass"),
    ("a review's findings are not scanned", SERVICE, 'text = "\\n".join([parsed.summary, *(f"{f.target} {f.problem} {f.fix}" for f in parsed.findings)])', 'text = ""'),
    ("the repository has no last line of defence", REPOS, "        found = self.backstop.scan(body, only=BACKSTOP_RULES)   # BACKSTOP_RULES holds secret rules only\n        if found:", "        found = []\n        if found:"),
    ("the backstop covers every rule", REPOS, "self.backstop.scan(body, only=BACKSTOP_RULES)", "self.backstop.scan(body)"),
    # Left out on purpose: "the backstop refuses personal data". BACKSTOP_RULES is built from secret rules only, so the scan can never
    # return a personal finding there; an extra class check changed nothing observable and was removed instead of tested.
    # tests/test_guardrails_wiring.py still proves the backstop saves text containing an email, a phone number and a card.
    ("the atomic save skips the backstop", REPOS, "        self._refuse_secrets(body)\n        with self.db.write() as conn:\n            _require_project(conn, project_id)", "        with self.db.write() as conn:\n            _require_project(conn, project_id)"),
    ("add_version skips the backstop", REPOS, "        self._refuse_secrets(body)\n        with self.db.write() as conn:\n            if guard is not None:", "        with self.db.write() as conn:\n            if guard is not None:"),
    ("a refusal repeats the value", REPOS, 'f"this version was not saved: {describe(found[0])}"', 'f"this version was not saved: {describe(found[0])} {body[:40]}"'),
    ("the app does not arm the backstop", MAIN, "    store.artefacts.backstop = scanner", "    pass"),
    ("the app does not arm the document scan", MAIN, "    store.context.scanner = scanner ", "    pass "),
    ("the status block is missing", MAIN, '            "guardrails": guardrails_status(scanner),\n', ""),
    ("a document scan is skipped", CONTEXT, "        if self.scanner is None:\n            return ()", "        return ()"),
    ("an upload with a secret is refused", CONTEXT, "        return tuple(self.scanner.scan_sections([(s.heading_path, s.text) for s in extracted.sections]))", "        found = tuple(self.scanner.scan_sections([(s.heading_path, s.text) for s in extracted.sections]))\n        if any(f.klass == 'secret' for f in found):\n            raise DocumentRefused('secret')\n        return found"),
    ("the document audit row has no counts", CONTEXT, '**({"guardrail_flags": _counts(findings)} if findings else {})},', "},"),
    ("the document audit row has every finding", CONTEXT, '**({"guardrail_flags": _counts(findings)} if findings else {})},', '**({"guardrail_flags": [f.as_dict() for f in findings]} if findings else {})},'),
    ("a repeat upload reports nothing", CONTEXT, "return replace(_info(existing, already_added=True), findings=findings)\n            return replace(self._insert_document(conn, project_id, name, extracted.kind, digest, len(data),\n                                                  extracted.chars, chunks, actor, findings), findings=findings)\n\n    def replace_document", "return _info(existing, already_added=True)\n            return replace(self._insert_document(conn, project_id, name, extracted.kind, digest, len(data),\n                                                  extracted.chars, chunks, actor, findings), findings=findings)\n\n    def replace_document"),
    ("the flag count is not published", RUNNER, '"items": len(result.items), "links": result.links, "flags": result.flags, "author": result.author,', '"items": len(result.items), "links": result.links, "author": result.author,'),
    ("the rule names are published in an event", RUNNER, '"flags": result.flags,', '"flags": result.flags, "flag_rules": [f["rule"] for f in (self.store.artefacts.get_version(project_id, result.artefact_id).generation or {}).get("guardrails", [])],'),
]
