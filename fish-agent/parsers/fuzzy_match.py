from dataclasses import dataclass

from rapidfuzz import fuzz, process

from config import settings


@dataclass
class MatchResult:
    canonical_name: str
    score: float
    product_id: int | None = None


def normalize_product_name(
    raw: str, products: list[tuple[int, str, list[str]]], threshold: int | None = None
) -> MatchResult | None:
    """
    Map a raw name from a parser/supplier message to the canonical product name.

    products: list of (id, canonical_name, aliases)
    Returns MatchResult with the best match, or None if score < threshold.
    """
    if threshold is None:
        threshold = settings.fuzzy_match_threshold

    raw_lower = raw.lower().strip()

    # Build a flat lookup: normalized_string -> (product_id, canonical_name)
    candidates: dict[str, tuple[int, str]] = {}
    for pid, canonical, aliases in products:
        candidates[canonical.lower()] = (pid, canonical)
        for alias in aliases:
            candidates[alias.lower()] = (pid, canonical)

    if not candidates:
        return None

    result = process.extractOne(
        raw_lower,
        list(candidates.keys()),
        scorer=fuzz.token_sort_ratio,
        score_cutoff=threshold,
    )
    if result is None:
        return None

    matched_key, score, _ = result
    pid, canonical = candidates[matched_key]
    return MatchResult(canonical_name=canonical, score=score, product_id=pid)
