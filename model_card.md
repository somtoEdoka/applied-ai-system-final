# 🎧 Model Card: VibeFinder 1.0

## 1. Model Name

**VibeFinder 1.0** is a small, explainable music recommender for classroom learning.

## 2. Goal / Task

VibeFinder predicts which songs in its catalog best match a user's stated taste. It ranks songs and gives a short explanation for each recommendation.

## 3. Data Used

The dataset contains **18 songs**. Each row has an ID, title, artist, genre, mood, energy, tempo, valence, danceability, and acousticness. It includes styles such as pop, lofi, rock, jazz, classical, and reggae, but many genres and moods appear only once. The catalog has no listening history, user ratings, lyrics, or broad coverage of music.

## 4. Algorithm Summary

The curator validates and sanitizes a profile, selects one of four scoring modes, and retrieves editorial notes from `data/music_knowledge.json`. Retrieved mood tags are added to the scoring profile before calling the existing content-based ranker. A post-ranking guardrail checks whether one genre or artist exceeds 60% of the requested list and reranks with adjusted strategy weights and/or artist diversity penalty when needed. The agent reports confidence based on score margin, catalog match coverage, and input reliability, and writes its steps to `logs/agent_trace.json`.

The base `balanced` mode retains the original 30-point genre and 25-point mood exact-match weights, plus proximity weights for audio features. `genre_first`, `mood_first`, and `energy_focused` use alternative weights. Profiles with energy, danceability, or acousticness outside 0.0–1.0 are clamped, and conflicting or unsupported preferences are reported rather than silently treated as a strong match.

## 5. Strengths

The rules are simple to understand, and the score reasons make rankings easy to inspect. When a profile uses labels that exist in the catalog, songs that match those labels tend to rise to the top. Energy matching also helps distinguish songs with different intensity.

## 6. Observed Behavior / Biases

The catalog contains only 18 hand-curated songs, with many genres and moods represented by just one song, so recommendations reflect the catalog's gaps rather than the full range of music. An exact genre match is worth 30 points and an exact mood match is worth 25, which can outweigh close audio-feature matches and may keep users in a narrow genre or mood. When a profile asks for an unseen genre and mood, as in our adversarial test, neither preference can match; the results are then driven largely by available numeric preferences. The agent checks artist and genre concentration, but its reranking cannot guarantee diversity when the catalog is limited.

In the Deep Intense Rock test, Storm Runner ranked first because it matched both requested labels and was close to the high energy target. The upgraded agent adds diversity checks and confidence reporting, but a small catalog can still produce a concentrated list or leave preferences unsupported. Retrieved editorial notes are contextual guidance and do not establish that a song is objectively suitable for a scenario.

---

## 7. Evaluation Process

The current `python -m src.main` run evaluates **Focused study**, **Workout**, and the adversarial **Heartbreak with high energy** profile. It prints each plan, retrieved notes, guardrail action, confidence components, and recommendation table. The full structured trace records the input warnings and whether the post-ranking guardrail passed. The baseline outputs below document the earlier recommender-only version; they are retained as a historical comparison and do not show the current agent's output.

- **High-Energy Pop:** pop, happy, energy 0.85.
- **Chill Lofi:** lofi, chill, energy 0.40.
- **Deep Intense Rock:** rock, intense, energy 0.90.
- **Conflicting edge case:** unseen shoegaze genre, sad mood, energy 0.90.

### Baseline terminal output

