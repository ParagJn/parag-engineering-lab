"""The guardrail scanner: every rule, its near misses, the masking guarantee, hostile input and the settings."""
from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.guardrails.scan import (
    ALWAYS_ON, BACKSTOP_RULES, BY_NAME, MAX_FINDINGS, PERSONAL, RULE_NAMES, RULES, SECRET, Finding, Scanner, SecretRefused,
    counts_by_rule, describe, parse_disabled,
)
from app.guardrails.status import guardrails_status

from . import _fakes as F

scanner = Scanner(secrets=[F.CONFIGURED])


def rules_in(text: str, sc: Scanner = scanner) -> list[str]:
    return [f.rule for f in sc.scan(text)]


# ---- the rule table --------------------------------------------------------------------------------------------------------

def test_there_are_fourteen_rules_ten_secret_and_four_personal_and_each_has_a_fixture():
    assert len(RULES) == 14 and len(set(RULE_NAMES)) == 14
    assert [r.klass for r in RULES].count(SECRET) == 10 and [r.klass for r in RULES].count(PERSONAL) == 4
    assert set(F.POSITIVE) | {"configured_credential"} == set(RULE_NAMES)      # a fixture for every rule


def test_exactly_two_rules_can_never_be_switched_off():
    assert ALWAYS_ON == {"private_key", "configured_credential"}


def test_the_repository_backstop_covers_high_confidence_secrets_only():
    assert BACKSTOP_RULES == {"private_key", "configured_credential", "aws_key_id", "github_token", "slack_token", "stripe_key",
                              "google_api_key", "jwt", "url_password"}
    assert "credential_assignment" not in BACKSTOP_RULES and not any(BY_NAME[r].klass == PERSONAL for r in BACKSTOP_RULES)


# ---- each rule: found, with the right class, line and heading, and never the value ---------------------------------------------------

@pytest.mark.parametrize("rule, text", sorted(F.POSITIVE.items()))
def test_each_rule_finds_its_planted_value_on_the_right_line_under_the_right_heading(rule, text):
    body = f"## Notes\nan ordinary line\n{text}\nanother line"
    [finding] = [f for f in scanner.scan(body) if f.rule == rule]
    assert (finding.klass, finding.line, finding.heading) == (BY_NAME[rule].klass, 3, "Notes")
    assert finding.length > 0
    assert set(finding.as_dict()) == {"rule", "class", "line", "heading", "length"}      # the only fields a finding has


def test_a_configured_credential_is_found_by_exact_match_anywhere_in_a_word():
    found = scanner.scan(f"prefix{F.CONFIGURED}suffix and again {F.CONFIGURED}")
    assert [(f.rule, f.line) for f in found] == [("configured_credential", 1), ("configured_credential", 1)]


def test_a_configured_endpoint_is_found_whatever_its_letter_case():
    endpoint = "https://ica.example-internal.test/api"
    sc = Scanner(secrets=[endpoint])
    assert rules_in("see HTTPS://ICA.EXAMPLE-INTERNAL.TEST/API for details", sc) == ["configured_credential"]
    assert rules_in("see a different host", sc) == []


def test_a_configured_value_under_four_characters_or_blank_never_matches_everything():
    sc = Scanner(secrets=["", "  ", "ab", "abc"])
    assert sc.scan("abc ab a anything at all") == []


def test_the_secret_list_is_read_fresh_on_every_scan_so_a_changed_setting_is_noticed():
    values = ["first-secret-value-1"]
    sc = Scanner(secrets=lambda: values)
    assert rules_in("has first-secret-value-1 inside", sc) == ["configured_credential"]
    values[:] = ["second-secret-value-2"]
    assert rules_in("has first-secret-value-1 inside", sc) == [] and rules_in("has second-secret-value-2 inside", sc) == ["configured_credential"]


# ---- near misses ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    F.join("AK", "IA", "ABCDEFGHIJKLMNO"),                                  # one character short
    F.join("AK", "IA", "ABCDEFGHIJKLMNOPQ"),                                # one character long
    F.join("gh", "p_", "short"),
    F.join("xo", "xb-", "short"),
    F.join("sk", "_live_", "short"),
    F.join("sk", "_test_", "abcdefghijklmnop1234"),                         # a test-mode key is not a live one
    F.join("AI", "za", "tooShort"),
    F.join("ey", "J", "abc.def.ghi"),
    "-----BEGIN CERTIFICATE-----",                                           # a certificate is public
    "-----BEGIN PUBLIC KEY-----",
])
def test_a_near_miss_of_a_secret_is_not_flagged(text):
    assert rules_in(text) == []


