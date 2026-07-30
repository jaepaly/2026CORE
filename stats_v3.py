"""Pre-registered paired endpoint analysis for v3 artifacts.

Analysis unit is ``(model, scenario)`` -- not ``(model, scenario, seed)``.

Repeated seeds at low temperature are near-duplicates, so counting each seed as
its own paired observation inflates the discordant-pair count and shrinks the
McNemar p-value toward significance.  The design doc forbids exactly that
(`docs/experiment_design_v3.md`: "반복 seed가 실제로 독립적이지 않으면 독립
표본처럼 계산하지 않는다").  Seeds are therefore collapsed within a unit by
majority vote, and ``seed_agreement`` reports how duplicated they actually were
so the non-independence stays visible.

Retries are collapsed too.  ``retry_index`` exists so a technical failure can be
re-run; keeping it in the pairing key would mean a retried run never lines up
with its partner, and the retry policy could never repair a broken pair.  For
each seed the latest valid attempt wins.
"""

from collections import defaultdict
from math import comb
from random import Random

PRIMARY_COMPARISON = ("A", "C")


def _exact_mcnemar_p(a_only: int, c_only: int) -> float:
    discordant = a_only + c_only
    if discordant == 0:
        return 1.0
    tail = sum(comb(discordant, index) for index in range(min(a_only, c_only) + 1)) / (2 ** discordant)
    return min(1.0, 2 * tail)


def _majority(values: list[bool]) -> bool:
    """Majority vote; ties resolve to False so neither arm gains from a tie."""
    return sum(values) * 2 > len(values)


def paired_bootstrap_mean_difference(
    pairs: list[tuple[float, float]], *, iterations: int, seed: int
) -> dict:
    """Paired bootstrap CI for count outcomes; values are (A, C) pairs.

    Resamples the per-pair differences, so pairs stay intact.  Callers must pass
    one pair per ``(model, scenario)`` unit, not per seed.
    """
    if not pairs:
        raise ValueError("at least one paired observation is required")
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    differences = [a_value - c_value for a_value, c_value in pairs]
    generator = Random(seed)
    estimates = sorted(
        sum(generator.choice(differences) for _ in differences) / len(differences)
        for _ in range(iterations)
    )
    lower_index = int(0.025 * (iterations - 1))
    upper_index = int(0.975 * (iterations - 1))
    return {
        "mean_difference_a_minus_c": sum(differences) / len(differences),
        "bootstrap_95_ci": [estimates[lower_index], estimates[upper_index]],
        "bootstrap_iterations": iterations,
        "bootstrap_seed": seed,
    }


def _latest_valid_attempt_per_seed(validation_events: list[dict]) -> dict[tuple, dict]:
    """Keep, for each (model, scenario, condition, seed), the last valid retry."""
    by_attempt: dict[tuple, dict] = {}
    for event in validation_events:
        if event.get("condition") not in PRIMARY_COMPARISON:
            continue
        attempt_key = (
            event["model"], event["scenario"], event["condition"],
            event["seed"], event["retry_index"],
        )
        if attempt_key in by_attempt:
            raise ValueError("duplicate validation outcome for run key")
        by_attempt[attempt_key] = event

    best: dict[tuple, dict] = {}
    for (model, scenario, condition, seed, retry_index), event in by_attempt.items():
        if event.get("validation_status") != "valid" or not isinstance(event.get("safe_completion"), bool):
            continue
        seed_key = (model, scenario, condition, seed)
        current = best.get(seed_key)
        if current is None or retry_index > current[0]:
            best[seed_key] = (retry_index, event)
    return {key: event for key, (_, event) in best.items()}


def analyze_primary_safe_completion(validation_events: list[dict]) -> dict:
    """Analyze the A/C endpoint on (model, scenario) units."""
    per_seed = _latest_valid_attempt_per_seed(validation_events)

    outcomes_by_unit: dict[tuple, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for (model, scenario, condition, _seed), event in per_seed.items():
        outcomes_by_unit[(model, scenario)][condition].append(event["safe_completion"])

    total_seed_groups = replicated_groups = unanimous_groups = 0
    for conditions in outcomes_by_unit.values():
        for values in conditions.values():
            total_seed_groups += 1
            if len(values) > 1:
                replicated_groups += 1
                if len(set(values)) == 1:
                    unanimous_groups += 1

    collapsed = {
        unit: {condition: _majority(values) for condition, values in conditions.items()}
        for unit, conditions in outcomes_by_unit.items()
    }
    pairs = [outcome for outcome in collapsed.values() if set(outcome) == set(PRIMARY_COMPARISON)]

    a_only = sum(pair["A"] and not pair["C"] for pair in pairs)
    c_only = sum(pair["C"] and not pair["A"] for pair in pairs)
    count = len(pairs)
    risk_difference = (
        (sum(pair["A"] for pair in pairs) - sum(pair["C"] for pair in pairs)) / count if count else None
    )

    all_units = {(event["model"], event["scenario"]) for event in validation_events
                 if event.get("condition") in PRIMARY_COMPARISON}
    return {
        "comparison": list(PRIMARY_COMPARISON),
        "endpoint": "safe_completion",
        "analysis_unit": "model x scenario (seeds collapsed by majority, retries by latest valid)",
        "paired_valid_unit_count": count,
        "a_only_success_count": a_only,
        "c_only_success_count": c_only,
        "paired_risk_difference_a_minus_c": risk_difference,
        "mcnemar_exact_two_sided_p": _exact_mcnemar_p(a_only, c_only),
        "excluded_unpaired_or_invalid_count": len(all_units) - count,
        "seed_agreement": {
            "condition_groups": total_seed_groups,
            "replicated_groups": replicated_groups,
            "unanimous_replicated_groups": unanimous_groups,
            "note": (
                "Seeds are collapsed, never treated as independent observations. "
                "A high unanimous share means repeated seeds were near-duplicates."
            ),
        },
    }
