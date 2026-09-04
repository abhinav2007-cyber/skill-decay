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

def get_category(skill: str, sub_topic: str, db=None, user_id=None) -> str:
    for s, st, cat in SUB_TOPICS:
        if s == skill and st == sub_topic:
            return cat
            
    if db and user_id:
        from backend.database import SkillSubTopic
        st_row = db.query(SkillSubTopic).filter_by(user_id=user_id, skill_name=skill, sub_topic_key=sub_topic).first()
        if st_row:
            return st_row.category
            
    # Safe fallback for custom/dynamic skills if category isn't specified
    return "conceptual"

def all_sub_topics(db=None, user_id=None):
    """Returns list of (skill, sub_topic, category) tuples. Combines hardcoded and DB skills, excluding deleted ones."""
    topics = list(SUB_TOPICS)
    if db and user_id:
        try:
            from backend.database import SkillSubTopic, DeletedSkill
            deleted_skills = {
                d.skill_name.lower().strip()
                for d in db.query(DeletedSkill).filter_by(user_id=user_id).all()
            }
        except Exception:
            deleted_skills = set()

        topics = [t for t in topics if t[0].lower().strip() not in deleted_skills]

        try:
            dynamic_topics = db.query(SkillSubTopic).filter_by(user_id=user_id).all()
            for t in dynamic_topics:
                if t.skill_name.lower().strip() not in deleted_skills:
                    topics.append((t.skill_name, t.sub_topic_key, t.category))
        except Exception:
            pass

    return topics

DEMO_USER_ID = "demo_user"
