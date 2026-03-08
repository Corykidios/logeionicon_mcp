# Logeionicon 🏛️

**Ancient Greek lexical tools for Claude and other AI assistants — powered by [Logeion](https://logeion.uchicago.edu)**

Logeionicon is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that gives AI assistants real-time access to the world's finest Ancient Greek dictionaries, including the **Liddell-Scott-Jones (LSJ)**, via the University of Chicago's Logeion database. Look up any Greek word, parse inflected forms, and build a personal vocabulary collection — all without leaving your AI conversation.

---

## Features

- **`lookup`** — Full dictionary entries from LSJ and 8 other lexica, with auto-lemmatization of inflected forms
- **`analyze`** — Morphological parsing of Greek words: lemma, part of speech, case/number/gender or tense/mood/voice
- **`favorites`** — A persistent personal Greek dictionary: save, tag, search, and manage words across sessions

---

## Supported Dictionaries

| Key | Dictionary | Language |
|-----|-----------|----------|
| `LSJ` | Liddell-Scott-Jones *Greek-English Lexicon* | English |
| `MiddleLiddell` | Middle Liddell (abridged) | English |
| `Autenrieth` | Autenrieth *Homeric Dictionary* | English |
| `Cunliffe` | Cunliffe *Lexicon of the Homeric Dialect* | English |
| `Slater` | Slater *Lexicon to Pindar* | English |
| `AbbottSmith` | Abbott-Smith *NT Greek Lexicon* | English |
| `DGE` | *Diccionario Griego-Español* | Spanish → translated |
| `Bailly` | Bailly *Dictionnaire grec-français* | French → translated |
| `BetantLexNT` | Betant *Lexicon NT* | English |

---

## Requirements

- Python 3.8+
- [Claude Desktop](https://claude.ai/download) (or any MCP-compatible client)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Corykidios/logeionicon_mcp.git
cd logeionicon_mcp
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Claude Desktop

Open your Claude Desktop config file:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

Add Logeionicon to the `mcpServers` block:

```json
{
  "mcpServers": {
    "logeionicon": {
      "command": "python",
      "args": ["/absolute/path/to/logeionicon_mcp/logeionicon.py"]
    }
  }
}
```

Replace `/absolute/path/to/logeionicon_mcp/` with the actual path where you cloned the repo.

### 4. Restart Claude Desktop

Fully quit Claude Desktop (including from the system tray), then reopen it. You should see Logeionicon available in the tools menu.

---

## Usage

Once installed, just talk to Claude naturally. Examples:

> *"Look up ἀρετή in the LSJ"*

> *"What does λύουσι parse as?"*

> *"Add ψυχή to my favorites with the tag 'philosophy'"*

> *"Show me all my favorites tagged 'homer'"*

> *"What are some Greek words for love?"*

---

## Tool Reference

### `lookup(word, direction, sources, format)`

Look up a Greek word (or search for Greek words matching an English concept).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `word` | string | required | Unicode Greek word **or** English search term |
| `direction` | `"greek"` \| `"english"` | `"greek"` | Greek → definitions, or English → Greek |
| `sources` | list | `["LSJ"]` | Which dictionaries to query (see table above, or `"all"`) |
| `format` | `"holonic"` \| `"full"` | `"holonic"` | Compressed summary or full entry |

**Examples:**
```
lookup("ἀρετή")
lookup("virtue", direction="english")
lookup("λόγος", sources=["LSJ", "Bailly"], format="full")
```

---

### `analyze(text)`

Parse one or more Greek words morphologically.

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | string | One or more Unicode Greek words (space-separated) |

Returns per word: lemma, part of speech, morphological features (case, number, gender, tense, mood, voice), and a holonic definition of the lemma.

**Examples:**
```
analyze("λύουσι")
analyze("τὴν ψυχὴν τοῦ ἀνθρώπου")
```

---

### `favorites(action, word, tags, query)`

Manage your personal Greek dictionary. Data persists locally in `favorites.json`.

| Action | Description | Required params |
|--------|-------------|-----------------|
| `add` | Save a word | `word` |
| `remove` | Delete a word | `word` |
| `tag` | Add tags to a word | `word`, `tags` |
| `untag` | Remove tags | `word`, `tags` |
| `list` | List saved words (optionally filter by tag) | — |
| `search` | Full-text search across words and definitions | `query` |
| `tags` | Show all tags in use | — |
| `info` | Show full record for a word | `word` |

**Examples:**
```
favorites(action="add", word="ἀρετή", tags=["ethics", "plato"])
favorites(action="list", tags=["homer"])
favorites(action="search", query="courage")
```

---

## How It Works

Logeionicon talks to the [Logeion API](https://anastrophe.uchicago.edu/logeion-api) maintained by the University of Chicago. No local database is required — all dictionary data is fetched live. Morphological parsing uses Logeion's own `/find` endpoint, which draws on the Perseus Morpheus engine under the hood.

---

## Project Structure

```
logeionicon_mcp/
├── logeionicon.py      # MCP server — tool definitions and entry point
├── api.py              # Logeion HTTP client
├── morphology.py       # Lemmatization and morphological parsing
├── favorites.py        # Personal dictionary CRUD + JSON storage
├── format.py           # Holonic definition renderer + Greek syllabifier
├── requirements.txt
├── favorites.json      # Auto-created; gitignored
└── README.md
```

---

## Acknowledgements

- **[Logeion](https://logeion.uchicago.edu)** — University of Chicago's extraordinary Greek and Latin lexical resource
- **[LSJ](http://stephanus.tlg.uci.edu/lsj/)** — Liddell, Scott, Jones *A Greek-English Lexicon*, the gold standard since 1843
- Inspired by [philipaidanbooth/Logeion-mcp-server](https://github.com/philipaidanbooth/Logeion-mcp-server)

---

## License

MIT
