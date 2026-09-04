"""
gemini_client.py — Fast, direct Gemini REST client matching the chat_complete() interface.

Used for the 5 heavy/interactive AI tasks:
  1. decision_agent.py -> run_decision_agent()
  2. action_layer.py -> _generate_quiz()
  3. action_layer.py -> _generate_recommendation()
  4. skill_analyzer.py -> analyze_skill()
  5. skill_analyzer.py -> generate_baseline_assessment()

strength_report.py continues to use featherless_client.py (hackathon compliance).
"""

import os
import json
import logging
import time
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

import httpx

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.6-flash"
CALL_TIMEOUT_SECONDS = 45
_RETRY_DELAYS = [1, 3, 7]  # seconds to wait between retries on 503/429


class GeminiError(Exception):
    """Raised when the Gemini API request fails or key is missing."""
    pass


def _get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiError("GEMINI_API_KEY is not set in environment or .env file.")
    return key


def _convert_messages_to_gemini(messages: list[dict]) -> tuple[Optional[str], list[dict]]:
    """
    Converts OpenAI-style messages list:
      [{"role": "system"|"user"|"assistant", "content": "..."}]
    Into Gemini API format:
      system_instruction: str or None
      contents: [{"role": "user"|"model", "parts": [{"text": "..."}]}]
    """
    system_parts = []
    contents = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            system_parts.append(content)
        elif role == "assistant":
            contents.append({
                "role": "model",
                "parts": [{"text": content}]
            })
        else:  # user or other
            contents.append({
                "role": "user",
                "parts": [{"text": content}]
            })

    # If no user message was provided, ensure at least one exists
    if not contents and system_parts:
        contents.append({
            "role": "user",
            "parts": [{"text": "Please proceed according to system instructions."}]
        })

    system_instruction = "\n\n".join(system_parts) if system_parts else None
    return system_instruction, contents


def chat_complete(
    messages: list[dict],
    *,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    call_site: str = "unknown",
) -> str:
    """
    Synchronous chat completion using Google Gemini REST API.
    Signature matches backend.services.featherless_client.chat_complete for drop-in use.
    """
    api_key = _get_api_key()
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    system_instruction, contents = _convert_messages_to_gemini(messages)

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    url = f"{GEMINI_API_URL}/{model}:generateContent?key={api_key}"

    logger.debug("[gemini/%s] Calling Gemini model=%s with %d messages", call_site, model, len(messages))

    last_error = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS, start=1):
        if delay:
            logger.warning("[gemini/%s] Retry attempt %d after %ds delay...", call_site, attempt, delay)
            time.sleep(delay)
        try:
            response = httpx.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=CALL_TIMEOUT_SECONDS,
            )

            if response.status_code in (429, 503):
                # Transient overload — retry
                logger.warning("[gemini/%s] HTTP %d on attempt %d, will retry", call_site, response.status_code, attempt)
                last_error = GeminiError(f"Gemini API returned HTTP {response.status_code}: {response.text[:200]}")
                continue

            if response.status_code != 200:
                logger.error("[gemini/%s] HTTP %d: %s", call_site, response.status_code, response.text[:400])
                raise GeminiError(f"Gemini API returned HTTP {response.status_code}: {response.text[:200]}")

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise GeminiError(f"Gemini returned no candidates. Raw response: {data}")

            first_candidate = candidates[0]
            content_obj = first_candidate.get("content", {})
            parts = content_obj.get("parts", [])
            if not parts:
                raise GeminiError(f"Gemini candidate has no parts. Raw candidate: {first_candidate}")

            text = parts[0].get("text", "")
            logger.debug("[gemini/%s] Success on attempt %d! Generated %d chars", call_site, attempt, len(text))
            return text

        except httpx.TimeoutException as exc:
            logger.warning("[gemini/%s] Timed out on attempt %d after %ds", call_site, attempt, CALL_TIMEOUT_SECONDS)
            last_error = GeminiError(f"Gemini API call timed out after {CALL_TIMEOUT_SECONDS}s")
            continue
        except GeminiError:
            raise
        except Exception as exc:
            logger.error("[gemini/%s] Unexpected error: %s: %s", call_site, type(exc).__name__, exc)
            raise GeminiError(f"Gemini API call failed: {exc}") from exc

    raise last_error or GeminiError("All Gemini retry attempts exhausted.")


async def gemini_chat(
    messages: list[dict],
    *,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    call_site: str = "unknown",
) -> str:
    """
    Asynchronous chat completion using Google Gemini REST API.
    """
    api_key = _get_api_key()
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    system_instruction, contents = _convert_messages_to_gemini(messages)

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    url = f"{GEMINI_API_URL}/{model}:generateContent?key={api_key}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=CALL_TIMEOUT_SECONDS,
            )

        if response.status_code != 200:
            logger.error("[gemini/%s] HTTP %d: %s", call_site, response.status_code, response.text[:400])
            raise GeminiError(f"Gemini API returned HTTP {response.status_code}: {response.text[:200]}")

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise GeminiError(f"Gemini returned no candidates: {data}")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise GeminiError(f"Gemini candidate has no parts: {candidates[0]}")

        return parts[0].get("text", "")

    except httpx.TimeoutException as exc:
        logger.warning("[gemini/%s] Timed out after %ds", call_site, CALL_TIMEOUT_SECONDS)
        raise GeminiError(f"Gemini API call timed out after {CALL_TIMEOUT_SECONDS}s") from exc
    except GeminiError:
        raise
    except Exception as exc:
        logger.error("[gemini/%s] Unexpected error: %s: %s", call_site, type(exc).__name__, exc)
        raise GeminiError(f"Gemini API call failed: {exc}") from exc
