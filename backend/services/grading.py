"""
grading.py — §10.1: Grading + question_id validation.

Responsibility:
  - Look up quiz_cycles by cycle_id
  - Validate question_id belongs to that cycle
  - Grade against stored correct answer
  - Write to quiz_responses
  - Mark cycle consumed
  MUST NOT: recalculate signals or make decisions.
"""

import logging
from datetime import datetime
from typing import Tuple

from sqlalchemy.orm import Session

from backend.database import QuizCycle, QuizResponse, get_simulated_now

logger = logging.getLogger(__name__)


class GradingError(Exception):
    """Raised for controlled grading validation failures (400-level)."""
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code  # machine-readable error code for API responses


def grade_answer(
    db: Session,
    user_id: str,
    sub_topic: str,
    question_id: str,
    selected_option: str,
    cycle_id: str,
) -> Tuple[bool, str]:
    """
    §10.1 grading steps:
      1. Look up quiz_cycles by cycle_id; reject if not found or consumed=True
      2. Confirm question_id exists in that cycle's questions; reject if not
      3. Grade, write quiz_responses row, mark cycle consumed=True

    Returns: (is_correct: bool, explanation: str)
    Raises: GradingError on validation failure (handled as 400 by API layer).
    """

    # Step 1: Look up cycle
    cycle = db.query(QuizCycle).filter_by(cycle_id=cycle_id, user_id=user_id).first()
    if cycle is None:
        raise GradingError(
            f"cycle_id '{cycle_id}' not found for user '{user_id}'",
            "CYCLE_NOT_FOUND"
        )
    if cycle.consumed:
        raise GradingError(
            f"cycle_id '{cycle_id}' has already been graded (consumed=True)",
            "CYCLE_ALREADY_CONSUMED"
        )

    # Step 2: Confirm question_id belongs to this cycle
    questions = cycle.questions or []
    matching_question = None
    for q in questions:
        if q.get("question_id") == question_id:
            matching_question = q
            break

    if matching_question is None:
        raise GradingError(
            f"question_id '{question_id}' does not belong to cycle '{cycle_id}'",
            "INVALID_QUESTION_ID"
        )

    # Step 3: Grade
    correct_answer = matching_question.get("correct_answer", "").strip()
    sel = selected_option.strip()

    # Match exact or match by option letter prefix (e.g. "C" matches "C" or "C) ..." or "C. ...")
    def _extract_letter(s: str) -> str:
        s = s.strip()
        if len(s) == 1 and s.upper() in "ABCD":
            return s.upper()
        if len(s) > 1 and s[0].upper() in "ABCD" and s[1] in (")", ".", " ", ":", "-"):
            return s[0].upper()
        return s

    sel_letter = _extract_letter(sel)
    cor_letter = _extract_letter(correct_answer)

    if sel_letter in "ABCD" and cor_letter in "ABCD":
        is_correct = (sel_letter == cor_letter)
    else:
        is_correct = (sel.lower() == correct_answer.lower())

    explanation = matching_question.get("explanation", "")

    # Check if this specific question has already been answered
    existing = db.query(QuizResponse).filter_by(
        user_id=user_id, cycle_id=cycle_id, question_id=question_id
    ).first()
    if existing:
        return existing.correct, matching_question.get("explanation", "")

    # Write quiz_responses (append-only)
    now = get_simulated_now(db)
    
    # Use the question's sub_topic if available, otherwise fallback to cycle's sub_topic
    actual_sub_topic = matching_question.get("sub_topic") or cycle.sub_topic
    
    db.add(QuizResponse(
        user_id=user_id,
        skill=cycle.skill,
        sub_topic=actual_sub_topic,
        question_id=question_id,
        correct=is_correct,
        timestamp=now,
        cycle_id=cycle_id,
    ))

    # Mark cycle consumed only when all questions have been answered
    answered_count = db.query(QuizResponse).filter_by(
        user_id=user_id, cycle_id=cycle_id
    ).count() + 1
    if answered_count >= len(questions):
        cycle.consumed = True

    # Update last_used_at on subtopic state
    from backend.database import SubTopicState
    st_row = db.query(SubTopicState).filter_by(
        user_id=user_id, skill=cycle.skill, sub_topic=actual_sub_topic
    ).first()
    if st_row:
        st_row.last_used_at = now

    db.flush()

    logger.info(
        "Graded: user=%s sub_topic=%s question_id=%s correct=%s (answered %d/%d)",
        user_id, sub_topic, question_id, is_correct, answered_count, len(questions)
    )

    return is_correct, explanation
