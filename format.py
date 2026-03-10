"""
format.py — Holonic definition format + transliteration for Logeionicon

Holonic format spec (Cory C. Childs):

    . word [syl.la.bles]: <senses>

Punctuation encodes depth of the sense hierarchy:

    FLAT  (no subsenses):
        periods only between senses
        e.g.  . λόγος [lo.gos]: word, speech. reason, account. ratio, proportion.

    TWO-TIER  (senses + subsenses, no sub-subsenses):
        periods between major senses, commas between subsenses
        e.g.  . ψυχή [psu.chē]: life, vital force. ghost, departed spirit. immortal soul, principle of movement.

    THREE-TIER  (senses + subsenses + sub-subsenses):
        periods between major senses, semicolons between subsenses,
        commas between sub-subsenses
        e.g.  . νόμος [no.mos]: usage; custom, established practice; law of a state, decree. melody, musical mode.

Rules:
    - NO citations (no "Il. 5.296", no "Hdt. 2.123", no author abbreviations)
    - NO parenthetical source notes like "(Homer)" or "(Plato)"
    - NO grammatical labels unless essential (e.g. "of persons:" → omit)
    - Compress ruthlessly — capture the semantic core only
    - Choose ONE tier depth for the whole entry (the deepest complexity present)
"""

import re
import unicodedata
import httpx
from bs4 import BeautifulSoup

# ─── LM Studio config ────────────────────────────────────────────────────────
# LM Studio default OpenAI-compatible endpoint
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
# Model name — LM Studio accepts any string when a model is loaded
LM_STUDIO_MODEL = "local-model"
LM_STUDIO_TIMEOUT = 30.0  # seconds — local models can be slow

# ─── Transliteration tables ──────────────────────────────────────────────────
_GREEK_TO_LATIN = {
    'α':'a','β':'b','γ':'g','δ':'d','ε':'e','ζ':'z','η':'ē','θ':'th',
    'ι':'i','κ':'k','λ':'l','μ':'m','ν':'n','ξ':'x','ο':'o','π':'p',
    'ρ':'r','σ':'s','ς':'s','τ':'t','υ':'u','φ':'ph','χ':'ch','ψ':'ps','ω':'ō',
    'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'Ē','Θ':'Th',
    'Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P',
    'Ρ':'R','Σ':'S','Τ':'T','Υ':'U','Φ':'Ph','Χ':'Ch','Ψ':'Ps','Ω':'Ō',
}
_ROUGH_BREATHING = '\u0314'
_GK_VOWELS = set('αεηιοωυ')
_GK_DIPHTHONGS = {'αι','ει','οι','αυ','ευ','ου','υι','ηι','ωι'}
_VALID_ONSET = {
    'βλ','βρ','γλ','γν','γρ','δρ','θλ','θν','θρ','κλ','κν','κρ','κτ',
    'μν','πλ','πν','πρ','πτ','σβ','σθ','σκ','σμ','σν','σπ','στ','σφ',
    'σχ','τρ','φθ','φλ','φρ','χθ','χλ','χρ','στρ','σπλ','σκλ','σκρ','σφρ',
}

# ─── Transliteration ─────────────────────────────────────────────────────────

def transliterate(greek_word: str) -> str:
    """Convert a Greek word to syllabic transliteration. η→ē, ω→ō."""
    nfd = unicodedata.normalize("NFD", greek_word)
    has_rough = _ROUGH_BREATHING in nfd[:6]
    base = "".join(c for c in nfd if not unicodedata.combining(c))
    if not base:
        return greek_word
    syllables = _syllabify_greek(base)
    latin = []
    for i, syl in enumerate(syllables):
        t = _transliterate_syllable(syl)
        if i == 0 and has_rough:
            t = 'h' + t
        latin.append(t)
    # cross-syllable γ+γ/κ/ξ/χ → trailing γ becomes 'n'
    for i in range(len(syllables) - 1):
        if syllables[i] and syllables[i+1]:
            if syllables[i][-1] == 'γ' and syllables[i+1][0] in ('γ','κ','ξ','χ'):
                if latin[i].endswith('g'):
                    latin[i] = latin[i][:-1] + 'n'
    return ".".join(latin)


def _syllabify_greek(base: str) -> list:
    tokens = []
    i = 0
    while i < len(base):
        c = base[i]
        if c in _GK_VOWELS:
            if i + 1 < len(base) and base[i:i+2] in _GK_DIPHTHONGS:
                tokens.append(('V', base[i:i+2])); i += 2
            else:
                tokens.append(('V', c)); i += 1
        else:
            tokens.append(('C', c)); i += 1
    syllables, current, j = [], "", 0
    while j < len(tokens):
        kind, val = tokens[j]
        if kind == 'V':
            current += val; j += 1
            cons = []
            while j < len(tokens) and tokens[j][0] == 'C':
                cons.append(tokens[j][1]); j += 1
            if not cons or j >= len(tokens):
                current += "".join(cons); syllables.append(current); current = ""
            else:
                keep, move = _split_onset(cons)
                current += "".join(keep); syllables.append(current)
                current = "".join(move)
        else:
            current += val; j += 1
    if current:
        syllables.append(current)
    return syllables or [base]


def _split_onset(cons):
    for start in range(len(cons)):
        if "".join(cons[start:]) in _VALID_ONSET or start == len(cons) - 1:
            return cons[:start], cons[start:]
    return cons[:-1], cons[-1:]


