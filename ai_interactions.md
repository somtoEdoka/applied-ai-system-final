# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agentic Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

Implement the music-recommender stretch challenges: enrich the song catalog and explainable scoring, add switchable scoring modes, diversify recommendations, and present the results clearly.

**Prompts used:**

- **Challenge 1:** “Add five new song attributes to the CSV, parse their types, and incorporate optional preferences in explainable scoring.”
- **Challenge 2:** “Use a Strategy pattern for balanced, genre-first, mood-first, and energy-focused scoring modes, then compare modes on one profile.”
- **Challenges 3–4:** “Apply a greedy repeat-artist penalty to recommendations and render the results as an aligned ASCII table.”

**What did the agent generate or change?**

Added popularity, release decade, detailed mood tags, musical key, and time signature to the catalog; added metadata scoring and four dictionary-backed strategies; added an iterative artist-diversity penalty and a standard-library ASCII table. The CLI compares scoring modes using one profile. Focused tests cover parsing, ranking changes, explanations, diversity, and table alignment.

**What did you verify or fix manually?**

Manually checked the CSV headers and row shapes, reviewed the displayed rankings and explanation strings, and ran the CLI and pytest suite. The catalog check reported 15 headers, 18 song rows, and zero malformed rows.

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

Strategy, implemented as a dictionary mapping each mode name to its scoring weights.

**How did AI help you brainstorm or implement it?**

AI compared a mode-to-weights strategy table with scattered mode-specific conditionals. The table keeps each strategy's weights together, allows the existing scoring loop to be reused, and makes adding a mode a local change. The optional `mode="balanced"` argument preserves the default behavior for existing calls.

**How does the pattern appear in your final code?**

`SCORING_STRATEGIES` in `src/recommender.py` contains the `balanced`, `genre_first`, `mood_first`, and `energy_focused` strategies. `score_song()` reads the selected weights, and `recommend_songs()` passes through the mode.

## Challenge 1: Advanced Song Features

The five new CSV columns are `popularity` (integer), `release_decade` (integer), `detailed_mood_tags` (pipe-separated in the file and parsed as a list), `key` (text), and `time_signature` (integer). Optional profile preferences score popularity and decade by proximity, tags by overlap, and key/time signature by exact match; each contributing feature adds an explanation reason. Danceability and acousticness were already in the catalog and remain supported.

Manual verification confirmed 15 unique headers, 18 rows, and no missing or extra CSV cells. The loader produced integer values for the numeric metadata and a list of strings for mood tags.

## Challenge 3: Diversity Penalty

`recommend_songs()` greedily selects the best remaining candidate at each rank. Once an artist has been selected, later songs by that artist receive the configurable default `0.5` score reduction and a `diversity penalty (-0.50: repeat artist)` explanation. The returned score reflects the adjusted score.

## Challenge 4: Visual Summary Table

The CLI formats each mode's results as an aligned ASCII table with Rank, Title, Artist, Score, and Reasons columns. Column widths are calculated from the output, using Python's standard library without requiring `tabulate`.

## Agentic Workflow Reasoning Traces

The agent records its sanitized profile, plan, retrieved local context, ranking,
diversity critique, any reranking action, and confidence in
[`logs/agent_trace.json`](logs/agent_trace.json). This excerpt is from a real
`genre=lofi`, `k=3` run and follows the Plan -> Retrieve -> Self-Critique ->
Re-rank path:

```json
{
  "profile": {"genre": "lofi"},
  "plan": {
    "strategy": "genre_first",
    "retrieval_query": "lofi"
  },
  "retrieval": {
    "query": "lofi",
    "contexts": [
      {"category": "genre", "key": "lofi"},
      {"category": "general", "key": "music listening"}
    ],
    "scoring_tags_added": ["focused", "calm", "introspective"]
  },
  "ranking": {
    "strategy": "mood_first",
    "diversity_penalty": 3.0
  },
  "guardrail": {
    "initial": {
      "passed": false,
      "findings": [
        {"type": "genre_concentration", "value": "lofi", "share": 1.0},
        {"type": "artist_concentration", "value": "loroom", "share": 0.6667}
      ]
    },
    "final": {"passed": false},
    "action": "Re-ranked with strategy=mood_first and diversity_penalty=3.0; guardrail still flags concentration."
  },
  "confidence": {"score": 0.7766}
}
```

The critique triggers a second ranking pass and increases the repeat-artist
penalty. The trace also shows the remaining genre concentration: reranking is a
best-effort corrective step, not a guarantee when the catalog is this small.