```text
Loaded 18 songs.

High-Energy Pop — Top recommendations:

1. Sunrise City - Neon Echo
   Score: 69.39
   Reasons: genre match (+30.0); mood match (+25.0); energy proximity (+14.39)

2. Gym Hero - Max Pulse
   Score: 43.38
   Reasons: genre match (+30.0); energy proximity (+13.38)

3. Rooftop Lights - Indigo Parade
   Score: 38.18
   Reasons: mood match (+25.0); energy proximity (+13.18)

4. Neon Pulse - Vector Bloom
   Score: 14.59
   Reasons: energy proximity (+14.59)

5. Paper Crown - Static Youth
   Score: 14.19
   Reasons: energy proximity (+14.19)


Chill Lofi — Top recommendations:

1. Midnight Coding - LoRoom
   Score: 69.59
   Reasons: genre match (+30.0); mood match (+25.0); energy proximity (+14.59)

2. Library Rain - Paper Lanterns
   Score: 68.99
   Reasons: genre match (+30.0); mood match (+25.0); energy proximity (+13.99)

3. Focus Flow - LoRoom
   Score: 45.00
   Reasons: genre match (+30.0); energy proximity (+15.00)

4. Spacewalk Thoughts - Orbit Bloom
   Score: 37.57
   Reasons: mood match (+25.0); energy proximity (+12.57)

5. Coffee Shop Stories - Slow Stereo
   Score: 14.39
   Reasons: energy proximity (+14.39)


Deep Intense Rock — Top recommendations:

1. Storm Runner - Voltline
   Score: 69.80
   Reasons: genre match (+30.0); mood match (+25.0); energy proximity (+14.80)

2. Gym Hero - Max Pulse
   Score: 39.39
   Reasons: mood match (+25.0); energy proximity (+14.39)

3. Paper Crown - Static Youth
   Score: 14.80
   Reasons: energy proximity (+14.80)

4. Neon Pulse - Vector Bloom
   Score: 14.39
   Reasons: energy proximity (+14.39)

5. Iron Horizon - Black Meridian
   Score: 13.78
   Reasons: energy proximity (+13.78)


Conflicting: Unseen Genre, Sad Mood, High Energy — Top recommendations:

1. Storm Runner - Voltline
   Score: 14.80
   Reasons: energy proximity (+14.80)

2. Paper Crown - Static Youth
   Score: 14.80
   Reasons: energy proximity (+14.80)

3. Gym Hero - Max Pulse
   Score: 14.39
   Reasons: energy proximity (+14.39)

4. Neon Pulse - Vector Bloom
   Score: 14.39
   Reasons: energy proximity (+14.39)

5. Iron Horizon - Black Meridian
   Score: 13.78
   Reasons: energy proximity (+13.78)
```

### What we observed

The results felt accurate when a profile's genre and mood existed in the catalog. Chill Lofi starts with two songs matching both labels, and Deep Intense Rock starts with a song matching rock and intense. Storm Runner ranked first there because it earned 30 genre points, 25 mood points, and 14.80 points for energy proximity. I was surprised that the conflicting profile still produced a full ranked list even though its genre and mood did not match any song.

### Pairwise profile comparisons

- **High-Energy Pop vs. Chill Lofi:** The pop profile favors Sunrise City and Gym Hero, while the lofi profile favors Midnight Coding, Library Rain, and Focus Flow. This makes sense because each profile's exact genre and mood matches earn large bonuses; the lower target energy also helps the calmer lofi songs.
- **High-Energy Pop vs. Deep Intense Rock:** Sunrise City wins for pop/happy, whereas Storm Runner wins for rock/intense. Gym Hero appears in both lists because it is pop and energetic, and it also matches the intense mood even though its genre is not rock.
- **High-Energy Pop vs. the conflicting profile:** The pop profile has exact genre and mood matches, which place Sunrise City first. The conflicting profile has no matching labels, so its recommendations are determined only by closeness to high energy, with Storm Runner and Paper Crown tied at the top.
- **Chill Lofi vs. Deep Intense Rock:** The chill profile favors lofi/chill songs around energy 0.40, while the rock profile favors Storm Runner, which matches rock/intense and has high energy. Their shared high-scoring rule is the exact-match bonus, applied to different labels.
- **Chill Lofi vs. the conflicting profile:** Lofi/chill receives two exact-match bonuses, giving Midnight Coding and Library Rain large leads. The conflicting profile receives neither bonus, so higher-energy songs rise based on energy closeness.
- **Deep Intense Rock vs. the conflicting profile:** Both ask for high energy, so their lists overlap on Storm Runner, Paper Crown, Gym Hero, Neon Pulse, and Iron Horizon. Storm Runner receives both exact-match bonuses only for the rock profile; in the conflicting list it earns energy points alone.

### Weight Shift sensitivity experiment

