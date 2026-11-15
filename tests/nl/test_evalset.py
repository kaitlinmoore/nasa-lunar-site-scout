# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""The eval set loads, and every ready label is itself valid against the contract and registry."""

from __future__ import annotations

import re

import pytest

from lss.nl.evalset import ItemStatus, Source, load_eval_set
from lss.nl.schema import NLLimitation, NLOutput, Outcome
from lss.nl.validate import default_context, validate_output
from lss.nl.vocabulary import HeightSource

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
    """Assemble the label into an NL output and run it through the same validator the LLM faces."""
    exp = item.expected
    limitations = []
    if exp.outcome != Outcome.answer:
        limitations = [NLLimitation(topic="label", citations=exp.citations + exp.citations_optional)]
    output = NLOutput(
        outcome=exp.outcome,
        interpretation=item.text,
        query=exp.query,
        height_source=exp.height_source or HeightSource.not_applicable,
        limitations=limitations,
    )
    if exp.params_match == "subset":
        pytest.skip("subset labels are not complete queries")
    validate_output(output, default_context(selected_site_id=item.context.selected_site_id))
