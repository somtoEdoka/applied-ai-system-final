"""Input validation and post-ranking checks for the music curator."""

import math
from typing import Any, Dict, List, Sequence, Tuple


_NUMERIC_FIELDS = {
    "energy",
    "danceability",
    "acousticness",
    "valence",
    "tempo_bpm",
    "popularity",
    "release_decade",
    "time_signature",
}
_CLAMPED_FIELDS = {"energy", "danceability", "acousticness"}
_ALLOWED_FIELDS = _NUMERIC_FIELDS | {
    "genre",
    "mood",
    "detailed_mood_tags",
    "key",
    "scenario",
    "listening_scenario",
}
_SAD_MOODS = {"sad", "heartbroken", "heartbreak", "melancholic", "melancholy"}


def sanitize_profile(
    profile: Any, songs: Sequence[Dict[str, Any]] = ()
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return a safe scoring profile and validation findings."""
    sanitized: Dict[str, Any] = {}
    warnings: List[str] = []
    conflicts: List[str] = []
    fallback = not isinstance(profile, dict) or not profile

    if not isinstance(profile, dict):
        warnings.append("Profile was missing or not an object; using an empty profile.")
        profile = {}

    aliases = {"favorite_genre": "genre", "favorite_mood": "mood"}
    for raw_key, value in profile.items():
        key = aliases.get(raw_key, raw_key)
        if key not in _ALLOWED_FIELDS:
            warnings.append(f"Ignored unknown profile field: {raw_key}.")
            continue
        if value is None:
            continue

        if key in _NUMERIC_FIELDS:
            if isinstance(value, bool):
                warnings.append(f"Ignored invalid numeric value for {key}.")
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                warnings.append(f"Ignored invalid numeric value for {key}.")
                continue
            if not math.isfinite(number):
                warnings.append(f"Ignored non-finite numeric value for {key}.")
                continue
            if key in _CLAMPED_FIELDS:
                clamped = min(1.0, max(0.0, number))
                if clamped != number:
                    warnings.append(f"Clamped {key} to the range 0.0–1.0.")
                number = clamped
            if key in {"popularity", "release_decade", "time_signature"} and number.is_integer():
                sanitized[key] = int(number)
            else:
                sanitized[key] = number
            continue

        if key == "detailed_mood_tags":
            values = value.split("|") if isinstance(value, str) else value
            if not isinstance(values, (list, tuple, set)):
                warnings.append("Ignored invalid detailed_mood_tags value.")
                continue
            tags = [str(tag).strip().lower() for tag in values if str(tag).strip()]
            if tags:
                sanitized[key] = list(dict.fromkeys(tags))
            continue

        text = str(value).strip().lower()
        if text:
            sanitized[key] = text

    if sanitized.get("genre") and songs:
        catalog_genres = {str(song.get("genre", "")).casefold() for song in songs}
        if sanitized["genre"].casefold() not in catalog_genres:
            warnings.append(f"Genre {sanitized['genre']!r} is not present in the catalog.")
            fallback = True
    if sanitized.get("mood") and songs:
        catalog_moods = {str(song.get("mood", "")).casefold() for song in songs}
        if sanitized["mood"].casefold() not in catalog_moods:
            warnings.append(f"Mood {sanitized['mood']!r} is not present in the catalog.")
            fallback = True

    if sanitized.get("mood", "").casefold() in _SAD_MOODS and sanitized.get("energy", 0) >= 0.75:
        conflicts.append("High energy conflicts with the requested sad mood.")
    if conflicts:
        warnings.extend(conflicts)

    return sanitized, {
        "warnings": warnings,
        "conflicts": conflicts,
        "fallback": fallback or not sanitized,
    }


def check_diversity(
    recommendations: Sequence[Tuple[Dict[str, Any], float, List[str]]],
    top_k: int = 5,
) -> Dict[str, Any]:
    """Flag genre or artist concentration above 60% in the selected results."""
    selected = recommendations[: max(top_k, 0)]
    threshold = 0.60
    findings = []
    denominator = len(selected)
    if denominator:
        for field in ("genre", "artist"):
            counts: Dict[str, int] = {}
            for song, _, _ in selected:
                value = str(song.get(field, "")).strip().casefold()
                if value:
                    counts[value] = counts.get(value, 0) + 1
            if counts:
                label, count = max(counts.items(), key=lambda item: item[1])
                share = count / denominator
                if share > threshold:
                    findings.append({
                        "type": f"{field}_concentration",
                        "value": label,
                        "share": round(share, 4),
                        "count": count,
                        "top_k": denominator,
                    })
    return {"passed": not findings, "threshold": threshold, "findings": findings}
