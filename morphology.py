"""
morphology.py — Greek lemmatization and morphological parsing for Logeionicon
Uses Logeion's own /find endpoint as primary source.
"""

import unicodedata
from typing import Optional


async def lemmatize(word: str, timeout: float = 10.0) -> dict:
    """
    Find the lemma for a Greek word using Logeion's /find endpoint.
    Returns: { "input", "lemma", "all_lemmas", "source", "is_inflected" }
    """
    from api import fetch_find

    try:
        result = await fetch_find(word, timeout=timeout)
        found_word = result.get("word")
        parses = result.get("parses", [])

        if found_word and parses:
            lemmas = list({p["lemma"] for p in parses if p.get("lemma")})
            best = lemmas[0] if lemmas else found_word
            return {
                "input": word,
                "lemma": best,
                "all_lemmas": lemmas,
                "source": "logeion_find",
                "is_inflected": best != word,
            }
        elif found_word:
            return {
                "input": word,
                "lemma": found_word,
                "all_lemmas": [found_word],
                "source": "logeion_find",
                "is_inflected": found_word != word,
            }
    except Exception:
        pass

    # Fallback: return unchanged
    return {
        "input": word,
        "lemma": word,
        "all_lemmas": [word],
        "source": "unchanged",
        "is_inflected": False,
    }


async def full_parse(word: str, timeout: float = 10.0) -> list:
    """
    Get full morphological parse(s) via Logeion's /find endpoint.
    Returns list of parse dicts: { lemma, part_of_speech, features, short_label }
    """
    from api import fetch_find

    try:
        result = await fetch_find(word, timeout=timeout)
        parses = result.get("parses", [])
        if parses:
            return [_format_parse(p) for p in parses]
    except Exception:
        pass

    return [{"lemma": word, "part_of_speech": "unknown", "features": {}, "short_label": ""}]


def _format_parse(parse_entry: dict) -> dict:
    """
    Format a Logeion /find parse entry.
    Logeion returns: {"lemma": "λόγος", "parse": " - Noun - masculine - nominative singular"}
    """
    lemma = parse_entry.get("lemma", "")
    parse_str = parse_entry.get("parse", "")

    # Parse the string: " - Noun - masculine - nominative singular"
    parts = [p.strip() for p in parse_str.split(" - ") if p.strip()]

    features = {}
    pofs = "unknown"
    labels = []

    if parts:
        pofs = parts[0].lower()
        labels.append(pofs)

    # Map remaining parts to features
    case_words = {"nominative", "genitive", "dative", "accusative", "vocative"}
    number_words = {"singular", "plural", "dual"}
    gender_words = {"masculine", "feminine", "neuter"}
    tense_words = {"present", "imperfect", "future", "aorist", "perfect",
                   "pluperfect", "future perfect"}
    mood_words = {"indicative", "subjunctive", "optative", "imperative",
                  "infinitive", "participle"}
    voice_words = {"active", "middle", "passive", "medio-passive"}
    person_words = {"first", "second", "third",
                    "1st", "2nd", "3rd"}

    for part in parts[1:]:
        pl = part.lower()
        if any(c in pl for c in case_words):
            features["case"] = pl
            labels.append(pl)
        elif pl in number_words:
            features["number"] = pl
            labels.append(pl)
        elif pl in gender_words:
            features["gender"] = pl
            labels.append(pl)
        elif pl in tense_words:
            features["tense"] = pl
            labels.append(pl)
        elif pl in mood_words:
            features["mood"] = pl
            labels.append(pl)
        elif pl in voice_words:
            features["voice"] = pl
            labels.append(pl)
        elif pl in person_words or "person" in pl:
            features["person"] = pl
            labels.append(pl)
        else:
            labels.append(pl)

    return {
        "lemma": lemma,
        "part_of_speech": pofs,
        "features": features,
        "short_label": ", ".join(labels),
        "raw_parse": parse_str,
    }
