"""
format.py — Holonic definition format renderer for Logeionicon
"""

import re
import unicodedata
from typing import Optional
from bs4 import BeautifulSoup

_GREEK_TO_LATIN = {
    'α': 'a',  'β': 'b',  'γ': 'g',  'δ': 'd',  'ε': 'e',
    'ζ': 'z',  'η': 'ē',  'θ': 'th', 'ι': 'i',  'κ': 'k',
    'λ': 'l',  'μ': 'm',  'ν': 'n',  'ξ': 'x',  'ο': 'o',
    'π': 'p',  'ρ': 'r',  'σ': 's',  'ς': 's',  'τ': 't',
    'υ': 'u',  'φ': 'ph', 'χ': 'ch', 'ψ': 'ps', 'ω': 'ō',
    'Α': 'A',  'Β': 'B',  'Γ': 'G',  'Δ': 'D',  'Ε': 'E',
    'Ζ': 'Z',  'Η': 'Ē',  'Θ': 'Th', 'Ι': 'I',  'Κ': 'K',
    'Λ': 'L',  'Μ': 'M',  'Ν': 'N',  'Ξ': 'X',  'Ο': 'O',
    'Π': 'P',  'Ρ': 'R',  'Σ': 'S',  'Τ': 'T',  'Υ': 'U',
    'Φ': 'Ph', 'Χ': 'Ch', 'Ψ': 'Ps', 'Ω': 'Ō',
}

_ROUGH_BREATHING = '\u0314'

_GK_VOWELS = set('αεηιοωυ')
_GK_DIPHTHONGS = {'αι', 'ει', 'οι', 'αυ', 'ευ', 'ου', 'υι', 'ηι', 'ωι'}

_VALID_ONSET = {
    'βλ','βρ','γλ','γν','γρ','δρ','θλ','θν','θρ','κλ','κν','κρ','κτ',
    'μν','πλ','πν','πρ','πτ','σβ','σθ','σκ','σμ','σν','σπ','στ','σφ',
    'σχ','τρ','φθ','φλ','φρ','χθ','χλ','χρ',
    'στρ','σπλ','σκλ','σκρ','σφρ',
}


def transliterate(greek_word: str) -> str:
    """
    Convert a Greek word to syllabic transliteration with macrons.
    Syllables separated by periods. η→ē, ω→ō.
    """
    nfd = unicodedata.normalize("NFD", greek_word)
    has_rough_breathing = _ROUGH_BREATHING in nfd[:5]
    base = "".join(c for c in nfd if not unicodedata.combining(c))
    if not base:
        return greek_word

    greek_syllables = _syllabify_greek(base)

    latin_syllables = []
    for i, syl in enumerate(greek_syllables):
        trans = _transliterate_syllable(syl)
        if i == 0 and has_rough_breathing:
            trans = 'h' + trans
        latin_syllables.append(trans)

    # Fix cross-syllable γ+γ/κ/ξ/χ → trailing γ becomes 'n' (e.g. ζιγ|γος → zin|gos)
    for i in range(len(greek_syllables) - 1):
        if greek_syllables[i] and greek_syllables[i+1]:
            last_gk = greek_syllables[i][-1]
            first_next = greek_syllables[i+1][0]
            if last_gk == 'γ' and first_next in ('γ', 'κ', 'ξ', 'χ'):
                if latin_syllables[i].endswith('g'):
                    latin_syllables[i] = latin_syllables[i][:-1] + 'n'

    return ".".join(latin_syllables)


def _syllabify_greek(base: str) -> list:
    """Syllabify a bare Greek string (no diacritics)."""
    tokens = []
    i = 0
    while i < len(base):
        c = base[i]
        if c in _GK_VOWELS:
            if i + 1 < len(base) and base[i:i+2] in _GK_DIPHTHONGS:
                tokens.append(('V', base[i:i+2]))
                i += 2
            else:
                tokens.append(('V', c))
                i += 1
        else:
            tokens.append(('C', c))
            i += 1

    syllables = []
    current = ""
    j = 0

    while j < len(tokens):
        kind, val = tokens[j]
        if kind == 'V':
            current += val
            j += 1
            cons = []
            while j < len(tokens) and tokens[j][0] == 'C':
                cons.append(tokens[j][1])
                j += 1

            if not cons or j >= len(tokens):
                current += "".join(cons)
                syllables.append(current)
                current = ""
            else:
                keep, move = _split_onset(cons)
                current += "".join(keep)
                syllables.append(current)
                current = "".join(move)
        else:
            current += val
            j += 1

    if current:
        syllables.append(current)

    return syllables if syllables else [base]


def _split_onset(cons: list) -> tuple:
    """Split consonant sequence: (keep_with_left, move_to_right)."""
    if not cons:
        return [], []
    for start in range(len(cons)):
        candidate = "".join(cons[start:])
        if candidate in _VALID_ONSET or start == len(cons) - 1:
            return cons[:start], cons[start:]
    return cons[:-1], cons[-1:]


def _transliterate_syllable(syl: str) -> str:
    """Transliterate a single Greek syllable (base letters only)."""
    result = []
    i = 0
    while i < len(syl):
        c = syl[i]
        if c == 'γ' and i + 1 < len(syl) and syl[i+1] in ('γ', 'κ', 'ξ', 'χ'):
            result.append('n')
            i += 1
            continue
        result.append(_GREEK_TO_LATIN.get(c, c))
        i += 1
    return "".join(result)


def render_holonic(word: str, raw_entry: str, source: str = "LSJ") -> str:
    """Render a Logeion dictionary entry in holonic format."""
    clean_text = _clean_entry_text(raw_entry)
    translit = transliterate(word)
    if clean_text:
        return f". {word} [{translit}]: {clean_text}"
    else:
        return f". {word} [{translit}]: (no entry found in {source})"


def format_holonic_from_parts(word: str, definitions: list) -> str:
    """Build a holonic entry from pre-extracted definition strings."""
    translit = transliterate(word)
    defs_joined = ". ".join(d.strip().rstrip(".") for d in definitions if d.strip())
    if defs_joined and not defs_joined.endswith("."):
        defs_joined += "."
    return f". {word} [{translit}]: {defs_joined}"


def _clean_entry_text(text: str) -> str:
    """Clean and compress a dictionary entry text."""
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator=" ")
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\b[A-Z][a-z]*\.\d+(\.\d+)*\b', '', text)
    text = re.sub(r'\(v\.l\.[^)]*\)', '', text)
    text = re.sub(r'\bcf\.\s+\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s+([,;.])', r'\1', text)
    if text and not text.endswith('.'):
        text += '.'
    return text
