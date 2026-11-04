"""S20a: reading a FastAPI project's routes, models and tables from source text. Nothing is imported or run; every project is a string."""
from __future__ import annotations

from app.verify.readers import python_fastapi as P


def read(**files):
    return P.read_backend([(name.replace("__", "/").replace("_py", ".py").replace("_sql", ".sql"), text) for name, text in files.items()])


def routes(backend):
    return [(r.method, r.path) for r in backend.routes]


APP = '''
from fastapi import FastAPI
app = FastAPI()
@app.get("/api/rooms")
def list_rooms(): ...
@app.post("/api/reservations", status_code=201)
async def make(): ...
@app.put("/api/rooms/{room_id}")
def rename(room_id: int): ...
@app.patch("/api/rooms/{room_id}")
def tweak(room_id: int): ...
@app.delete("/api/reservations/{reservation_id}", status_code=204)
def cancel(reservation_id: int): ...
'''


# ---- routes ---------------------------------------------------------------------------------------------------------------------------------------------

def test_every_method_on_the_app_is_found_with_its_path_and_function_and_line():
    b = read(app_py=APP)
    assert routes(b) == [("GET", "/api/rooms"), ("PATCH", "/api/rooms/{room_id}"), ("PUT", "/api/rooms/{room_id}"), ("POST", "/api/reservations"), ("DELETE", "/api/reservations/{reservation_id}")] \
        or sorted(routes(b)) == sorted([("GET", "/api/rooms"), ("PATCH", "/api/rooms/{room_id}"), ("PUT", "/api/rooms/{room_id}"), ("POST", "/api/reservations"), ("DELETE", "/api/reservations/{reservation_id}")])
    first = next(r for r in b.routes if r.function == "list_rooms")
    assert (first.file, first.line, first.own_path) == ("app.py", 4, "/api/rooms")


def test_the_success_code_is_the_one_written_and_200_when_none_is():
    b = read(app_py=APP)
    codes = {r.function: r.status_codes for r in b.routes}
    assert codes["make"] == (201,) and codes["cancel"] == (204,) and codes["list_rooms"] == (200,)


def test_a_router_prefix_and_the_prefix_where_it_is_attached_are_both_added():
    b = read(app_py='''
from fastapi import APIRouter, FastAPI
app = FastAPI()
router = APIRouter(prefix="/rooms")
@router.get("/{room_id}")
def one(room_id: int): ...
@router.get("")
def many(): ...
app.include_router(router, prefix="/api")
''')
    assert sorted(routes(b)) == [("GET", "/api/rooms"), ("GET", "/api/rooms/{room_id}")]


def test_a_router_in_one_file_attached_in_another_gets_the_prefix_of_the_attaching_file():
    b = read(rooms_py='''
from fastapi import APIRouter
router = APIRouter()
@router.get("/rooms")
def many(): ...
''', main_py='''
from fastapi import FastAPI
from rooms import router
app = FastAPI()
app.include_router(router, prefix="/api/v1")
''')
    assert routes(b) == [("GET", "/api/v1/rooms")]


def test_a_router_attached_twice_gives_a_route_for_each_prefix():
    b = read(app_py='''
from fastapi import APIRouter, FastAPI
app = FastAPI()
r = APIRouter()
@r.get("/ping")
def ping(): ...
app.include_router(r, prefix="/a")
app.include_router(r, prefix="/b")
''')
    assert sorted(routes(b)) == [("GET", "/a/ping"), ("GET", "/b/ping")]


def test_api_route_with_several_methods_gives_one_route_per_method():
    b = read(app_py='''
from fastapi import FastAPI
app = FastAPI()
@app.api_route("/thing", methods=["GET", "POST"])
def thing(): ...
''')
    assert sorted(routes(b)) == [("GET", "/thing"), ("POST", "/thing")]


def test_a_prefix_built_in_code_is_flagged_as_unknown_and_the_route_is_still_listed():
    b = read(app_py='''
from fastapi import APIRouter
router = APIRouter(prefix=BASE + "/x")
@router.get("/y")
def y(): ...
''')
    assert routes(b) == [("GET", "/y")] and b.routes[0].prefix_unknown is True


