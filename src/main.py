"""Run the local music-curator agent against representative profiles."""

from pathlib import Path
from typing import List, Sequence

try:
    from .agent import MusicCuratorAgent
    from .recommender import load_songs
except ImportError:
    from agent import MusicCuratorAgent
    from recommender import load_songs


ROOT = Path(__file__).resolve().parents[1]


def format_ascii_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """Render rows as a bordered, column-aligned ASCII table."""
    widths = [len(header) for header in headers]
    for row in rows:
        if len(row) != len(headers):
            raise ValueError("Each table row must have the same number of cells as headers")
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))

    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"

    def format_row(cells: Sequence[str]) -> str:
        return "| " + " | ".join(
            str(cell).ljust(width) for cell, width in zip(cells, widths)
        ) + " |"

    lines = [border, format_row(headers), border]
    lines.extend(format_row(row) for row in rows)
    lines.append(border)
    return "\n".join(lines)


def main() -> None:
    songs = load_songs(str(ROOT / "data" / "songs.csv"))
    agent = MusicCuratorAgent(songs)
    profiles = [
        ("Focused study", {
            "genre": "lofi",
            "mood": "focused",
            "energy": 0.4,
            "scenario": "study",
        }),
        ("Workout", {
            "genre": "pop",
            "mood": "intense",
            "energy": 0.9,
            "scenario": "workout",
        }),
        ("Adversarial: heartbreak with high energy", {
            "genre": "shoegaze",
            "mood": "sad",
            "energy": 1.4,
            "scenario": "heartbreak",
            "unexpected_field": "ignored safely",
        }),
    ]

    print(f"Loaded {len(songs)} songs.")
    for name, profile in profiles:
        result = agent.run(profile, k=5)
        print(f"\nProfile: {name}")
        if result["validation"]["warnings"]:
            print("Input validation: " + "; ".join(result["validation"]["warnings"]))
        print(f"Plan: strategy={result['plan']['strategy']}; "
              f"retrieval query={result['plan']['retrieval_query']!r}")
        print("Retrieved RAG context:")
        for entry in result["context"]:
            print(f"  - [{entry['category']}: {entry['key']}] {entry['note']}")
        if result["scoring_tags_added"]:
            print("  Contextual scoring tags: "
                  f"{', '.join(result['scoring_tags_added'])}")
        print(f"Guardrail action: {result['guardrail']['action']}")
        print(f"Final guardrail: {'passed' if result['guardrail']['final']['passed'] else 'flagged'}")
        print(f"Confidence: {result['confidence']['score']:.2f} "
              f"(margin={result['confidence']['components']['score_margin']:.2f}, "
              f"coverage={result['confidence']['components']['match_coverage']:.2f}, "
              f"input reliability={result['confidence']['components']['input_reliability']:.2f})")
        if result["guardrail"]["final"]["findings"]:
            print(f"Guardrail findings: {result['guardrail']['final']['findings']}")
        rows: List[List[str]] = [
            [
                str(rank),
                song.get("title", ""),
                song.get("artist", ""),
                f"{score:.2f}",
                "; ".join(reasons) if reasons else "No strong preference matches",
            ]
            for rank, (song, score, reasons) in enumerate(result["recommendations"], start=1)
        ]
        print(format_ascii_table(["Rank", "Title", "Artist", "Score", "Reasons"], rows))
    print(f"\nStructured agent trace written to {agent.trace_path}")


if __name__ == "__main__":
    main()
