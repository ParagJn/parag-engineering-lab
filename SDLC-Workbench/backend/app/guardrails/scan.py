"""The guardrail scanner: finds secrets and personal data in text. Pure code: no model, no network, no I/O.

Two classes of finding:

  secret    something that must never be written into an artefact (a key, a token, a private key, a password).
            These are REFUSED at save, and an agent is told to take them out through the repair loop.
  personal  personal data (an email address, a phone number, a card or bank number). These are FLAGGED: the text is saved
            and the findings are kept with it, because such data is sometimes legitimate (a named support contact).

A finding NEVER carries the matched text. It records the rule, the class, the line, the section heading the line sits
under, and the length, and nothing else, because findings are stored and shown and the point is to keep the value out of
every record. Every pattern is bounded so that scanning is linear in the length of the text, and a hostile document cannot
make it hang.

This is a safety net for the ACCIDENTAL, not a defence against someone hiding a secret: it does not read prose
("the password is hunter2"), split or encoded values, names, postal addresses or national ID numbers.
"""
from __future__ import annotations

import math
import re
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from itertools import accumulate
from typing import Callable, Collection, Iterable, Sequence

from ..models import InvalidInput

SECRET, PERSONAL = "secret", "personal"
MAX_FINDINGS = 200          # per scan: a document full of addresses reports the first 200
MAX_HEADING_CHARS = 80
HEADING_REMOVED = "(heading removed)"
MIN_SECRET_CHARS = 4        # a configured value shorter than this would match everywhere


class SecretRefused(InvalidInput):
    """Text containing a secret was not saved. The message names the rule and the line, never the value."""


@dataclass(frozen=True)
class Rule:
    name: str
    klass: str
    what: str            # how a secret is described to a model or a person
    always_on: bool = False
    backstop: bool = True   # applied by the repository's last-line refusal (secret rules only)


RULES: tuple[Rule, ...] = (
    Rule("private_key", SECRET, "a private key", always_on=True),
    Rule("configured_credential", SECRET, "one of this application's own credentials", always_on=True),
    Rule("aws_key_id", SECRET, "a cloud access key"),
    Rule("github_token", SECRET, "a code-hosting access token"),
    Rule("slack_token", SECRET, "a chat access token"),
    Rule("stripe_key", SECRET, "a payment-service secret key"),
    Rule("google_api_key", SECRET, "a cloud API key"),
    Rule("jwt", SECRET, "a signed login token"),
    Rule("url_password", SECRET, "a web address with a password in it"),
    Rule("credential_assignment", SECRET, "a password, secret or token value", backstop=False),
    Rule("email", PERSONAL, "an email address", backstop=False),
    Rule("phone", PERSONAL, "a phone number", backstop=False),
    Rule("payment_card", PERSONAL, "a payment card number", backstop=False),
    Rule("iban", PERSONAL, "a bank account number (IBAN)", backstop=False),
)
BY_NAME = {r.name: r for r in RULES}
RULE_NAMES = tuple(BY_NAME)
ALWAYS_ON = frozenset(r.name for r in RULES if r.always_on)
BACKSTOP_RULES = frozenset(r.name for r in RULES if r.klass == SECRET and r.backstop)


def parse_disabled(value: str | Iterable[str]) -> frozenset[str]:
    """Rule names to switch off, from a comma-separated string or a list. Unknown or always-on names are refused."""
    names = [p.strip().lower() for p in (value.split(",") if isinstance(value, str) else value) if p and p.strip()]
    unknown = sorted(set(names) - set(BY_NAME))
    if unknown:
        raise ValueError(f"unknown guardrail rule(s) {unknown}; the rules are {list(RULE_NAMES)}")
    locked = sorted(set(names) & ALWAYS_ON)
    if locked:
        raise ValueError(f"guardrail rule(s) {locked} cannot be switched off: a switch that lets your own key or a private key into an artefact defeats the purpose")
    return frozenset(names)


