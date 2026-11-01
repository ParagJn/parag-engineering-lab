"""Skill files: parsing, the linter's rules, and that the shipped skills agree with the catalogue."""
from __future__ import annotations

import pytest

from app.agents.skills import (
    HEADINGS,
    MAX_SEARCHES,
    SKILLS_DIR,
    SkillError,
    SkillLibrary,
    normalise_heading,
    parse_skill,
    upstream_keys,
)
from app.llm.routing import Routing
from app.workflow.definitions import load_catalogue

SHIPPED = {
    "project_charter", "problem_statement", "personas", "functional_requirements",
    "vision_objectives", "non_functional_requirements", "epics_features", "user_stories",
    "user_journey", "lowfi_wireframes", "hifi_wireframes",          # S13
    "component_overview", "high_level_design", "low_level_design",  # S14a
    "flow_diagram", "usecase_diagram",                              # S14b
}


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue(Routing.load().roles.keys())


@pytest.fixture(scope="module")
def library(catalogue):
    return SkillLibrary.load(catalogue)


def skill_text(
    key="personas", *, inputs="- artefact: project_charter\n- search: who uses this", sections="- Overview\n- Personas",
    skip: str | None = None, extra: str = "", title="Skill: Personas",
) -> str:
    parts = {
        "Role": "You are an analyst.",
        "Inputs": inputs,
        "Output": f"Artefact: {key}\nRequired sections:\n{sections}",
        "Method": "1. Read it.\n2. Write it.",
        "Quality bar": "- Be clear.",
        "Never": "- Invent things.",
    }
    out = f"# {title}\n"
    for name in HEADINGS:
        if name != skip:
            out += f"## {name}\n{parts[name]}\n"
    return out + extra


def parse(text: str, name="personas.md", catalogue_=None):
    return parse_skill(text, name, catalogue_)


# ---- the shipped skills ---------------------------------------------------------------------------------

def test_exactly_the_planned_skills_are_shipped(library):
    """Eight for the first two phases (S07, S11), three for Design (S13) and three for Architecture (S14a) and two diagrams (S14b). Each step that adds one updates SHIPPED."""
    assert set(library.keys) == SHIPPED and len(library) == 16


def test_every_shipped_skill_names_a_catalogue_key_and_takes_its_role_and_prefix_from_the_catalogue(library, catalogue):
    for key in library.keys:
        skill = library.get(key)
        entry = next(a for p in catalogue.phases for a in p.artefacts if a.key == key)
        assert skill.artefact == entry and skill.artefact.role and skill.artefact.id_prefix
    assert library.get("personas").artefact.id_prefix == "REQ-PER"
    assert library.get("project_charter").artefact.role == "orchestrator"


def test_every_shipped_skills_inputs_are_generated_before_it(library, catalogue):
    for key in library.keys:
        skill = library.get(key)
        assert set(skill.upstream) <= upstream_keys(catalogue, skill.artefact), key


def test_the_shipped_chain_reads_forwards(library):
    assert library.get("project_charter").upstream == ()
    assert library.get("problem_statement").upstream == ("project_charter",)
    assert set(library.get("functional_requirements").upstream) == {"project_charter", "personas", "problem_statement"}


def test_every_shipped_skill_has_the_required_content(library):
    for key in library.keys:
        skill = library.get(key)
        assert len(skill.required_sections) >= 3 and skill.method and skill.quality_bar and skill.never
        assert len(skill.searches) <= MAX_SEARCHES
        assert "Cite a source that was not provided" in skill.never, key
        assert "reference material" in skill.never.lower(), key  # the prompt-injection line is in every skill


def test_every_markdown_file_in_the_skills_folder_loads_and_none_is_misnamed(catalogue):
    files = sorted(p.stem for p in SKILLS_DIR.glob("*.md"))
    assert files == sorted(SHIPPED)
    assert set(SkillLibrary.load(catalogue).keys) == set(files)


def test_a_missing_skill_is_simply_absent_not_an_error(library):
    assert library.get("deployment_plan") is None and not library.has("deployment_plan") and library.has("personas")      # Deploy has none yet


