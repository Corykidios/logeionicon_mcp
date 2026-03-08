"""
favorites.py — Persistent personal Greek dictionary for Logeionicon

Storage: favorites.json (flat JSON, human-readable, gitignored)

Each entry:
{
  "word": "λόγος",
  "transliteration": "lo.gos",
  "holonic_definition": ". λόγος [lo.gos]: word, speech, reason...",
  "tags": ["philosophy", "important"],
  "added_at": "2025-01-01T12:00:00Z",
  "source": "LSJ"
}
"""

import json
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from format import transliterate

_DEFAULT_PATH = Path(__file__).parent / "favorites.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_word(word, holonic_definition, tags=None, source="LSJ", path=_DEFAULT_PATH):
    data = _load(path)
    entry = {
        "word": word,
        "transliteration": transliterate(word),
        "holonic_definition": holonic_definition,
        "tags": sorted(set(tags or [])),
        "added_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }
    data[word] = entry
    _save(data, path)
    return entry


def remove_word(word, path=_DEFAULT_PATH):
    data = _load(path)
    if word in data:
        del data[word]
        _save(data, path)
        return True
    return False


def tag_word(word, tags, replace=False, path=_DEFAULT_PATH):
    data = _load(path)
    if word not in data:
        return None
    if replace:
        data[word]["tags"] = sorted(set(tags))
    else:
        existing = set(data[word].get("tags", []))
        data[word]["tags"] = sorted(existing | set(tags))
    _save(data, path)
    return data[word]


def untag_word(word, tags, path=_DEFAULT_PATH):
    data = _load(path)
    if word not in data:
        return None
    existing = set(data[word].get("tags", []))
    data[word]["tags"] = sorted(existing - set(tags))
    _save(data, path)
    return data[word]


def list_favorites(tags=None, path=_DEFAULT_PATH):
    data = _load(path)
    entries = list(data.values())
    if tags:
        tag_set = set(tags)
        entries = [e for e in entries if tag_set.issubset(set(e.get("tags", [])))]
    return sorted(entries, key=lambda e: e["word"])


def search_favorites(query, path=_DEFAULT_PATH):
    data = _load(path)
    query_lower = query.lower()
    results = []
    for word, entry in data.items():
        score = 0
        if word == query:
            score += 100
        elif query_lower in word.lower():
            score += 50
        for tag in entry.get("tags", []):
            if query_lower == tag.lower():
                score += 40
            elif query_lower in tag.lower():
                score += 20
        if query_lower in entry.get("holonic_definition", "").lower():
            score += 10
        if query_lower in entry.get("transliteration", "").lower():
            score += 15
        if score > 0:
            results.append((score, entry))
    results.sort(key=lambda x: -x[0])
    return [e for _, e in results]


def get_all_tags(path=_DEFAULT_PATH):
    data = _load(path)
    all_tags = set()
    for entry in data.values():
        all_tags.update(entry.get("tags", []))
    return sorted(all_tags)


def get_word(word, path=_DEFAULT_PATH):
    return _load(path).get(word)


def favorites_count(path=_DEFAULT_PATH):
    return len(_load(path))
