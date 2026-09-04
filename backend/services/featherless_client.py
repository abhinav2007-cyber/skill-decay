"""
featherless_client.py — Key-rotation utility for Featherless.ai call sites.

Shared utility: Decision Agent (call #1), Agent Action Layer (call #2),
and Strength Report AI summary (call #3) ALL route through this.

Key rotation behavior (§8.1):
  - Tries FEATHERLESS_KEY_1 -> FEATHERLESS_KEY_2 -> FEATHERLESS_KEY_3 -> FEATHERLESS_KEY_4 -> FEATHERLESS_KEY_5
  - On 401 (auth failure) or 429 (rate limit) or timeout: rotates to next key in sequence
  - Hard timeout: 20 seconds per attempt (§8.1)
  - After all configured keys fail: raises FeatherlessAllKeysFailedError — caller handles gracefully

NEVER logs the actual API key values.
"""

import os
import json
import time
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"

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
    """Raised when all configured Featherless keys have been exhausted for a single call."""
    pass



def _get_keys() -> list[str]:
    """Read and return all configured Featherless API keys (non-empty ones)."""
    keys = [
        os.getenv("FEATHERLESS_KEY_1", ""),
        os.getenv("FEATHERLESS_KEY_2", ""),
        os.getenv("FEATHERLESS_KEY_3", ""),
        os.getenv("FEATHERLESS_KEY_4", ""),
        os.getenv("FEATHERLESS_KEY_5", ""),
    ]
    valid = [k for k in keys if k.strip()]
    if not valid:
        raise FeatherlessAllKeysFailedError(
            "No Featherless API keys configured. Set FEATHERLESS_KEY_1 to 5 in .env"
        )
    return valid


def chat_complete(
    messages: list[dict],
    *,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    call_site: str = "unknown",  # for logging only, never the key
) -> str:
    keys = _get_keys()
    last_exc: Optional[Exception] = None
    for key_idx, key in enumerate(keys):
        key_label = f"key_{key_idx + 1}"  # never log the actual key
        try:
            logger.debug("[featherless/%s] Attempting with %s", call_site, key_label)
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
                logger.warning("[featherless/%s] %s returned %d — rotating to next key", call_site, key_label, response.status_code)
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
                continue

            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug("[featherless/%s] Success with %s, tokens_used=%s", call_site, key_label, data.get("usage", {}).get("total_tokens", "?"))
            return content

        except httpx.TimeoutException as exc:
            logger.warning("[featherless/%s] %s timed out after %ss", call_site, key_label, CALL_TIMEOUT_SECONDS)
            last_exc = exc
            continue
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in ROTATION_TRIGGER_STATUSES:
                logger.warning("[featherless/%s] %s auth/rate-limit — rotating", call_site, key_label)
                last_exc = exc
                continue
            logger.error("[featherless/%s] %s HTTP error %d", call_site, key_label, exc.response.status_code)
            last_exc = exc
            continue
        except Exception as exc:
            logger.error("[featherless/%s] %s unexpected error: %s", call_site, key_label, type(exc).__name__)
            last_exc = exc
            continue

    raise FeatherlessAllKeysFailedError(
        f"All Featherless keys failed for call_site={call_site}. "
        f"Last error: {last_exc}"
    ) from last_exc

async def featherless_chat(
    messages: list[dict],
    *,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    call_site: str = "unknown",  # for logging only, never the key
) -> str:
    keys = _get_keys()
    last_exc: Optional[Exception] = None

    for key_idx, key in enumerate(keys):
        key_label = f"key_{key_idx + 1}"  # never log the actual key
        try:
            logger.debug("[featherless/%s] Attempting with %s", call_site, key_label)
            async with httpx.AsyncClient() as client:
                response = await client.post(
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
                logger.warning("[featherless/%s] %s returned %d — rotating to next key", call_site, key_label, response.status_code)
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
                continue

            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug("[featherless/%s] Success with %s, tokens_used=%s", call_site, key_label, data.get("usage", {}).get("total_tokens", "?"))
            return content

        except httpx.TimeoutException as exc:
            logger.warning("[featherless/%s] %s timed out after %ss", call_site, key_label, CALL_TIMEOUT_SECONDS)
            last_exc = exc
            continue

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in ROTATION_TRIGGER_STATUSES:
                logger.warning("[featherless/%s] %s auth/rate-limit — rotating", call_site, key_label)
                last_exc = exc
                continue
            logger.error("[featherless/%s] %s HTTP error %d", call_site, key_label, exc.response.status_code)
            last_exc = exc
            continue

        except Exception as exc:
            logger.error("[featherless/%s] %s unexpected error: %s", call_site, key_label, type(exc).__name__)
            last_exc = exc
            continue

    raise FeatherlessAllKeysFailedError(
        f"All Featherless keys failed for call_site={call_site}. "
        f"Last error: {last_exc}"
    ) from last_exc