# ---- parsing --------------------------------------------------------------------------------------------

def test_a_valid_skill_parses(catalogue):
    skill = parse(skill_text(), catalogue_=catalogue)
    assert skill.key == "personas" and skill.title == "Personas"
    assert skill.required_sections == ("Overview", "Personas") and skill.upstream == ("project_charter",)
    assert skill.searches == ("who uses this",) and skill.method.startswith("1. Read it.")


def test_search_and_artefact_inputs_are_kept_in_their_own_lists(catalogue):
    text = skill_text(inputs="- artefact: project_charter\n- search: one\n- search: two\n\n- search: three")
    skill = parse(text, catalogue_=catalogue)
    assert skill.upstream == ("project_charter",) and skill.searches == ("one", "two", "three")


# ---- the linter: one test per rule ----------------------------------------------------------------------------

@pytest.mark.parametrize("missing", HEADINGS)
def test_a_missing_heading_is_named(catalogue, missing):
    with pytest.raises(SkillError, match=f"missing heading.*{missing}"):
        parse(skill_text(skip=missing), catalogue_=catalogue)


def test_a_duplicate_heading_is_refused_with_its_line(catalogue):
    with pytest.raises(SkillError, match=r"personas.md: line \d+: heading '## Role' appears twice"):
        parse(skill_text(extra="## Role\nagain\n"), catalogue_=catalogue)


def test_a_misspelled_or_unknown_heading_is_refused_and_the_allowed_list_is_shown(catalogue):
    with pytest.raises(SkillError, match=r"unknown heading '## Quality'.*Quality bar"):
        parse(skill_text().replace("## Quality bar", "## Quality"), catalogue_=catalogue)
    with pytest.raises(SkillError, match="unknown heading '## Extras'"):
        parse(skill_text(extra="## Extras\nx\n"), catalogue_=catalogue)


def test_headings_out_of_order_are_refused(catalogue):
    swapped = skill_text().replace("## Method", "## TMP").replace("## Never", "## Method").replace("## TMP", "## Never")
    with pytest.raises(SkillError, match="headings must appear in this order"):
        parse(swapped, catalogue_=catalogue)


@pytest.mark.parametrize("section", ["Role", "Method", "Quality bar", "Never"])
def test_a_blank_section_is_refused_with_its_line(catalogue, section):
    text = skill_text()
    start = text.index(f"## {section}\n") + len(f"## {section}\n")
    end = text.index("\n## ", start) if "\n## " in text[start:] else len(text)
    blanked = text[:start] + "   \n" + text[end + 1:]
    with pytest.raises(SkillError, match=rf"line \d+: section '## {section}' is empty"):
        parse(blanked, catalogue_=catalogue)


def test_the_title_line_is_required_and_there_can_be_only_one(catalogue):
    with pytest.raises(SkillError, match="must start with '# Skill:"):
        parse("## Role\nx\n", catalogue_=catalogue)
    with pytest.raises(SkillError, match="file is empty|must start"):
        parse("", catalogue_=catalogue)
    with pytest.raises(SkillError, match="only one '# ' title"):
        parse(skill_text(extra="# Another\n"), catalogue_=catalogue)


def test_an_artefact_that_is_not_a_catalogue_key_is_refused(catalogue):
    with pytest.raises(SkillError, match="not a key in the workflow catalogue"):
        parse(skill_text(key="gadgets"), name="gadgets.md", catalogue_=catalogue)


def test_the_file_name_must_match_the_artefact_it_says_it_is_for(catalogue):
    with pytest.raises(SkillError, match=r"named 'wrong'; they must match"):
        parse(skill_text(), name="wrong.md", catalogue_=catalogue)


def test_the_output_block_must_start_with_artefact_and_a_required_sections_list(catalogue):
    with pytest.raises(SkillError, match="must start with 'Artefact:"):
        parse(skill_text().replace("Artefact: personas", "For: personas"), catalogue_=catalogue)
    with pytest.raises(SkillError, match="comes a 'Required sections:' list"):
        parse(skill_text().replace("Required sections:", "Sections:"), catalogue_=catalogue)