def _transliterate_syllable(syl: str) -> str:
    result, i = [], 0
    while i < len(syl):
        c = syl[i]
        if c == 'γ' and i + 1 < len(syl) and syl[i+1] in ('γ','κ','ξ','χ'):
            result.append('n'); i += 1; continue
        result.append(_GREEK_TO_LATIN.get(c, c)); i += 1
    return "".join(result)

# ─── HTML cleaning ────────────────────────────────────────────────────────────

def strip_html(raw: str) -> str:
    """Strip HTML tags, return plain text."""
    if "<" in raw:
        soup = BeautifulSoup(raw, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    return raw


# ─── Holonic rendering via LM Studio ─────────────────────────────────────────

_HOLONIC_SYSTEM = """You are a specialist in Ancient Greek lexicography.
Your task is to compress a full LSJ dictionary entry into a single-line "holonic definition" following an exact format.

FORMAT RULES — read carefully:

The output must be a single line starting with `. WORD [translit]:` followed by the compressed senses.

Choose ONE punctuation tier based on how complex the entry is:

TIER 1 — flat senses (no subsenses needed):
  Periods separate each sense.
  Example: . λόγος [lo.gos]: word, speech. reason, account. ratio, proportion.

TIER 2 — senses with subsenses (no sub-subsenses):
  Periods separate major senses. Commas separate subsenses within a sense.
  Example: . ψυχή [psu.chē]: life, vital force. ghost, departed spirit. immortal soul, principle of movement. butterfly.

TIER 3 — senses with subsenses AND sub-subsenses:
  Periods separate major senses. Semicolons separate subsenses. Commas separate sub-subsenses.
  Example: . νόμος [no.mos]: usage; custom, established practice; law of a state, decree. melody; musical mode, tune.

STRICT PROHIBITIONS — violating these invalidates the output:
  - NO citations: never include "Il. 5.296" or "Hdt. 2.123" or any author+reference
  - NO author names or abbreviations: not "Homer", not "Plato", not "Hdt.", not "A.", not "S."
  - NO parenthetical source notes: not "(Homer)", not "(Plato)", not "(lyr.)"
  - NO grammatical labels: not "trans.", not "intrans.", not "abs.", not "metaph."
  - NO editorial notes: not "v.l.", not "cf.", not "q.v."
  - Output must be ONE LINE only — no newlines, no markdown

GOAL: Capture the semantic range of the word as densely as possible.
Aim for 1–4 major senses. Each sense: 1–5 words. Total output: under 120 words."""


async def render_holonic(word: str, raw_entry: str, source: str = "LSJ") -> str:
    """
    Render a dictionary entry in holonic format using the local LM Studio model.
    Falls back to a basic cleaned version if LM Studio is not reachable.
    """
    translit = transliterate(word)
    plain = strip_html(raw_entry)

    # Trim to ~2000 chars — enough for any entry, not overwhelming for small models
    plain_trimmed = plain[:2000]

    prompt = (
        f"Compress this LSJ entry for '{word}' [{translit}] into holonic format.\n\n"
        f"LSJ ENTRY:\n{plain_trimmed}\n\n"
        f"OUTPUT (one line, starting with `. {word} [{translit}]:`):"
    )

    try:
        async with httpx.AsyncClient(timeout=LM_STUDIO_TIMEOUT) as client:
            resp = await client.post(
                LM_STUDIO_URL,
                json={
                    "model": LM_STUDIO_MODEL,
                    "messages": [
                        {"role": "system", "content": _HOLONIC_SYSTEM},
                        {"role": "user",   "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 200,
                    "stop": ["\n\n", "LSJ", "Entry"],
                }
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()

            # Ensure it starts correctly
            if not text.startswith(". "):
                # Try to find the holonic line if model prefixed something
                for line in text.splitlines():
                    if line.startswith(". "):
                        text = line
                        break
                else:
                    text = f". {word} [{translit}]: {text}"

            return text

    except (httpx.ConnectError, httpx.ConnectTimeout):
        # LM Studio not running — return a basic fallback
        return _fallback_holonic(word, translit, plain)
    except Exception as e:
        return _fallback_holonic(word, translit, plain, error=str(e))


def _fallback_holonic(word: str, translit: str, plain: str, error: str = "") -> str:
    """
    Basic fallback when LM Studio is unavailable.
    Strips citations and returns the first meaningful line of the entry.
    """
    # Strip citation-heavy content — grab text up to first author abbreviation
    text = re.sub(r'\b[A-Z][a-z]{0,5}\.\s*\d[\w.]*', '', plain)
    text = re.sub(r'\s+', ' ', text).strip()
    # Grab first ~120 chars, cut at a word boundary
    snippet = text[:120].rsplit(' ', 1)[0].rstrip(',:;—')
    note = f" [LM Studio offline{': ' + error[:40] if error else ''}]"
    return f". {word} [{translit}]: {snippet}.{note}"


def format_holonic_from_parts(word: str, definitions: list) -> str:
    """Build a holonic entry from pre-extracted definition strings (sync, no LLM)."""
    translit = transliterate(word)
    defs_joined = ". ".join(d.strip().rstrip(".") for d in definitions if d.strip())
    if defs_joined and not defs_joined.endswith("."):
        defs_joined += "."
    return f". {word} [{translit}]: {defs_joined}"