@pytest.mark.parametrize("text", ["4111 1111 1111 1112", "4111111111111112", "5" * 16, "1234 5678 9012 3456", "order 1234567890123",
                                  "GB82 WEST 1234 5698 7654 33", "GB00 WEST 1234 5698 7654 32", "ZZ82 WEST 1234 5698 7654 32"])
def test_a_long_number_that_fails_its_checksum_is_not_a_card_or_a_bank_account(text):
    assert rules_in(text) == []


@pytest.mark.parametrize("text", ["a@example.com", "a@sub.example.org", "a@example.net", "a@b.test", "a@x.invalid", "a@host.localhost", "a@corp.local",
                                  "not an email @ all", "user@", "@domain.com"])
def test_an_email_on_a_reserved_or_broken_address_is_not_flagged(text):
    assert "email" not in rules_in(text)


@pytest.mark.parametrize("text", ["2026-10-29 08:00", "v1.2.3.4", "call 555-123", "ref 12345678", "+1", "10:30-12:45", "1,395 tokens", "$0.01467"])
def test_numbers_that_are_not_phone_numbers_are_not_flagged(text):
    assert "phone" not in rules_in(text)


def test_a_phone_number_needs_a_plus_and_eight_to_fifteen_digits_or_a_grouped_ten_digit_form():
    assert rules_in("+44 20 7946 0958") == ["phone"] and rules_in("+1 555 123 4567") == ["phone"] and rules_in(F.PHONE_US) == ["phone"]
    assert rules_in("+44 20") == [] and rules_in("+" + "1" * 16) == []


@pytest.mark.parametrize("text", F.CLEAN)
def test_ordinary_artefact_text_fires_nothing(text):
    assert scanner.scan(text) == [], text


def test_the_phrase_after_a_password_label_is_never_taken_for_a_value():
    for text in ("password: The booking rules apply to every member of staff", "token: this sentence is not a token at all",
                 "secret: see the vault for details", "pass: ok"):
        assert rules_in(text) == [], text


@pytest.mark.parametrize("value", ["changeme", "CHANGE_ME_please", "your-key-here-1234", "<your-token-value>", "${API_TOKEN_VALUE}", "{{ secret }}",
                                   "xxxxxxxxxxxxxxxx", "example-value-1234", "placeholder-token-1", "REQ-F-001-REQ-NF-002", "aaaaaaaaaaaaaaaa"])
def test_placeholders_and_item_ids_are_not_credentials(value):
    for line in (f"password = {value}", f"api_key: {value}", f'token="{value}"'):
        assert rules_in(line) == [], line


@pytest.mark.parametrize("line", [F.join("password = ", "Zk9", "xQ2mP7", "vR4tY8wL"), F.join('token: "', "Zk9", "xQ2mP7", 'vR4tY8wL"'),
                                  F.join("API_KEY=", "Zk9", "xQ2mP7", "vR4tY8wL"), F.join("client secret : ", "Zk9", "xQ2mP7", "vR4tY8wL")])
def test_a_real_looking_value_after_a_credential_label_is_found(line):
    assert rules_in(line) == ["credential_assignment"]


def test_a_password_in_a_url_is_found_but_a_placeholder_password_is_not():
    assert rules_in(F.URL_WITH_PASSWORD) == ["url_password"]
    for placeholder in ("user:password", "user:pass", "user:${PASS}", "user:<password>", "user:****", "user:x"):
        assert rules_in("postgres" + f"://{placeholder}@host/db") == [], placeholder


def test_a_url_without_a_password_is_not_flagged():
    for url in ("https://example.com/path", "https://user@host/path", "ssh://git@github.com/org/repo.git"):
        assert rules_in(url) == [], url


def test_a_stronger_finding_swallows_a_weaker_one_inside_it():
    both = scanner.scan("see " + F.join("postgres", "://admin:", "Tr0ub4dor", "@mail.corp-internal.co.uk/db"))
    assert [f.rule for f in both] == ["url_password"]                       # the host's look-alike email is not reported separately
    around = scanner.scan(F.join("token = ", F.GITHUB_TOKEN))
    assert [f.rule for f in around] == ["github_token"]                     # not also a generic assignment


# ---- lines and headings -----------------------------------------------------------------------------------------------------------------

def test_the_line_is_the_one_the_value_is_on_across_blank_lines_and_windows_newlines():
    body = "first\n\n\nthird\n" + F.EMAIL + "\n"
    [f] = scanner.scan(body)
    assert f.line == 5
    [g] = scanner.scan("a\r\nb\r\n" + F.EMAIL)
    assert g.line == 3