def test_required_sections_must_exist_be_a_list_and_be_distinct(catalogue):
    with pytest.raises(SkillError, match="at least one required section"):
        parse(skill_text(sections=""), catalogue_=catalogue)
    with pytest.raises(SkillError, match="'- ' list item"):
        parse(skill_text(sections="Overview"), catalogue_=catalogue)
    with pytest.raises(SkillError, match="duplicate"):
        parse(skill_text(sections="- Overview\n- overview:"), catalogue_=catalogue)
    with pytest.raises(SkillError, match="no letters or digits"):
        parse(skill_text(sections="- Overview\n- ???"), catalogue_=catalogue)
    with pytest.raises(SkillError, match="at most 20"):
        parse(skill_text(sections="\n".join(f"- Section {n}" for n in range(21))), catalogue_=catalogue)


@pytest.mark.parametrize("bad", ["- widget: x", "- artefact:", "just text", "* artefact: personas", "- search:"])
def test_an_input_that_is_neither_artefact_nor_search_is_refused(catalogue, bad):
    with pytest.raises(SkillError, match="an input must be"):
        parse(skill_text(inputs=bad), catalogue_=catalogue)


def test_too_many_searches_and_over_long_searches_are_refused(catalogue):
    many = "\n".join(f"- search: query {n}" for n in range(MAX_SEARCHES + 1))
    with pytest.raises(SkillError, match=f"at most {MAX_SEARCHES}"):
        parse(skill_text(inputs="- artefact: project_charter\n" + many), catalogue_=catalogue)
    with pytest.raises(SkillError, match="limited to 200 characters"):
        parse(skill_text(inputs="- search: " + "x" * 201), catalogue_=catalogue)


def test_an_artefact_input_that_does_not_exist_is_refused(catalogue):
    with pytest.raises(SkillError, match="not in the catalogue"):
        parse(skill_text(inputs="- artefact: gadgets"), catalogue_=catalogue)
    with pytest.raises(SkillError, match="not an artefact key"):
        parse(skill_text(inputs="- artefact: Not A Key"), catalogue_=catalogue)


def test_an_artefact_input_listed_twice_or_pointing_at_itself_is_refused(catalogue):
    with pytest.raises(SkillError, match="listed twice"):
        parse(skill_text(inputs="- artefact: project_charter\n- artefact: project_charter"), catalogue_=catalogue)
    with pytest.raises(SkillError, match="its own artefact"):
        parse(skill_text(inputs="- artefact: personas"), catalogue_=catalogue)


def test_an_input_from_a_LATER_phase_is_refused(catalogue):
    with pytest.raises(SkillError, match="not generated before 'personas'"):
        parse(skill_text(inputs="- artefact: high_level_design"), catalogue_=catalogue)


def test_an_input_from_the_same_phase_must_be_listed_in_after(catalogue):
    # personas has after=[]; problem_statement is in the same phase but personas does not wait for it.
    with pytest.raises(SkillError, match="not generated before 'personas'"):
        parse(skill_text(inputs="- artefact: problem_statement"), catalogue_=catalogue)
    # functional_requirements has after=[personas, problem_statement], so both are fine.
    ok = skill_text(key="functional_requirements", title="Skill: FR", inputs="- artefact: personas\n- artefact: problem_statement")
    assert parse(ok, name="functional_requirements.md", catalogue_=catalogue).upstream == ("personas", "problem_statement")


def test_an_input_reached_through_a_chain_of_after_rules_is_allowed(catalogue):
    # epics_features waits for functional_requirements, which waits for personas: personas is upstream of it.
    text = skill_text(key="epics_features", title="Skill: EF", inputs="- artefact: personas")
    assert parse(text, name="epics_features.md", catalogue_=catalogue).upstream == ("personas",)


def test_an_oversize_skill_is_refused(catalogue):
    with pytest.raises(SkillError, match="limited to 20000 bytes"):
        parse(skill_text(extra="x" * 25_000), catalogue_=catalogue)


