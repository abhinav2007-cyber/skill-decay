"""
skill_analyzer.py — Featherless AI-powered skill analysis service.

Given a raw user-entered skill name (e.g. "Advanced SQL", "React.js", "Cloud Computing"),
calls Featherless to:
  1. Normalize the skill name
  2. Suggest relevant sub-topics with procedural/conceptual classification
  3. Suggest assessment areas
  4. Provide a brief explanation

Returns a structured dict ready to send to the frontend for user confirmation.
"""

import json
import logging
import re
from typing import Optional

from backend.services.featherless_client import chat_complete, FeatherlessAllKeysFailedError

logger = logging.getLogger(__name__)


# ── Fallback sub-topics when AI fails ─────────────────────────────────────────
def _generic_fallback(skill_name: str) -> dict:
    """Return a minimal valid analysis when Featherless is unavailable."""
    slug = skill_name.lower().replace(" ", "_").replace(".", "").replace("-", "_")
    return {
        "skill": skill_name,
        "normalized_name": skill_name,
        "sub_topics": [
            {"key": f"{slug}_fundamentals", "label": f"{skill_name} Fundamentals", "category": "conceptual"},
            {"key": f"{slug}_practical_application", "label": f"{skill_name} Practical Application", "category": "procedural"},
        ],
        "assessment_areas": [f"{skill_name} Basics", f"{skill_name} Practice"],
        "explanation": f"Core foundational and practical components of {skill_name}.",
        "ai_generated": False,
    }


def _slugify(text: str) -> str:
    """Convert a label to a safe snake_case key."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text[:60]


def _parse_ai_response(raw: str, skill_name: str) -> Optional[dict]:
    """
    Parse the AI JSON response. Handles both clean JSON and JSON embedded in text.
    Returns None if parsing fails.
    """
    # Try to extract JSON block if it's wrapped in markdown fences
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if json_match:
        raw = json_match.group(1)
    else:
        # Try to find a bare JSON object
        brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if brace_match:
            raw = brace_match.group(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[skill_analyzer] Failed to parse AI JSON response")
        return None

    # Validate and normalize sub_topics
    sub_topics = data.get("sub_topics", [])
    valid_topics = []
    for st in sub_topics:
        if not isinstance(st, dict):
            continue
        label = str(st.get("label") or st.get("name") or "").strip()
        if not label:
            continue
        category = str(st.get("category", "conceptual")).lower()
        if category not in ("procedural", "conceptual"):
            category = "conceptual"
        key = _slugify(str(st.get("key") or label))
        valid_topics.append({"key": key, "label": label, "category": category})

    # Require at least 1 sub-topic
    if not valid_topics:
        return None

    # Clamp to 6 max sub-topics
    valid_topics = valid_topics[:6]

    return {
        "skill": str(data.get("normalized_name") or data.get("skill") or skill_name).strip(),
        "normalized_name": str(data.get("normalized_name") or data.get("skill") or skill_name).strip(),
        "sub_topics": valid_topics,
        "assessment_areas": [str(a) for a in data.get("assessment_areas", [])[:6]],
        "explanation": str(data.get("explanation") or "").strip()[:400],
        "ai_generated": True,
    }


def analyze_skill(skill_name: str) -> dict:
    """
    Main entry point: analyze a user-entered skill name.

    Args:
        skill_name: Raw user input, e.g. "Advanced SQL", "React.js", "AWS"

    Returns:
        A dict with keys: skill, normalized_name, sub_topics, assessment_areas,
        explanation, ai_generated.
    """
    skill_name = skill_name.strip()
    if not skill_name or len(skill_name) > 120:
        return _generic_fallback(skill_name or "New Skill")

    prompt = f"""You are an expert learning curriculum designer and skill taxonomy specialist.

A student wants to track their learning and skill decay for: "{skill_name}"

Analyze this skill and respond with ONLY a valid JSON object (no extra text, no markdown):

{{
  "normalized_name": "<clean, properly capitalized skill name>",
  "sub_topics": [
    {{"key": "<snake_case_key>", "label": "<Human Readable Label>", "category": "procedural"}},
    {{"key": "<snake_case_key>", "label": "<Human Readable Label>", "category": "conceptual"}},
    {{"key": "<snake_case_key>", "label": "<Human Readable Label>", "category": "procedural"}},
    {{"key": "<snake_case_key>", "label": "<Human Readable Label>", "category": "conceptual"}}
  ],
  "assessment_areas": ["<Topic 1>", "<Topic 2>", "<Topic 3>", "<Topic 4>"],
  "explanation": "<One sentence explaining why these sub-topics are relevant for tracking skill decay.>"
}}

