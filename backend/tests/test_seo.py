"""Unit tests for the Groq SEO pack module (pure core, no network)."""

from __future__ import annotations

import importlib.util
import json

import pytest

from app.models import SeoPack
from app.pipeline import seo
from app.pipeline.seo import PLATFORM_TEXT_LIMITS, SeoError, build_prompt, parse_seo_json


class TestBuildPrompt:
    def test_contains_platform_rules_and_transcript(self) -> None:
        messages = build_prompt("Ankle mobility drills.", "tiktok", {"duration_s": 30})
        joined = json.dumps(messages)
        assert "Ankle mobility drills." in joined
        assert "tiktok" in joined
        assert "Title max: 100" in joined
        assert "Hashtags: 3 to 5" in joined
        assert "30" in joined  # duration

    def test_x_limits_differ(self) -> None:
        messages = build_prompt("t", "x", {"duration_s": 10})
        joined = json.dumps(messages)
        assert "Title max: 280" in joined
        assert "Hashtags: 1 to 3" in joined

    def test_unknown_platform_falls_back_to_tiktok_rules(self) -> None:
        messages = build_prompt("t", "unknown", {"duration_s": 1})
        assert "Title max: 100" in json.dumps(messages)


class TestParseSeoJson:
    def test_happy_path(self) -> None:
        raw = json.dumps(
            {"title": "Ankle Mobility in 30s", "description": "Drill 1, 2, 3.", "hashtags": ["ankle", "mobility", "fitness"]}
        )
        pack = parse_seo_json(raw, "tiktok")
        assert isinstance(pack, SeoPack)
        assert pack.title == "Ankle Mobility in 30s"
        assert pack.hashtags == ["ankle", "mobility", "fitness"]
        assert pack.error is None

    def test_clamps_overlong_title_and_description(self) -> None:
        raw = json.dumps({"title": "x" * 500, "description": "y" * 5000, "hashtags": []})
        pack = parse_seo_json(raw, "tiktok")
        assert len(pack.title) == 100
        assert len(pack.description) == 2200

    def test_strips_hash_prefix_and_dedupes(self) -> None:
        raw = json.dumps(
            {"title": "t", "description": "d", "hashtags": ["#Fitness", "FITNESS", "!!!", "   " ]}
        )
        pack = parse_seo_json(raw, "tiktok")
        assert pack.hashtags == ["fitness"]  # lowercased, deduped, empties dropped

    def test_limits_hashtag_count(self) -> None:
        raw = json.dumps({"title": "t", "description": "d", "hashtags": [f"tag{i}" for i in range(20)]})
        pack = parse_seo_json(raw, "tiktok")
        assert len(pack.hashtags) == 5  # tiktok max

    def test_x_joins_within_280(self) -> None:
        raw = json.dumps(
            {
                "title": "T" * 150,
                "description": "D" * 120,
                "hashtags": ["aaaa", "bbbb", "cccc"],
            }
        )
        pack = parse_seo_json(raw, "x")
        total = len(pack.title) + len(pack.description) + sum(len(t) + 2 for t in pack.hashtags)
        assert total <= 280

    def test_missing_keys_rejected(self) -> None:
        with pytest.raises(SeoError):
            parse_seo_json('{"title": "t"}', "tiktok")

    def test_non_json_rejected(self) -> None:
        with pytest.raises(SeoError):
            parse_seo_json("not json at all", "tiktok")


class TestStackAvailable:
    def test_false_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(seo.config, "GROQ_API_KEY", None)
        assert seo.stack_available() is False

    def test_false_without_groq_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(seo.config, "GROQ_API_KEY", "k")
        monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)
        assert seo.stack_available() is False

    def test_true_with_key_and_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(seo.config, "GROQ_API_KEY", "k")
        assert seo.stack_available() is True


class TestGeneratePack:
    def test_retries_once_on_parse_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[float] = []

        def fake_call(api_key, transcript, platform, meta, temperature, timeout_s):
            calls.append(temperature)
            if temperature == 0.7:
                return "not json"
            return json.dumps({"title": "t", "description": "d", "hashtags": ["a", "b", "c"]})

        monkeypatch.setattr(seo, "_call_groq", fake_call)
        pack = seo.generate_pack("k", "transcript", "tiktok", {})
        assert pack.title == "t"
        assert calls == [0.7, 0.0]  # retry happened

    def test_raises_after_two_failures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_call(api_key, transcript, platform, meta, temperature, timeout_s):
            return "still not json"

        monkeypatch.setattr(seo, "_call_groq", fake_call)
        with pytest.raises(SeoError):
            seo.generate_pack("k", "t", "tiktok", {})

    def test_raises_on_api_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The real _call_groq wraps API errors into SeoError; emulate that so
        # generate_pack's retry-then-raise path is exercised end to end.
        def fake_call(api_key, transcript, platform, meta, temperature, timeout_s):
            raise SeoError("Groq API error: connection refused")

        monkeypatch.setattr(seo, "_call_groq", fake_call)
        with pytest.raises(SeoError, match="Groq API error"):
            seo.generate_pack("k", "t", "tiktok", {})