@dataclass(frozen=True)
class Finding:
    rule: str
    klass: str
    line: int        # 1-based
    heading: str     # the section heading in effect; "" if none
    length: int      # characters matched (never the characters themselves)

    def as_dict(self) -> dict:
        return {"rule": self.rule, "class": self.klass, "line": self.line, "heading": self.heading, "length": self.length}


def describe(finding: Finding) -> str:
    """One plain sentence about a secret finding, safe to send back to a model: it names the rule and the place, never the value."""
    where = f"line {finding.line}" + (f", under '{finding.heading}'" if finding.heading else "")
    what = BY_NAME[finding.rule].what
    return (f"{where}: this looks like {what} (rule {finding.rule}); remove it, and never write a secret, password, token or key "
            "into an artefact. Say that one exists, not what it is")


def counts_by_rule(findings: Iterable[Finding]) -> dict[str, int]:
    return dict(sorted(Counter(f.rule for f in findings).items()))


# ---- the patterns: all bounded, none with nested repeats --------------------------------------------------------------

_PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9]{1,20} ){0,4}PRIVATE KEY(?: BLOCK)?-----")
_AWS = re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Za-z0-9])")
_GITHUB = re.compile(r"(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9]{30,255}|github_pat_[A-Za-z0-9_]{22,255})")
_SLACK = re.compile(r"(?<![A-Za-z0-9])xox[abprs]-[A-Za-z0-9-]{10,255}")
_STRIPE = re.compile(r"(?<![A-Za-z0-9_])[sr]k_live_[A-Za-z0-9]{16,255}")
_GOOGLE = re.compile(r"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])")
_JWT = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,2000}\.[A-Za-z0-9_-]{8,2000}\.[A-Za-z0-9_-]{8,2000}")
_URL_USERINFO = re.compile(r"([^\s/:@]{1,128}):([^\s/@]{1,256})@")   # applied to the 300 characters after '://'
_ASSIGN = re.compile(
    r"(?<![A-Za-z0-9])(?:secret[_ -]?key|client[_ -]?secret|auth[_ -]?token|access[_ -]?key|private[_ -]?key|api[_ -]?key|apikey"
    r"|password|passwd|pass|pwd|secret|token)(?![A-Za-z0-9])[\"']?[ \t]{0,3}[:=][ \t]{0,3}[\"']?([^\s\"'`,;]{12,128})",
    re.IGNORECASE,
)
_ASSIGN_WORDS = ("pass", "pwd", "secret", "token", "apikey", "api_key", "api-key", "api key", "access", "private")
_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@((?:[A-Za-z0-9-]{1,63}\.){1,5}[A-Za-z]{2,24})(?![A-Za-z0-9-])"
)
_PHONE_INTL = re.compile(r"(?<![\w.+])\+[0-9][0-9 ()\-.]{6,22}[0-9](?!\w)")
_PHONE_GROUPED = re.compile(r"(?<![\w.+\-])(?:\([0-9]{3}\)[ .\-]?|[0-9]{3}[ .\-])[0-9]{3}[ .\-][0-9]{4}(?![\w\-])")
_CARD = re.compile(
    r"(?<![\w.\-])(?:[0-9]{13,19}|[0-9]{4}([ \-])[0-9]{4}\1[0-9]{4}\1[0-9]{1,7}|[0-9]{4}([ \-])[0-9]{6}\2[0-9]{5})(?![\w\-])"
)
_IBAN = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}[0-9]{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?(?![A-Za-z0-9])")

_IBAN_COUNTRIES = frozenset(
    "AD AE AL AT AZ BA BE BG BH BR BY CH CR CY CZ DE DK DO EE EG ES FI FO FR GB GE GI GL GR GT HR HU IE IL IQ IS IT JO KW KZ LB LC "
    "LI LT LU LV MC MD ME MK MR MT MU NL NO PK PL PS PT QA RO RS SA SC SE SI SK SM ST SV TL TN TR UA VA VG XK".split()
)
_RESERVED_DOMAIN_SUFFIXES = (".example", ".invalid", ".test", ".localhost", ".local")
_RESERVED_DOMAINS = ("example.com", "example.org", "example.net", "localhost")
# A value that contains one of these is labelling itself as a stand-in. The cost, stated plainly: a REAL password that happens to
# contain "test", "demo", "fake" or "secret" is missed by the generic-assignment rule (the token-format rules and the
# configured-credential rule are unaffected). A random token containing one of them by chance is vanishingly unlikely.
_PLACEHOLDER_WORDS = (
    "example", "changeme", "change-me", "change_me", "your", "placeholder", "redacted", "dummy", "sample", "xxxx", "****", "....",
    "todo", "<", ">", "${", "{{", "%(", "insert", "replace", "test", "fake", "demo", "secret",
)
_PLACEHOLDER_EXACT = frozenset({
    "password", "passwd", "pass", "pwd", "secret", "token", "user", "username", "admin", "test", "null", "none", "string",
})
_CODE_CHARS = frozenset("()[]{}<>$%")
_ID_LIKE = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,}")


