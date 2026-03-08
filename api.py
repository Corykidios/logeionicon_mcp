"""
api.py — Logeion HTTP client for Logeionicon
Hits logeion.uchicago.edu endpoints live.
"""

import httpx
import json
from bs4 import BeautifulSoup, Tag
from typing import Optional

BASE_URL = "https://logeion.uchicago.edu/cgi-bin/logeion"

DICT_NAMES = {
    "lsj": "LSJ", "lsj_s": "LSJ", "middle": "Middle Liddell",
    "dge": "DGE", "bailly": "Bailly", "pape": "Pape",
    "cunliffe": "Cunliffe", "abbott-smith": "Abbott-Smith",
    "autenrieth": "Autenrieth", "slater": "Slater", "woodhouse": "Woodhouse",
}

GREEK_DICTS = {"lsj", "lsj_s", "middle", "dge", "bailly", "pape",
               "cunliffe", "abbott-smith", "autenrieth", "slater"}

NON_ENGLISH = {"dge": "Spanish", "bailly": "French", "pape": "German"}


async def fetch_headword(word: str, timeout: float = 10.0) -> dict:
    """Fetch all dictionary entries for a Greek word from Logeion."""
    url = f"{BASE_URL}/headword.py"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"search_term": word})
        response.raise_for_status()
        html = response.text
    entries = _parse_headword_html(html)
    return {"word": word, "entries": entries, "raw_html": html}


async def fetch_wordwheel(word: str, timeout: float = 10.0) -> list:
    """Fetch wordwheel (lemma suggestions) for a word."""
    url = f"{BASE_URL}/wordwheel.py"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"search_term": word})
        response.raise_for_status()
    return _parse_wordwheel_html(response.text)


async def fetch_collocations(word: str, timeout: float = 10.0) -> str:
    """Fetch collocation data for a word."""
    url = f"{BASE_URL}/collocation.py"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"search_term": word})
        response.raise_for_status()
    return response.text


async def search_english(english_term: str, timeout: float = 10.0) -> dict:
    """Reverse lookup: English → Greek via Logeion autocomplete."""
    url = f"{BASE_URL}/autocomplete.py"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"term": english_term})
        response.raise_for_status()
    try:
        suggestions = json.loads(response.text)
    except json.JSONDecodeError:
        suggestions = []
    greek_results = []
    for s in suggestions:
        if isinstance(s, str) and any(ord(c) > 0x0370 for c in s):
            greek_results.append(s)
        elif isinstance(s, dict):
            val = s.get("value") or s.get("label") or ""
            if any(ord(c) > 0x0370 for c in val):
                greek_results.append(val)
    return {"query": english_term, "greek_matches": greek_results, "raw": suggestions}


def _parse_headword_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    entries = {}

    for elem in soup.find_all(["div", "section", "article"]):
        dico_key = _identify_dict_element(elem)
        if dico_key and dico_key in GREEK_DICTS:
            display_name = DICT_NAMES.get(dico_key, dico_key.upper())
            content = elem.get_text(separator=" ", strip=True)
            if content and len(content) > 5:
                entries[display_name] = content

    if not entries:
        for header in soup.find_all(["h2", "h3", "h4"]):
            header_text = header.get_text(strip=True).lower()
            dico_key = _match_dict_name(header_text)
            if dico_key and dico_key in GREEK_DICTS:
                content_parts = []
                sibling = header.find_next_sibling()
                while sibling and sibling.name not in ["h2", "h3", "h4"]:
                    if hasattr(sibling, "get_text"):
                        content_parts.append(sibling.get_text(separator=" ", strip=True))
                    sibling = sibling.find_next_sibling() if sibling else None
                content = " ".join(content_parts).strip()
                if content:
                    entries[DICT_NAMES.get(dico_key, dico_key.upper())] = content

    if not entries:
        full_text = soup.get_text(separator=" ", strip=True)
        if full_text and not full_text.startswith("0"):
            entries["_raw"] = full_text

    return entries


def _parse_wordwheel_html(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    words = [li.get_text(strip=True) for li in soup.find_all("li") if li.get_text(strip=True)]
    if not words:
        words = [e.get_text(strip=True) for e in soup.find_all(["span", "div", "a"])
                 if e.get_text(strip=True) and any(ord(c) > 0x0370 for c in e.get_text())]
    return words


def _identify_dict_element(elem) -> Optional[str]:
    for cls in elem.get("class", []):
        cls_lower = cls.lower()
        for key in GREEK_DICTS:
            if key in cls_lower or cls_lower in key:
                return key
    elem_id = (elem.get("id") or "").lower()
    for key in GREEK_DICTS:
        if key in elem_id:
            return key
    dico = (elem.get("data-dico") or elem.get("data-dict") or "").lower()
    for key in GREEK_DICTS:
        if key in dico:
            return key
    return None


def _match_dict_name(text: str) -> Optional[str]:
    text = text.lower()
    if "liddell" in text or "lsj" in text or "scott" in text: return "lsj"
    if "dge" in text or "diccionario" in text: return "dge"
    if "bailly" in text: return "bailly"
    if "pape" in text: return "pape"
    if "cunliffe" in text: return "cunliffe"
    if "abbott" in text: return "abbott-smith"
    if "autenrieth" in text: return "autenrieth"
    if "slater" in text or "pindar" in text: return "slater"
    return None
