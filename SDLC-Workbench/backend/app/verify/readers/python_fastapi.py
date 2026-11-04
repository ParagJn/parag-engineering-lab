"""Read a FastAPI project's routes, models and tables from its source text (S20a). Uses Python's `ast` only: nothing is imported, run or evaluated.

What is found:
  * routes: `@app.get("/x")`, `@router.post("/y", status_code=201)`, `@app.api_route(..., methods=[...])`, with the prefix of the router (`APIRouter(prefix=...)`)
    and the prefix given where it is attached (`app.include_router(router, prefix=...)`), the parameters of the function and the models it takes and returns;
  * models: classes that inherit `BaseModel` (directly or through another model in the project): field names, types and whether each is optional;
  * status codes: `status_code=` on the route, and `HTTPException(status_code=N)` or `status.HTTP_NNN_...` inside the function;
  * tables: `__tablename__` on SQLAlchemy classes (their `Column(...)` / `mapped_column(...)` names) and `CREATE TABLE` text in `.sql` files and strings.
A file that cannot be parsed is reported for that file; the others are still read. A value the reader cannot work out (a prefix built in code) is left blank and said so.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
_STATUS_NAME = re.compile(r"HTTP_(\d{3})_")
_CREATE = re.compile(r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?([A-Za-z_][A-Za-z0-9_]*)[`"\]]?\s*\(""", re.IGNORECASE)


@dataclass(frozen=True)
class Field:
    name: str
    type: str = ""
    optional: bool = False


@dataclass(frozen=True)
class Model:
    name: str
    fields: tuple[Field, ...]
    file: str
    line: int


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[str, ...]
    file: str
    line: int
    source: str = "orm"            # "orm" or "sql"


@dataclass(frozen=True)
class Route:
    method: str
    path: str                      # the full path, with the router prefixes
    own_path: str                  # as written on the decorator
    function: str
    file: str
    line: int
    params: tuple[str, ...] = ()           # path and query parameters (function arguments that are not models or injected)
    body_model: str = ""
    response_model: str = ""
    status_codes: tuple[int, ...] = ()     # the success code and every code raised inside
    prefix_unknown: bool = False


@dataclass
class Backend:
    routes: list[Route] = field(default_factory=list)
    models: dict[str, Model] = field(default_factory=dict)
    tables: list[Table] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    files_read: int = 0
    texts: list[tuple[str, str]] = field(default_factory=list)         # (file, a comment, docstring, test name or message) for the rule check


# ---- small helpers over the syntax tree ----------------------------------------------------------------------------------------------------------------

def _text(node: ast.AST | None) -> str:
    return ast.unparse(node) if node is not None else ""


def _str(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _int(node: ast.AST | None) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Attribute):
        m = _STATUS_NAME.search(node.attr)
        return int(m.group(1)) if m else None
    return None


def _kw(call: ast.Call, name: str) -> ast.AST | None:
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def _base_names(cls: ast.ClassDef) -> list[str]:
    out = []
    for b in cls.bases:
        out.append(b.attr if isinstance(b, ast.Attribute) else b.id if isinstance(b, ast.Name) else _text(b))
    return out


def _is_optional(annotation: ast.AST | None, default: ast.AST | None) -> bool:
    text = _text(annotation)
    if "Optional[" in text or "| None" in text or "None |" in text:
        return True
    if default is None:
        return False
    if isinstance(default, ast.Call) and _text(default.func).split(".")[-1] == "Field":
        # Field(...) is required; Field(default=X) and Field(default_factory=F) are not, and neither is Field(X) with a real X.
        if default.args:
            return _text(default.args[0]) != "..."
        given = {k.arg: k.value for k in default.keywords}
        if "default_factory" in given:
            return True
        return "default" in given and _text(given["default"]) != "..."
    return True


def _join(*parts: str) -> str:
    """Path pieces joined with single slashes, always starting with one: ('/api', '/rooms/', '') -> '/api/rooms'."""
    return "/" + "/".join(p.strip("/") for p in parts if p.strip("/"))


# ---- reading one file --------------------------------------------------------------------------------------------------------------------------------

class _File:
    def __init__(self, rel: str, tree: ast.Module):
        self.rel, self.tree = rel, tree
        self.routers: dict[str, str | None] = {}          # variable name -> its own prefix (None = built in code)
        self.attached: list[tuple[str, str | None]] = []   # (router variable, prefix given where it is attached)
        self.raw_routes: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, str, str, int]] = []   # (owner variable, function, method, own path, decorator line)

    def scan(self) -> None:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                callee = _text(node.value.func).split(".")[-1]
                if callee in ("APIRouter", "FastAPI"):
                    prefix = _kw(node.value, "prefix")
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.routers[target.id] = "" if prefix is None else _str(prefix)
            elif isinstance(node, ast.Call) and _text(node.func).endswith(".include_router") and node.args:
                router = _text(node.args[0]).split(".")[-1] if isinstance(node.args[0], (ast.Name, ast.Attribute)) else ""
                prefix = _kw(node, "prefix")
                self.attached.append((router, "" if prefix is None else _str(prefix)))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                        continue
                    owner = _text(dec.func.value).split(".")[-1]
                    verb = dec.func.attr.lower()
                    path = _str(dec.args[0]) if dec.args else _str(_kw(dec, "path"))
                    if path is None:
                        continue
                    if verb in METHODS:
                        self.raw_routes.append((owner, node, verb.upper(), path, dec.lineno))
                    elif verb == "api_route":
                        methods = _kw(dec, "methods")
                        names = [m.value.upper() for m in getattr(methods, "elts", []) if isinstance(m, ast.Constant) and isinstance(m.value, str)] or ["GET"]
                        for m in names:
                            self.raw_routes.append((owner, node, m, path, dec.lineno))