Rules:
- Generate 3-5 sub_topics total, balanced between procedural and conceptual
- "procedural" = hands-on syntax/implementation skills (fast decay, ~14 day half-life)
- "conceptual" = theoretical/architectural understanding (slow decay, ~45 day half-life)
- Keys must be lowercase snake_case, no spaces, no special chars
- assessment_areas are short topic names for MCQ test generation (3-5 items)
- Keep the explanation under 100 words
- Respond with ONLY the JSON object, no other text"""

    messages = [
        {
            "role": "system",
            "content": "You are a precise JSON-generating curriculum design assistant. Output only valid JSON, never markdown or extra text."
        },
        {
            "role": "user",
            "content": prompt,
        }
    ]

    try:
        raw_response = chat_complete(
            messages=messages,
            temperature=0.2,
            max_tokens=2048,
            call_site="skill_analyzer",
        )
        parsed = _parse_ai_response(raw_response, skill_name)
        if parsed:
            logger.info("[skill_analyzer] Successfully analyzed skill: %s", skill_name)
            return parsed
        else:
            logger.warning("[skill_analyzer] AI response unparseable, using fallback for: %s", skill_name)
            return _generic_fallback(skill_name)

    except FeatherlessAllKeysFailedError as exc:
        logger.error("[skill_analyzer] All Featherless keys failed: %s", exc)
        return _generic_fallback(skill_name)
    except Exception as exc:
        logger.error("[skill_analyzer] Unexpected error: %s", type(exc).__name__)
        return _generic_fallback(skill_name)


def _parse_baseline_response(raw: str, skill_name: str, sub_topics: list[str]) -> Optional[dict]:
    """Parse JSON for baseline assessment. Handles options as dict OR list."""
    # Strip markdown fences
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if json_match:
        raw = json_match.group(1)
    else:
        brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if brace_match:
            raw = brace_match.group(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[skill_analyzer] Failed to parse baseline JSON")
        return None

    questions = data.get("questions", [])
    if not isinstance(questions, list):
        logger.warning("[skill_analyzer] 'questions' field is not a list")
        return None

    valid_qs = []
    import uuid

    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            continue

        question_text = str(q.get("question") or "").strip()
        if not question_text:
            continue  # skip blank questions

        # Match sub-topic
        st = str(q.get("sub_topic") or "").strip()
        matched_st = next((s for s in sub_topics if s.lower() == st.lower()), sub_topics[0] if sub_topics else "general")

        # ── Handle options in BOTH formats ──────────────────────────────
        raw_opts = q.get("options", {})
        if isinstance(raw_opts, dict):
            # Format: {"A": "...", "B": "...", "C": "...", "D": "..."}
            opt_a = str(raw_opts.get("A") or raw_opts.get("a") or "").strip()
            opt_b = str(raw_opts.get("B") or raw_opts.get("b") or "").strip()
            opt_c = str(raw_opts.get("C") or raw_opts.get("c") or "").strip()
            opt_d = str(raw_opts.get("D") or raw_opts.get("d") or "").strip()
        elif isinstance(raw_opts, list):
            # Format: ["A) ...", "B) ...", "C) ...", "D) ..."] or just plain strings
            padded = (list(raw_opts) + ["", "", "", ""])[:4]
            opt_a = str(padded[0]).strip()
            opt_b = str(padded[1]).strip()
            opt_c = str(padded[2]).strip()
            opt_d = str(padded[3]).strip()
        else:
            opt_a = opt_b = opt_c = opt_d = ""

        # Skip questions where all options are empty
        if not any([opt_a, opt_b, opt_c, opt_d]):
            logger.warning("[skill_analyzer] Question %d has no options, skipping", i + 1)
            continue

        correct = str(q.get("correct_option") or q.get("correct_answer") or "A").strip().upper()
        if correct not in ("A", "B", "C", "D"):
            correct = "A"

        valid_qs.append({
            "question_id": f"base_{uuid.uuid4().hex[:8]}",
            "question_num": i + 1,
            "subject": skill_name,
            "sub_topic": matched_st,
            "difficulty": str(q.get("difficulty") or "basic").strip(),
            "question": question_text,
            "options": [opt_a, opt_b, opt_c, opt_d],
            "correct_answer": correct,
            "explanation": str(q.get("explanation") or "").strip(),
        })

    if not valid_qs:
        logger.warning("[skill_analyzer] No valid questions parsed from AI response")
        return None

    return {
        "assessment_type": "baseline",
        "questions": valid_qs
    }

def generate_baseline_assessment(skill: str, sub_topics: list[dict], question_count: int = 6) -> dict:
    """
    Generate 5-6 baseline MCQs for a new skill using Featherless.
    """
    topic_list = [st["key"] for st in sub_topics]
    topics_str = ", ".join(topic_list)
    
    prompt = f"""Generate a diagnostic baseline assessment for a new skill.

Skill: {skill}
Sub-topics: {topics_str}
Question Count: {question_count}