We temporarily changed genre weight from 30 to 15 points and energy weight from 15 to 30 points. All other weights stayed the same. Songs closer to the energy target gained influence. The experiment output was:

```text
Loaded 18 songs.

High-Energy Pop — Top recommendations:

1. Sunrise City - Neon Echo
   Score: 68.78
   Reasons: genre match (+15.0); mood match (+25.0); energy proximity (+28.78)

2. Rooftop Lights - Indigo Parade
   Score: 51.35
   Reasons: mood match (+25.0); energy proximity (+26.35)

3. Gym Hero - Max Pulse
   Score: 41.76
   Reasons: genre match (+15.0); energy proximity (+26.76)

4. Neon Pulse - Vector Bloom
   Score: 29.19
   Reasons: energy proximity (+29.19)

5. Paper Crown - Static Youth
   Score: 28.38
   Reasons: energy proximity (+28.38)


Chill Lofi — Top recommendations:

1. Midnight Coding - LoRoom
   Score: 69.19
   Reasons: genre match (+15.0); mood match (+25.0); energy proximity (+29.19)

2. Library Rain - Paper Lanterns
   Score: 67.97
   Reasons: genre match (+15.0); mood match (+25.0); energy proximity (+27.97)

3. Spacewalk Thoughts - Orbit Bloom
   Score: 50.14
   Reasons: mood match (+25.0); energy proximity (+25.14)

4. Focus Flow - LoRoom
   Score: 45.00
   Reasons: genre match (+15.0); energy proximity (+30.00)

5. Coffee Shop Stories - Slow Stereo
   Score: 28.78
   Reasons: energy proximity (+28.78)


Deep Intense Rock — Top recommendations:

1. Storm Runner - Voltline
   Score: 69.59
   Reasons: genre match (+15.0); mood match (+25.0); energy proximity (+29.59)

2. Gym Hero - Max Pulse
   Score: 53.78
   Reasons: mood match (+25.0); energy proximity (+28.78)

3. Paper Crown - Static Youth
   Score: 29.59
   Reasons: energy proximity (+29.59)

4. Neon Pulse - Vector Bloom
   Score: 28.78
   Reasons: energy proximity (+28.78)

5. Iron Horizon - Black Meridian
   Score: 27.57
   Reasons: energy proximity (+27.57)


Conflicting: Unseen Genre, Sad Mood, High Energy — Top recommendations:

1. Storm Runner - Voltline
   Score: 29.59
   Reasons: energy proximity (+29.59)

2. Paper Crown - Static Youth
   Score: 29.59
   Reasons: energy proximity (+29.59)

3. Gym Hero - Max Pulse
   Score: 28.78
   Reasons: energy proximity (+28.78)

4. Neon Pulse - Vector Bloom
   Score: 28.78
   Reasons: energy proximity (+28.78)

5. Iron Horizon - Black Meridian
   Score: 27.57
   Reasons: energy proximity (+27.57)
```

In the shifted run, Rooftop Lights moved above Gym Hero for High-Energy Pop, and Spacewalk Thoughts moved above Focus Flow for Chill Lofi. Deep Intense Rock and the conflicting profile kept the same top-five order, but their scores changed. The baseline weights were restored after the experiment.

## 8. Intended Use and Non-Intended Use

This simulation is built to teach and demonstrate content-based filtering. It compares stated preferences with song attributes and explains its scores. It is not built for a production streaming service. It should not be used for large-scale personalization without user histories, broader data, and careful evaluation.

## 9. Ideas for Improvement

- Add a larger, more diverse song catalog so more genres and moods are represented.
- Normalize tempo and other features with clear, data-driven ranges, then test their effect on rankings.
- Collect likes, skips, and listening history to add user feedback and collaborative filtering.

## 10. Personal Reflection

My biggest learning moment was seeing how changing a few weights changed which songs appeared near the top. AI tools helped me implement and explain the recommender, but I needed to double-check the CSV schema, the scoring math and weights, and the exact CLI output. I was surprised that simple weighted rules could still feel like real recommendations because the matches were recognizable and the reasons were clear. If I extended the project, I would add a larger catalog and use listener feedback, such as likes and skips, to improve recommendations.
