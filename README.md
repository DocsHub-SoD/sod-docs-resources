# Shape of Dreams ModDocs Toolchain & Pipeline Resources

This repository contains the standalone scraping, parsing, compilation, and code generation toolchain used to extract, normalize, and build the Shape of Dreams Modding Documentation.

If the upstream documentation changes or you need to recreate the entire pipeline from scratch, these scripts allow full reproduction of the dataset and static site.

---

## Toolchain Architecture

1. **`scraper.py`**:
   - Offline-first polite scraper using standard Python libraries.
   - Downloads `manifest.json`, `xrefmap.yml`, and all 898 DocFX API HTML pages into `cache/raw_html/`.
   - Built-in retry mechanism with jitter to prevent rate-limiting (HTTP 429).
   - If files are already cached locally, no network requests are dispatched.

2. **`parser.py`**:
   - Parses raw DocFX HTML files into normalized, strongly-typed JSON models.
   - Extracts member declarations, summaries, inheritance trees, interfaces, parameters, and return types.
   - Outputs individual JSON files to `data/api/` and a summary index to `data/api-catalog.json`.

3. **`generator.py`**:
   - Transforms JSON models into clean, cross-linked VitePress Markdown files for `docs/api/`.
   - Automatically converts type references (e.g. `Entity`, `Actor`) into direct hyperlinks.
   - Handles Vue/VitePress tag escaping (`&lt;`, `&gt;`).

4. **`compile_db.py`**:
   - Ingests the normalized JSON models and compiles:
     - `api.db`: Indexed SQLite database with foreign keys and query indices.
     - `api-graph.json`: Lightweight dependency graph for AI models.

---

## Requirements & Usage

```bash
# Pure standard library (Python 3.10+) with BeautifulSoup4
pip install beautifulsoup4

# 1. Scrape raw HTML to cache
python scraper.py

# 2. Parse HTML to structured JSON
python parser.py

# 3. Build SQLite database and knowledge graph
python compile_db.py

# 4. Generate VitePress Markdown pages
python generator.py
```

## License
MIT License. Free for community modding maintenance and evolution.