def _entropy(text: str) -> float:
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in Counter(text).values()) if n else 0.0


def _is_placeholder(value: str) -> bool:
    low = value.lower()
    if low in _PLACEHOLDER_EXACT or len(set(low)) <= 2 or low.startswith(("$", "%")):
        return True
    return any(word in low for word in _PLACEHOLDER_WORDS)


def _looks_like_secret_value(value: str) -> bool:
    """Is this the value of a 'password = ...' line a real-looking secret and not a word, a placeholder or code?"""
    value = value.rstrip(".")
    if len(value) < 12 or _is_placeholder(value) or "://" in value or _ID_LIKE.fullmatch(value):
        return False
    if any(c in _CODE_CHARS for c in value):
        return False
    kinds = sum((
        any(c.islower() for c in value), any(c.isupper() for c in value), any(c.isdigit() for c in value),
        any(not c.isalnum() for c in value),
    ))
    if kinds < 2:
        return False
    if not any(c.isdigit() for c in value) and len(value) < 24:
        return False        # a long run of letters and symbols with no digit is usually a name or a code identifier
    return _entropy(value) >= 3.0


def _luhn(digits: str) -> bool:
    total, flip = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if flip:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        flip = not flip
    return total % 10 == 0


def _iban_ok(compact: str) -> bool:
    if not (15 <= len(compact) <= 34) or compact[:2] not in _IBAN_COUNTRIES:
        return False
    rearranged = compact[4:] + compact[:4]
    number = "".join(str(int(c, 36)) for c in rearranged)
    return int(number) % 97 == 1


def _card_ok(text: str) -> bool:
    digits = "".join(c for c in text if c.isdigit())
    # A run of one repeated digit is not a card. (Two distinct digits is fine: the best-known test card, 4111 1111 1111 1111, has two.)
    return 13 <= len(digits) <= 19 and digits[0] in "3456" and len(set(digits)) > 1 and _luhn(digits)


_GIT_USERS = ("git@", "ssh@", "hg@")


def _is_git_remote(text: str, m: re.Match) -> bool:
    """`git@github.com:org/repo.git` and `ssh://git@host/...` are repository addresses, not people."""
    local = m.group(0).split("@", 1)[0].lower()
    before = text[max(0, m.start() - 8):m.start()]
    return f"{local}@" in _GIT_USERS and (before.endswith("://") or text[m.end():m.end() + 1] == ":" or ".git" in text[m.end():m.end() + 80])


def _reserved_domain(domain: str) -> bool:
    low = domain.lower()
    return low in _RESERVED_DOMAINS or low.endswith(_RESERVED_DOMAIN_SUFFIXES) or any(low.endswith("." + d) for d in _RESERVED_DOMAINS)


def _heading_text(line: str) -> str | None:
    """The text of a Markdown heading line ('## Scope'), or None. String operations only, so it is linear."""
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3 or not stripped.startswith("#"):
        return None
    hashes = len(stripped) - len(stripped.lstrip("#"))
    rest = stripped[hashes:]
    if hashes > 6 or not rest or rest[0] not in " \t":
        return None
    return rest.strip().rstrip("#").strip() or None


