"""
bkt_service.py — pyBKT knowledge-state estimator (§6.3).

pyBKT version 1.4.1 is used. The Model API works as follows:
  - Model.fit(data=df, skills='skill_name', forgets=True/False)
    DataFrame columns: user_id, skill_name, correct, order_id
  - Model.predict(data=df) → DataFrame with 'state_predictions' column
    state_predictions[i] is P(know) AFTER seeing response i.

NOTE: pyBKT 1.4.1 has a compatibility bug in its metrics.py with sklearn>=1.9.0.
      We patch the metrics module before importing Model to suppress the crash.
      This patch only affects pyBKT's evaluate() API (which we never call);
      fit() and predict() remain unaffected.

BKT+Forgets: pyBKT 1.4.1 supports the 'forgets' parameter in Model.fit().
      We use forgets=True because skill knowledge can decay between sessions,
      which aligns with SDA's core premise. The forget probability is estimated
      from the data via EM — it's a learned parameter, not a constant.
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Patch pyBKT / sklearn metrics before importing Model ────────────────────────
# In sklearn >= 1.9, metrics functions like log_loss raise AttributeError when
# passed raw Python lists instead of ndarrays, which breaks pyBKT's module-level
# fetch_supported_metrics(). We wrap them to raise TypeError instead so pyBKT's
# try/except TypeError catches them cleanly during import.
try:
    import sklearn.metrics._classification as _smc
    import sklearn.metrics._regression as _smr

    for _mod in (_smc, _smr):
        for _name in dir(_mod):
            if _name.endswith(("_loss", "_score", "_error")):
                _fn = getattr(_mod, _name)
                if callable(_fn):
                    def _make_w(_f):
                        def _w(*a, **kw):
                            try:
                                return _f(*a, **kw)
                            except AttributeError:
                                raise TypeError("sklearn 1.9 compatibility wrapper")
                        return _w
                    setattr(_mod, _name, _make_w(_fn))
except Exception as patch_err:
    logger.warning("Could not patch sklearn metrics for pyBKT: %s", patch_err)

from pyBKT.models import Model as BKTModel  # type: ignore  # noqa: E402

# ── Constants (§6.3) ──────────────────────────────────────────────────────────
# Change only here — referenced nowhere else hard-coded.
MIN_BKT_OBSERVATIONS = 5


def estimate_knowledge_probability(
    user_id: str, sub_topic: str, responses: list[dict]
) -> float | None:
    """
    Run pyBKT on the ordered response history for (user_id, sub_topic).

    Parameters
    ----------
    user_id   : the user
    sub_topic : the sub-topic label (used as pyBKT's skill_name)
    responses : list of dicts with keys {correct: bool, timestamp: str}.
                Must be pre-sorted chronologically (oldest first).

    Returns
    -------
    float in [0, 1]  — P(knows the skill) after all observed responses, or
    None             — if len(responses) < MIN_BKT_OBSERVATIONS (caller checks).

    BKT+Forgets is used (forgets=True). This is technically appropriate because
    our domain is explicitly about skill decay — the forget parameter captures
    real-world knowledge erosion between sessions, complementing §6.1's decay
    formula (which is deterministic; BKT's forget is probabilistic and learned
    from response patterns).
    """
    if len(responses) < MIN_BKT_OBSERVATIONS:
        return None

    # Build the DataFrame pyBKT expects (§API verified via Model source inspection)
    df = pd.DataFrame(
        {
            "user_id": [user_id] * len(responses),
            "skill_name": [sub_topic] * len(responses),
            "correct": [int(r["correct"]) for r in responses],
            "order_id": list(range(len(responses))),
        }
    )

    try:
        model = BKTModel(seed=42, num_fits=3)
        # forgets=True: BKT+Forgets — pyBKT 1.4.1 supports this.
        # Alternative without forgets: forgets=False; left as-is per spec §6.3.
        model.fit(data=df, skills=sub_topic, forgets=True)
        pred_df = model.predict(data=df)
        # state_predictions[-1] is P(know) after the last observation
        last_prob = float(pred_df["state_predictions"].iloc[-1])
        # Clamp to valid probability range (numerical edge cases)
        return max(0.0, min(1.0, last_prob))
    except Exception as exc:
        logger.error(
            "pyBKT estimation failed for user=%s sub_topic=%s: %s",
            user_id,
            sub_topic,
            exc,
        )
        raise  # Let the caller handle — don't silently fabricate a number


def get_tracking_mode(observation_count: int) -> str:
    """Determine tracking mode from observation count (§6.3)."""
    if observation_count == 0:
        return "cold_start"
    elif observation_count < MIN_BKT_OBSERVATIONS:
        return "decay_fallback"
    else:
        return "bkt"
