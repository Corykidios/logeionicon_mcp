"""
api.py — Logeion HTTP client for Logeionicon
Communicates with https://anastrophe.uchicago.edu/logeion-api
and https://anastrophe.uchicago.edu/retro-api (English→Greek via Woodhouse)
"""

import httpx
from bs4 import BeautifulSoup
from typing import Optional

BASE_URL = "https://anastrophe.uchicago.edu/logeion-api"
RETRO_URL = "https://anastrophe.uchicago.edu/retro-api"

GREEK_DICTS = {"LSJ", "MiddleLiddell", "Autenrieth", "Cunliffe",
               "Slater", "AbbottSmith", "DGE", "Bailly", "BetantLexNT"}


async def fetch_headword(word: str, timeout: float = 10.0) -> dict:
    """
    Fetch all dictionary entries for a Greek word.
    Returns: { "word": str, "entries": {"LSJ": html_str, ...}, "info": {...} }
    """
    url = f"{BASE_URL}/detail"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"w": word, "type": "greek"})
        response.raise_for_status()
        data = response.json()

    entries = {}
    detail = data.get("detail", {})
    dicos = detail.get("dicos", [])

    for dico in dicos:
        dname = dico.get("dname", "")
        es = dico.get("es", [])
        if dname in GREEK_DICTS and es:
            content = " ".join(es)
            entries[dname] = content

    return {
        "word": word,
        "entries": entries,
        "info": data.get("info", {}),
        "raw": data,
    }


async def fetch_wordwheel(word: str, timeout: float = 10.0) -> list:
    """
    Fetch wordwheel suggestions — used for lemma candidates.
    """
    url = f"{BASE_URL}/wheel"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"w": word, "type": "greek"})
        response.raise_for_status()
        data = response.json()
    return [r for r in data.get("results", []) if r]


async def fetch_find(word: str, timeout: float = 10.0) -> dict:
    """
    Use /find endpoint — returns lemma, parses, confirms word exists.
    Primary lemmatization source.
    """
    url = f"{BASE_URL}/find"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"w": word})
        response.raise_for_status()
        data = response.json()
    return data  # {"word": ..., "parses": [...], "description": ...}


async def search_english(english_term: str, timeout: float = 10.0) -> dict:
    """
    Reverse lookup: English → Greek via Retro API (Woodhouse dictionary).
    Returns: { "query", "woodhouse_html", "greek_words", "candidates" }
    """
    # Step 1: search for matching English entry
    search_url = f"{RETRO_URL}/search"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(search_url, params={"q": english_term})
        resp.raise_for_status()
        search_data = resp.json()

    candidates = search_data.get("words", [])
    if not candidates:
        return {
            "query": english_term,
            "woodhouse_html": "",
            "greek_words": [],
            "candidates": [],
        }

    # Step 2: get detail for the best match (prefer exact match)
    best = next((w for w in candidates if w.lower() == english_term.lower()), candidates[0])
    detail_url = f"{RETRO_URL}/detail"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(detail_url, params={"w": best})
        resp.raise_for_status()
        detail_data = resp.json()

    detail = detail_data.get("detail", {})
    woodhouse_entries = detail.get("woodhouse", [])
    woodhouse_html = " ".join(woodhouse_entries) if woodhouse_entries else ""

    # Extract Greek words (Unicode range 0x0370–0x03FF and 0x1F00–0x1FFF)
    greek_words = []
    if woodhouse_html:
        soup = BeautifulSoup(woodhouse_html, "html.parser")
        text = soup.get_text()
        import re
        # Find sequences of Greek characters
        greek_tokens = re.findall(r'[\u0370-\u03ff\u1f00-\u1fff][\u0370-\u03ff\u1f00-\u1fff\u0300-\u036f]*(?:[\u0370-\u03ff\u1f00-\u1fff][\u0300-\u036f]*)+', text)
        seen = set()
        for tok in greek_tokens:
            if tok not in seen and len(tok) > 1:
                seen.add(tok)
                greek_words.append(tok)

    return {
        "query": english_term,
        "matched_entry": best,
        "woodhouse_html": woodhouse_html,
        "greek_words": greek_words,
        "candidates": candidates[:10],
    }


async def fetch_morpho(word: str, timeout: float = 10.0) -> dict:
    """Use Logeion's morpho-api for morphological parsing."""
    url = "https://anastrophe.uchicago.edu/morpho-api/"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"word": word, "lang": "greek"})
        response.raise_for_status()
        return response.json()


def extract_plain_text(html: str) -> str:
    """Strip HTML tags from a Logeion entry, preserving Greek characters."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)
