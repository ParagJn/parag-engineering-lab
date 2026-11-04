"""S17a: the Build skills, and the rules for the code inside a Build artefact. No subprocess and no model: only text in, sentences out."""
from __future__ import annotations

import pytest

from app.agents.checks import check_body
from app.agents.skills import SkillLibrary
from app.build import files as F
from app.guardrails.scan import Scanner
from app.llm.routing import Routing
from app.build import legacy

from ._build import DB_FILES, make_body

KEYS = ("database_schema", "backend_code", "frontend_code", "test_suite")


@pytest.fixture(scope="module")
def library():
    return legacy.library()


# ---- the skills ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key, role, prefix, item, covers, upstream", [
    ("database_schema", "database_engineer", "BLD-DB", "DBF", ("TBL",), ("low_level_design", "high_level_design", "functional_requirements")),
    ("backend_code", "backend_developer", "BLD-BE", "BEF", ("API",), ("low_level_design", "high_level_design", "functional_requirements")),
    ("frontend_code", "frontend_developer", "BLD-FE", "FEF", (), ("hifi_wireframes", "user_journey", "low_level_design")),
    ("test_suite", "test_engineer", "BLD-TST", "TSF", (), ("backend_code", "low_level_design", "functional_requirements")),
])
def test_each_build_skill_has_its_role_prefix_items_and_inputs(library, key, role, prefix, item, covers, upstream):
    skill = library.get(key)
    assert (skill.artefact.role, skill.artefact.id_prefix, skill.covers, skill.upstream) == (role, prefix, covers, upstream)
    assert [(i.prefix, i.section) for i in skill.items] == [(item, "Files")]
    assert skill.required_sections[:3] == ("Overview", "Files", "Code")


def test_the_frontend_skill_cannot_read_the_backend_code_because_both_are_built_at_the_same_time(library):
    assert "backend_code" not in library.get("frontend_code").upstream and "database_schema" not in library.get("backend_code").upstream


def test_only_the_four_build_artefacts_have_files():
    assert set(F.KINDS) == set(KEYS)
    assert F.is_build_artefact("backend_code") and not F.is_build_artefact("low_level_design")


def test_every_other_artefact_has_no_file_problems_whatever_its_body(library):
    assert F.file_problems("low_level_design", "File: ../../x\n```\nboom\n```", library.get("low_level_design").items) == []


# ---- reading the Code section --------------------------------------------------------------------------------------------------

def test_a_good_body_parses_to_exactly_its_files():
    files, problems = F.parse_code(make_body(DB_FILES, "DBF"))
    assert problems == [] and [(f.path, f.text) for f in files] == [("db/schema.sql", DB_FILES[0][1] + "\n"), ("db/init_db.py", "print(1)\n")]


def test_a_body_with_no_code_section_gives_nothing_and_no_second_complaint():
    assert F.parse_code("## Overview\nx") == ([], [])


@pytest.mark.parametrize("line", ["File: db/x.sql", "**File: db/x.sql**", "### File: db/x.sql", "- File: db/x.sql", "File: `db/x.sql`", "  File:   db/x.sql  "])
def test_the_usual_ways_a_model_writes_the_file_line_are_all_read(line):
    files, problems = F.parse_code(f"## Code\n{line}\n```sql\nSELECT 1;\n```\n")
    assert problems == [] and [f.path for f in files] == ["db/x.sql"]


def test_a_longer_fence_can_hold_a_shorter_one_inside_it():
    files, problems = F.parse_code("## Code\nFile: tests/a.py\n````python\nx = '''\n```\n'''\n````\n")
    assert problems == [] and "```" in files[0].text


def test_a_block_with_no_file_line_is_a_problem():
    _, problems = F.parse_code("## Code\n```python\nx = 1\n```\n")
    assert len(problems) == 1 and "has no 'File: <path>' line" in problems[0]


def test_a_file_line_with_no_block_is_a_problem_even_if_text_follows():
    _, problems = F.parse_code("## Code\nFile: db/x.sql\nsome words\n")
    assert len(problems) == 1 and "'File: db/x.sql' is not followed by a code block" in problems[0]


def test_words_between_a_file_line_and_its_block_break_the_link_so_the_block_is_not_written_under_that_name():
    files, problems = F.parse_code("## Code\nFile: db/x.sql\nHere is the file:\n```sql\nSELECT 1;\n```\n")
    assert files == [] and len(problems) == 2
    assert "'File: db/x.sql' is not followed by a code block" in problems[0] and "has no 'File: <path>' line" in problems[1]


