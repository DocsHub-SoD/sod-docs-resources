# sod-docs-resources

Standalone scripts used to scrape, parse, and compile the Shape of Dreams modding documentation.

These tools were used to build the data in [docs-data](https://github.com/DocsHub-SoD/docs-data) and generate the site in [docs-site](https://github.com/DocsHub-SoD/docs-site). They are kept here so anyone can re-run the pipeline or adapt it if the game updates.

---

## Scripts

1. **`scraper.py`**:
   - Downloads `manifest.json`, `xrefmap.yml`, and the 898 HTML API pages from the official DocFX docs into `cache/raw_html/`.
   - Uses standard library `urllib` and `ThreadPoolExecutor`.
   - Checks if files already exist locally before downloading to prevent unnecessary requests.

2. **`parser.py`**:
   - Parses the cached HTML pages using `BeautifulSoup4`.
   - Extracts types, signatures, parameters, inheritance, and available comments into JSON files (`data/api/`).

3. **`compile_db.py`**:
   - Reads the parsed JSON files and generates:
     - `api.db`: SQLite database with indexes on types, members, and parameters.
     - `api-graph.json`: Dependency graph mapping inheritance and interfaces.

4. **`generator.py`**:
   - Converts the JSON models into VitePress-compatible Markdown pages with automatic cross-linking between known game types.

---

## Requirements & Usage

```bash
# Requires Python 3.10+ and BeautifulSoup4
pip install beautifulsoup4

# 1. Download official docs into local cache
python scraper.py

# 2. Parse HTML into JSON models
python parser.py

# 3. Build SQLite DB and graph
python compile_db.py

# 4. Generate Markdown for VitePress
python generator.py
```

## License

MIT
