"""
logeionicon.py — Logeionicon MCP Server
Ancient Greek lexical intelligence for AI assistants.

Three tools:
  1. lookup   — Greek → definitions, or English → Greek
  2. analyze  — Morphological breakdown + definition per word
  3. favorites — Personal Greek dictionary with tagging

Author: Cory C. Childs (Corykidios)
"""

from mcp.server.fastmcp import FastMCP
from api import fetch_headword, NON_ENGLISH
from morphology import lemmatize, full_parse
from favorites import (add_word, remove_word, tag_word, untag_word,
                       list_favorites, search_favorites, get_all_tags,
                       get_word, favorites_count)
from format import render_holonic, transliterate

mcp = FastMCP("Logeionicon")


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 1: lookup
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def lookup(
    word: str,
    direction: str = "greek",
    sources: list = None,
    format: str = "holonic",
) -> str:
    """
    Look up an Ancient Greek word (Greek → definitions) or search for Greek
    words matching an English concept (English → Greek).

    Args:
        word: A Unicode Greek word (e.g. λόγος, ἀρετή) for direction='greek',
              or an English word/phrase (e.g. 'love', 'virtue') for direction='english'.
              Inflected Greek forms are automatically lemmatized.

        direction: 'greek' (default) — look up a Greek word and get its definitions.
                   'english' — find Greek words matching an English concept.

        sources: Which lexica to use. Default: ['LSJ'].
                 Options: 'LSJ', 'DGE', 'Bailly', 'Pape', 'Cunliffe',
                          'Abbott-Smith', 'Autenrieth', 'Slater', 'all'.
                 Non-English sources (DGE, Bailly, Pape) are translated to English.

        format: 'holonic' (default) — Cory's compressed syllabified definition format.
                'full' — complete raw dictionary text.

    Returns:
        Formatted definition(s) as a string.
    """
    if sources is None:
        sources = ["LSJ"]

    if direction == "english":
        return await _lookup_english(word)

    # Lemmatize if inflected
    lemma_result = await lemmatize(word)
    lookup_word = lemma_result["lemma"]
    was_inflected = lemma_result["is_inflected"]

    try:
        headword_data = await fetch_headword(lookup_word)
    except Exception as e:
        return f"Error fetching from Logeion: {e}\nWord attempted: {lookup_word}"

    entries = headword_data.get("entries", {})

    if not entries and was_inflected and lookup_word != word:
        try:
            headword_data = await fetch_headword(word)
            entries = headword_data.get("entries", {})
            lookup_word = word
        except Exception:
            pass

    if not entries:
        return (f"No entries found for '{word}' in Logeion. "
                f"The word may not be in the database, or may require different diacritics.")

    requested = _normalize_sources(sources)
    filtered = {k: v for k, v in entries.items() if k in requested or "all" in requested}
    if not filtered:
        filtered = entries
        note = f"\n(Note: requested sources {sources} not found; showing: {list(entries.keys())})"
    else:
        note = ""

    parts = []
    if was_inflected:
        parts.append(f"[Inflected form '{word}' → lemma '{lookup_word}']\n")

    for source_name, content in filtered.items():
        if _is_non_english(source_name):
            lang = _get_language(source_name)
            content = f"[Originally {lang} — auto-translated]\n{content}"

        if format == "holonic":
            holonic = render_holonic(lookup_word, content, source=source_name)
            parts.append(f"[{source_name}]\n{holonic}" if len(filtered) > 1 else holonic)
        else:
            parts.append(f"[{source_name}]\n{content}")

    return "\n\n".join(parts) + note