def test_errors_name_the_file(catalogue):
    with pytest.raises(SkillError) as exc:
        parse(skill_text(skip="Never"), catalogue_=catalogue)
    assert str(exc.value).startswith("personas.md:")


def test_a_missing_or_unreadable_skills_folder_is_an_error(catalogue, tmp_path):
    with pytest.raises(SkillError, match="does not exist"):
        SkillLibrary.load(catalogue, tmp_path / "nowhere")
    (tmp_path / "personas.md").write_bytes(b"\xff\xfe\x00bad bytes")
    with pytest.raises(SkillError, match="cannot be read"):
        SkillLibrary.load(catalogue, tmp_path)


def test_an_empty_folder_is_a_valid_library_with_no_skills(catalogue, tmp_path):
    assert len(SkillLibrary.load(catalogue, tmp_path)) == 0


def test_other_files_in_the_folder_are_ignored(catalogue, tmp_path):
    (tmp_path / "notes.txt").write_text("not a skill")
    (tmp_path / "README.md.bak").write_text("nor this")
    assert len(SkillLibrary.load(catalogue, tmp_path)) == 0


# ---- upstream_keys -------------------------------------------------------------------------------------------------

def test_upstream_includes_every_earlier_phase_and_the_after_closure_and_nothing_later(catalogue):
    art = next(a for a in catalogue.phase("requirements").artefacts if a.key == "epics_features")
    allowed = upstream_keys(catalogue, art)
    assert {"project_charter", "functional_requirements", "non_functional_requirements", "personas", "problem_statement"} <= allowed
    assert "user_stories" not in allowed and "user_journey" not in allowed and "epics_features" not in allowed


def test_the_first_artefact_of_the_first_phase_has_nothing_upstream(catalogue):
    art = next(a for a in catalogue.phase("setup").artefacts if a.key == "project_charter")
    assert upstream_keys(catalogue, art) == set()


def test_normalise_heading():
    assert normalise_heading("  Open-questions: ") == "open questions" == normalise_heading("OPEN   questions")
    assert normalise_heading("???") == ""


# ---- S11: items and coverage ------------------------------------------------------------------------------------

def items_skill(*lines: str, sections="- Overview\n- Requirements", key="functional_requirements", inputs="- artefact: personas\n- artefact: problem_statement"):
    block = "\n".join(lines)
    text = skill_text(key=key, title="Skill: X", inputs=inputs, sections=sections)
    return text.replace(f"Artefact: {key}\n", f"Artefact: {key}\n{block}\n" if block else f"Artefact: {key}\n")


def parse_fr(text, catalogue_):
    return parse(text, name="functional_requirements.md", catalogue_=catalogue_)


def test_an_items_line_is_read_into_the_skill(catalogue):
    skill = parse_fr(items_skill("Items: FR in Requirements"), catalogue)
    assert [(i.prefix, i.section) for i in skill.items] == [("FR", "Requirements")] and skill.covers == ()


def test_two_items_lines_and_a_covers_line_are_read_in_any_order(catalogue):
    text = items_skill("Covers: PER", "Items: EPIC in Epics", "Items: FEAT in Features", sections="- Overview\n- Epics\n- Features",
                       key="epics_features", inputs="- artefact: personas\n- artefact: functional_requirements")
    skill = parse(text, name="epics_features.md", catalogue_=catalogue)
    assert [i.prefix for i in skill.items] == ["EPIC", "FEAT"] and skill.covers == ("PER",)


def test_a_skill_without_items_lines_has_none(catalogue):
    skill = parse_fr(items_skill(), catalogue)
    assert skill.items == () and skill.covers == ()


