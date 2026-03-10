"""
format.py — Holonic definition format + transliteration for Logeionicon

Holonic format spec (Cory C. Childs):

    . word [syl.la.bles]: <senses>

Punctuation encodes depth of the sense hierarchy:

    FLAT  (no subsenses):
        periods only between senses
        e.g.  . λόγος [lo.gos]: word, speech. reason, account. ratio, proportion.

    TWO-TIER  (senses + subsenses):
        periods between major senses, commas between subsenses
        e.g.  . ψυχή [psu.chē]: life, vital force. ghost, departed spirit. soul, principle of movement.

    THREE-TIER  (senses + subsenses + sub-subsenses):
        periods between major senses, semicolons between subsenses,
        commas between sub-subsenses
        e.g.  . νόμος [no.mos]: usage; custom, established practice; law of a state, decree. melody; musical mode.

Rules:
    - NO citations (no "Il. 5.296", no "Hdt. 2.123", no author abbreviations)
    - NO parenthetical source notes like "(Homer)" or "(Plato)"
    - NO grammatical labels
    - Compress ruthlessly — capture the semantic core only
"""

import re
import unicodedata
from bs4 import BeautifulSoup

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

# ─── Pure-Python holonic extraction ──────────────────────────────────────────

# Greek Unicode ranges
_GREEK_RE     = re.compile(r'[\u0370-\u03ff\u1f00-\u1fff\u0300-\u036f]+')

# Citations: "Il. 5.296", "Hdt. 2.123", "A. Pr. 123", bare "5.296" etc.
_CITATION_RE  = re.compile(
    r'\b[A-Z][a-z]{0,5}\.\s*(?:\d[\w.]*)?'   # Hdt., Il., Od., A., S., E.
    r'|\b[A-Z]{2,6}\.\s*(?:\d[\w.]*)?'        # NT., LXX., LSJ.
    r'|\b\d+\.\d+\b'                           # bare 5.296
)

# Parentheticals: (lyr.), (of persons), (v.l.), (q.v.) etc.
_PAREN_RE     = re.compile(r'\([^)]{1,80}\)')

# Noise words / grammatical labels
_NOISE_RE     = re.compile(
    r'\b(trans\.|intrans\.|absol\.|abs\.|metaph\.|poet\.|prop\.|orig\.'
    r'|freq\.|perh\.|esp\.|usu\.|mostly|chiefly|always|never|only|once'
    r'|twice|rarely|rare\.|dub\.|later|hence|also|v\.l\.|cf\.|q\.v\.'
    r'|ib\.|ibid\.|ap\.|l\.c\.|sub\s+fin\.|fin\.|init\.)\s*',
    re.IGNORECASE
)

# Roman numeral / letter sense dividers used in LSJ: "I.", "II.", "A.", "B."
_SENSE_SPLIT_RE = re.compile(r'(?:^|(?<=[\s.;,]))\s*(?:[IVX]{1,5}|[A-D])\.\s+')

# Dashes used as sense separators in LSJ
_DASH_RE      = re.compile(r'\s*[—–]\s*')

# English word check (at least 3 letters)
_ENGLISH_WORD_RE = re.compile(r'[a-zA-Z]{3,}')


def _clean_segment(text: str) -> str:
    """Clean a single sense segment: strip Greek, citations, noise."""
    text = _GREEK_RE.sub(' ', text)
    text = _CITATION_RE.sub(' ', text)
    text = _PAREN_RE.sub(' ', text)
    text = _NOISE_RE.sub(' ', text)
    text = _DASH_RE.sub(', ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.strip(',.;:— ')
    return text


def _best_phrase(segment: str, max_chars: int = 60) -> str:
    """Extract the most meaningful short phrase from a cleaned segment."""
    part = segment.split(';')[0].strip()
    if len(part) > max_chars:
        part = part[:max_chars].rsplit(' ', 1)[0]
    return part.strip(',.;:— ')


def _has_english(text: str) -> bool:
    return bool(_ENGLISH_WORD_RE.search(text))


def _extract_holonic(word: str, raw_entry: str) -> str:
    """
    Pure-Python holonic rendering — fast, no LLM needed.
    Splits on LSJ sense markers first, then cleans each segment.
    Falls back to semicolon-splitting if no sense markers found.
    """
    translit = transliterate(word)
    plain = strip_html(raw_entry)

    # Strategy 1: split on Roman numeral / letter sense markers
    # Do this BEFORE citation stripping so "I." isn't eaten by citation regex
    parts = _SENSE_SPLIT_RE.split(plain)
    if len(parts) >= 3:
        senses = []
        for part in parts[1:]:   # skip preamble before first marker
            seg = _clean_segment(part)
            phrase = _best_phrase(seg)
            if phrase and _has_english(phrase):
                senses.append(phrase)
        if len(senses) >= 2:
            formatted = ". ".join(senses[:4])
            return f". {word} [{translit}]: {formatted}."

    # Strategy 2: clean whole entry, split on semicolons
    clean = _clean_segment(plain)
    clean = re.sub(r'^[^a-z]{0,20}', '', clean).strip()

    parts = re.split(r';', clean)
    senses = []
    for part in parts:
        phrase = _best_phrase(part.strip())
        if phrase and _has_english(phrase) and len(phrase) > 3:
            senses.append(phrase)
    if senses:
        formatted = ". ".join(senses[:4])
        return f". {word} [{translit}]: {formatted}."

    # Strategy 3: last resort
    snippet = clean[:80].rsplit(' ', 1)[0].strip(',.;:— ')
    return f". {word} [{translit}]: {snippet}."


# ─── Public async interface (kept async for compatibility with logeionicon.py) ─

async def render_holonic(word: str, raw_entry: str, source: str = "LSJ") -> str:
    """
    Render a dictionary entry in holonic format.
    Pure-Python extraction — instant, no external dependencies.
    """
    return _extract_holonic(word, raw_entry)


def format_holonic_from_parts(word: str, definitions: list) -> str:
    """Build a holonic entry from pre-extracted definition strings (sync)."""
    translit = transliterate(word)
    defs_joined = ". ".join(d.strip().rstrip(".") for d in definitions if d.strip())
    if defs_joined and not defs_joined.endswith("."):
        defs_joined += "."
    return f". {word} [{translit}]: {defs_joined}"