def test_path_parameters_come_first_then_query_parameters_and_injected_arguments_are_left_out():
    b = read(app_py='''
from fastapi import APIRouter, Depends, Request
router = APIRouter()
@router.get("/rooms/{room_id}")
async def one(request: Request, room_id: int, floor: int = 0, db=Depends(get_db), user: User = Depends(current_user)): ...
''')
    assert b.routes[0].params == ("room_id", "floor")


def test_a_body_model_and_a_response_model_are_named():
    b = read(app_py='''
from fastapi import APIRouter
from pydantic import BaseModel
router = APIRouter()
class Booking(BaseModel):
    room_id: int
@router.post("/b", response_model=Booking)
def make(body: Booking): ...
@router.post("/many")
def many(items: list[Booking]): ...
''')
    by = {r.function: r for r in b.routes}
    assert (by["make"].body_model, by["make"].response_model) == ("Booking", "Booking") and by["many"].body_model == "Booking"


def test_error_codes_raised_inside_a_function_are_collected_by_number_and_by_name():
    b = read(app_py='''
from fastapi import APIRouter, HTTPException, status
router = APIRouter()
@router.post("/r", status_code=201)
def r():
    if a: raise HTTPException(status_code=409, detail="x")
    if b: raise HTTPException(404)
    if c: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
''')
    assert b.routes[0].status_codes == (201, 404, 409, 422)


def test_a_function_with_no_route_decorator_and_a_decorator_that_is_not_a_route_are_ignored():
    b = read(app_py='''
import functools
def helper(): ...
@functools.lru_cache(maxsize=1)
def cached(): ...
@app.middleware("http")
async def mw(request, call_next): ...
''')
    assert b.routes == []


def test_a_file_with_a_syntax_error_is_reported_and_the_others_are_still_read():
    b = read(bad_py="def broken(:\n", good_py='''
from fastapi import FastAPI
app = FastAPI()
@app.get("/ok")
def ok(): ...
''')
    assert routes(b) == [("GET", "/ok")] and len(b.problems) == 1 and b.problems[0].startswith("bad.py: could not be read as Python")
    assert b.files_read == 1


def test_routes_come_out_in_one_stable_order_whatever_order_the_files_arrive_in():
    one = '@app.get("/a")\ndef a(): ...\n'
    two = '@app.get("/b")\ndef b(): ...\n'
    forward = P.read_backend([("one.py", one), ("two.py", two)])
    backward = P.read_backend([("two.py", two), ("one.py", one)])
    assert [(r.method, r.path) for r in forward.routes] == [(r.method, r.path) for r in backward.routes]


def test_nothing_in_the_source_is_run_or_imported():
    b = read(app_py='''
import os
os.system("echo this must never run")
raise SystemExit("never")
@app.get("/x")
def x(): ...
''')
    assert routes(b) == [("GET", "/x")]


# ---- models ---------------------------------------------------------------------------------------------------------------------------------------------

def test_model_fields_are_named_with_their_types_and_optional_ones_are_marked():
    b = read(models_py='''
from typing import Optional
from pydantic import BaseModel, Field
class Booking(BaseModel):
    room_id: int
    note: Optional[str] = None
    floor: int | None = None
    title: str = "x"
    start_time: str = Field(...)
    end_time: str = Field(default="09:00")
    _private: int = 0
    tags: list[str] = Field(default_factory=list)
    must: str = Field(..., description='x')
    given: str = Field('x')
    open_default: str = Field(default=...)
''')
    fields = {f.name: f for f in b.models["Booking"].fields}
    assert list(fields) == ["room_id", "note", "floor", "title", "start_time", "end_time", "tags", "must", "given", "open_default"]
    assert [fields[n].optional for n in fields] == [False, True, True, True, False, True, True, False, True, False]
    assert fields["room_id"].type == "int"


def test_a_model_inherits_the_fields_of_the_model_it_extends_even_when_it_is_defined_first_or_elsewhere():
    b = read(a_py="from pydantic import BaseModel\nclass Base(BaseModel):\n    id: int\n", b_py="from a import Base\nclass Child(Base):\n    name: str\nclass Grand(Child):\n    extra: str\n")
    assert [f.name for f in b.models["Child"].fields] == ["id", "name"] and [f.name for f in b.models["Grand"].fields] == ["id", "name", "extra"]


def test_a_class_that_is_not_a_model_is_not_listed_and_a_cycle_does_not_hang():
    b = read(a_py="class Plain:\n    x: int\nfrom pydantic import BaseModel\nclass A(B):\n    a: int\nclass B(A):\n    b: int\nclass Ok(BaseModel):\n    z: int\n")
    assert list(b.models) == ["Ok"]


