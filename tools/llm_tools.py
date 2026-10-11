from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


def _env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = WORKSPACE_ROOT / ".env"
    if not env_path.is_file():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def chef_summary(text: str) -> str:
    if not text or not text.strip():
        raise ValueError("Spend text must not be blank.")

    file_values = _env_file()
    api_key = os.environ.get("LLM_API_KEY") or file_values.get("LLM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "LLM_API_KEY is not set in the process environment or .env file."
        )
    model = (
        os.environ.get("OPENAI_MODEL")
        or file_values.get("OPENAI_MODEL")
        or "gpt-4o-mini"
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You summarize kitchen spending for a chef. "
                        "Reply with exactly two short, factual sentences."
                    ),
                },
                {"role": "user", "content": text.strip()},
            ],
            "temperature": 0.2,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        CHAT_COMPLETIONS_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM response was not valid JSON.") from exc

    try:
        return response_data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise RuntimeError("LLM response did not contain summary text.") from exc