@pytest.mark.parametrize("line, message", [
    ("Items: fr in Requirements", "must be capital letters and digits"),
    ("Items: DOC in Requirements", "reserved for source citations"),
    ("Items: MEM in Requirements", "reserved for source citations"),
    ("Items: REQ in Requirements", "start of\\) an artefact ID prefix"),   # REQ begins REQ-F, REQ-PER, ...
    ("Items: SET in Requirements", "start of\\) an artefact ID prefix"),
    ("Items: FR in Nonsense", "not in 'Required sections'"),
    ("Items: FR", "after 'Artefact:' comes a 'Required sections:' list"),
    ("Covers: PER", "needs at least one 'Items:' line"),
    ("Items: FR in Requirements\nItems: FR in Overview", "listed twice"),
    ("Items: FR in Requirements\nCovers: PER\nCovers: NFR", "only one 'Covers:' line"),
    ("Items: FR in Requirements\nCovers: per", "not item prefixes"),
    ("Items: FR in Requirements\nCovers: PER PER", "lists a prefix twice"),
    ("Items: A in Requirements\nItems: B in Requirements\nItems: C in Requirements\nItems: D in Requirements\nItems: E in Requirements", "at most 4"),
])
def test_each_bad_items_or_covers_line_is_refused_with_its_reason(catalogue, line, message):
    with pytest.raises(SkillError, match=message):
        parse_fr(items_skill(line), catalogue)


def test_a_whole_artefact_prefix_with_its_hyphen_is_refused_as_not_a_plain_item_prefix(catalogue):
    with pytest.raises(SkillError, match="must be capital letters and digits"):
        parse_fr(items_skill("Items: REQ-F in Requirements"), catalogue)


def test_every_shipped_item_prefix_is_unique_and_each_covered_prefix_is_held_by_an_input(library):
    prefixes = [spec.prefix for key in library.keys for spec in library.get(key).items]
    assert sorted(prefixes) == sorted(["PER", "OBJ", "FR", "NFR", "EPIC", "FEAT", "US", "JS", "LFS", "HFS", "COMP", "DEC", "IFC", "API", "TBL", "RUL", "FLOW", "UC"])
    for key in library.keys:
        skill = library.get(key)
        for prefix in skill.covers:
            assert any(spec.prefix == prefix for i in skill.upstream for spec in library.get(i).items), (key, prefix)
    assert library.get("epics_features").covers == ("FR", "NFR") and library.get("user_stories").covers == ("FEAT",)
    assert library.get("component_overview").covers == ("FR", "NFR") and library.get("high_level_design").covers == ("COMP",) and library.get("low_level_design").covers == ("FR",)
    assert library.get("flow_diagram").covers == ("IFC",) and library.get("usecase_diagram").covers == ("PER",)
    assert library.get("problem_statement").items == () and library.get("project_charter").items == ()


def test_two_skills_sharing_an_item_prefix_stop_the_library_loading(catalogue, tmp_path):
    import shutil

    folder = tmp_path / "skills"
    shutil.copytree(SKILLS_DIR, folder)
    text = (folder / "non_functional_requirements.md").read_text().replace("Items: NFR in Requirements", "Items: FR in Requirements")
    (folder / "non_functional_requirements.md").write_text(text)
    with pytest.raises(SkillError, match=r"item prefix 'FR' is already used by 'functional_requirements'"):
        SkillLibrary.load(catalogue, folder)


def test_covering_a_prefix_no_input_holds_stops_the_library_loading(catalogue, tmp_path):
    import shutil

    folder = tmp_path / "skills"
    shutil.copytree(SKILLS_DIR, folder)
    text = (folder / "user_stories.md").read_text().replace("Covers: FEAT", "Covers: OBJ")
    (folder / "user_stories.md").write_text(text)
    with pytest.raises(SkillError, match=r"'Covers: OBJ' but none of its input artefacts holds OBJ items"):
        SkillLibrary.load(catalogue, folder)


def test_every_item_bearing_skill_tells_the_model_to_use_derives_from_keep_ids_and_withdraw_by_name(library):
    for key in library.keys:
        skill = library.get(key)
        if not skill.items:
            continue
        method = " ".join(skill.method.lower().split())
        assert "derives from" in method, key
        assert "never reuse or renumber an id" in method, key
        assert '"withdrawn items" heading' in method, key
