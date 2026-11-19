"""Agentic music curation with local knowledge retrieval and trace logging."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

try:
    from .guardrails import check_diversity, sanitize_profile
    from .recommender import recommend_songs
except ImportError:
    from guardrails import check_diversity, sanitize_profile
    from recommender import recommend_songs


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_PATH = ROOT / "data" / "music_knowledge.json"
TRACE_PATH = ROOT / "logs" / "agent_trace.json"
_MATCH_FIELDS = {
    "genre": "genre",
    "mood": "mood",
    "energy": "energy",
    "danceability": "danceability",
    "acousticness": "acousticness",
    "valence": "valence",
    "tempo_bpm": "tempo_bpm",
    "popularity": "popularity",
    "release_decade": "release_decade",
    "time_signature": "time_signature",
    "key": "key",
    "detailed_mood_tags": "detailed_mood_tags",
}


class MusicCuratorAgent:
    """Plan, retrieve, rank, critique, and explain recommendations."""

    def __init__(
        self,
        songs: Sequence[Dict[str, Any]],
        knowledge_path: Path = KNOWLEDGE_PATH,
        trace_path: Path = TRACE_PATH,
    ) -> None:
        self.songs = list(songs)
        self.knowledge_path = Path(knowledge_path)
        self.trace_path = Path(trace_path)
        with self.knowledge_path.open("r", encoding="utf-8") as knowledge_file:
            self.knowledge = json.load(knowledge_file)["entries"]
        self.traces: List[Dict[str, Any]] = []

    @staticmethod
    def _plan(profile: Dict[str, Any]) -> Dict[str, str]:
        scenario = profile.get("scenario", profile.get("listening_scenario", ""))
        if profile.get("energy", 0) >= 0.75 or scenario in {"workout", "exercise", "gym", "training"}:
            strategy = "energy_focused"
        elif profile.get("genre") and not profile.get("mood"):
            strategy = "genre_first"
        elif profile.get("mood") and not profile.get("genre"):
            strategy = "mood_first"
        else:
            strategy = "balanced"
        query_parts = [
            profile.get("genre", ""),
            profile.get("mood", ""),
            scenario,
            *profile.get("detailed_mood_tags", []),
        ]
        query = " ".join(part for part in query_parts if part).strip() or "general music listening"
        return {"strategy": strategy, "retrieval_query": query}

    def _retrieve(self, query: str, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        query_terms = set(re.findall(r"[\w-]+", query.casefold()))
        ranked = []
        for entry in self.knowledge:
            searchable = " ".join([entry["key"], *entry.get("terms", [])]).casefold()
            entry_terms = set(re.findall(r"[\w-]+", searchable))
            overlap = len(query_terms & entry_terms)
            if overlap:
                ranked.append((overlap, entry))
        ranked.sort(key=lambda result: result[0], reverse=True)
        # Always include general guidance as a fallback, without displacing better matches.
        selected = [entry for _, entry in ranked[:3]]
        if not selected or all(entry["category"] != "general" for entry in selected):
            general = next(entry for entry in self.knowledge if entry["category"] == "general")
            selected.append(general)
        return selected

    def run(self, user_profile: Any, k: int = 5) -> Dict[str, Any]:
        profile, validation = sanitize_profile(user_profile, self.songs)
        plan = self._plan(profile)
        context = self._retrieve(plan["retrieval_query"], profile)
        scoring_profile = dict(profile)
        retrieved_tags = list(dict.fromkeys(
            tag for entry in context for tag in entry.get("scoring_tags", [])
        ))
        if retrieved_tags:
            scoring_profile["detailed_mood_tags"] = list(dict.fromkeys(
                [*scoring_profile.get("detailed_mood_tags", []), *retrieved_tags]
            ))

        initial = recommend_songs(scoring_profile, self.songs, k=k, mode=plan["strategy"])
        initial_guardrail = check_diversity(initial, top_k=k)
        recommendations = initial
        guardrail = initial_guardrail
        action = "No adjustment required."
        strategy = plan["strategy"]
        diversity_penalty = 0.5

        if not initial_guardrail["passed"]:
            issue_types = {finding["type"] for finding in initial_guardrail["findings"]}
            if "artist_concentration" in issue_types:
                diversity_penalty = 3.0
            if "genre_concentration" in issue_types:
                strategy = {
                    "genre_first": "mood_first",
                    "mood_first": "energy_focused",
                    "energy_focused": "balanced",
                    "balanced": "energy_focused",
                }[strategy]
            recommendations = recommend_songs(
                scoring_profile,
                self.songs,
                k=k,
                mode=strategy,
                diversity_penalty=diversity_penalty,
            )
            guardrail = check_diversity(recommendations, top_k=k)
            action = (
                f"Re-ranked with strategy={strategy} and "
                f"diversity_penalty={diversity_penalty:.1f}; "
                f"guardrail {'passed' if guardrail['passed'] else 'still flags concentration'}."
            )

        confidence = self._confidence(recommendations, profile, validation)
        trace = {
            "profile": profile,
            "validation": validation,
            "plan": plan,
            "retrieval": {
                "query": plan["retrieval_query"],
                "contexts": context,
                "scoring_tags_added": retrieved_tags,
            },
            "ranking": {
                "strategy": strategy,
                "diversity_penalty": diversity_penalty,
                "recommendations": [
                    {"title": song.get("title", ""), "artist": song.get("artist", ""),
                     "score": score, "reasons": reasons}
                    for song, score, reasons in recommendations
                ],
            },
            "guardrail": {
                "initial": initial_guardrail,
                "final": guardrail,
                "action": action,
            },
            "confidence": confidence,
        }
        self.traces.append(trace)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("w", encoding="utf-8") as trace_file:
            json.dump({"profiles": self.traces}, trace_file, indent=2, ensure_ascii=False)
            trace_file.write("\n")

        return {
            "profile": profile,
            "validation": validation,
            "plan": plan,
            "context": context,
            "scoring_tags_added": retrieved_tags,
            "guardrail": trace["guardrail"],
            "confidence": confidence,
            "recommendations": recommendations,
        }

    def _confidence(
        self,
        recommendations: Sequence[Tuple[Dict[str, Any], float, List[str]]],
        profile: Dict[str, Any],
        validation: Dict[str, Any],
    ) -> Dict[str, Any]:
        if len(recommendations) > 1:
            margin = max(0.0, recommendations[0][1] - recommendations[1][1])
            margin_score = margin / (margin + 10.0)
        elif recommendations:
            margin_score = 1.0
        else:
            margin_score = 0.0

        requested = [(key, value) for key, value in profile.items() if key in _MATCH_FIELDS]
        covered = 0
        for key, value in requested:
            field = _MATCH_FIELDS[key]
            if key == "detailed_mood_tags":
                found = any(
                    set(str(tag).casefold() for tag in value)
                    & set(str(tag).casefold() for tag in song.get(field, []))
                    for song in self.songs
                )
            elif key in {"genre", "mood"}:
                found = any(str(song.get(field, "")).casefold() == str(value).casefold()
                            for song in self.songs)
            else:
                found = bool(self.songs) and all(field in song for song in self.songs)
            covered += int(found)
        coverage = covered / len(requested) if requested else 0.0
        reliability = 0.5 if validation["fallback"] or validation["conflicts"] else 1.0
        score = 0.35 * margin_score + 0.50 * coverage + 0.15 * reliability
        return {
            "score": round(min(1.0, max(0.0, score)), 4),
            "components": {
                "score_margin": round(margin_score, 4),
                "match_coverage": round(coverage, 4),
                "input_reliability": reliability,
            },
        }