def test_the_heading_is_the_nearest_one_above_and_empty_when_there_is_none():
    body = f"{F.EMAIL}\n## First\nplain\n### Second *one*\n{F.EMAIL}\n"
    assert [(f.line, f.heading) for f in scanner.scan(body)] == [(1, ""), (5, "Second *one*")]


def test_a_heading_that_itself_contains_a_value_is_never_copied_into_a_finding():
    body = f"## contact {F.EMAIL}\n{F.EMAIL}"
    [f] = [f for f in scanner.scan(body) if f.line == 2]
    assert f.heading == "(heading removed)" and F.EMAIL not in repr(f.as_dict())


def test_a_long_heading_is_cut_and_a_hash_that_is_not_a_heading_is_ignored():
    body = f"## {'x' * 200}\n{F.EMAIL}\n#not a heading\n{F.EMAIL}"
    first, second = scanner.scan(body)
    assert len(first.heading) == 80 and second.heading == first.heading


def test_findings_are_in_order_and_capped():
    many = "\n".join(F.EMAIL for _ in range(MAX_FINDINGS + 50))
    found = scanner.scan(many)
    assert len(found) == MAX_FINDINGS and [f.line for f in found] == sorted(f.line for f in found)


def test_several_findings_on_one_line_are_all_reported():
    assert rules_in(f"{F.EMAIL} and {F.AWS_KEY} and {F.PHONE_INTL}") == ["email", "aws_key_id", "phone"] or \
        sorted(rules_in(f"{F.EMAIL} and {F.AWS_KEY} and {F.PHONE_INTL}")) == ["aws_key_id", "email", "phone"]


def test_scanning_sections_numbers_lines_across_the_whole_document_and_uses_the_given_headings():
    sections = [("Intro", "hello\nthere"), ("Contacts", f"name\n{F.EMAIL}"), ("Keys", F.AWS_KEY)]
    assert [(f.rule, f.line, f.heading) for f in scanner.scan_sections(sections)] == [("email", 4, "Contacts"), ("aws_key_id", 5, "Keys")]


def test_a_section_heading_that_contains_a_value_is_removed_in_section_scans_too():
    [f] = scanner.scan_sections([(f"about {F.EMAIL}", F.AWS_KEY)])
    assert f.heading == "(heading removed)"


# ---- masking: a value never appears in anything the scanner produces -----------------------------------------------------------------------

@pytest.mark.parametrize("rule, text", sorted(F.POSITIVE.items()))
def test_no_finding_and_no_description_contains_the_value(rule, text):
    planted = {"email": F.EMAIL, "phone": F.PHONE_INTL, "payment_card": F.CARD, "iban": F.IBAN, "url_password": "Tr0ub4dor",
               "credential_assignment": "Zk9xQ2mP7vR4tY8wL"}.get(rule, text)
    findings = scanner.scan(f"## About\n{text}")
    shown = repr([f.as_dict() for f in findings]) + " ".join(describe(f) for f in findings if f.klass == SECRET) + " ".join(scanner.problems(text))
    assert planted not in shown and text not in shown
    for fragment in (planted[:8], planted[-8:]):
        assert fragment not in shown or fragment in ("BEGIN RS", "RSA PRIV")   # a fragment is not a leak, but the value cannot be rebuilt either


def test_a_description_names_the_rule_the_place_and_the_instruction_and_nothing_else():
    text = describe(Finding("aws_key_id", SECRET, 14, "Constraints", 20))
    assert text.startswith("line 14, under 'Constraints': this looks like a cloud access key (rule aws_key_id); remove it")
    assert "Say that one exists, not what it is" in text
    assert describe(Finding("aws_key_id", SECRET, 3, "", 20)).startswith("line 3: this looks like")


def test_problems_lists_secrets_only_and_personal_data_is_not_a_problem():
    assert scanner.problems(f"{F.EMAIL} {F.PHONE_INTL} {F.CARD} {F.IBAN}") == []
    assert len(scanner.problems(f"{F.AWS_KEY}\n{F.JWT}")) == 2


def test_secret_rules_found_gives_distinct_rule_names_in_order_of_appearance():
    assert scanner.secret_rules_found(f"{F.JWT} {F.AWS_KEY} {F.JWT}") == ["jwt", "aws_key_id"]
    assert scanner.secret_rules_found(F.EMAIL) == []


