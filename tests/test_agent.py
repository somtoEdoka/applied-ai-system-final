import json

from src.agent import MusicCuratorAgent
from src.guardrails import check_diversity, sanitize_profile


def test_sanitize_profile_clamps_and_flags_conflict():
    profile, report = sanitize_profile({
        "energy": 1.4,
        "danceability": -0.5,
        "acousticness": 0.6,
        "mood": "sad",
        "unexpected": "ignored",
    })

    assert profile["energy"] == 1.0
    assert profile["danceability"] == 0.0
    assert profile["acousticness"] == 0.6
    assert report["conflicts"]
    assert any("unknown profile field" in warning for warning in report["warnings"])


def test_diversity_guardrail_flags_more_than_sixty_percent():
    recommendations = [
        ({"genre": "pop", "artist": f"Artist {index}"}, 1.0, [])
        for index in range(4)
    ] + [({"genre": "rock", "artist": "Different"}, 0.5, [])]

    result = check_diversity(recommendations, top_k=5)

    assert not result["passed"]
    assert result["findings"][0]["type"] == "genre_concentration"
    assert result["findings"][0]["share"] == 0.8


def test_agent_writes_trace_and_handles_empty_profile(tmp_path):
    songs = [
        {"title": f"Song {index}", "artist": f"Artist {index}",
         "genre": "pop", "mood": "happy", "energy": 0.5}
        for index in range(3)
    ]
    knowledge = tmp_path / "knowledge.json"
    knowledge.write_text(json.dumps({"entries": [
        {"category": "general", "key": "music listening",
         "terms": ["music", "listening", "general"], "note": "General note.",
         "scoring_tags": []}
    ]}), encoding="utf-8")
    trace = tmp_path / "logs" / "agent_trace.json"
    agent = MusicCuratorAgent(songs, knowledge_path=knowledge, trace_path=trace)

    result = agent.run({})

    assert len(result["recommendations"]) == 3
    assert result["confidence"]["score"] <= 1.0
    assert trace.is_file()
    assert len(json.loads(trace.read_text(encoding="utf-8"))["profiles"]) == 1


def test_agent_reranks_when_one_genre_dominates(tmp_path):
    songs = [
        {"title": f"Pop {index}", "artist": f"Artist {index}",
         "genre": "pop", "mood": "happy"}
        for index in range(4)
    ] + [{"title": "Rock", "artist": "Different", "genre": "rock", "mood": "calm"}]
    knowledge = tmp_path / "knowledge.json"
    knowledge.write_text(json.dumps({"entries": [
        {"category": "general", "key": "music listening",
         "terms": ["music", "listening", "general"], "note": "General note.",
         "scoring_tags": []}
    ]}), encoding="utf-8")
    agent = MusicCuratorAgent(
        songs,
        knowledge_path=knowledge,
        trace_path=tmp_path / "trace.json",
    )

    result = agent.run({"genre": "pop"}, k=5)

    assert "Re-ranked" in result["guardrail"]["action"]
    assert "strategy=mood_first" in result["guardrail"]["action"]
