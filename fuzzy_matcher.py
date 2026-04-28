from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, asdict
from typing import Iterable


ALIAS_MAP = {
    "gnd": {"gnd", "ground", "vss", "0v", "pgnd", "agnd", "dgnd"},
    "vcc": {"vcc", "vdd", "vin", "vbat", "vbus", "power"},
    "3v3": {"3v3", "33v", "3.3v", "+3.3v", "vdd3v3", "vcc3v3"},
    "5v": {"5v", "+5v", "vcc5v", "vdd5v"},
}


@dataclass
class MatchResult:
    ok: bool
    requested: str
    matched: str | None
    score: float
    threshold: float
    reason: str
    candidates: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_label(value: str) -> str:
    value = str(value).strip().lower()
    value = value.replace("+", "")
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def _alias_group(value: str) -> set[str]:
    norm = normalize_label(value)

    for group in ALIAS_MAP.values():
        normalized_group = {normalize_label(x) for x in group}
        if norm in normalized_group:
            return normalized_group

    return {norm}


def fuzzy_match(
    requested: str,
    candidates: Iterable[str],
    threshold: float = 0.92,
) -> MatchResult:
    candidates_list = [str(c) for c in candidates]
    req_norm = normalize_label(requested)

    if not candidates_list:
        return MatchResult(
            ok=False,
            requested=requested,
            matched=None,
            score=0.0,
            threshold=threshold,
            reason="NO_CANDIDATES",
            candidates=[],
        )

    # Exact normalized match.
    for candidate in candidates_list:
        if normalize_label(candidate) == req_norm:
            return MatchResult(
                ok=True,
                requested=requested,
                matched=candidate,
                score=1.0,
                threshold=threshold,
                reason="EXACT_NORMALIZED_MATCH",
                candidates=candidates_list,
            )

    # Alias match.
    req_aliases = _alias_group(requested)
    for candidate in candidates_list:
        if normalize_label(candidate) in req_aliases:
            return MatchResult(
                ok=True,
                requested=requested,
                matched=candidate,
                score=0.95,
                threshold=threshold,
                reason="HIGH_CONFIDENCE_ALIAS_MATCH",
                candidates=candidates_list,
            )

    # Similarity match.
    best_candidate = None
    best_score = 0.0

    for candidate in candidates_list:
        score = difflib.SequenceMatcher(None, req_norm, normalize_label(candidate)).ratio()
        if score > best_score:
            best_score = score
            best_candidate = candidate

    if best_score >= threshold:
        return MatchResult(
            ok=True,
            requested=requested,
            matched=best_candidate,
            score=round(best_score, 4),
            threshold=threshold,
            reason="FUZZY_MATCH_ACCEPTED",
            candidates=candidates_list,
        )

    return MatchResult(
        ok=False,
        requested=requested,
        matched=None,
        score=round(best_score, 4),
        threshold=threshold,
        reason="FAILED_UNCERTAIN_MATCH",
        candidates=candidates_list,
    )
