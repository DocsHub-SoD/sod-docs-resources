"""
Parser for DocFX HTML into structured JSON models and VitePress markdown.
Processes cached HTML files offline, preserving:
- Cross-references to other types/members
- Full member signatures (methods, properties, fields, events)
- XML doc comments (summary, remarks, parameters, returns)
- Inheritance hierarchy and implemented interfaces
- Namespace & Assembly info
"""

import os
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent
CACHE_DIR = PROJECT_ROOT / "cache"
RAW_HTML_DIR = CACHE_DIR / "raw_html"
DATA_DIR = PROJECT_ROOT / "data"
API_JSON_DIR = DATA_DIR / "api"


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def parse_docfx_html(html_text: str, filename: str) -> dict:
    soup = BeautifulSoup(html_text, "html.parser")
    content = soup.find("article", id="_content")
    if not content:
        return None

    # Title & UID
    h1 = content.find("h1")
    title_raw = h1.get_text(strip=True) if h1 else filename
    uid = h1.get("data-uid") if h1 else filename.replace(".html", "")

    # Class, Interface, Enum, Struct, Delegate?
    type_kind = "Class"
    name = title_raw
    for prefix in ["Class ", "Interface ", "Enum ", "Struct ", "Delegate "]:
        if title_raw.startswith(prefix):
            type_kind = prefix.strip()
            name = title_raw[len(prefix):].strip()
            break

    # Top-level summary
    summary_elem = content.find("div", class_="level0 summary")
    summary = summary_elem.get_text(strip=True) if summary_elem else ""

    # Assembly & Namespace
    assembly = ""
    namespace = ""
    for h6 in content.find_all("h6"):
        text = h6.get_text(strip=True)
        if text.startswith("Assembly:"):
            assembly = text.replace("Assembly:", "").strip()
        elif text.startswith("Namespace:"):
            namespace = text.replace("Namespace:", "").strip()

    # Syntax definition
    syntax_code = ""
    syntax_div = content.find("div", class_="codewrapper")
    if syntax_div:
        syntax_code = syntax_div.get_text().strip()

    # Inheritance
    inheritance = []
    inh_div = content.find("div", class_="inheritance")
    if inh_div:
        for a in inh_div.find_all("a"):
            inheritance.append({
                "name": a.get_text(strip=True),
                "href": a.get("href", ""),
                "uid": a.get("href", "").replace(".html", "")
            })

    # Implements
    implements = []
    imp_div = content.find("div", class_="implements")
    if imp_div:
        for a in imp_div.find_all("a"):
            implements.append({
                "name": a.get_text(strip=True),
                "href": a.get("href", ""),
                "uid": a.get("href", "").replace(".html", "")
            })

    # Members parsing
    fields = []
    properties = []
    methods = []
    events = []

    current_section = None
    
    for elem in content.children:
        if not getattr(elem, "name", None):
            continue
        
        # Section headers (h3)
        if elem.name == "h3":
            sec_id = elem.get("id", "").lower()
            sec_text = elem.get_text(strip=True).lower()
            if "field" in sec_id or "field" in sec_text:
                current_section = "fields"
            elif "property" in sec_id or "properties" in sec_text:
                current_section = "properties"
            elif "method" in sec_id or "method" in sec_text:
                current_section = "methods"
            elif "event" in sec_id or "event" in sec_text:
                current_section = "events"
            else:
                current_section = None
            continue

        if current_section and elem.name == "h4":
            member_name = elem.get_text(strip=True)
            member_uid = elem.get("id", "")
            
            # Look ahead for details until next h4 or h3
            member_summary = ""
            member_code = ""
            parameters = []
            returns_info = ""

            curr = elem.find_next_sibling()
            while curr and curr.name not in ["h3", "h4"]:
                if "level1 summary" in " ".join(curr.get("class", [])):
                    member_summary = curr.get_text(strip=True)
                elif "codewrapper" in " ".join(curr.get("class", [])):
                    member_code = curr.get_text().strip()
                elif curr.name == "table" and "table" in curr.get("class", []):
                    # Check if it's parameters or returns
                    prev_h5 = curr.find_previous_sibling("h5")
                    prev_title = prev_h5.get_text(strip=True).lower() if prev_h5 else ""
                    
                    rows = curr.find_all("tr")
                    for tr in rows[1:]:
                        cols = tr.find_all(["td", "th"])
                        if len(cols) >= 2 and "parameter" in prev_title:
                            p_type = cols[0].get_text(strip=True)
                            p_name = cols[1].get_text(strip=True)
                            p_desc = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                            # Check link in p_type
                            p_type_link = cols[0].find("a")
                            p_type_uid = p_type_link.get("href", "").replace(".html", "") if p_type_link else None
                            
                            parameters.append({
                                "name": p_name,
                                "type": p_type,
                                "type_uid": p_type_uid,
                                "description": p_desc
                            })
                        elif len(cols) >= 1 and "return" in prev_title:
                            r_type = cols[0].get_text(strip=True)
                            r_desc = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                            returns_info = f"{r_type}: {r_desc}".strip(": ")

                curr = curr.find_next_sibling()

            item = {
                "name": member_name,
                "id": member_uid,
                "declaration": member_code,
                "summary": member_summary,
                "parameters": parameters,
                "returns": returns_info
            }

            if current_section == "fields":
                fields.append(item)
            elif current_section == "properties":
                properties.append(item)
            elif current_section == "methods":
                methods.append(item)
            elif current_section == "events":
                events.append(item)

    return {
        "uid": uid,
        "name": name,
        "kind": type_kind,
        "namespace": namespace,
        "assembly": assembly,
        "summary": summary,
        "syntax": syntax_code,
        "inheritance": inheritance,
        "implements": implements,
        "fields": fields,
        "properties": properties,
        "methods": methods,
        "events": events
    }


def main():
    API_JSON_DIR.mkdir(parents=True, exist_ok=True)
    
    html_files = list(RAW_HTML_DIR.glob("*.html"))
    print(f"Parsing {len(html_files)} HTML files into structured JSON...")

    all_types = []
    
    for idx, filepath in enumerate(html_files):
        html_text = filepath.read_text(encoding="utf-8", errors="replace")
        data = parse_docfx_html(html_text, filepath.name)
        if not data:
            continue
        
        # Save individual JSON
        json_path = API_JSON_DIR / f"{data['uid']}.json"
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        
        all_types.append({
            "uid": data["uid"],
            "name": data["name"],
            "kind": data["kind"],
            "summary": data["summary"],
            "methods_count": len(data["methods"]),
            "fields_count": len(data["fields"]),
            "properties_count": len(data["properties"])
        })

    # Save summary index
    index_path = DATA_DIR / "api-catalog.json"
    index_path.write_text(json.dumps(all_types, indent=2, ensure_ascii=False), encoding="utf-8")
    
    print(f"Successfully generated {len(all_types)} type records in {API_JSON_DIR}")
    print(f"Saved catalog to {index_path}")


if __name__ == "__main__":
    main()