def _function_codes(func: ast.FunctionDef | ast.AsyncFunctionDef, decorator: ast.AST | None) -> tuple[int, ...]:
    codes: set[int] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and _text(node.func).split(".")[-1] == "HTTPException":
            code = _int(_kw(node, "status_code")) if _kw(node, "status_code") is not None else (_int(node.args[0]) if node.args else None)
            if code is not None:
                codes.add(code)
    return tuple(sorted(codes))


def _success_code(func: ast.FunctionDef | ast.AsyncFunctionDef, line: int) -> int | None:
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call) and dec.lineno == line:
            return _int(_kw(dec, "status_code"))
    return None


def _decorator_at(func: ast.FunctionDef | ast.AsyncFunctionDef, line: int) -> ast.Call | None:
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call) and dec.lineno == line:
            return dec
    return None


def _depends_names(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Arguments that are filled in by `Depends(...)`, not sent by the caller."""
    names: set[str] = set()
    positional = [*func.args.posonlyargs, *func.args.args]
    for arg, default in zip(reversed(positional), reversed(func.args.defaults)):
        if "Depends(" in _text(default) or "Security(" in _text(default):
            names.add(arg.arg)
    for arg, default in zip(func.args.kwonlyargs, func.args.kw_defaults):
        if default is not None and ("Depends(" in _text(default) or "Security(" in _text(default)):
            names.add(arg.arg)
    return names


_INJECTED = frozenset({"self", "cls", "request", "response", "background_tasks", "websocket"})
_INJECTED_TYPES = frozenset({"Request", "Response", "Session", "AsyncSession", "BackgroundTasks", "WebSocket"})


def _inputs(func: ast.FunctionDef | ast.AsyncFunctionDef, models: set[str]) -> tuple[tuple[str, ...], str]:
    """(the names of the path and query parameters, the body model if there is one). Injected arguments (`Depends`, the request, a session) are left out."""
    params: list[str] = []
    body = ""
    injected = _depends_names(func)
    for a in [*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs]:
        ann = _text(a.annotation)
        outer = re.sub(r"^(?:Optional|List|list|Sequence)\[", "", ann)
        base = re.split(r"[\[\],| ]", outer)[0] if outer else ""
        if a.arg in _INJECTED or a.arg in injected or ann in _INJECTED_TYPES:
            continue
        if base in models:
            body = body or base
        else:
            params.append(a.arg)
    return tuple(params), body


def _models_of(rel: str, tree: ast.Module, known: set[str]) -> dict[str, tuple[Model, list[str]]]:
    """Each model class in a file with the names of its base classes. The fields it inherits are added later, once every model of the project is known."""
    out: dict[str, tuple[Model, list[str]]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = _base_names(node)
        if not any(b == "BaseModel" or b in known for b in bases):
            continue
        fields: list[Field] = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and not item.target.id.startswith("_") and item.target.id != "model_config":
                fields.append(Field(item.target.id, _text(item.annotation), _is_optional(item.annotation, item.value)))
        out[node.name] = (Model(node.name, tuple(fields), rel, node.lineno), bases)
    return out


def _texts_of(rel: str, source: str, tree: ast.Module) -> list[tuple[str, str]]:
    """Comments, docstrings, test function names and the text of a raised error: the places a rule's ID or words may be written."""
    out: list[tuple[str, str]] = []
    for m in re.finditer(r"(?<![\"'])#[ \t]?(.*)$", source, re.MULTILINE):
        if m.group(1).strip():
            out.append((rel, m.group(1).strip()))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            doc = ast.get_docstring(node)
            if doc:
                out.append((rel, " ".join(doc.split())))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                out.append((rel, node.name.replace("_", " ")))
        elif isinstance(node, ast.Call) and _text(node.func).split(".")[-1] == "HTTPException":
            detail = _kw(node, "detail") if _kw(node, "detail") is not None else (node.args[1] if len(node.args) > 1 else None)
            if _str(detail):
                out.append((rel, _str(detail) or ""))
    return out


def _tables_of(rel: str, tree: ast.Module) -> list[Table]:
    out: list[Table] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            name = None
            for item in node.body:
                if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in item.targets):
                    name = _str(item.value)
            if not name:
                continue
            cols: list[str] = []
            for item in node.body:
                if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call) and _text(item.value.func).split(".")[-1] in ("Column", "mapped_column"):
                    cols += [t.id for t in item.targets if isinstance(t, ast.Name)]
                elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and isinstance(item.value, ast.Call) \
                        and _text(item.value.func).split(".")[-1] in ("Column", "mapped_column"):
                    cols.append(item.target.id)
            out.append(Table(name, tuple(cols), rel, node.lineno))
    return out


