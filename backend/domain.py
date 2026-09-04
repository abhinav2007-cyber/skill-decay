"""
domain.py — Hardcoded 10 sub-topic definitions (5 skills × 2 sub-topics each).
All skill/sub-topic keys used throughout the system originate from this file.
"""

# Each entry: (skill, sub_topic, category)
# category: "procedural" (fast decay, 14-day half-life) | "conceptual" (slow decay, 45-day half-life)
SUB_TOPICS = [
    ("Python",           "syntax_and_core_libraries",      "procedural"),
    ("Python",           "oop_and_design_patterns",        "conceptual"),
    ("Java",             "syntax_and_collections",         "procedural"),
    ("Java",             "oop_and_jvm_concepts",           "conceptual"),
    ("DBMS",             "sql_queries_and_joins",          "procedural"),
    ("DBMS",             "normalization_and_transactions", "conceptual"),
    ("Machine Learning", "model_apis_and_libraries",       "procedural"),
    ("Machine Learning", "algorithms_and_theory",          "conceptual"),
    ("DSA",              "implementation_and_syntax",      "procedural"),
    ("DSA",              "complexity_and_problem_solving", "conceptual"),
]

# Lookup helpers
SKILL_NAMES = list(dict.fromkeys(s for s, _, _ in SUB_TOPICS))  # ordered, deduplicated

def get_category(skill: str, sub_topic: str) -> str:
    for s, st, cat in SUB_TOPICS:
        if s == skill and st == sub_topic:
            return cat
    raise ValueError(f"Unknown sub-topic: {skill}/{sub_topic}")

def all_sub_topics():
    """Returns list of (skill, sub_topic, category) tuples."""
    return list(SUB_TOPICS)



DEMO_USER_ID = "demo_user"