def test_two_file_lines_in_a_row_name_the_first_as_unfollowed():
    files, problems = F.parse_code("## Code\nFile: db/a.sql\nFile: db/b.sql\n```sql\nSELECT 1;\n```\n")
    assert [f.path for f in files] == ["db/b.sql"] and "db/a.sql" in problems[0]


def test_an_unclosed_block_is_a_problem_and_names_the_file():
    files, problems = F.parse_code("## Code\nFile: db/x.sql\n```sql\nSELECT 1;\n")
    assert files == [] and problems == ["the code block for db/x.sql is never closed; end it with a line holding only ```"]


def test_a_file_line_at_the_very_end_is_a_problem():
    _, problems = F.parse_code("## Code\nFile: db/x.sql")
    assert len(problems) == 1 and "not followed by a code block" in problems[0]


# ---- paths and folders --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["../db/x.sql", "/db/x.sql", "db/../x.sql", "db/.env", "db/x y.sql", "db\\x.sql", "~/x.sql", "db/id_rsa", "db/a.pem"])
def test_a_bad_path_is_refused_with_the_path_rule(path):
    assert "is not allowed" in F.path_problem(path, F.KINDS["database_schema"])


def test_a_path_outside_the_artefacts_folder_is_refused():
    assert "outside backend/" in F.path_problem("frontend/app.js", F.KINDS["backend_code"])
    assert "outside backend/" in F.path_problem("backendx/a.py", F.KINDS["backend_code"])


def test_the_database_artefact_may_write_only_its_two_files():
    kind = F.KINDS["database_schema"]
    assert F.path_problem("db/schema.sql", kind) is None and F.path_problem("db/init_db.py", kind) is None
    assert "not one of the files" in F.path_problem("db/extra.sql", kind)


@pytest.mark.parametrize("key, path", [("backend_code", "backend/a.js"), ("frontend_code", "frontend/a.py"), ("test_suite", "tests/a.html")])
def test_a_file_type_the_artefact_cannot_write_is_refused(key, path):
    assert "a type this artefact cannot write" in F.path_problem(path, F.KINDS[key])


@pytest.mark.parametrize("key, path", [("backend_code", "backend/main.py"), ("backend_code", "backend/sub/util.py"), ("frontend_code", "frontend/index.html"),
                                       ("frontend_code", "frontend/app.js"), ("frontend_code", "frontend/style.css"), ("test_suite", "tests/test_a.py")])
def test_a_good_path_is_accepted(key, path):
    assert F.path_problem(path, F.KINDS[key]) is None


# ---- the whole check ---------------------------------------------------------------------------------------------------------

def problems_for(library, key, body):
    return F.file_problems(key, body, library.get(key).items)


def test_a_good_database_body_has_no_problems(library):
    assert problems_for(library, "database_schema", make_body(DB_FILES, "DBF")) == []


def test_a_duplicate_path_is_one_problem_and_the_second_copy_is_not_judged_again(library):
    body = make_body(DB_FILES + [("db/schema.sql", "SELECT 1;")], "DBF", listed=["db/schema.sql", "db/init_db.py"])
    assert [p for p in problems_for(library, "database_schema", body) if "more than once" in p] == ["db/schema.sql is given more than once in Code; write each file once"]


def test_a_bad_file_given_twice_is_reported_once_for_being_bad_and_once_for_being_repeated(library):
    body = make_body([("db/schema.sql", " "), ("db/schema.sql", " "), DB_FILES[1]], "DBF", listed=["db/schema.sql", "db/init_db.py"])
    found = problems_for(library, "database_schema", body)
    assert [p for p in found if "is empty" in p] == ["db/schema.sql is empty; a file needs content"]
    assert [p for p in found if "more than once" in p] == ["db/schema.sql is given more than once in Code; write each file once"]


def test_an_empty_file_is_refused(library):
    body = make_body([("db/schema.sql", "  "), DB_FILES[1]], "DBF")
    assert any("db/schema.sql is empty" in p for p in problems_for(library, "database_schema", body))


def test_a_file_that_holds_a_nul_byte_is_refused(library):
    body = make_body([("db/schema.sql", "a\x00b"), DB_FILES[1]], "DBF")
    assert any("NUL byte" in p for p in problems_for(library, "database_schema", body))


