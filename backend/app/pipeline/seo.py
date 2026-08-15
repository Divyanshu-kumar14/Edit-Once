"""Groq-powered per-platform SEO packs (title/description/hashtags).

Pure core (build_prompt, parse_seo_json) is testable without network;
the Groq client is constructed lazily per call and never at import time,
mirroring transcriber.py's graceful-degradation pattern.
"""

from __future__ import annotations

import importlib.util
import json
import re
from datetime import datetime, timezone

from .. import config
from ..models import SeoPack

# Per-platform text rules — the "platforms.json philosophy" applied to copy.
# (title_limit, description_limit, hashtag_min, hashtag_max)
PLATFORM_TEXT_LIMITS: dict[str, tuple[int, int, int, int]] = {
    "tiktok": (100, 2200, 3, 5),
    "reels": (100, 2200, 3, 5),
    "shorts": (100, 5000, 3, 5),
    "x": (280, 280, 1, 3),  # whole post (title + description + hashtags) ≤ 280
}

SYSTEM_PROMPT = (
    "You are an expert short-form video SEO copywriter for TikTok, Instagram Reels, "
    "YouTube Shorts, and X. Given a video transcript and platform rules, produce a "
    "title, description, and viral hashtags that are GROUNDED IN THE ACTUAL VIDEO "
    "CONTENT. Be specific and concrete; never generic filler. Return STRICT JSON "
    'only: {"title": string, "description": string, "hashtags": [string]}. '
    "Hashtags must NOT include the # character. "
    "Titles: hook-style, curiosity + benefit. Descriptions: 2-4 short sentences, "
    "keywords first, no emoji spam. Hashtags: mix of niche-specific and medium-size "
    "tags matching the video's real topic."
)

MAX_TRANSCRIPT_CHARS = 2400


class SeoError(Exception):
    """Typed failure for SEO generation (API, timeout, unparseable output)."""


def _platform_rules(platform: str) -> tuple[int, int, int, int]:
    """Platform text limits, defaulting to the most permissive (TikTok-style)."""
    return PLATFORM_TEXT_LIMITS.get(platform, PLATFORM_TEXT_LIMITS["tiktok"])


def build_prompt(
    transcript: str, platform: str, meta: dict[str, object]
) -> list[dict[str, str]]:
    """Build the chat messages for one platform's SEO pack."""
    title_limit, desc_limit, tag_min, tag_max = _platform_rules(platform)
    rules = (
        f"Platform: {platform}\n"
        f"Title max: {title_limit} characters\n"
        f"Description max: {desc_limit} characters\n"
        f"Hashtags: {tag_min} to {tag_max}, no '#' prefix\n"
        f"Video duration: {meta.get('duration_s', '?')} seconds"
    )
    user = (
        f"Video transcript:\n\"\"\"\n{transcript}\n\"\"\"\n\n"
        f"Platform rules:\n{rules}\n\n"
        f'Return JSON: {{"title": "...", "description": "...", "hashtags": ["..."]}}'
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _clean_hashtag(tag: str) -> str:
    """Strip '#', whitespace, and punctuation so tags are clean lowercase keywords."""
    tag = tag.strip().lstrip("#").strip().lower()
    tag = re.sub(r"[^0-9a-z]", "", tag)
    return tag


def parse_seo_json(raw: str, platform: str) -> SeoPack:
    """Parse and validate Groq's JSON output; clamp to platform limits."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SeoError(f"Groq returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SeoError("Groq JSON is not an object")
    for key in ("title", "description", "hashtags"):
        if key not in data:
            raise SeoError(f"Groq JSON missing required key: {key}")

    title_limit, desc_limit, tag_min, tag_max = _platform_rules(platform)
    title = str(data["title"]).strip()[:title_limit] or "Untitled"
    description = str(data["description"]).strip()[:desc_limit]

    hashtags: list[str] = []
    seen: set[str] = set()
    for tag in data["hashtags"]:
        clean = _clean_hashtag(str(tag))
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            hashtags.append(clean)
        if len(hashtags) >= tag_max:
            break
    # X: keep the whole post (title + description + hashtags) within 280 chars.
    if platform == "x":
        over = len(title) + len(description) + sum(len(t) + 2 for t in hashtags) - 280
        while hashtags and over > 0 and len(hashtags) > tag_min:
            hashtags.pop()
            over = len(title) + len(description) + sum(len(t) + 2 for t in hashtags) - 280

    return SeoPack(title=title, description=description, hashtags=hashtags)


def stack_available() -> bool:
    """True when the groq client is importable AND a key is configured.

    Import-only check (never constructs the client or hits the network), so
    health stays fast and offline-safe — same pattern as transcriber.
    """
    return (
        config.GROQ_API_KEY is not None
        and config.GROQ_API_KEY.strip() != ""
        and importlib.util.find_spec("groq") is not None
    )


def _call_groq(
    api_key: str,
    transcript: str,
    platform: str,
    meta: dict[str, object],
    temperature: float,
    timeout_s: float,
) -> str:
    from groq import Groq  # lazy: import cost only on demand

    try:
        client = Groq(api_key=api_key, timeout=timeout_s)
        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=build_prompt(transcript, platform, meta),
            temperature=temperature,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
    except Exception as exc:  # network, auth, rate limit, timeout...
        raise SeoError(f"Groq API error: {exc}") from exc
    content = response.choices[0].message.content
    if not content:
        raise SeoError("Groq returned an empty response")
    return content


def generate_pack(
    api_key: str,
    transcript: str,
    platform: str,
    meta: dict[str, object],
    timeout_s: float | None = None,
) -> SeoPack:
    """Generate one platform's SEO pack; retries once at temperature 0 on parse failure."""
    timeout = timeout_s if timeout_s is not None else config.GROQ_TIMEOUT_S

    def attempt(temperature: float) -> SeoPack:
        raw = _call_groq(api_key, transcript, platform, meta, temperature, timeout)
        return parse_seo_json(raw, platform)

    try:
        return attempt(0.7)
    except SeoError as first:
        # Retry once with a deterministic temperature before giving up.
        try:
            return attempt(0.0)
        except SeoError as second:
            raise SeoError(f"Groq SEO generation failed: {second}") from first


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
