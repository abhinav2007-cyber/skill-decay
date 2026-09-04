"""
domain.py — hardcoded domain scope (§3)
5 skills × 2 sub-topics = 10 sub-topics, each tagged procedural or conceptual.
"""

SKILLS = {
    "Python": {
        "syntax_and_core_libraries": "procedural",
        "oop_and_design_patterns": "conceptual",
    },
    "Java": {
        "syntax_and_collections": "procedural",
        "oop_and_jvm_concepts": "conceptual",
    },
    "DBMS": {
        "sql_queries_and_joins": "procedural",
        "normalization_and_transactions": "conceptual",
    },
    "Machine Learning": {
        "model_apis_and_libraries": "procedural",
        "algorithms_and_theory": "conceptual",
    },
    "DSA": {
        "implementation_and_syntax": "procedural",
        "complexity_and_problem_solving": "conceptual",
    },
}

# Flat list of all (skill, sub_topic, category) tuples
ALL_SUB_TOPICS = [
    (skill, sub_topic, category)
    for skill, sub_topics in SKILLS.items()
    for sub_topic, category in sub_topics.items()
]

DEMO_USER_ID = "demo_user"