# ---- tables ---------------------------------------------------------------------------------------------------------------------------------------------

def test_orm_tables_give_the_table_name_and_the_column_names():
    b = read(db_py='''
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True)
    name = Column(String)
class Booking(Base):
    __tablename__ = "reservations"
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column()
''')
    assert [(t.name, t.columns, t.source) for t in b.tables] == [("rooms", ("id", "name"), "orm"), ("reservations", ("id", "room_id"), "orm")]


def test_create_table_text_in_a_sql_file_and_in_a_python_string_gives_tables_and_columns():
    sql = "CREATE TABLE IF NOT EXISTS rooms (\n  id INTEGER PRIMARY KEY,\n  name TEXT NOT NULL,\n  capacity INTEGER DEFAULT (4),\n  UNIQUE (name)\n);\nCREATE TABLE `reservations` (id INT, room_id INT, FOREIGN KEY (room_id) REFERENCES rooms(id));"
    b = read(schema_sql=sql, db_py=f'SCHEMA = """\n{sql.splitlines()[0]}\n  id INTEGER,\n  title TEXT\n);\n"""\n')
    by = {(t.file, t.name): t for t in b.tables}
    assert by[("schema.sql", "rooms")].columns == ("id", "name", "capacity") and by[("schema.sql", "reservations")].columns == ("id", "room_id")
    assert by[("db.py", "rooms")].columns == ("id", "title") and all(t.source == "sql" for t in b.tables)


def test_a_project_with_nothing_to_find_gives_empty_lists_and_no_error():
    b = read(readme_py="print('hello')\n")
    assert (b.routes, b.models, b.tables, b.problems) == ([], {}, [], []) and b.files_read == 1


# ---- the edges (S20a mutation survivors) ---------------------------------------------------------------------------------------------------------------

def test_a_route_on_an_app_made_in_another_file_has_no_prefix_and_is_not_flagged_as_unknown():
    b = read(routes_py='''
from main import app
@app.get("/api/rooms")
def rooms(): ...
''')
    assert routes(b) == [("GET", "/api/rooms")] and b.routes[0].prefix_unknown is False


def test_api_route_with_no_methods_is_a_get_and_a_path_given_by_keyword_is_read():
    b = read(app_py='''
from fastapi import FastAPI
app = FastAPI()
@app.api_route("/plain")
def plain(): ...
@app.get(path="/by-keyword")
def kw(): ...
''')
    assert sorted(routes(b)) == [("GET", "/by-keyword"), ("GET", "/plain")]


def test_a_router_attached_by_a_dotted_name_in_another_file_still_gets_its_prefix():
    b = read(rooms_py='''
from fastapi import APIRouter
router = APIRouter()
@router.get("/rooms")
def many(): ...
''', main_py='''
from fastapi import FastAPI
import rooms
app = FastAPI()
app.include_router(rooms.router, prefix="/api")
''')
    assert routes(b) == [("GET", "/api/rooms")]


def test_a_typed_path_parameter_is_named_and_comes_first():
    b = read(app_py='''
from fastapi import FastAPI
app = FastAPI()
@app.get("/files/{file_path:path}/{version}")
def f(version: int, file_path: str, q: str = ""): ...
''')
    assert b.routes[0].params == ("file_path", "version", "q")                     # both path parameters first, in name order, then the query one


def test_a_path_parameter_the_function_does_not_declare_is_still_listed():
    b = read(app_py='''
from fastapi import FastAPI
app = FastAPI()
@app.get("/rooms/{room_id}")
def f(): ...
''')
    assert b.routes[0].params == ("room_id",)


def test_a_request_a_session_and_every_kind_of_dependency_are_not_parameters_of_the_call():
    b = read(app_py='''
from fastapi import FastAPI, Depends, Security, Request, Response, BackgroundTasks
app = FastAPI()
@app.get("/x")
def a(real: int, req: Request, resp: Response, tasks: BackgroundTasks, db: Session, adb: AsyncSession): ...
@app.get("/y")
def b(real: int, *, dep=Depends(get_db), sec=Security(get_user), other: int = 1): ...
@app.get("/bare")
def bare(real: int, request, response, background_tasks): ...
@app.get("/z")
def c(real: int, user=Security(get_user), db: Session = Depends(get_db)): ...
''')
    got = {r.function: r.params for r in b.routes}
    assert got == {"a": ("real",), "b": ("real", "other"), "c": ("real",), "bare": ("real",)}