def test_counts_by_rule_is_sorted_and_carries_no_text():
    assert counts_by_rule(scanner.scan(f"{F.EMAIL} {F.EMAIL}\n{F.AWS_KEY}")) == {"aws_key_id": 1, "email": 2}


# ---- hostile input -------------------------------------------------------------------------------------------------------------------------

HOSTILE = {
    "a million a's": "a" * 1_000_000,
    "long digit run": "1" * 200_000,
    "digits with separators": "1-" * 100_000,
    "many at signs": "a@" * 100_000,
    "dots and plus": "+." * 100_000,
    "nested brackets": "((((((((((" * 20_000,
    "long url userinfo": "http" + "://" + "u:" * 50_000,
    "many scheme markers": "a://" * 50_000,
    "password labels": "password = " * 30_000,
    "base64 soup": ("eyJ" + "A" * 3000 + ".") * 300,
    "hash runs": "#" * 300_000,
    "long single line of tokens": ("AK" + "IA" + "A") * 100_000,
}


@pytest.mark.parametrize("name", sorted(HOSTILE))
def test_hostile_text_is_scanned_quickly_and_never_raises(name):
    started = time.perf_counter()
    scanner.scan(HOSTILE[name])
    assert time.perf_counter() - started < 2.0, name


def test_a_five_megabyte_document_scans_in_reasonable_time():
    text = ("Staff may book a room for up to four hours. Office hours are 08:00 to 18:00.\n" * 70_000)[: 5 * 1024 * 1024]
    started = time.perf_counter()
    assert scanner.scan(text) == []
    assert time.perf_counter() - started < 3.0


def test_non_text_and_empty_input_is_handled():
    assert scanner.scan("") == [] and scanner.scan(None) == [] and scanner.scan(b"bytes") == []   # type: ignore[arg-type]
    assert scanner.problems("") == []


# ---- switching rules off ----------------------------------------------------------------------------------------------------------------------

def test_a_disabled_rule_stops_firing_and_the_others_still_do():
    sc = Scanner(secrets=[F.CONFIGURED], disabled=parse_disabled("phone,email"))
    assert rules_in(f"{F.EMAIL} {F.PHONE_INTL}", sc) == [] and rules_in(F.AWS_KEY, sc) == ["aws_key_id"]


def test_disabled_names_are_case_and_space_insensitive_and_blank_entries_are_ignored():
    assert parse_disabled(" Phone , EMAIL,, ") == {"phone", "email"} and parse_disabled("") == frozenset()


@pytest.mark.parametrize("value", ["nonsense", "phone,nonsense", "private_key", "configured_credential", "phone,private_key"])
def test_an_unknown_or_unswitchable_rule_name_is_refused_with_the_valid_list(value):
    with pytest.raises(ValueError, match="rules are|cannot be switched off"):
        parse_disabled(value)


def test_the_setting_is_checked_when_the_settings_are_built_so_a_typo_stops_start_up():
    with pytest.raises(ValidationError, match="unknown guardrail rule"):
        Settings(_env_file=None, guardrails_disabled_rules="phoen")
    with pytest.raises(ValidationError, match="cannot be switched off"):
        Settings(_env_file=None, guardrails_disabled_rules="configured_credential")
    assert Settings(_env_file=None, guardrails_disabled_rules="phone").guardrails_disabled == {"phone"}
    assert Settings(_env_file=None).guardrails_disabled == frozenset()


def test_the_scanner_built_from_settings_uses_its_credentials_and_its_disabled_rules():
    settings = Settings(_env_file=None, ibm_ica_api_key="a-long-test-key-0001", guardrails_disabled_rules="phone")
    sc = Scanner.from_settings(settings)
    assert rules_in("has a-long-test-key-0001 inside", sc) == ["configured_credential"] and rules_in(F.PHONE_INTL, sc) == []


def test_the_status_block_lists_what_is_off_and_what_cannot_be_and_nothing_else():
    block = guardrails_status(Scanner(disabled=parse_disabled("phone")))
    assert block == {"rules": 14, "secret_rules": 10, "personal_rules": 4, "disabled": ["phone"],
                     "cannot_be_disabled": ["configured_credential", "private_key"]}


def test_a_scan_restricted_to_some_rules_runs_only_those():
    assert [f.rule for f in scanner.scan(f"{F.AWS_KEY} {F.EMAIL}", only={"email"})] == ["email"]
    assert scanner.scan(F.AWS_KEY, only=set()) == []


def test_a_secret_refused_error_is_a_plain_invalid_input():
    from app.models import InvalidInput

    assert issubclass(SecretRefused, InvalidInput)


