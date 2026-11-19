import json
from pathlib import Path

import pytest

from src import agent as agent_module
from src.agent import MusicCuratorAgent
from src.guardrails import sanitize_profile
from src.recommender import load_songs


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def songs():
    return load_songs(str(ROOT / "data" / "songs.csv"))


def make_agent(songs, tmp_path):
    return MusicCuratorAgent(
        songs,
        knowledge_path=ROOT / "data" / "music_knowledge.json",
        trace_path=tmp_path / "logs" / "agent_trace.json",
    )


def test_guardrails_clamp_numeric_values_and_detect_conflict():
    profile, report = sanitize_profile({
        "energy": 1.4,
        "danceability": -0.5,
        "acousticness": 0.6,
        "mood": "sad",
    })

    assert profile == {
        "energy": 1.0,
        "danceability": 0.0,
        "acousticness": 0.6,
        "mood": "sad",
    }
    assert len(report["conflicts"]) == 1
    assert any("Clamped energy" in warning for warning in report["warnings"])
    assert any("Clamped danceability" in warning for warning in report["warnings"])


@pytest.mark.parametrize("profile", [None, {}])
def test_guardrails_handle_missing_or_empty_profiles(profile):
    sanitized, report = sanitize_profile(profile)

    assert sanitized == {}
    assert report["fallback"] is True
    if profile is None:
        assert report["warnings"]
    else:
        assert report["warnings"] == []


def test_agent_runs_retrieves_rag_context_and_writes_json_trace(songs, tmp_path):
    agent = make_agent(songs, tmp_path)
    result = agent.run({
        "genre": "lofi",
        "mood": "focused",
        "energy": 0.4,
        "scenario": "study",
    })

    assert result["recommendations"]
    assert len(result["recommendations"]) == 5
    assert any(entry["key"] in {"lofi", "study"} for entry in result["context"])
    assert result["scoring_tags_added"]
    assert 0.0 <= result["confidence"]["score"] <= 1.0

    trace = json.loads(agent.trace_path.read_text(encoding="utf-8"))
    assert len(trace["profiles"]) == 1
    assert trace["profiles"][0]["retrieval"]["contexts"] == result["context"]
    assert trace["profiles"][0]["confidence"]["score"] == result["confidence"]["score"]


def test_agent_self_critiques_and_reranks_low_diversity(monkeypatch, tmp_path):
    songs = [
        {"title": f"Pop {index}", "artist": f"Artist {index}",
         "genre": "pop", "mood": "happy"}
        for index in range(4)
    ] + [{"title": "Rock", "artist": "Different", "genre": "rock", "mood": "calm"}]
    knowledge = tmp_path / "knowledge.json"
    knowledge.write_text(json.dumps({"entries": [
        {"category": "general", "key": "music listening",
         "terms": ["music", "listening", "general"], "note": "General guidance.",
         "scoring_tags": []}
    ]}), encoding="utf-8")
    agent = MusicCuratorAgent(
        songs,
        knowledge_path=knowledge,
        trace_path=tmp_path / "trace.json",
    )
    recommend = agent_module.recommend_songs
    call_count = 0

    def tracking_recommend(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return recommend(*args, **kwargs)

    monkeypatch.setattr(agent_module, "recommend_songs", tracking_recommend)
    result = agent.run({"genre": "pop"}, k=5)

    assert result["guardrail"]["initial"]["passed"] is False
    assert call_count == 2
    assert "Re-ranked" in result["guardrail"]["action"]


def test_agent_rankings_are_reproducible(songs, tmp_path):
    agent = make_agent(songs, tmp_path)
    profile = {"genre": "rock", "mood": "intense", "energy": 0.9}

    first = agent.run(profile, k=5)["recommendations"]
    second = agent.run(profile, k=5)["recommendations"]

    assert [(song["title"], score) for song, score, _ in first] == [
        (song["title"], score) for song, score, _ in second
    ]
