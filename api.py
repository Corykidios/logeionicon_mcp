"""
api.py — Logeion HTTP client for Logeionicon
Communicates with https://anastrophe.uchicago.edu/logeion-api
"""

import httpx
from bs4 import BeautifulSoup
from typing import Optional

BASE_URL = "https://anastrophe.uchicago.edu/logeion-api"

DICT_NAMES = {
    "LSJ": "LSJ",
    "MiddleLiddell": "Middle Liddell",
    "Autenrieth": "Autenrieth",
    "Cunliffe": "Cunliffe",
    "Slater": "Slater",
    "AbbottSmith": "Abbott-Smith",
    "DGE": "DGE",
    "Bailly": "Bailly",
    "BetantLexNT": "Betant NT",
    "Woodhouse": "Woodhouse",
}

NON_ENGLISH = {
    "DGE": "Spanish",
    "Bailly": "French",
}

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
    Fetch wordwheel suggestions for a word — used for lemma candidates.
    """
    url = f"{BASE_URL}/wheel"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"w": word, "type": "greek"})
        response.raise_for_status()
        data = response.json()
    return [r for r in data.get("results", []) if r]


async def fetch_find(word: str, timeout: float = 10.0) -> dict:
    """
    Use /find endpoint — returns lemma, parses, and confirms the word exists.
    This is the primary lemmatization source.
    """
    url = f"{BASE_URL}/find"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"w": word})
        response.raise_for_status()
        data = response.json()
    return data  # {"word": ..., "parses": [...], "description": ...}


async def fetch_morpho(word: str, timeout: float = 10.0) -> dict:
    """
    Use Logeion's morpho-api for full morphological parsing.
    """
    url = "https://anastrophe.uchicago.edu/morpho-api/"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"word": word, "lang": "greek"})
        response.raise_for_status()
        return response.json()


async def search_english(english_term: str, timeout: float = 10.0) -> dict:
    """
    Reverse lookup: English → Greek via /search endpoint.
    """
    url = f"{BASE_URL}/search"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params={"q": english_term})
        response.raise_for_status()
        data = response.json()

    words = data.get("words", [])
    greek_matches = [w for w in words if w and any(ord(c) > 0x0370 for c in w)]
    return {
        "query": english_term,
        "greek_matches": greek_matches,
        "all_matches": words,
    }


def extract_plain_text(html: str) -> str:
    """Strip HTML tags from a Logeion entry, preserving Greek characters."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)