Span = tuple[int, int, str]   # start, end, rule


class Scanner:
    """Scans text with the rules that are switched on. Holds no state between scans, so one scanner can be shared."""

    def __init__(self, secrets: Callable[[], Iterable[str]] | Iterable[str] = (), disabled: Iterable[str] = ()):
        self._secrets = secrets if callable(secrets) else (lambda s=tuple(secrets): s)
        self.disabled = parse_disabled(disabled) if not isinstance(disabled, frozenset) else disabled

    @classmethod
    def from_settings(cls, settings) -> "Scanner":
        return cls(settings.secret_values, settings.guardrails_disabled)

    def active_rules(self, only: Collection[str] | None = None) -> list[Rule]:
        return [r for r in RULES if r.name not in self.disabled and (only is None or r.name in only)]

    # ---- the public questions ----------------------------------------------------------------------------------------

    def scan(self, text: str, *, only: Collection[str] | None = None) -> list[Finding]:
        """Every finding in `text`, in order of position, at most MAX_FINDINGS."""
        if not isinstance(text, str) or not text:
            return []
        names = {r.name for r in self.active_rules(only)}
        if not names:
            return []
        spans = _resolve(self._matches(text, names))
        spans = _merge_overlaps(sorted(spans))
        return _findings(text, spans[:MAX_FINDINGS])

    def scan_sections(self, sections: Sequence[tuple[str, str]], *, only: Collection[str] | None = None) -> list[Finding]:
        """Scan (heading, text) sections of a document. Lines are numbered across the whole document, headings are the given ones."""
        out: list[Finding] = []
        offset = 0
        for heading, text in sections:
            clean = _clean_heading(heading, self)
            for f in self.scan(text, only=only):
                out.append(Finding(f.rule, f.klass, f.line + offset, clean, f.length))
                if len(out) >= MAX_FINDINGS:
                    return out
            offset += text.count("\n") + 1
        return out

    def problems(self, text: str) -> list[str]:
        """Plain sentences about every SECRET in `text`, for a repair message or a refused edit. Personal data is not a problem."""
        return [describe(f) for f in self.scan(text) if f.klass == SECRET]

    def secret_rules_found(self, text: str) -> list[str]:
        """The distinct secret rules that match `text`, in order of first appearance (no lines: used for text that has none)."""
        seen: dict[str, None] = {}
        for f in self.scan(text):
            if f.klass == SECRET:
                seen.setdefault(f.rule)
        return list(seen)

    # ---- matching -------------------------------------------------------------------------------------------------------

    def _matches(self, text: str, names: set[str]) -> list[Span]:
        out: list[Span] = []
        limit = MAX_FINDINGS * 4

        def collect(rule: str, regex: re.Pattern, *, gate: bool = True, accept=None, group: int = 0) -> None:
            if rule not in names or not gate:
                return
            for m in regex.finditer(text):
                if len(out) >= limit:
                    return
                if accept is not None and not accept(m):
                    continue
                out.append((m.start(group), m.end(group), rule))

        collect("private_key", _PRIVATE_KEY, gate="PRIVATE KEY" in text)
        collect("aws_key_id", _AWS, gate="AKIA" in text or "ASIA" in text)
        collect("github_token", _GITHUB, gate="gh" in text)
        collect("slack_token", _SLACK, gate="xox" in text)
        collect("stripe_key", _STRIPE, gate="_live_" in text)
        collect("google_api_key", _GOOGLE, gate="AIza" in text)
        collect("jwt", _JWT, gate="eyJ" in text)
        if "configured_credential" in names:
            self._configured(text, out, limit)
        if "url_password" in names and "://" in text:
            self._url_passwords(text, out, limit)
        if "credential_assignment" in names:
            low = text.lower()
            if any(w in low for w in _ASSIGN_WORDS):
                collect("credential_assignment", _ASSIGN, accept=lambda m: _looks_like_secret_value(m.group(1)), group=1)
        collect("email", _EMAIL, gate="@" in text, accept=lambda m: not _reserved_domain(m.group(1)) and not _is_git_remote(text, m))
        if "phone" in names and ("+" in text or "(" in text or "-" in text or "." in text or " " in text):
            collect("phone", _PHONE_INTL, gate="+" in text, accept=lambda m: 8 <= sum(c.isdigit() for c in m.group(0)) <= 15)
            collect("phone", _PHONE_GROUPED)
        collect("payment_card", _CARD, accept=lambda m: _card_ok(m.group(0)))
        collect("iban", _IBAN, accept=lambda m: _iban_ok(m.group(0).replace(" ", "")))
        return out

    def _configured(self, text: str, out: list[Span], limit: int) -> None:
        folded: str | None = None
        for secret in dict.fromkeys(s.strip() for s in self._secrets() if s and s.strip()):
            if len(secret) < MIN_SECRET_CHARS:
                continue
            haystack, needle = text, secret
            if secret.lower().startswith(("http://", "https://")):   # a host name is not case-sensitive
                folded = folded if folded is not None else text.lower()
                haystack, needle = folded, secret.lower()
            at = haystack.find(needle)
            while at != -1 and len(out) < limit:
                out.append((at, at + len(needle), "configured_credential"))
                at = haystack.find(needle, at + len(needle))

    @staticmethod
    def _url_passwords(text: str, out: list[Span], limit: int) -> None:
        at = text.find("://")
        while at != -1 and len(out) < limit:
            if at > 0 and text[at - 1].isalnum():
                start = at + 3
                m = _URL_USERINFO.match(text[start:start + 300])
                if m and not _placeholder_password(m.group(2)):
                    out.append((start, start + m.end(), "url_password"))
            at = text.find("://", at + 3)


