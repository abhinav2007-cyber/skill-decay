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

# Target URL for LinkedIn import demo
LINKEDIN_TARGET_URL = "https://www.linkedin.com/in/aishwarya-madam-96296a1b7/?lipi=urn%3Ali%3Apage%3Ad_flagship3_profile_view_base_contact_details%3BvJ%2FWJG9WQVGxNxAookNlcw%3D%3D"

LINKEDIN_AISHWARYA_PROFILE = {
  "profile": {
    "name": "Aishwarya",
    "headline": "IT Project & Program Manager | Cloud Storage & Infrastructure | Agile & Waterfall Lead",
    "linkedin_url": "https://www.linkedin.com/in/aishwarya",
    "summary": "Results-driven IT Project and Program Manager with expertise spanning enterprise cloud infrastructure, cybersecurity fundamentals, and strategic IT operations.",
    "skills": [
      {"name": "Agile & Waterfall Methodologies", "category": "conceptual", "days_dormant": 15},
      {"name": "Cross-functional Collaborations", "category": "conceptual", "days_dormant": 10},
      {"name": "Strategic Planning", "category": "conceptual", "days_dormant": 30},
      {"name": "Business Acumen", "category": "conceptual", "days_dormant": 20},
      {"name": "Project Management", "category": "conceptual", "days_dormant": 5},
      {"name": "IT Project & Program Management", "category": "conceptual", "days_dormant": 10},
      {"name": "Stakeholder Management", "category": "conceptual", "days_dormant": 12},
      {"name": "Salesforce.com", "category": "procedural", "days_dormant": 60},
      {"name": "Jira", "category": "procedural", "days_dormant": 5},
      {"name": "Confluence", "category": "procedural", "days_dormant": 8},
      {"name": "Cloud Security", "category": "conceptual", "days_dormant": 45},
      {"name": "Dell PowerFlex Rack", "category": "procedural", "days_dormant": 120},
      {"name": "Microsoft Excel", "category": "procedural", "days_dormant": 2},
      {"name": "Cloud Storage", "category": "procedural", "days_dormant": 90}
    ],
    "certifications": [
      {
        "title": "Dell Certified Associate Information Storage and Management Version 5.0",
        "issuer": "Dell Technologies"
      },
      {
        "title": "ITIL® v4 Foundation",
        "issuer": "AXELOS Global Best Practice"
      },
      {
        "title": "Introduction to Cybersecurity",
        "issuer": "Cisco"
      },
      {
        "title": "Project Management Foundations",
        "issuer": "PMI"
      },
      {
        "title": "Generative AI - Fundamentals",
        "issuer": "Industry Credential"
      }
    ]
  }
}
