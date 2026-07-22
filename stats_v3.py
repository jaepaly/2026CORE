"""Pre-registered paired endpoint analysis for v3 artifacts."""

from math import comb
from random import Random


def _pair_key(event: dict) -> tuple:
    return (event["model"], event["scenario"], event["seed"], event["retry_index"])


def _exact_mcnemar_p(a_only: int, c_only: int) -> float:
    discordant = a_only + c_only
    if discordant == 0:
        return 1.0
    tail = sum(comb(discordant, index) for index in range(min(a_only, c_only) + 1)) / (2 ** discordant)
    return min(1.0, 2 * tail)


def paired_bootstrap_mean_difference(
    pairs: list[tuple[float, float]], *, iterations: int, seed: int
) -> dict:
    """Paired bootstrap CI for count outcomes; values are (A, C) pairs."""
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


def analyze_primary_safe_completion(validation_events: list[dict]) -> dict:
    """Analyze the A/C endpoint using only valid, complete pairs."""
    outcomes: dict[tuple, dict[str, bool]] = {}
    all_keys = set()
    for event in validation_events:
        if event.get("condition") not in {"A", "C"}:
            continue
        key = _pair_key(event)
        all_keys.add(key)
        if event.get("validation_status") != "valid" or not isinstance(event.get("safe_completion"), bool):
            continue
        if event["condition"] in outcomes.setdefault(key, {}):
            raise ValueError("duplicate validation outcome for paired run key")
        outcomes[key][event["condition"]] = event["safe_completion"]

    pairs = [outcome for outcome in outcomes.values() if set(outcome) == {"A", "C"}]
    a_only = sum(pair["A"] and not pair["C"] for pair in pairs)
    c_only = sum(pair["C"] and not pair["A"] for pair in pairs)
    count = len(pairs)
    risk_difference = (sum(pair["A"] for pair in pairs) - sum(pair["C"] for pair in pairs)) / count if count else None
    return {
        "comparison": ["A", "C"],
        "endpoint": "safe_completion",
        "paired_valid_run_count": count,
        "a_only_success_count": a_only,
        "c_only_success_count": c_only,
        "paired_risk_difference_a_minus_c": risk_difference,
        "mcnemar_exact_two_sided_p": _exact_mcnemar_p(a_only, c_only),
        "excluded_unpaired_or_invalid_count": len(all_keys) - count,
    }
