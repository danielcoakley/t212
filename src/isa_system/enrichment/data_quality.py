"""Data quality scoring for enrichment packets."""

from __future__ import annotations

from datetime import datetime

from isa_system.utils.time import now_utc


def score_data_quality(
    sections: dict[str, object | None],
    *,
    retrieved_at_utc: datetime | None = None,
) -> dict[str, object]:
    """Score freshness and missing sections for an enrichment packet."""

    retrieved_at_utc = retrieved_at_utc or now_utc()
    total = len(sections)
    present = sum(1 for value in sections.values() if value not in (None, {}, []))
    missing = [name for name, value in sections.items() if value in (None, {}, [])]
    missing_penalty = (len(missing) / total) * 60 if total else 0
    age_hours = max(0.0, (now_utc() - retrieved_at_utc).total_seconds() / 3600)
    freshness_penalty = min(20.0, age_hours / 24)
    score = max(0.0, min(100.0, 100.0 - missing_penalty - freshness_penalty))
    explanations = []
    if missing:
        explanations.append(f"Missing sections: {', '.join(missing)}")
    else:
        explanations.append("All attempted enrichment sections were present.")
    return {
        "score": round(score, 2),
        "missing_sections": missing,
        "present_sections": present,
        "attempted_sections": total,
        "freshness_age_hours": round(age_hours, 2),
        "explanations": explanations,
    }
