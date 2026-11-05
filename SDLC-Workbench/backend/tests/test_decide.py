"""S23b: the one rule for who may take a decision on a phase, as a plain function. Pure over a small fake of the Users list."""
from __future__ import annotations

import pytest

from app.access.decide import NotAllowed, deciding_role
from app.access.roles import DEFAULT_APPROVERS, ROLES
from app.models import User


class Users:
    def __init__(self, *people, approvers=None):
        self._people = {p.name.casefold(): p for p in people}
        self._approvers = approvers or DEFAULT_APPROVERS

    def count_active(self): return sum(1 for p in self._people.values() if p.active)
    def approvers(self): return self._approvers
    def find(self, name): return self._people.get(" ".join(name.split()).casefold())


def person(name, *roles, active=True):
    return User(1, name, active, tuple(r for r in ROLES if r in roles), "system", "t")


def test_nobody_on_the_list_means_nothing_is_restricted_and_no_role_is_named():
    assert deciding_role(Users(), "human:Anyone", "requirements", "Requirements") is None
    assert deciding_role(Users(person("Off", "Architect", active=False)), "human:Anyone", "requirements", "Requirements") is None


def test_the_allowed_role_is_named_and_a_phase_the_table_does_not_know_is_not_restricted():
    users = Users(person("Ann", "Architect"))
    assert deciding_role(users, "human:ann", "requirements", "Requirements") == "Architect"
    assert deciding_role(users, "human:Ann", "unknown_phase", "Unknown") is None


@pytest.mark.parametrize("roles, sentence", [
    (("Project Manager",), "Design can be approved only by an Architect; Bo holds Project Manager"),
    ((), "Design can be approved only by an Architect; Bo holds no role"),
    (("Project Manager", "BAU Lead"), "Design can be approved only by an Architect; Bo holds Project Manager, BAU Lead"),
])
def test_the_refusal_names_the_role_needed_and_what_the_person_holds(roles, sentence):
    with pytest.raises(NotAllowed) as e:
        deciding_role(Users(person("Root", "Administrator"), person("Bo", *roles)), "human:Bo", "design", "Design")
    assert str(e.value) == sentence


def test_the_article_follows_the_first_letter_and_several_roles_are_joined_with_or():
    users = Users(person("Root", "Administrator"), approvers={"design": ("Architect", "Technical Lead", "BAU Lead")})
    with pytest.raises(NotAllowed, match="by an Architect or a Technical Lead or a BAU Lead; Root holds Administrator"):
        deciding_role(users, "human:Root", "design", "Design")


def test_the_verb_is_the_one_asked_for():
    with pytest.raises(NotAllowed, match="can be sent back only by"):
        deciding_role(Users(person("Bo", "BAU Lead")), "human:Bo", "design", "Design", "sent back")


def test_a_stranger_and_a_switched_off_person_are_told_to_ask_an_administrator():
    users = Users(person("Root", "Administrator"), person("Off", "Architect", active=False))
    for who in ("Stranger", "Off"):
        with pytest.raises(NotAllowed, match=rf"and {who} is not on the Users list; ask an Administrator to add you$"):
            deciding_role(users, f"human:{who}", "design", "Design")


def test_the_role_recorded_is_the_first_allowed_one_in_the_fixed_order_whatever_order_the_phase_lists_them():
    users = Users(person("Mix", "Technical Lead", "Architect"), approvers={"design": ("Technical Lead", "Architect")})
    assert deciding_role(users, "human:Mix", "design", "Design") == "Architect"
