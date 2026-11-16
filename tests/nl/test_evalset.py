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
    assert by_id["k6"].blocked_reasons == ["blocked on contract"]  # C3 filter/rank
    assert by_id["k7"].blocked_reasons == ["blocked on contract"]
    assert by_id["k5"].blocked_reasons == []


def test_only_the_filter_rank_items_are_still_blocked():
    """Contract 0.7.0 and the registry batch (03d24f4) unblocked everything except C3."""
    blocked = {i.id: i.blocked_on for i in EVAL.items if i.status == ItemStatus.blocked}
    assert blocked == {"k6": ["C3"], "k7": ["C3"]}


def test_clarify_label_is_scored_in_a():
    from lss.nl.eval import oracle_provider, run_item

    item = next(i for i in EVAL.items if i.id == "k1-no-site")
    res = run_item(item, oracle_provider(EVAL), EVAL)
    assert res.outcome == "clarify" and res.query_correct is True and res.reason_correct is None


def test_clarify_count_is_reported_inside_a():
    from lss.nl.eval import oracle_provider, run_eval

    report = run_eval(oracle_provider(EVAL), EVAL)
    a = report["scores"]["a_structured_query"]
    assert a["of_which_clarify"] == {"correct": 1, "total": 1}
    assert report["scores_by_split"]["holdout"]["a_structured_query"]["of_which_clarify"]["total"] == 0


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
    assert all(i.status == ItemStatus.ready for i in holdout)  # s11 unblocked by the registry batch
    assert "s13" not in {i.id for i in holdout}  # label changed after its output was seen


@pytest.mark.parametrize(
    "alternative, ok",
    [
        (
            {
                "dataset_id": "diviner_polar_temperature",
                "cannot_answer": "Temperatures equatorward of 80° (the tool has not integrated a Diviner "
                "product for that range)",
            },
            True,
        ),
        (
            {
                "dataset_id": "lss_tool_capabilities",
                "cannot_answer": "Temperature queries (not available yet)",
            },
            True,
        ),
        (None, False),
    ],
)
def test_k8_accepts_either_temperature_citation(alternative, ok):
    from lss.nl.eval import run_item
    from lss.nl.provider import FakeProvider

    item = next(i for i in EVAL.items if i.id == "k8")
    thermal = {
        "dataset_id": "diviner_polar_temperature",
        "cannot_answer": (
            "Spacecraft thermal or battery-heating requirements (needs a spacecraft thermal model)"
        ),
    }
    cites = [thermal] + ([alternative] if alternative else [])
    out = {
        "outcome": "unsupported",
        "interpretation": "i",
        "limitations": [{"topic": "t", "citations": cites}],
    }
    res = run_item(item, FakeProvider({item.text: out}), EVAL)
    assert res.reason_correct is ok
