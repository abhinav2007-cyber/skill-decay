"""
strength_report.py — §10.2 deterministic stats + §10.3 AI analysis (LLM call #3).

Responsibility:
  - §10.2: per-sub-topic and per-skill mastery %, category, trend
  - §10.3: AI-generated analyst-style summary (separate Featherless.ai call)
  MUST NOT: be folded into the Decision Agent prompt (§10.3 note).

"Effective mastery" = knowledge_probability if tracking_mode == 'bkt',
  else 1 - decay_score as proxy — stated explicitly in comments as a real
  modeling choice: decay captures a different dimension than BKT mastery;
  the proxy makes the UI useful even before BKT activates.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import SubTopicState, get_simulated_now
from backend.domain import all_sub_topics, SKILL_NAMES
from backend.services.signal_engine import get_trend_for_subtopic
from backend.services.featherless_client import chat_complete, FeatherlessAllKeysFailedError

logger = logging.getLogger(__name__)


def _effective_mastery(state: SubTopicState) -> float:
    """
    §10.2: Effective mastery % for a sub-topic.
      - If tracking_mode == 'bkt': use knowledge_probability (range [0,1])
      - Else: use (1 - decay_score) as the best available proxy.
        NOTE: This is a modeling approximation — decay captures time-since-use,
        not actual skill mastery. BKT is the gold standard when available.
        The proxy exists solely to make the UI useful in cold_start/decay_fallback.
    """
    if state.tracking_mode == "bkt" and state.knowledge_probability is not None:
        return state.knowledge_probability
    # Proxy: higher decay → lower effective mastery
    return max(0.0, round(1.0 - state.decay_score, 4))


def get_strength_report(db: Session, user_id: str) -> dict:
    """
    §10.2: Returns per-skill and per-sub-topic mastery stats.
    Includes trend (§6.2) per sub-topic.
    """
    report: dict = {
        "user_id": user_id,
        "skills": {},
        "sub_topics": {},
    }

    for skill in SKILL_NAMES:
        skill_sub_topics = [
            (st, cat)
            for s, st, cat in all_sub_topics()
            if s == skill
        ]
        skill_mastery_values = []

        for sub_topic, category in skill_sub_topics:
            state = db.query(SubTopicState).filter_by(
                user_id=user_id, skill=skill, sub_topic=sub_topic
            ).first()

            if state is None:
                mastery = 0.0
                mode = "cold_start"
                trend = "insufficient_data"
                obs_count = 0
            else:
                mastery = _effective_mastery(state)
                mode = state.tracking_mode
                trend = get_trend_for_subtopic(db, user_id, skill, sub_topic)
                obs_count = state.observation_count

            pct = round(mastery * 100, 1)
            skill_mastery_values.append(mastery)

            report["sub_topics"][sub_topic] = {
                "skill":             skill,
                "category":          category,
                "tracking_mode":     mode,
                "mastery_pct":       pct,
                "observation_count": obs_count,
                "trend":             trend,
            }

        # Skill-level mastery = average of its two sub-topics' effective mastery
        skill_avg = round(
            sum(skill_mastery_values) / len(skill_mastery_values) * 100, 1
        ) if skill_mastery_values else 0.0

        report["skills"][skill] = {
            "mastery_pct":  skill_avg,
            "sub_topics":   [st for st, _ in skill_sub_topics],
        }

    return report


_cached_ai_summary: Optional[str] = None
_cached_stats_fingerprint: Optional[str] = None


def _get_stats_fingerprint(stats: dict) -> str:
    """Generate a lightweight fingerprint of current mastery levels to detect meaningful changes."""
    items = []
    for st, d in sorted(stats.get("sub_topics", {}).items()):
        items.append(f"{st}:{d.get('mastery_pct', 0)}:{d.get('trend', '')}")
    return "|".join(items)


def generate_deterministic_summary(stats: dict) -> str:
    """Fast, zero-credit diagnostic summary derived directly from statistics."""
    sub_topics = stats.get("sub_topics", {})
    if not sub_topics:
        return "No diagnostic telemetry recorded yet. Complete quizzes to generate skill trajectory insights."

    sorted_st = sorted(sub_topics.items(), key=lambda x: x[1].get("mastery_pct", 0))
    weakest = sorted_st[0]
    second_weak = sorted_st[1] if len(sorted_st) > 1 else None

    weakest_name = weakest[0]
    weakest_pct = weakest[1].get("mastery_pct", 0)

    declining = [st for st, data in sub_topics.items() if data.get("trend") == "declining"]

    parts = [
        f"Skill diagnostic analysis highlights foundational review needed in {weakest_name} at {weakest_pct}% mastery."
    ]
    if second_weak and second_weak[1].get("mastery_pct", 0) < 50:
        parts.append(f"Secondary attention is advised for {second_weak[0]} ({second_weak[1].get('mastery_pct', 0)}% mastery).")
    if declining:
        parts.append(f"Declining retention trends were flagged in {', '.join(declining)}.")
    parts.append(f"Priority recommendation: Focus targeted practice on {weakest_name} to restore retention before advancing to complex topics.")

    return " ".join(parts)


def generate_ai_summary(stats: dict, force: bool = False) -> str:
    """
    §10.3: Featherless.ai call #3 — analyst-style summary of weakest area(s).
    Uses caching to conserve API credits and respond instantaneously when stats haven't changed.
    """
    global _cached_ai_summary, _cached_stats_fingerprint

    fingerprint = _get_stats_fingerprint(stats)

    # Return cached summary if available and stats haven't changed (0 credits consumed)
    if not force and _cached_ai_summary and _cached_stats_fingerprint == fingerprint:
        logger.info("Serving cached AI summary (0 credits consumed)")
        return _cached_ai_summary

    # Build a text summary of the stats for the prompt
    sub_topic_lines = []
    for st, data in stats.get("sub_topics", {}).items():
        sub_topic_lines.append(
            f"  - {data['skill']} / {st}: {data['mastery_pct']}% mastery "
            f"(mode={data['tracking_mode']}, trend={data['trend']})"
        )
    sub_topics_text = "\n".join(sub_topic_lines)

    skill_lines = []
    for skill, data in stats.get("skills", {}).items():
        skill_lines.append(f"  - {skill}: {data['mastery_pct']}% overall")
    skills_text = "\n".join(skill_lines)

    prompt = f"""You are a professional learning analyst. Provide a brief 3-sentence executive skill summary:
1. Identify the weakest sub-topic and its mastery percentage.
2. Note any declining retention trend or bright spot.
3. State a concrete next-step recommendation.

Telemetry:
{sub_topics_text}
Overall skills: {skills_text}
Keep it concise, direct, under 60 words."""

    try:
        summary = chat_complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150,
            call_site="strength_report",
        )
        result = summary.strip()
        _cached_ai_summary = result
        _cached_stats_fingerprint = fingerprint
        return result
    except FeatherlessAllKeysFailedError as exc:
        logger.error("Strength report AI summary failed (all keys): %s", exc)
        return generate_deterministic_summary(stats)
    except Exception as exc:
        logger.error("Strength report AI summary error: %s", exc)
        return generate_deterministic_summary(stats)