def test_a_missing_required_file_is_named(library):
    body = make_body([DB_FILES[0]], "DBF")
    assert [p for p in problems_for(library, "database_schema", body) if "required file" in p] == ["the required file db/init_db.py is missing from Code"]


def test_the_backend_must_have_main_py(library):
    body = make_body([("backend/util.py", "x = 1")], "BEF")
    assert any("the required file backend/main.py is missing" in p for p in problems_for(library, "backend_code", body))


def test_a_file_listed_but_not_written_and_one_written_but_not_listed_are_each_named(library):
    body = make_body(DB_FILES, "DBF", listed=["db/schema.sql", "db/other.sql"])
    found = problems_for(library, "database_schema", body)
    assert "Files lists db/other.sql, but Code has no 'File: db/other.sql' block" in found
    assert "Code has a 'File: db/init_db.py' block, but Files does not list it" in found


def test_a_files_entry_that_does_not_start_with_a_path_is_named(library):
    body = make_body(DB_FILES, "DBF").replace("DBF-001 db/schema.sql:", "DBF-001 the schema file:")
    assert any(p.startswith("DBF-001 does not start with a file path") for p in problems_for(library, "database_schema", body))


def test_a_path_written_in_backticks_or_bold_in_files_is_still_read(library):
    body = make_body(DB_FILES, "DBF").replace("DBF-001 db/schema.sql:", "DBF-001 `db/schema.sql`:").replace("DBF-002 db/init_db.py:", "DBF-002 **db/init_db.py**:")
    assert problems_for(library, "database_schema", body) == []


def test_more_than_twelve_files_is_one_problem(library):
    entries = [("backend/main.py", "x = 1")] + [(f"backend/m{n}.py", "x = 1") for n in range(12)]
    found = problems_for(library, "backend_code", make_body(entries, "BEF"))
    assert [p for p in found if "the limit is" in p] == ["the artefact has 13 files; the limit is 12"]


def test_exactly_twelve_files_is_allowed(library):
    entries = [("backend/main.py", "x = 1")] + [(f"backend/m{n}.py", "x = 1") for n in range(11)]
    assert problems_for(library, "backend_code", make_body(entries, "BEF")) == []


def test_a_path_outside_the_folder_is_reported_for_the_whole_body(library):
    body = make_body([("backend/main.py", "x = 1"), ("frontend/evil.js", "x = 1")], "BEF")
    assert any("'frontend/evil.js' is outside backend/" in p for p in problems_for(library, "backend_code", body))


# ---- through check_body (so a person's edit is held to the same rules) ----------------------------------------------------------

def test_check_body_applies_the_file_rules_to_a_build_artefact(library):
    skill = library.get("database_schema")
    good = make_body(DB_FILES, "DBF")
    assert not any("File" in p or "file" in p for p in check_body(good, skill, set(), None))
    bad = make_body([("db/schema.sql", "x"), ("../escape.py", "x")], "DBF")
    assert any("../escape.py" in p for p in check_body(bad, skill, set(), None))


def test_check_body_leaves_a_design_artefact_alone(library):
    skill = library.get("low_level_design")
    body = "## Overview\nx\n## Code\nFile: ../../x\n```\nboom\n```\n"
    assert not any("../../x" in p for p in check_body(body, skill, set(), None))


def test_a_secret_in_a_code_file_is_listed_first(library):
    key = "AKIA" + "IOSFODNN7EXAMPLE"
    body = make_body([("db/schema.sql", f"-- {key}"), DB_FILES[1], ("db/extra.sql", "x")], "DBF")
    found = check_body(body, library.get("database_schema"), set(), None, scanner=Scanner())
    assert "cloud access" in found[0] and key not in " ".join(found)


# ---- the design's tables --------------------------------------------------------------------------------------------------------

def test_table_names_are_read_from_the_design_items(library):
    from app.build.checks import table_names_in_design
    body = ("## Tables\n- TBL-001 users: id, name. Derives from: COMP-001\n- TBL-002 `Orders` (id, user_id). Derives from: COMP-001\n"
            "- TBL-003 The invoices table. Derives from: COMP-001\n- TBL-004 users: again. Derives from: COMP-001\n- TBL-006 `Users` (again). Derives from: COMP-001\n- TBL-005 line_items (id). Derives from: COMP-001\n")
    assert table_names_in_design(body, library.get("low_level_design").items) == ["users", "Orders", "line_items"]