Output a valid JSON object with the following structure:
{{
  "assessment_type": "baseline",
  "questions": [
    {{
      "sub_topic": "<one of the exact sub-topic keys provided>",
      "difficulty": "basic|intermediate|advanced",
      "question": "<the question text>",
      "options": {{
        "A": "...",
        "B": "...",
        "C": "...",
        "D": "..."
      }},
      "correct_option": "A|B|C|D",
      "explanation": "<short explanation>"
    }}
  ]
}}

Rules:
- Generate EXACTLY {question_count} questions.
- Every question must map to exactly one sub-topic from the provided list.
- Progress difficulty: Q1 (basic), Q2 (basic/intermediate), Q3-4 (intermediate), Q5-6 (advanced/application).
- Return ONLY valid JSON, no markdown formatting.
"""

    messages = [
        {"role": "system", "content": "You are a precise technical assessment generator. Output ONLY valid JSON."},
        {"role": "user", "content": prompt}
    ]

    try:
        raw_response = chat_complete(
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
            call_site="generate_baseline"
        )
        parsed = _parse_baseline_response(raw_response, skill, topic_list)
        if parsed and parsed.get("questions"):
            return parsed
    except Exception as exc:
        logger.error("[skill_analyzer] Baseline generation failed: %s", exc)

    # Fallback: generate basic template questions so the test always works
    logger.warning("[skill_analyzer] Using fallback questions for skill: %s", skill)
    return _generate_fallback_questions(skill, topic_list, question_count)


def _generate_fallback_questions(skill: str, topic_list: list, count: int = 6) -> dict:
    """
    Generate basic fallback MCQ questions when AI is unavailable.
    These are generic but valid enough for a baseline assessment.
    """
    import uuid

    templates = [
        {
            "question": f"Which of the following best describes the primary purpose of {skill}?",
            "options": {
                "A": f"To automate repetitive tasks related to {skill}",
                "B": f"To provide a structured approach to solving problems using {skill}",
                "C": f"To replace existing tools with {skill}",
                "D": f"To create documentation for {skill}"
            },
            "correct_option": "B",
            "difficulty": "basic",
            "explanation": f"{skill} is primarily used to provide a structured approach to solving related problems."
        },
        {
            "question": f"What is considered a fundamental concept in {skill}?",
            "options": {
                "A": "Memorizing syntax without understanding",
                "B": "Understanding core principles and applying them",
                "C": "Copying code from online sources",
                "D": "Avoiding best practices"
            },
            "correct_option": "B",
            "difficulty": "basic",
            "explanation": "Understanding core principles is the foundation of any skill."
        },
        {
            "question": f"Which approach is most effective when learning {skill}?",
            "options": {
                "A": "Reading theory without practice",
                "B": "Practice only without understanding concepts",
                "C": "Combining theoretical understanding with hands-on practice",
                "D": "Relying solely on memorization"
            },
            "correct_option": "C",
            "difficulty": "intermediate",
            "explanation": "Combining theory and practice yields the best results in skill development."
        },
        {
            "question": f"When debugging issues in {skill}, what is the recommended first step?",
            "options": {
                "A": "Rewrite the entire solution",
                "B": "Identify the root cause systematically",
                "C": "Ask for help immediately without investigation",
                "D": "Ignore the issue and move on"
            },
            "correct_option": "B",
            "difficulty": "intermediate",
            "explanation": "Systematic identification of root cause is the foundation of effective debugging."
        },
        {
            "question": f"What distinguishes an intermediate practitioner from a beginner in {skill}?",
            "options": {
                "A": "Ability to follow tutorials step-by-step",
                "B": "Knowledge of basic syntax only",
                "C": "Ability to apply concepts to new and unfamiliar problems",
                "D": "Speed of typing"
            },
            "correct_option": "C",
            "difficulty": "advanced",
            "explanation": "Applying knowledge to novel problems is the hallmark of intermediate skill."
        },
        {
            "question": f"Which practice best supports long-term retention of {skill}?",
            "options": {
                "A": "Cramming before deadlines",
                "B": "Spaced repetition and regular practice",
                "C": "Reading once and never revisiting",
                "D": "Avoiding difficult problems"
            },
            "correct_option": "B",
            "difficulty": "advanced",
            "explanation": "Spaced repetition is scientifically proven to improve long-term retention."
        },
    ]

    questions = []
    for i, tmpl in enumerate(templates[:count]):
        st = topic_list[i % len(topic_list)] if topic_list else "general"
        questions.append({
            "question_id": f"base_{uuid.uuid4().hex[:8]}",
            "question_num": i + 1,
            "subject": skill,
            "sub_topic": st,
            "difficulty": tmpl["difficulty"],
            "question": tmpl["question"],
            "options": [
                f"A. {tmpl['options']['A']}",
                f"B. {tmpl['options']['B']}",
                f"C. {tmpl['options']['C']}",
                f"D. {tmpl['options']['D']}",
            ],
            "correct_answer": tmpl["correct_option"],
            "explanation": tmpl["explanation"],
        })

    return {"assessment_type": "baseline", "questions": questions}

