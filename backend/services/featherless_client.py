"""
<<<<<<< HEAD
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
=======
featherless_client.py — Key-rotation utility for all three Featherless.ai call sites.

Shared utility: Decision Agent (call #1), Agent Action Layer (call #2),
and Strength Report AI summary (call #3) ALL route through this.

Key rotation behavior (§8.1):
  - Tries FEATHERLESS_KEY_1, then FEATHERLESS_KEY_2, then FEATHERLESS_KEY_3
  - On 401 (auth failure) or 429 (rate limit): rotates to next key, retries once per key
  - Hard timeout: 20 seconds per attempt (§8.1)
  - After all 3 keys fail: raises FeatherlessAllKeysFailedError — caller handles gracefully

NEVER logs the actual API key values.
"""

import os
import json
import time
import logging
from typing import Optional
>>>>>>> 87b73f4 (feat: complete Skill Decay Alerts dashboard, quiz integration, strength report tab, and backend SDA Signal Engine)

import httpx

logger = logging.getLogger(__name__)

FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"
<<<<<<< HEAD
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
=======

# Model to use — fast, free-tier friendly; alternatives: meta-llama/Meta-Llama-3.1-70B-Instruct
FEATHERLESS_MODEL = os.getenv(
    "FEATHERLESS_MODEL",
    "meta-llama/Meta-Llama-3.1-8B-Instruct"
)

# Timeout per single HTTP attempt (§8.1)
CALL_TIMEOUT_SECONDS = 20

# Retryable HTTP status codes (auth failure or rate limit)
ROTATION_TRIGGER_STATUSES = {401, 429}


class FeatherlessAllKeysFailedError(Exception):
    """Raised when all 3 Featherless keys have been exhausted for a single call."""
    pass


def _get_keys() -> list[str]:
    """Read and return all configured Featherless API keys (non-empty ones)."""
    keys = [
        os.getenv("FEATHERLESS_KEY_1", ""),
        os.getenv("FEATHERLESS_KEY_2", ""),
        os.getenv("FEATHERLESS_KEY_3", ""),
    ]
    valid = [k for k in keys if k.strip()]
    if not valid:
        raise FeatherlessAllKeysFailedError(
            "No Featherless API keys configured. Set FEATHERLESS_KEY_1/2/3 in .env"
        )
    return valid


def chat_complete(
    messages: list[dict],
    *,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    call_site: str = "unknown",  # for logging only, never the key
) -> str:
    """
    Send a chat completion request to Featherless.ai with key rotation.

    Args:
        messages: OpenAI-format message list [{"role": ..., "content": ...}]
        temperature: sampling temperature
        max_tokens: max output tokens
        call_site: a label like "decision_agent" / "action_layer" / "strength_report"
                   used only in log messages — never the key itself

    Returns:
        The assistant's message content as a string.

    Raises:
        FeatherlessAllKeysFailedError: if all keys fail.
    """
    keys = _get_keys()
    last_exc: Optional[Exception] = None

    for key_idx, key in enumerate(keys):
        key_label = f"key_{key_idx + 1}"  # never log the actual key
        try:
            logger.debug(
                "[featherless/%s] Attempting with %s", call_site, key_label
            )
            response = httpx.post(
                f"{FEATHERLESS_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": FEATHERLESS_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=CALL_TIMEOUT_SECONDS,
            )

            if response.status_code in ROTATION_TRIGGER_STATUSES:
                logger.warning(
                    "[featherless/%s] %s returned %d — rotating to next key",
                    call_site, key_label, response.status_code
                )
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
                continue

            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug(
                "[featherless/%s] Success with %s, tokens_used=%s",
                call_site, key_label,
                data.get("usage", {}).get("total_tokens", "?")
            )
            return content

        except httpx.TimeoutException as exc:
            logger.warning(
                "[featherless/%s] %s timed out after %ss",
                call_site, key_label, CALL_TIMEOUT_SECONDS
            )
            last_exc = exc
            continue

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in ROTATION_TRIGGER_STATUSES:
                logger.warning(
                    "[featherless/%s] %s auth/rate-limit — rotating",
                    call_site, key_label
                )
                last_exc = exc
                continue
            logger.error(
                "[featherless/%s] %s HTTP error %d",
                call_site, key_label, exc.response.status_code
            )
            last_exc = exc
            continue

        except Exception as exc:
            logger.error(
                "[featherless/%s] %s unexpected error: %s",
                call_site, key_label, type(exc).__name__
            )
            last_exc = exc
            continue

    raise FeatherlessAllKeysFailedError(
        f"All Featherless keys failed for call_site={call_site}. "
        f"Last error: {last_exc}"
    ) from last_exc
>>>>>>> 87b73f4 (feat: complete Skill Decay Alerts dashboard, quiz integration, strength report tab, and backend SDA Signal Engine)
