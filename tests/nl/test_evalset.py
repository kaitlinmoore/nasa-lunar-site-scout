# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""The eval set loads, and every ready label is itself valid against the contract and registry."""

from __future__ import annotations

import re

import pytest

from lss.nl.evalset import ItemStatus, Source, label_output, load_eval_set
from lss.nl.validate import default_context, validate_output

EVAL = load_eval_set()
READY = [i for i in EVAL.items if i.status == ItemStatus.ready]
KNOWN_BLOCKERS = re.compile(r"^(C[1-8]|G-R[1-4]|D-[a-z-]+)$")


def test_kaitlins_nine_queries_are_all_present():
    texts = {i.text for i in EVAL.items if i.source == Source.kaitlin}
    assert len(texts) == 9


def test_blockers_are_known_request_ids():
    for item in EVAL.items:
        for b in item.blocked_on:
            assert KNOWN_BLOCKERS.match(b), (item.id, b)


def test_contract_blocked_items_are_labeled():
    by_id = {i.id: i for i in EVAL.items}
    assert "blocked on contract" in by_id["k2"].blocked_reasons
    assert by_id["k8"].blocked_reasons == ["blocked on registry"]
    assert by_id["k5"].blocked_reasons == []


@pytest.mark.parametrize("item", READY, ids=lambda i: i.id)
def test_ready_label_passes_validation(item):
    """Every ready label, as an NL output, passes the same validator the LLM faces."""
    output = label_output(item)
    if output is None:
        pytest.skip("subset labels are not complete queries")
    ctx = default_context(selected_site_id=item.context.selected_site_id, today=EVAL.reference_date)
    validate_output(output, ctx)


def test_si_supplied_items_are_marked():
    si = [i.id for i in EVAL.items if i.source == Source.si_supplied]
    assert si == [f"s{n}" for n in range(1, 17)]


def test_holdout_set_covers_answers_and_refusals():
    holdout = [i for i in EVAL.items if i.split.value == "holdout"]
    assert {i.id for i in holdout} == {"s3", "s5", "s8", "s11", "s16"}
    assert all(i.source == Source.si_supplied for i in holdout)
    outcomes = {i.expected.outcome.value for i in holdout}
    assert {"answer", "unsupported"} <= outcomes
    assert "s13" not in {i.id for i in holdout}  # label changed after its output was seen