async def _lookup_english(english_term: str) -> str:
    from api import search_english, extract_plain_text
    try:
        result = await search_english(english_term)
    except Exception as e:
        return f"Error searching for '{english_term}': {e}"

    woodhouse_html = result.get("woodhouse_html", "")
    greek_words = result.get("greek_words", [])
    candidates = result.get("candidates", [])

    if not woodhouse_html:
        hint = f"\nSimilar entries: {', '.join(candidates[:6])}" if candidates else ""
        return f"No Greek words found matching '{english_term}'.{hint}"

    # Show the Woodhouse entry (plain text) as the primary result
    woodhouse_text = extract_plain_text(woodhouse_html)
    output_lines = [f"Woodhouse English-Greek: '{result.get('matched_entry', english_term)}'\n",
                    woodhouse_text]

    # Then offer LSJ holonic definitions for each found Greek word
    if greek_words:
        output_lines.append(f"\n─── LSJ entries for found Greek words ───")
        for greek_word in greek_words[:6]:
            try:
                headword_data = await fetch_headword(greek_word)
                entries = headword_data.get("entries", {})
                content = entries.get("LSJ") or next(iter(entries.values()), "")
                if content:
                    output_lines.append(render_holonic(greek_word, content))
            except Exception:
                output_lines.append(f". {greek_word} [{transliterate(greek_word)}]: (definition unavailable)")

    return "\n".join(output_lines)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 2: analyze
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def analyze(text: str) -> str:
    """
    Analyze a Greek word or passage: morphological parse + holonic definition per word.

    Args:
        text: One or more Unicode Greek words (space-separated).
              Inflected forms are automatically analyzed.

    Returns:
        Per-word: lemma, part of speech, morphological parse, holonic definition.
    """
    words = [w.strip(",.;·") for w in text.strip().split()]
    words = [w for w in words if w]
    if not words:
        return "No words provided."

    results = []
    for word in words:
        if not any(ord(c) > 0x0370 for c in word):
            results.append(f"'{word}' — no Greek characters found.")
            continue
        results.append(await _analyze_word(word))

    return "\n\n" + ("─" * 40 + "\n\n").join([""] + results)