# ---- stand-in values label themselves (found by the repo self-scan) ---------------------------------------------------------------

@pytest.mark.parametrize("value", ["sk-SECRET-123456", "a-long-test-key-0001", "fake-token-9988776655", "demo-password-2026!", "TestKey-Abc123-xyz",
                                   "my-secret-value-42"])
def test_a_value_that_says_it_is_a_test_fake_demo_or_secret_stand_in_is_not_a_credential(value):
    for line in (f"password = {value}", f'API_KEY = "{value}"', f"token: {value}"):
        assert rules_in(line) == [], line


def test_the_trade_off_is_real_and_stated_a_real_looking_value_without_such_a_word_is_still_found():
    assert rules_in(F.ASSIGNED_SECRET) == ["credential_assignment"]
    assert rules_in(F.join("password = ", "Zk9", "xQ2mP7", "vR4tY8wL")) == ["credential_assignment"]


def test_a_stand_in_word_does_not_hide_a_known_token_format_or_a_configured_credential():
    """The word list only affects the GENERIC rule. A real GitHub token is a GitHub token whatever is around it."""
    assert rules_in(f"test token = {F.GITHUB_TOKEN}") == ["github_token"]
    assert rules_in(f"this is a test key {F.AWS_KEY}") == ["aws_key_id"]
    assert rules_in(f"demo: {F.CONFIGURED}") == ["configured_credential"]


# ---- gaps found by the S10 mutation check ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("rule, value", [("aws_key_id", F.AWS_TEMP_KEY), ("github_token", F.GITHUB_FINE), ("stripe_key", F.STRIPE_RESTRICTED)])
def test_the_other_forms_of_a_known_token_are_found_too(rule, value):
    """Temporary cloud keys (ASIA...), fine-grained code-hosting tokens (github_pat_...) and restricted payment keys (rk_live_...)
    are real, common, and were in the fixtures but not in a test."""
    assert rules_in(f"x {value} y") == [rule]


@pytest.mark.parametrize("value", ["4" * 17, "6" * 13])
def test_a_run_of_one_repeated_digit_is_not_a_card_even_when_it_passes_the_checksum(value):
    from app.guardrails.scan import _luhn

    assert _luhn(value)                                  # precondition: only the repeated-digit guard stands between this and a finding
    assert rules_in(f"number {value}") == []


def test_a_well_formed_bank_account_number_from_an_unknown_country_is_not_flagged():
    value = "ZZ33WEST12345698765432"
    assert int("".join(str(int(c, 36)) for c in (value[4:] + value[:4]))) % 97 == 1   # precondition: checksum passes
    assert rules_in("pay to ZZ33 WEST 1234 5698 7654 32") == []
    assert rules_in("pay to GB82 WEST 1234 5698 7654 32") == ["iban"]               # the same shape from a real country is found


@pytest.mark.parametrize("value", ["ab1ab1ab1ab1ab1", "xyxyxyxyxy12xyxy"])
def test_a_repetitive_value_after_a_credential_label_is_not_a_credential(value):
    from app.guardrails.scan import _entropy

    assert _entropy(value) < 3.0 and len(value) >= 12                                # precondition: low entropy is the ONLY thing separating it
    assert rules_in(f"password = {value}") == []


@pytest.mark.parametrize("value", ["REQ-PER-001234", "SET-CHR-004567", "REQ-F-012345"])
def test_an_item_id_after_a_credential_label_is_not_a_credential(value):
    from app.guardrails.scan import _entropy

    assert _entropy(value) >= 3.0                                                   # precondition: entropy would let it through
    assert rules_in(f"token = {value}") == []


@pytest.mark.parametrize("value", ["internationalizationandlocalization", "configurationmanagementprocedures"])
def test_a_long_run_of_one_kind_of_letter_after_a_credential_label_is_not_a_credential(value):
    from app.guardrails.scan import _entropy

    assert _entropy(value) >= 3.0 and len(value) >= 24 and value.isalpha() and value.islower()   # only the character-type guard stops it
    assert rules_in(f"secret_key: {value}") == []


def test_a_finding_on_a_heading_line_takes_the_heading_before_it_and_never_its_own_text():
    [f] = scanner.scan(f"## Intro\n## contact {F.EMAIL}")
    assert (f.line, f.heading) == (2, "Intro") and F.EMAIL not in repr(f.as_dict())
    [g] = scanner.scan(f"## contact {F.EMAIL}")
    assert (g.line, g.heading) == (1, "")                                           # a heading with nothing above it: none, not its own text
