"""
Smart Offline-First Scraper for Shape of Dreams DocFX API.
Uses urllib and ThreadPoolExecutor (pure standard library, 0 external dependencies).
- Caches raw HTML files locally in cache/raw_html/
- If file exists locally, never makes a network request
- Respects rate limits: gentle thread pool with randomized jitter
- Downloads manifest.json and xrefmap.yml
"""

import os
import sys
import time
import json
import random
from pathlib import Path
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://lizardsmoothie.com/sod/moddoc/"
MANIFEST_URL = BASE_URL + "manifest.json"
XREFMAP_URL = BASE_URL + "xrefmap.yml"

PROJECT_ROOT = Path(__file__).resolve().parent
CACHE_DIR = PROJECT_ROOT / "cache"
RAW_HTML_DIR = CACHE_DIR / "raw_html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

MAX_WORKERS = 4
REQUEST_DELAY_RANGE = (0.05, 0.15)  # seconds


def init_dirs():
    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def download_single_file(url: str, dest_path: Path) -> bytes:
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return dest_path.read_bytes()
    
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read()
        dest_path.write_bytes(content)
        return content


def worker_download_page(rel_path: str, idx: int, total: int):
    filename = Path(rel_path).name
    dest_path = RAW_HTML_DIR / filename
    
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return filename, "CACHED"

    url = BASE_URL + rel_path
    for attempt in range(4):
        try:
            time.sleep(random.uniform(*REQUEST_DELAY_RANGE))
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
                dest_path.write_bytes(content)
                return filename, "OK"
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = (attempt + 1) * 3
                print(f"[{idx}/{total}] Rate limit 429 for {filename}, sleeping {wait_time}s...")
                time.sleep(wait_time)
                continue
            elif attempt == 3:
                return filename, f"HTTP_{e.code}"
        except Exception as e:
            if attempt == 3:
                return filename, f"ERR_{e}"
            time.sleep((attempt + 1) * 1.5)
    return filename, "FAILED"


def main():
    init_dirs()
    print("=== Shape of Dreams Doc Scraper (Offline-First) ===")
    
    # 1. Manifest
    manifest_path = CACHE_DIR / "manifest.json"
    print(f"Checking manifest: {MANIFEST_URL}")
    manifest_bytes = download_single_file(MANIFEST_URL, manifest_path)
    manifest = json.loads(manifest_bytes.decode("utf-8"))

    # 2. XRefMap
    xref_path = CACHE_DIR / "xrefmap.yml"
    print(f"Checking xrefmap: {XREFMAP_URL}")
    download_single_file(XREFMAP_URL, xref_path)
    print(f"Saved xrefmap.yml ({xref_path.stat().st_size / (1024*1024):.2f} MB)")

    # 3. Targets
    files_to_download = []
    for file_info in manifest.get("files", []):
        output_file = file_info.get("output", {}).get(".html", {}).get("relative_path")
        if output_file and output_file.startswith("api/"):
            files_to_download.append(output_file)

    total = len(files_to_download)
    cached_count = sum(1 for p in files_to_download if (RAW_HTML_DIR / Path(p).name).exists() and (RAW_HTML_DIR / Path(p).name).stat().st_size > 0)
    print(f"Total API files: {total} (Already cached: {cached_count})")

    download_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(worker_download_page, rel_path, i + 1, total): rel_path
            for i, rel_path in enumerate(files_to_download)
        }
        for future in as_completed(futures):
            filename, status = future.result()
            if status == "OK":
                download_count += 1
                if download_count % 50 == 0:
                    print(f"Progress: {download_count} new pages downloaded...")

    total_cached = sum(1 for p in files_to_download if (RAW_HTML_DIR / Path(p).name).exists() and (RAW_HTML_DIR / Path(p).name).stat().st_size > 0)
    print(f"\nAll done! Total cached locally: {total_cached}/{total} pages in {RAW_HTML_DIR}")


if __name__ == "__main__":
    main()