async def _analyze_word(word: str) -> str:
    lines = [f"  {word}  [{transliterate(word)}]"]

    parses = await full_parse(word)
    lemma_result = await lemmatize(word)
    lemma = lemma_result["lemma"]

    if lemma != word:
        lines.append(f"  Lemma: {lemma} [{transliterate(lemma)}]")

    unique_parses = list({p["short_label"] for p in parses if p.get("short_label")})
    if unique_parses:
        lines.append(f"  Parse: {' | '.join(unique_parses[:3])}")

    try:
        headword_data = await fetch_headword(lemma)
        entries = headword_data.get("entries", {})
        content = entries.get("LSJ") or next(iter(entries.values()), "")
        lines.append(f"  {render_holonic(lemma, content)}")
    except Exception as e:
        lines.append(f"  (Definition unavailable: {e})")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 3: favorites
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def favorites(
    action: str,
    word: str = None,
    tags: list = None,
    query: str = None,
) -> str:
    """
    Manage your personal Ancient Greek dictionary.

    Args:
        action: 'add', 'remove', 'tag', 'untag', 'list', 'search', 'tags', 'info'
        word:   Unicode Greek word (required for add/remove/tag/untag/info)
        tags:   List of tag strings (e.g. ['sound', 'homer', 'philosophy'])
        query:  Search string for action='search'

    Examples:
        favorites(action='add', word='λόγος', tags=['philosophy'])
        favorites(action='list', tags=['homer'])
        favorites(action='search', query='sound')
        favorites(action='tags')
    """
    action = action.lower().strip()

    if action == "add":
        if not word:
            return "Error: 'word' is required for action='add'."
        existing = get_word(word)
        if existing:
            return (f"'{word}' is already in your favorites.\n"
                    f"Tags: {existing.get('tags', [])}\n"
                    f"Use action='tag' to add more tags.")
        try:
            lemma_result = await lemmatize(word)
            lookup_word = lemma_result["lemma"]
            headword_data = await fetch_headword(lookup_word)
            entries = headword_data.get("entries", {})
            content = entries.get("LSJ") or next(iter(entries.values()), "")
            holonic = render_holonic(lookup_word, content)
            source = "LSJ" if "LSJ" in entries else next(iter(entries.keys()), "unknown")
        except Exception as e:
            holonic = f". {word} [{transliterate(word)}]: (definition fetch failed: {e})"
            source = "unknown"
        entry = add_word(word, holonic, tags=tags or [], source=source)
        count = favorites_count()
        tag_str = f" Tags: {entry['tags']}." if entry['tags'] else ""
        return (f"Added '{word}' to your favorites.{tag_str}\n"
                f"You now have {count} word{'s' if count != 1 else ''} saved.\n\n{holonic}")

    elif action == "remove":
        if not word:
            return "Error: 'word' is required for action='remove'."
        if remove_word(word):
            count = favorites_count()
            return f"Removed '{word}'. {count} word{'s' if count != 1 else ''} remaining."
        return f"'{word}' was not found in your favorites."

    elif action == "tag":
        if not word: return "Error: 'word' is required for action='tag'."
        if not tags: return "Error: 'tags' is required for action='tag'."
        result = tag_word(word, tags)
        if result:
            return f"Tagged '{word}' with {tags}.\nAll tags: {result['tags']}"
        return f"'{word}' is not in favorites. Use action='add' first."

    elif action == "untag":
        if not word: return "Error: 'word' is required for action='untag'."
        if not tags: return "Error: 'tags' is required for action='untag'."
        result = untag_word(word, tags)
        if result:
            return f"Removed tags {tags} from '{word}'.\nRemaining tags: {result['tags']}"
        return f"'{word}' is not in your favorites."

    elif action == "list":
        entries = list_favorites(tags=tags)
        if not entries:
            count = favorites_count()
            if count == 0:
                return "Your favorites list is empty. Use action='add' to start saving words."
            return f"No favorites match tags: {tags}." if tags else "No favorites found."
        tag_filter = f" (tags: {tags})" if tags else ""
        lines = [f"Your favorites{tag_filter} — {len(entries)} word{'s' if len(entries)!=1 else ''}:\n"]
        for entry in entries:
            tag_str = f"  [{', '.join(entry.get('tags', []))}]" if entry.get('tags') else ""
            lines.append(f"{entry.get('holonic_definition','')}{tag_str}")
        return "\n".join(lines)

    elif action == "search":
        if not query: return "Error: 'query' is required for action='search'."
        results = search_favorites(query)
        if not results:
            return f"No favorites found matching '{query}'."
        lines = [f"Matches for '{query}' — {len(results)} result{'s' if len(results)!=1 else ''}:\n"]
        for entry in results:
            tag_str = f"  [{', '.join(entry.get('tags',[]))}]" if entry.get('tags') else ""
            lines.append(f"{entry.get('holonic_definition','')}{tag_str}")
        return "\n".join(lines)

    elif action == "tags":
        all_tags = get_all_tags()
        count = favorites_count()
        if not all_tags:
            return f"No tags in use. You have {count} saved word{'s' if count!=1 else ''}."
        return (f"All tags ({count} word{'s' if count!=1 else ''} total):\n"
                + ", ".join(all_tags))

    elif action == "info":
        if not word: return "Error: 'word' is required for action='info'."
        entry = get_word(word)
        if not entry: return f"'{word}' is not in your favorites."
        return "\n".join([
            f"Word: {entry['word']}",
            f"Transliteration: {entry.get('transliteration','')}",
            f"Source: {entry.get('source','unknown')}",
            f"Tags: {entry.get('tags',[])}",
            f"Added: {entry.get('added_at','unknown')}",
            f"\n{entry.get('holonic_definition','')}",
        ])

    return (f"Unknown action: '{action}'.\n"
            f"Valid: add, remove, tag, untag, list, search, tags, info")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_sources(sources: list) -> set:
    mapping = {
        "lsj": "LSJ", "liddell": "LSJ", "scott": "LSJ",
        "middle": "Middle Liddell", "dge": "DGE", "bailly": "Bailly",
        "pape": "Pape", "cunliffe": "Cunliffe", "abbottsmith": "Abbott-Smith",
        "abbott": "Abbott-Smith", "autenrieth": "Autenrieth",
        "slater": "Slater", "all": "all",
    }
    normalized = set()
    for s in sources:
        key = s.lower().replace("-", "").replace(" ", "")
        if key == "all": return {"all"}
        normalized.add(mapping.get(key, s))
    return normalized


def _is_non_english(source_name: str) -> bool:
    key = source_name.lower().replace("-","").replace(" ","")
    return any(k in key for k in ["dge","bailly","pape"])


def _get_language(source_name: str) -> str:
    key = source_name.lower()
    if "dge" in key: return "Spanish"
    if "bailly" in key: return "French"
    if "pape" in key: return "German"
    return "non-English"


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
