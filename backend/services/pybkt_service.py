"""
pybkt_service.py — pyBKT probabilistic knowledge-state estimator.

Responsibility boundary (§2):
  - Reconstruct BKT model from full ordered response history
  - Return knowledge_probability in [0, 1] for (user, skill, sub_topic)
  MUST NOT: generate reasoning text; make decisions; replace §6.1 decay model.

pyBKT API used: pyBKT 1.4.3 (patched for Python 3.14 + numpy 2.x compat)
  - Model.fit(data=DataFrame, num_fits=1, seed=42)
  - Model.predict(data=DataFrame) → DataFrame with 'state_predictions' column
    state_predictions = P(knows skill) after each observation (last = current estimate)

BKT+Forgets: evaluated below — pyBKT 1.4.3 DOES support forgets via the `forgets`
  parameter (Model(forgets=True)). We use it here as an additional signal.
  It does NOT replace §6.1's decay model; decay is still in the signal bundle.

§6.3: MIN_BKT_OBSERVATIONS guard is enforced in signal_engine.py — this service
  is only called when there are >= MIN_BKT_OBSERVATIONS responses. It does NOT
  re-check; the caller is responsible for the mode guard.
"""

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def estimate_knowledge(
    user_id: str,
    skill: str,
    sub_topic: str,
    responses: list,  # list of QuizResponse ORM objects, already chronologically ordered
) -> Optional[float]:
    """
    Fit a BKT model on the full ordered response history and return the
    final knowledge probability (P(learned) after last observation).

    Returns None on any failure so the caller can fall back gracefully.

    BKT+Forgets is used (forgets=True in Model) as the estimator when
    ≥ MIN_BKT_OBSERVATIONS responses are available.
    """
    from pyBKT.models import Model  # deferred import — avoids import-time side-effects

    if not responses:
        return None

    try:
        # Build the DataFrame pyBKT expects
        df = pd.DataFrame([
            {
                "user_id":    user_id,
                "skill_name": f"{skill}__{sub_topic}",   # unique skill key per sub-topic
                "correct":    int(r.correct),
                "order_id":   idx,
            }
            for idx, r in enumerate(responses)
        ])

        # BKT+Forgets: in pyBKT 1.4.3, 'forgets' is a FIT_ARG (not a MODEL_ARG).
        # Must be passed to fit(), not to Model(). See FIT_ARGS = [..., 'forgets', ...]
        # This enables the model to learn a forgetting probability, giving a more
        # conservative knowledge estimate. It is an additional signal on top of §6.1
        # decay; they capture different aspects of knowledge loss.
        model = Model(
            seed=42,
            num_fits=1,    # single fit for speed; increase to 5+ for prod accuracy
        )

        # fit() reconstructs the BKT parameters from this user's full response history
        # forgets=True: BKT+Forgets enabled here in the fit call
        model.fit(data=df, forgets=True)

        # predict() returns state_predictions = P(knows) at each timestep
        result_df = model.predict(data=df)

        # Final value = current knowledge estimate (after all observations)
        prob = float(result_df["state_predictions"].iloc[-1])

        # Clamp to [0, 1] for safety (pyBKT should always return this range)
        prob = max(0.0, min(1.0, prob))
        return round(prob, 4)

    except Exception as exc:
        logger.error(
            "BKT estimation failed for user=%s skill=%s sub_topic=%s: %s",
            user_id, skill, sub_topic, exc
        )
        return None
