#!/usr/bin/env python3
"""Validate and optionally render a daily news digest.

Reads a JSON list of digest items from stdin (or an object with an "items"
list). Each item has: rank, headline, summary, source, url, published
(ISO-8601 with offset) and an optional label (developing|unconfirmed|updated).

Default mode prints a JSON report:
    {"ok": bool, "count": N, "errors": [...], "warnings": [...]}
and exits 1 when there are errors.

With --render, prints the markdown digest when validation passes. If there
are errors, the JSON report is printed instead and the exit code is 1.

Usage:
    python3 validate_digest.py --date 2025-01-31 --window-hours 36 \
        --tz-offset +09:00 [--expect 10] [--render --scope "Japan" --tz-name JST] < items.json
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, parse_qsl

REQUIRED_FIELDS = ["rank", "headline", "summary", "source", "url", "published"]
ALLOWED_LABELS = {"developing", "unconfirmed", "updated"}
MAX_SUMMARY_WORDS = 60
MAX_SUMMARY_SENTENCES = 2
MAX_PER_OUTLET = 2
MAX_ITEMS = 10
TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ocid", "cmpid", "icid")


def parse_offset(value):
    """Parse '+0900', '+09:00', 'Z' or 'UTC' into a timezone."""
    v = (value or "").strip()
    if v.upper() in ("Z", "UTC", "+0000", "+00:00", "-0000", "-00:00", ""):
        return timezone.utc
    m = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", v)
    if not m:
        raise ValueError("invalid --tz-offset %r (expected e.g. +09:00 or -0500)" % value)
    sign = 1 if m.group(1) == "+" else -1
    delta = timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
    return timezone(sign * delta)


def offset_label(tz):
    off = tz.utcoffset(None)
    if not off:
        return "UTC"
    total = int(off.total_seconds() // 60)
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return "UTC%s%02d:%02d" % (sign, total // 60, total % 60)


def parse_timestamp(value):
    """Return (datetime, is_naive). Raises ValueError if unparseable."""
    s = str(value).strip()
    if not s:
        raise ValueError("empty timestamp")
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    # Normalise offsets without a colon: +0900 -> +09:00
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    # Normalise fractional seconds to 6 digits for older Pythons.
    m = re.match(r"^(.*T\d{2}:\d{2}:\d{2})\.(\d+)(.*)$", s)
    if m:
        s = m.group(1) + "." + (m.group(2) + "000000")[:6] + m.group(3)
    s = s.replace(" ", "T", 1) if "T" not in s and " " in s else s
    dt = datetime.fromisoformat(s)
    return dt, dt.tzinfo is None


def url_key(url):
    parts = urlsplit(url)
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/") or "/"
    return netloc + path


def outlet_key(name):
    n = re.sub(r"\s+", " ", str(name).strip().lower())
    if n.startswith("the "):
        n = n[4:]
    return n


def count_sentences(text):
    t = text.strip()
    if not t:
        return 0
    parts = re.split(r"(?<=[.!?])[\"'\u201d\u2019)]*\s+(?=[A-Z0-9\"'\u201c\u2018(])", t)
    return len([p for p in parts if p.strip()])


def validate(items, args, tz):
    errors = []
    warnings = []

    def err(rank, field, message):
        errors.append({"rank": rank, "field": field, "message": message})

    def warn(rank, field, message):
        warnings.append({"rank": rank, "field": field, "message": message})

    try:
        target = datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        err(None, "date", "invalid --date %r (expected YYYY-MM-DD)" % args.date)
        return errors, warnings, []

    day_start = target.replace(tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    window_start = day_end - timedelta(hours=args.window_hours)

    if not isinstance(items, list):
        err(None, "input", "input must be a JSON list of items (or an object with an 'items' list)")
        return errors, warnings, []

    expect = args.expect
    if len(items) != expect:
        err(None, "count", "expected %d items but got %d; pass --expect N with the real count if fewer "
                           "verifiable stories exist (never pad)" % (expect, len(items)))
    if len(items) > MAX_ITEMS:
        err(None, "count", "at most %d items are allowed" % MAX_ITEMS)

    seen_urls = {}
    outlet_counts = {}
    seen_headlines = {}
    parsed = []

    for idx, item in enumerate(items):
        pos = idx + 1
        if not isinstance(item, dict):
            err(pos, "item", "item %d is not a JSON object" % pos)
            continue
        rank = item.get("rank", pos)

        missing = [f for f in REQUIRED_FIELDS if f not in item or item.get(f) in (None, "")]
        for f in missing:
            if f == "published":
                err(rank, f, "missing publish time; undated items must be dropped")
            else:
                err(rank, f, "missing required field '%s'" % f)

        # Rank order
        if "rank" in item:
            if not isinstance(item["rank"], int) or isinstance(item["rank"], bool):
                err(rank, "rank", "rank must be an integer")
            elif item["rank"] != pos:
                err(rank, "rank", "rank %r is out of order; expected %d (ranks must run 1..N in order)"
                    % (item["rank"], pos))

        # Text fields
        for f in ("headline", "summary", "source"):
            if f in item and item[f] not in (None, "") and not isinstance(item[f], str):
                err(rank, f, "'%s' must be a string" % f)

        headline = item.get("headline") if isinstance(item.get("headline"), str) else ""
        summary = item.get("summary") if isinstance(item.get("summary"), str) else ""
        source = item.get("source") if isinstance(item.get("source"), str) else ""

        if headline:
            hk = re.sub(r"\W+", " ", headline.lower()).strip()
            if hk in seen_headlines:
                err(rank, "headline", "duplicate headline (same as rank %s); merge duplicate events"
                    % seen_headlines[hk])
            else:
                seen_headlines[hk] = rank

        if summary:
            words = len(summary.split())
            if words > MAX_SUMMARY_WORDS:
                err(rank, "summary", "summary has %d words; maximum is %d" % (words, MAX_SUMMARY_WORDS))
            sentences = count_sentences(summary)
            if sentences > MAX_SUMMARY_SENTENCES:
                warn(rank, "summary", "summary appears to have %d sentences; aim for 1–2" % sentences)

        # Label
        label = item.get("label")
        if label not in (None, ""):
            if not isinstance(label, str) or label.lower() not in ALLOWED_LABELS:
                err(rank, "label", "label must be one of %s" % ", ".join(sorted(ALLOWED_LABELS)))

        # URL
        url = item.get("url")
        if isinstance(url, str) and url:
            parts = urlsplit(url.strip())
            if parts.scheme not in ("http", "https") or not parts.netloc:
                err(rank, "url", "url must be an absolute http(s) URL")
            else:
                if parts.scheme == "http":
                    warn(rank, "url", "plain-http link; prefer the https version if it exists")
                qs = [k for k, _ in parse_qsl(parts.query, keep_blank_values=True)]
                if any(k.lower().startswith(TRACKING_PREFIXES) for k in qs):
                    warn(rank, "url", "url contains tracking parameters; use the canonical URL")
                key = url_key(url.strip())
                if key in seen_urls:
                    err(rank, "url", "duplicate URL (same as rank %s, ignoring query string and fragment)"
                        % seen_urls[key])
                else:
                    seen_urls[key] = rank
        elif url not in (None, ""):
            err(rank, "url", "url must be a string")

        # Outlet cap
        if source:
            ok_key = outlet_key(source)
            outlet_counts[ok_key] = outlet_counts.get(ok_key, 0) + 1
            if outlet_counts[ok_key] > MAX_PER_OUTLET:
                err(rank, "source", "outlet cap exceeded: more than %d items from '%s'; find the story in "
                                    "another outlet or use the next candidate" % (MAX_PER_OUTLET, source))

        # Timestamp
        dt = None
        pub = item.get("published")
        if pub not in (None, ""):
            try:
                dt, naive = parse_timestamp(pub)
                if naive:
                    warn(rank, "published", "naive timestamp without offset; assumed %s. Add the offset "
                                            "if known" % offset_label(tz))
                    dt = dt.replace(tzinfo=tz)
                if dt < window_start:
                    err(rank, "published", "stale: published %s is more than %s hours before the end of %s"
                        % (dt.isoformat(), args.window_hours, args.date))
                elif dt >= day_end:
                    err(rank, "published", "published %s is after the end of the target date %s; check the "
                                           "timestamp and offset" % (dt.isoformat(), args.date))
                elif dt < day_start:
                    warn(rank, "published", "published before the target date (%s); include only if there "
                                            "is a new development today" % dt.isoformat())
            except (ValueError, TypeError):
                err(rank, "published", "unparseable timestamp %r; use ISO-8601 with offset" % pub)
                dt = None

        parsed.append({
            "rank": pos,
            "headline": headline.strip(),
            "summary": summary.strip(),
            "source": source.strip(),
            "url": (url or "").strip() if isinstance(url, str) else "",
            "published": dt,
            "label": label.lower() if isinstance(label, str) and label else None,
        })

    return errors, warnings, parsed


def render(parsed, args, tz):
    tz_name = args.tz_name or offset_label(tz)
    n = len(parsed)
    lines = ["# Top %d News — %s — %s" % (n, args.scope, args.date), ""]
    for it in parsed:
        headline = it["headline"]
        if it["label"]:
            headline = "[%s] %s" % (it["label"].capitalize(), headline)
        time_str = it["published"].astimezone(tz).strftime("%H:%M") if it["published"] else "--:--"
        lines.append("%d. **%s**" % (it["rank"], headline))
        lines.append("")
        lines.append("   %s" % it["summary"])
        lines.append("")
        lines.append("   — %s, %s %s · [link](%s)" % (it["source"], time_str, tz_name, it["url"]))
        lines.append("")

    if n < 10:
        lines.append("_Only %d verifiable stories published within the window were found for this scope; "
                     "the list was not padded._" % n)
        lines.append("")

    outlets = []
    seen = set()
    for it in parsed:
        k = outlet_key(it["source"])
        if k not in seen:
            seen.add(k)
            outlets.append(it["source"])
    outlets_sorted = sorted(outlets, key=lambda s: outlet_key(s))
    lines.append(
        "**Sources & method:** Searched the web on %s for %s news; %d stories from %d outlets (%s); "
        "publish times verified within %s hours of the end of %s (%s); ranked by impact, novelty and "
        "breadth of coverage."
        % (args.date, args.scope, n, len(outlets), ", ".join(outlets_sorted), args.window_hours,
           args.date, offset_label(tz))
    )
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Validate and render a daily news digest.")
    ap.add_argument("--date", required=True, help="target date, YYYY-MM-DD")
    ap.add_argument("--window-hours", type=float, default=36,
                    help="accept items published within this many hours before the end of the target date")
    ap.add_argument("--tz-offset", default="+00:00", help="user UTC offset from `date +%%z`, e.g. +09:00")
    ap.add_argument("--tz-name", default=None, help="timezone abbreviation for rendering, e.g. JST")
    ap.add_argument("--expect", type=int, default=10, help="expected number of items (default 10)")
    ap.add_argument("--render", action="store_true", help="print the markdown digest if validation passes")
    ap.add_argument("--scope", default="Global", help="scope shown in the title (default Global)")
    args = ap.parse_args()

    if args.window_hours == int(args.window_hours):
        args.window_hours = int(args.window_hours)

    try:
        tz = parse_offset(args.tz_offset)
    except ValueError as e:
        print(json.dumps({"ok": False, "count": 0,
                          "errors": [{"rank": None, "field": "tz-offset", "message": str(e)}],
                          "warnings": []}, ensure_ascii=False, indent=2))
        return 1

    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "count": 0,
                          "errors": [{"rank": None, "field": "input", "message": "invalid JSON: %s" % e}],
                          "warnings": []}, ensure_ascii=False, indent=2))
        return 1

    if isinstance(data, dict) and isinstance(data.get("items"), list):
        data = data["items"]

    errors, warnings, parsed = validate(data, args, tz)
    ok = not errors
    count = len(data) if isinstance(data, list) else 0

    if args.render and ok:
        sys.stdout.write(render(parsed, args, tz))
        return 0

    print(json.dumps({"ok": ok, "count": count, "errors": errors, "warnings": warnings},
                     ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
