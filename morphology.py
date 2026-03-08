"""
morphology.py — Greek lemmatization and morphological parsing for Logeionicon

Uses Logeion's wordwheel + Perseus Morpheus API for full parses.
"""

import httpx
import unicodedata
import os
from typing import Optional

MORPHEUS_API = "https://morph.perseids.org/analysis/word"


async def lemmatize(word: str, timeout: float = 10.0) -> dict:
    """
    Find the lemma for a Greek word.
    Returns dict with: input, lemma, all_lemmas, source, is_inflected.
    """
    from api import fetch_wordwheel

    wordwheel_results = []
    try:
        wordwheel_results = await fetch_wordwheel(word, timeout=timeout)
    except Exception:
        pass

    if word in wordwheel_results:
        return {"input": word, "lemma": word, "all_lemmas": [word],
                "source": "logeion", "is_inflected": False}

    morpheus_result = await _morpheus_parse(word, timeout=timeout)
    if morpheus_result and morpheus_result.get("lemmas"):
        lemmas = morpheus_result["lemmas"]
        return {"input": word, "lemma": lemmas[0], "all_lemmas": lemmas,
                "source": "morpheus", "is_inflected": lemmas[0] != word}

    if wordwheel_results:
        best = _find_closest(word, wordwheel_results)
        return {"input": word, "lemma": best, "all_lemmas": wordwheel_results[:5],
                "source": "logeion_wordwheel", "is_inflected": best != word}

    return {"input": word, "lemma": word, "all_lemmas": [word],
            "source": "unchanged", "is_inflected": False}


async def full_parse(word: str, timeout: float = 10.0) -> list:
    """Get full morphological parse(s) for a Greek word via Perseus Morpheus."""
    result = await _morpheus_parse(word, timeout=timeout)
    if not result:
        return [{"lemma": word, "part_of_speech": "unknown", "features": {}, "short_label": ""}]
    parses = [_format_parse(e) for e in result.get("entries", []) if _format_parse(e)]
    return parses or [{"lemma": word, "part_of_speech": "unknown", "features": {}, "short_label": ""}]


async def _morpheus_parse(word: str, timeout: float = 10.0) -> Optional[dict]:
    params = {"lang": "grc", "engine": "morpheusgrc", "word": word}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(MORPHEUS_API, params=params)
            if response.status_code != 200:
                return None
            return _parse_morpheus_response(response.json())
    except Exception:
        return None


def _parse_morpheus_response(data: dict) -> dict:
    result = {"lemmas": [], "entries": []}
    try:
        body = data.get("RDF", {}).get("Annotation", {}).get("Body", [])
        if isinstance(body, dict):
            body = [body]
        for annotation in body:
            entry_set = annotation.get("rest", {}).get("entry", {})
            if isinstance(entry_set, dict):
                entry_set = [entry_set]
            elif not isinstance(entry_set, list):
                continue
            for entry in entry_set:
                hdwd = entry.get("dict", {}).get("hdwd", {})
                lemma = hdwd.get("$") if isinstance(hdwd, dict) else str(hdwd)
                if lemma and lemma not in result["lemmas"]:
                    result["lemmas"].append(lemma)
                infl_list = entry.get("infl", [])
                if isinstance(infl_list, dict):
                    infl_list = [infl_list]
                for infl in infl_list:
                    result["entries"].append({
                        "lemma": lemma,
                        "pofs": _extract_value(infl.get("pofs")),
                        "case": _extract_value(infl.get("case")),
                        "num": _extract_value(infl.get("num")),
                        "gend": _extract_value(infl.get("gend")),
                        "tense": _extract_value(infl.get("tense")),
                        "mood": _extract_value(infl.get("mood")),
                        "voice": _extract_value(infl.get("voice")),
                        "pers": _extract_value(infl.get("pers")),
                    })
    except Exception:
        pass
    return result


def _extract_value(field) -> Optional[str]:
    if field is None: return None
    if isinstance(field, dict): return field.get("$") or field.get("order")
    return str(field) if field else None


def _format_parse(entry: dict) -> dict:
    lemma = entry.get("lemma") or ""
    pofs = entry.get("pofs") or "unknown"
    features = {}
    labels = [pofs]

    pos_map = {"noun":"noun","verb":"verb","adjective":"adjective","adverb":"adverb",
               "particle":"particle","conjunction":"conjunction","preposition":"preposition",
               "pronoun":"pronoun","article":"article"}
    clean_pofs = pos_map.get(pofs.lower(), pofs)

    if entry.get("case"):
        features["case"] = entry["case"]; labels.append(entry["case"])
    if entry.get("num"):
        n = entry["num"]
        features["number"] = "singular" if n in ("sg","singular") else \
                             "plural" if n in ("pl","plural") else \
                             "dual" if n in ("du","dual") else n
        labels.append(features["number"])
    if entry.get("gend"):
        features["gender"] = entry["gend"]; labels.append(entry["gend"])
    if entry.get("tense"):
        features["tense"] = entry["tense"]; labels.append(entry["tense"])
    if entry.get("mood"):
        features["mood"] = entry["mood"]; labels.append(entry["mood"])
    if entry.get("voice"):
        features["voice"] = entry["voice"]; labels.append(entry["voice"])
    if entry.get("pers"):
        p = entry["pers"]
        person_map = {"1":"first","2":"second","3":"third","1st":"first","2nd":"second","3rd":"third"}
        features["person"] = person_map.get(p, p); labels.append(features["person"])

    return {"lemma": lemma, "part_of_speech": clean_pofs,
            "features": features, "short_label": ", ".join(filter(None, labels))}


def _find_closest(word: str, candidates: list) -> str:
    normalized_word = _strip_diacritics(word)
    best, best_score = candidates[0], 0
    for candidate in candidates:
        score = len(os.path.commonprefix([normalized_word, _strip_diacritics(candidate)]))
        if score > best_score:
            best_score = score; best = candidate
    return best


def _strip_diacritics(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if not unicodedata.combining(c))
