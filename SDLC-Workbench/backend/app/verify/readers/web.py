"""Read a Node-style frontend from its source text (S20c). PATTERNS, not a parser: every result says so, and a file the patterns cannot make sense of is reported, not skipped.

What is found:
  * pages: React Router (`<Route path="/rooms" .../>`, `{ path: "/rooms", element: ... }`), Vue router (`{ path: '/rooms', component: ... }`), and file-based pages
    (`pages/rooms/index.tsx`, `app/rooms/page.tsx`, `src/routes/rooms.vue`, `src/pages/Rooms.jsx`) - the page's NAME is its route or its file name;
  * API calls: `fetch("/api/x")`, `axios.get("/api/x")`, `api.post('/x')`, `$fetch`, `http.get`, with the method when it can be read (the `method:` option, or the verb);
  * form fields: `name="..."` on inputs, `<input id="...">`, `register("...")`, `formData.append("...")`.
Comments, test names and messages are returned as text so the rule check (decision 4: weak evidence only) can look for a rule's ID or its words.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CODE_SUFFIXES = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte", ".html", ".htm")
PAGE_FOLDERS = ("pages", "views", "screens", "routes", "app")
NOT_PAGES = frozenset({"_app", "_document", "layout", "loading", "error", "not-found", "404", "index", "main", "app", "api"})

_ROUTE_JSX = re.compile(r"""<Route\b[^>]*?\bpath\s*=\s*["'{`]+\s*["'`]?([^"'`}]+)["'`]?""")
_ROUTE_OBJ = re.compile(r"""\bpath\s*:\s*["'`]([^"'`]*)["'`]\s*,\s*(?:element|component|Component|lazy|children|name|redirect|loader)""")
_VERBS = r"(?:get|post|put|patch|delete|head|options)"
_CALL = re.compile(rf"""(?<![A-Za-z0-9_$])(?:(?:axios|api|http|client|request|\$http|\$fetch|ky|got|superagent)\s*\.\s*({_VERBS})|(fetch|\$fetch|axios|ky))\s*\(\s*(?:`([^`]*)`|"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_METHOD_OPT = re.compile(r"""\bmethod\s*:\s*["'`](GET|POST|PUT|PATCH|DELETE)["'`]""", re.IGNORECASE)
_FIELD_NAME = re.compile(r"""<(?:input|select|textarea|Field|TextField|Input)\b[^>]*?\bname\s*=\s*["'{`]+([A-Za-z_][A-Za-z0-9_.\-]*)""")
_FIELD_REGISTER = re.compile(r"""\b(?:register|setFieldValue|formData\.append|form\.append|useField|v-model)\s*\(?\s*["'`]([A-Za-z_][A-Za-z0-9_.\-]*)["'`]""")
_COMMENT_LINE = re.compile(r"(?:^|[\s;,{}()])//[ \t]?(.*)$", re.MULTILINE)          # [ \t], not \s: an empty comment must not swallow the line break
_COMMENT_BLOCK = re.compile(r"/\*(?:\*(?!/))*(.*?)\*+/", re.DOTALL)          # `/**/` is an empty comment, not the start of a longer one
_COMMENT_HTML = re.compile(r"<!--(.*?)-->", re.DOTALL)
_TEST_NAME = re.compile(r"""\b(?:it|test|describe|specify)(?:\.each)?\s*\(\s*(?:`([^`]*)`|"([^"]*)"|'([^']*)')""")
_TEMPLATE = re.compile(r"\$\{[^}]*\}")


@dataclass(frozen=True)
class Page:
    name: str               # the route (`/rooms/:id`) or the file-based name (`rooms`)
    file: str
    line: int
    kind: str               # "route" | "file"


@dataclass(frozen=True)
class Call:
    method: str             # "" when it could not be read
    path: str               # as written, with `${...}` turned into `{}`
    file: str
    line: int


@dataclass
class Frontend:
    pages: list[Page] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    fields: dict[str, list[str]] = field(default_factory=dict)         # file -> form field names
    texts: list[tuple[str, str]] = field(default_factory=list)         # (file, a comment, a test name) for the rule check
    notes: list[str] = field(default_factory=list)
    files_read: int = 0

    def calls_by_file(self) -> dict[str, frozenset[str]]:
        out: dict[str, set[str]] = {}
        for c in self.calls:
            out.setdefault(c.file, set()).add(c.path)
        return {k: frozenset(v) for k, v in out.items()}


def _line(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _clean(path: str) -> str:
    return _TEMPLATE.sub("{}", path).strip()


def file_page_name(rel: str) -> str | None:
    """The page a file-based router would make of this file, or None when the file is not a page. `pages/rooms/index.tsx` and `app/rooms/page.tsx` are `rooms`."""
    parts = rel.replace("\\", "/").split("/")
    folder_at = next((i for i, p in enumerate(parts[:-1]) if p in PAGE_FOLDERS), None)
    if folder_at is None:
        return None
    inner = parts[folder_at + 1:]
    stem = inner[-1].rsplit(".", 1)[0]
    if "." not in inner[-1] or "." + inner[-1].rsplit(".", 1)[1] not in CODE_SUFFIXES or parts[folder_at] == "app" and stem != "page":
        return None
    if ".test" in inner[-1] or ".spec" in inner[-1] or stem.startswith("_") or inner[0] == "api":
        return None
    names = [p for p in inner[:-1]]
    if stem not in ("index", "page") and stem not in NOT_PAGES:
        names.append(stem)
    elif stem in NOT_PAGES and stem not in ("index", "page"):
        return None
    name = "/".join(re.sub(r"^\[(?:\.\.\.)?(.+)\]$", r":\1", n) for n in names if not (n.startswith("(") and n.endswith(")")))
    return name or "home"


def _call_arguments(text: str, start: int, limit: int = 400) -> str:
    """What follows the path inside this call's own brackets (the options object), and no further: the next call's options are not this call's."""
    depth, i = 1, start
    while i < len(text) and i < start + limit and depth:
        depth += {"(": 1, ")": -1}.get(text[i], 0)
        i += 1
    return text[start: i]


def read_frontend(files: list[tuple[str, str]]) -> Frontend:
    result = Frontend()
    for rel, text in files:
        if not rel.lower().endswith(CODE_SUFFIXES):
            continue
        result.files_read += 1
        name = file_page_name(rel)
        if name is not None:
            result.pages.append(Page(name, rel, 1, "file"))
        for rx in (_ROUTE_JSX, _ROUTE_OBJ):
            for m in rx.finditer(text):
                route = m.group(1).strip()
                if route and route != "*":
                    result.pages.append(Page(route, rel, _line(text, m.start()), "route"))
        for m in _CALL.finditer(text):
            verb, bare, a, b, c = m.groups()
            path = _clean(a if a is not None else b if b is not None else c or "")
            if not path.startswith(("/", "http")) or path in ("/",):
                continue
            method = (verb or "").upper()
            if not method:
                opt = _METHOD_OPT.search(_call_arguments(text, m.end()))
                method = opt.group(1).upper() if opt else ("GET" if (bare or "").lower() in ("fetch", "$fetch", "ky") else "")
            result.calls.append(Call(method, path, rel, _line(text, m.start())))
        names = list(dict.fromkeys([*_FIELD_NAME.findall(text), *_FIELD_REGISTER.findall(text)]))
        if names:
            result.fields[rel] = names
        for rx in (_COMMENT_LINE, _COMMENT_BLOCK, _COMMENT_HTML):
            for m in rx.finditer(text):
                if m.group(1).strip():
                    result.texts.append((rel, m.group(1).strip()))
        for m in _TEST_NAME.finditer(text):
            result.texts.append((rel, next(g for g in m.groups() if g is not None)))
    if result.files_read and not result.pages and not result.calls:
        result.notes.append("no page route or API call was recognised; this version reads React Router, Vue router, file-based pages and fetch/axios calls by pattern")
    result.pages = sorted(set(result.pages), key=lambda p: (p.name, p.file, p.line))
    result.calls = sorted(set(result.calls), key=lambda c: (c.path, c.method, c.file, c.line))
    return result
