"""Run deterministic reliability scenarios for the music-curator agent."""

import tempfile
from pathlib import Path
from typing import Any, Dict, List

try:
    from .agent import MusicCuratorAgent
    from .recommender import load_songs
except ImportError:
    from agent import MusicCuratorAgent
    from recommender import load_songs


ROOT = Path(__file__).resolve().parents[1]
TOP_K = 5
SCENARIOS = [
    {"name": "Normal study profile", "profile": {
        "genre": "lofi", "mood": "focused", "energy": 0.4, "scenario": "study",
    }, "guardrail_expected": False},
    {"name": "Normal workout profile", "profile": {
        "genre": "pop", "mood": "intense", "energy": 0.9, "scenario": "workout",
    }, "guardrail_expected": False},
    {"name": "Conflicting sad/high energy", "profile": {
        "mood": "sad", "energy": 1.2,
    }, "guardrail_expected": True},
    {"name": "Unknown genre", "profile": {
        "genre": "unlisted-genre",
    }, "guardrail_expected": True},
    {"name": "Empty profile", "profile": {}, "guardrail_expected": True},
    {"name": "Extreme numeric values", "profile": {
        "energy": -4.0, "danceability": 3.0,
    }, "guardrail_expected": True},
    {"name": "Missing profile", "profile": None, "guardrail_expected": True},
]


def evaluate_scenario(
    agent: MusicCuratorAgent,
    scenario: Dict[str, Any],
    song_count: int,
) -> Dict[str, Any]:
    """Run one scenario and report each pass/fail criterion."""
    result: Dict[str, Any] = {
        "name": scenario["name"],
        "expected_guardrail": scenario["guardrail_expected"],
        "actual_guardrail": False,
        "top_k_valid": False,
        "confidence": None,
        "passed": False,
        "details": [],
    }
    try:
        output = agent.run(scenario["profile"], k=TOP_K)
    except Exception as error:  # Report scenario failures while continuing the harness.
        result["details"].append(f"crashed: {type(error).__name__}: {error}")
        return result

    validation = output["validation"]
    result["actual_guardrail"] = bool(
        validation["warnings"] or validation["conflicts"] or validation["fallback"]
    )
    expected_count = min(TOP_K, song_count)
    result["top_k_valid"] = len(output["recommendations"]) == expected_count
    result["confidence"] = output["confidence"]["score"]
    confidence_valid = 0.0 <= result["confidence"] <= 1.0

    if result["top_k_valid"] is False:
        result["details"].append(
            f"expected {expected_count} recommendations; got "
            f"{len(output['recommendations'])}"
        )
    if result["actual_guardrail"] != result["expected_guardrail"]:
        result["details"].append(
            f"guardrail expected {result['expected_guardrail']}, "
            f"got {result['actual_guardrail']}"
        )
    if not confidence_valid:
        result["details"].append(f"confidence out of range: {result['confidence']}")
    result["passed"] = (
        result["top_k_valid"]
        and result["actual_guardrail"] == result["expected_guardrail"]
        and confidence_valid
    )
    return result


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def main() -> None:
    songs = load_songs(str(ROOT / "data" / "songs.csv"))
    with tempfile.TemporaryDirectory(prefix="music-curator-eval-") as temp_dir:
        agent = MusicCuratorAgent(
            songs,
            knowledge_path=ROOT / "data" / "music_knowledge.json",
            trace_path=Path(temp_dir) / "agent_trace.json",
        )
        results = [
            evaluate_scenario(agent, scenario, len(songs))
            for scenario in SCENARIOS
        ]

    print("| Scenario | Status | Guardrail (expected / actual) | Top-K | Confidence | Details |")
    print("|---|---|---|---:|---:|---|")
    for result in results:
        confidence = (
            f"{result['confidence']:.4f}"
            if result["confidence"] is not None else "N/A"
        )
        details = "; ".join(result["details"]) or "All criteria passed"
        print(
            f"| {_markdown_cell(result['name'])} "
            f"| {'PASS' if result['passed'] else 'FAIL'} "
            f"| {result['expected_guardrail']} / {result['actual_guardrail']} "
            f"| {'PASS' if result['top_k_valid'] else 'FAIL'} "
            f"| {confidence} | {_markdown_cell(details)} |"
        )

    passed = sum(result["passed"] for result in results)
    confidence_scores: List[float] = [
        result["confidence"] for result in results
        if result["confidence"] is not None
    ]
    average_confidence = (
        sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    )
    print(f"\nOverall pass rate: {passed}/{len(results)} ({passed / len(results):.1%})")
    print(f"Average confidence score: {average_confidence:.4f}")


if __name__ == "__main__":
    main()