def test_a_function_that_takes_two_models_names_the_first_as_the_body():
    b = read(app_py='''
from fastapi import FastAPI
from pydantic import BaseModel
app = FastAPI()
class First(BaseModel):
    a: int
class Second(BaseModel):
    b: int
@app.post("/x")
def x(one: First, two: Second): ...
''')
    assert b.routes[0].body_model == "First"


def test_the_name_of_the_router_is_what_it_was_given_not_the_whole_expression():
    b = read(app_py='''
from fastapi import APIRouter
api = APIRouter(prefix="/v1")
@api.get("/ping")
def ping(): ...
@other.get("/lost")
def lost(): ...
''')
    assert sorted(routes(b)) == [("GET", "/lost"), ("GET", "/v1/ping")]


def test_a_route_on_a_dotted_owner_takes_the_prefix_of_the_router_it_ends_in():
    b = read(app_py='''
from fastapi import APIRouter
router = APIRouter(prefix="/v1")
@api.router.get("/ping")
def ping(): ...
''')
    assert routes(b) == [("GET", "/v1/ping")]


def test_a_syntax_error_names_its_line():
    b = read(bad_py="x = 1\ndef broken(:\n")
    assert b.problems == ["bad.py: could not be read as Python (SyntaxError: line 2)"]


def test_a_model_that_overrides_a_parent_field_has_it_once_in_the_parents_place_order():
    b = read(a_py='''
from pydantic import BaseModel
class Base(BaseModel):
    id: int
    name: str
class Child(Base):
    name: str | None = None
    extra: int = 0
''')
    fields = b.models["Child"].fields
    assert [f.name for f in fields] == ["id", "name", "extra"] and fields[1].optional is True


def test_two_models_that_extend_each_other_do_not_hang_and_are_not_models():
    b = read(a_py="class A(B):\n    x: int\nclass B(A):\n    y: int\n")
    assert b.models == {}


def test_a_model_whose_parent_is_a_model_that_extends_itself_still_ends():
    b = read(a_py="from pydantic import BaseModel\nclass A(BaseModel, A2):\n    x: int\nclass A2(A):\n    y: int\n")
    assert set(b.models) <= {"A", "A2"}


def test_model_config_is_a_setting_and_not_a_field():
    b = read(a_py="from pydantic import BaseModel, ConfigDict\nclass A(BaseModel):\n    model_config: ConfigDict = ConfigDict(extra='forbid')\n    real: int\n")
    assert [f.name for f in b.models["A"].fields] == ["real"]


def test_each_way_of_writing_optional_marks_a_field_optional_and_a_plain_type_is_not():
    b = read(a_py='''
from typing import Optional
from pydantic import BaseModel
class A(BaseModel):
    plain: int
    one: Optional[int]
    two: int | None
    three: None | int
    four: "Optional[int]"
''')
    assert {f.name: f.optional for f in b.models["A"].fields} == {"plain": False, "one": True, "two": True, "three": True, "four": True}


def test_orm_columns_written_with_either_column_style_are_found_and_other_attributes_are_not():
    b = read(db_py='''
from sqlalchemy import Column, String
from sqlalchemy.orm import mapped_column, relationship
class T(Base):
    __tablename__ = "t"
    a = Column(String)
    b = mapped_column(String)
    c: Mapped[int] = mapped_column()
    d = relationship("Other")
    e = 5
''')
    assert b.tables[0].columns == ("a", "b", "c")


def test_a_comma_inside_brackets_does_not_split_a_column():
    b = read(s_sql="CREATE TABLE t (\n  price NUMERIC(10, 2) NOT NULL,\n  score INT DEFAULT (max(lo, hi)),\n  name TEXT\n);")
    assert b.tables[0].columns == ("price", "score", "name")                      # `hi` is inside the brackets of score, not a column


def test_files_that_are_not_python_or_sql_are_not_parsed_and_not_counted():
    b = P.read_backend([("notes.md", "def broken(:"), ("data.json", "{}"), ("ok.py", "x = 1\n")])
    assert b.problems == [] and b.files_read == 1