def _placeholder_password(value: str) -> bool:
    low = value.lower()
    return _is_placeholder(value) or low in _PLACEHOLDER_EXACT or low.startswith(("$", "{", "<", "%")) or len(value) < 3


def _merge_overlaps(spans: list[Span]) -> list[Span]:
    """Two matches of the SAME rule that overlap are one finding (a number matched by two phone patterns)."""
    out: list[Span] = []
    for span in spans:
        if out and out[-1][2] == span[2] and span[0] < out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], span[1]), span[2])
        else:
            out.append(span)
    return out


def _resolve(spans: list[Span]) -> list[Span]:
    """A weaker finding inside a stronger one is dropped: an email inside a URL password, an assignment around a known token."""
    secrets = [s for s in spans if BY_NAME[s[2]].klass == SECRET and s[2] != "credential_assignment"]
    keep: list[Span] = []
    seen: set[Span] = set()
    for span in spans:
        if span in seen:
            continue
        seen.add(span)
        rule = span[2]
        weaker = rule == "credential_assignment" or BY_NAME[rule].klass == PERSONAL
        if weaker and any(o is not span and o[0] < span[1] and span[0] < o[1] for o in secrets):
            continue
        keep.append(span)
    return keep


def _clean_heading(heading: str, scanner: "Scanner") -> str:
    heading = (heading or "").strip()
    if not heading:
        return ""
    return HEADING_REMOVED if scanner.scan(heading) else heading[:MAX_HEADING_CHARS]


def _findings(text: str, spans: list[Span]) -> list[Finding]:
    if not spans:
        return []
    lines = text.split("\n")
    starts = list(accumulate((len(l) + 1 for l in lines), initial=0))
    located = [(bisect_right(starts, s), e - s, r) for s, e, r in spans]
    on_finding_line = {line for line, _, _ in located}
    heading, cursor = "", 1
    out: list[Finding] = []
    for line, length, rule in located:
        while cursor < line:                         # headings strictly BEFORE this line
            title = _heading_text(lines[cursor - 1])
            if title is not None:
                heading = HEADING_REMOVED if cursor in on_finding_line else title[:MAX_HEADING_CHARS]
            cursor += 1
        out.append(Finding(rule, BY_NAME[rule].klass, line, heading, length))
    return out
