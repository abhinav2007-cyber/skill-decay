"""
featherless_client.py — Featherless.ai key-rotation HTTP client (§8.1, §11.5).

Three API keys are read from env vars FEATHERLESS_KEY_1, FEATHERLESS_KEY_2,
FEATHERLESS_KEY_3.  Calls rotate through them: on a 401/429 response (or any
connection-level failure on a key), the utility immediately retries with the
next key.  At most 1 retry per key, at most 3 keys tried before giving up for
that specific call.

Hard timeout: 20 seconds per key attempt.
API keys are NEVER logged.

Model used: a Mistral-class chat model available on Featherless.ai.
"""

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"
# Default model — change here if you want a different model on Featherless
DEFAULT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
CALL_TIMEOUT_SECONDS = 20
MAX_TOKENS_DEFAULT = 1500


def _get_keys() -> list[str]:
    """Load all configured Featherless API keys (non-empty only)."""
    raw = [
        os.environ.get("FEATHERLESS_KEY_1", ""),
        os.environ.get("FEATHERLESS_KEY_2", ""),
        os.environ.get("FEATHERLESS_KEY_3", ""),
    ]
    return [k.strip() for k in raw if k.strip()]


async def featherless_chat(
    messages: list[dict],
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = MAX_TOKENS_DEFAULT,
    temperature: float = 0.3,
    call_site: str = "unknown",  # for logging only — not sent to API
) -> str:
    """
    Make a single chat-completion request to Featherless.ai with key rotation.

    Parameters
    ----------
    messages   : OpenAI-style [{"role": ..., "content": ...}] list
    model      : Featherless model name
    max_tokens : cap on response length
    temperature: sampling temperature
    call_site  : label for log messages (e.g. 'decision_agent', 'action_layer')

    Returns
    -------
    str — the assistant's response text

    Raises
    ------
    RuntimeError — if all keys fail (caller should handle per §11.5)
    """
    keys = _get_keys()
    if not keys:
        raise RuntimeError("No Featherless API keys configured (FEATHERLESS_KEY_1/2/3).")

    last_error: Exception | None = None
    for idx, key in enumerate(keys):
        try:
            logger.info("[%s] Trying Featherless key #%d", call_site, idx + 1)
            async with httpx.AsyncClient(timeout=CALL_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    f"{FEATHERLESS_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
            if resp.status_code in (401, 429):
                # Auth failure or rate-limit — rotate to next key
                logger.warning(
                    "[%s] Key #%d returned HTTP %d — rotating to next key",
                    call_site,
                    idx + 1,
                    resp.status_code,
                )
                last_error = RuntimeError(
                    f"HTTP {resp.status_code} from Featherless on key #{idx+1}"
                )
                continue
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            logger.info("[%s] Featherless call succeeded on key #%d", call_site, idx + 1)
            return content
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            logger.warning("[%s] Key #%d connection/timeout error: %s", call_site, idx + 1, type(e).__name__)
            last_error = e
            continue
        except Exception as e:
            # Unexpected error on this key — try next
            logger.warning("[%s] Key #%d unexpected error: %s", call_site, idx + 1, e)
            last_error = e
            continue

    raise RuntimeError(
        f"[{call_site}] All {len(keys)} Featherless key(s) failed. Last error: {last_error}"
    )
