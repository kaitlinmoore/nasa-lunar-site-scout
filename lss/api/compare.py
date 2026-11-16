"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Filter and rank on POST /api/compare (contract 0.10.0, NL gap C3; Kaitlin's decisions 2026-11-16, recorded
in reference/logs/c3-design.md). Pure functions over served results: nothing here computes a new physical
quantity. Values come from the served MetricsResponse, the precomputed slope statistics, or (for
SunElevationBand) stream A's Sun-elevation histogram in format-3 served files (RA7); null without one.

Rules:
- `across` expands into one scenario per curated site, in registry order, after the request's `scenarios`;
- a filter on a null value never passes: the scenario is listed with the metric as not computed;
- a rank excludes null values the same way; equal values keep the compared order and are reported as ties;
- `rank.limit` keeps the first N and counts the rest.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta

from lss.contract import (
    CompareAcross,
    CompareFilteredOut,
    CompareMetric,
    CompareRank,
    EvaluatedValue,
    FilterOp,
    MetricFilter,
    MetricName,
    MetricsResponse,
    RankOrder,
    Scenario,
    Site,
    SunElevationBand,
)

OPS: dict[FilterOp, Callable[[float, float], bool]] = {
    FilterOp.lt: operator.lt,
    FilterOp.le: operator.le,
    FilterOp.gt: operator.gt,
    FilterOp.ge: operator.ge,
    FilterOp.eq: operator.eq,
}


class UnknownSitesError(ValueError):
    """`across` names a site id or region the registry doesn't have."""


def label(metric: CompareMetric) -> str:
    return metric.label() if isinstance(metric, SunElevationBand) else metric.value


def expand(across: CompareAcross, sites: Sequence[Site]) -> list[Scenario]:
    """One scenario per selected curated site (registry order)."""
    if across.site_ids:
        known = {s.id for s in sites}
        unknown = [i for i in across.site_ids if i not in known]
        if unknown:
            raise UnknownSitesError(f"unknown site id(s): {', '.join(unknown)}")
        chosen = [s for s in sites if s.id in set(across.site_ids)]
    elif across.region:
        chosen = [s for s in sites if across.region in s.regions]
        if not chosen:
            raise UnknownSitesError(f"no curated site is tagged with region {across.region!r}")
    else:
        chosen = list(sites)
    end = across.window_end or across.window_start + timedelta(days=across.window_days or 0)
    return [
        Scenario(
            location=s.location,
            unit_height_m=across.unit_height_m,
            window_start=across.window_start,
            window_end=end,
            step=across.step,
        )
        for s in chosen
    ]


SlopeAt = Callable[[float, float], tuple[float, str] | None]  # (slope deg, the map it was measured on)
BandAt = Callable[[str, float, float], float | None]  # (scenario key, min deg, max deg) -> fraction


def no_band(key: str, a: float, b: float) -> None:
    return None


def value_of(
    metric: CompareMetric, m: MetricsResponse, slope_at: SlopeAt, band_at: BandAt = no_band
) -> float | None:
    """The metric's value for one served result, or None (not computed / not available)."""
    if isinstance(metric, SunElevationBand):
        return band_at(m.scenario_key, metric.min_deg, metric.max_deg)
    if metric == MetricName.slope_at_point_deg:
        hit = slope_at(m.scenario.location.lat, m.scenario.location.lon)
        return hit[0] if hit else None
    node: object = m
    for part in metric.value.split("."):
        node = getattr(node, part, None)
        if node is None:
            return None
    return float(node) if isinstance(node, int | float) and not isinstance(node, bool) else None


@dataclass
class Outcome:
    items: list[MetricsResponse]
    evaluated: list[EvaluatedValue] = field(default_factory=list)
    filtered_out: list[CompareFilteredOut] = field(default_factory=list)
    rank_ties: list[list[str]] = field(default_factory=list)
    beyond_limit: int = 0


def apply(
    served: Sequence[tuple[int, MetricsResponse]],
    filters: Sequence[MetricFilter],
    rank: CompareRank | None,
    slope_at: SlopeAt,
    band_at: BandAt = no_band,
) -> Outcome:
    """Filter, then rank, the served results (`served`: (compared index, metrics), in compared order)."""
    metrics: dict[str, CompareMetric] = {label(f.metric): f.metric for f in filters}
    if rank is not None:
        metrics.setdefault(label(rank.metric), rank.metric)
    values: dict[int, Mapping[str, float | None]] = {
        i: {lab: value_of(metric, m, slope_at, band_at) for lab, metric in metrics.items()} for i, m in served
    }
    out = Outcome(items=[])
    for i, m in served:
        for lab, v in values[i].items():
            source = None
            if lab == MetricName.slope_at_point_deg.value and v is not None:
                hit = slope_at(m.scenario.location.lat, m.scenario.location.lon)
                source = hit[1] if hit else None
            out.evaluated.append(
                EvaluatedValue(scenario_key=m.scenario_key, metric=lab, value=v, source=source)
            )

    passing: list[tuple[int, MetricsResponse]] = []
    for i, m in served:
        failed, missing = [], []
        for f in filters:
            v = values[i][label(f.metric)]
            if v is None:
                missing.append(label(f.metric))
            elif not OPS[f.op](v, f.value):
                failed.append(label(f.metric))
        if rank is not None and values[i][label(rank.metric)] is None:
            missing.append(label(rank.metric))
        missing = list(dict.fromkeys(missing))
        if failed or missing:
            out.filtered_out.append(
                CompareFilteredOut(index=i, scenario_key=m.scenario_key, failed=failed, not_computed=missing)
            )
        else:
            passing.append((i, m))

    if rank is not None:
        lab = label(rank.metric)
        sign = -1.0 if rank.order == RankOrder.desc else 1.0
        passing.sort(key=lambda im: sign * values[im[0]][lab])  # stable: ties keep the compared order
        groups: dict[float, list[str]] = {}
        for i, m in passing:
            groups.setdefault(values[i][lab], []).append(m.scenario_key)
        out.rank_ties = [keys for keys in groups.values() if len(keys) > 1]
        if rank.limit is not None and len(passing) > rank.limit:
            out.beyond_limit = len(passing) - rank.limit
            passing = passing[: rank.limit]
    out.items = [m for _, m in passing]
    return out