def tables_from_sql(rel: str, text: str) -> list[Table]:
    """Tables named in `CREATE TABLE` statements: the name and the column names (the first word of each line of the column list)."""
    out: list[Table] = []
    for m in _CREATE.finditer(text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        body = text[m.end(): i - 1]
        cols, level, piece = [], 0, ""
        for ch in body:
            level += {"(": 1, ")": -1}.get(ch, 0)
            if ch == "," and level == 0:
                cols.append(piece)
                piece = ""
            else:
                piece += ch
        cols.append(piece)
        names = []
        for c in cols:
            word = re.match(r"\s*[`\"\[]?([A-Za-z_][A-Za-z0-9_]*)", c)
            if word and word.group(1).upper() not in ("PRIMARY", "FOREIGN", "UNIQUE", "CONSTRAINT", "CHECK", "KEY", "INDEX"):
                names.append(word.group(1))
        out.append(Table(m.group(1), tuple(names), rel, text.count("\n", 0, m.start()) + 1, source="sql"))
    return out


# ---- the whole project ------------------------------------------------------------------------------------------------------------------------------

def read_backend(files: list[tuple[str, str]]) -> Backend:
    """`files` are (relative path, text) pairs, from the safe walk. Returns every route, model and table found, and a sentence for each file that could not be read."""
    result = Backend()
    parsed: list[_File] = []
    trees: list[tuple[str, ast.Module]] = []
    for rel, text in files:
        if rel.endswith(".sql"):
            result.tables += tables_from_sql(rel, text)
            result.files_read += 1
            continue
        if not rel.endswith(".py"):
            continue
        try:
            tree = ast.parse(text, filename=rel)
        except (SyntaxError, ValueError, RecursionError) as exc:
            result.problems.append(f"{rel}: could not be read as Python ({type(exc).__name__}{': line ' + str(exc.lineno) if getattr(exc, 'lineno', None) else ''})")
            continue
        result.files_read += 1
        result.texts += _texts_of(rel, text, tree)
        trees.append((rel, tree))
        f = _File(rel, tree)
        f.scan()
        parsed.append(f)
        result.tables += _tables_of(rel, tree)
        for m in re.finditer(r"""(?:\"\"\"|'''|\"|')([^\"']*CREATE\s+TABLE[^\"']*)""", text, re.IGNORECASE | re.DOTALL):
            result.tables += tables_from_sql(rel, m.group(1))
    # models, in as many rounds as it takes for a model that inherits another model of the project to be recognised
    own: dict[str, tuple[Model, list[str]]] = {}
    known: set[str] = set()
    for _ in range(6):
        before = len(own)
        for rel, tree in trees:
            for name, pair in _models_of(rel, tree, known).items():
                own.setdefault(name, pair)
        known = set(own)
        if len(own) == before:
            break

    def with_inherited(name: str, seen: tuple[str, ...] = ()) -> tuple[Field, ...]:
        model, bases = own[name]
        inherited: list[Field] = []
        for b in bases:
            if b in own and b not in seen and b != name:
                inherited += [f for f in with_inherited(b, (*seen, name)) if f.name not in {x.name for x in inherited}]
        mine = {f.name for f in model.fields}
        return tuple([f for f in inherited if f.name not in mine] + list(model.fields))

    for name, (model, _bases) in own.items():
        result.models[name] = Model(model.name, with_inherited(name), model.file, model.line)
    # prefixes: where each router is attached, anywhere in the project
    attached: dict[str, list[str | None]] = {}
    for f in parsed:
        for router, prefix in f.attached:
            attached.setdefault(router, []).append(prefix)
    model_names = set(result.models)
    for f in parsed:
        for owner, func, method, own_path, line in f.raw_routes:
            own = f.routers[owner] if owner in f.routers else ""          # an owner that is not a router of this file (an app made elsewhere) adds no prefix of its own
            prefixes = attached.get(owner) or [""]
            for outer in prefixes:
                unknown = own is None or outer is None
                full = _join(outer or "", own or "", own_path)
                dec = _decorator_at(func, line)
                success = _int(_kw(dec, "status_code")) if dec is not None else None
                codes = set(_function_codes(func, dec))
                codes.add(success if success is not None else 200)
                params, body = _inputs(func, model_names)
                resp = _text(_kw(dec, "response_model")) if dec is not None and _kw(dec, "response_model") is not None else ""
                path_params = set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::[^}]*)?\}", full))
                result.routes.append(Route(method, full, own_path, func.name, f.rel, line, tuple(dict.fromkeys([*sorted(path_params), *[p for p in params if p not in path_params]])),
                                           body, resp, tuple(sorted(codes)), unknown))
    result.routes.sort(key=lambda r: (r.path, r.method, r.file, r.line))
    return result
