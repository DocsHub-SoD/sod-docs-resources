"""
Generator that converts normalized JSON API models into clean, cross-linked VitePress Markdown.
- Automatically escapes Vue-confusing HTML characters (&lt;, &gt;) in headers and tables
- Converts known types into clickable links (e.g., [Entity](/api/Global.Entity))
- Groups members clearly: Fields, Properties, Methods
- Prepares files for VitePress documentation
- Generates a compact LLM Context file (llms-full.txt) perfect for feeding to AI assistants!
"""

import json
from pathlib import Path
import html

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
API_JSON_DIR = DATA_DIR / "api"
DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_API_DIR = DOCS_DIR / "api"


def escape_md_inline(text: str) -> str:
    if not text:
        return ""
    # In VitePress markdown, raw <Tag> outside of code blocks is parsed as Vue components!
    return text.replace("<", "&lt;").replace(">", "&gt;")


def build_markdown_for_class(data: dict, known_uids: set) -> str:
    name = escape_md_inline(data.get("name", "Unknown"))
    kind = data.get("kind", "Class")
    summary = escape_md_inline(data.get("summary", "").strip())
    syntax = data.get("syntax", "").strip()
    namespace = data.get("namespace", "Global")
    assembly = data.get("assembly", "")
    
    lines = []
    lines.append(f"# {kind}: {name}\n")
    
    if summary:
        lines.append(f"> {summary}\n")
    
    lines.append(f"- **Namespace:** `{namespace}`")
    if assembly:
        lines.append(f"- **Assembly:** `{assembly}`")
    
    # Inheritance
    inheritance = data.get("inheritance", [])
    if inheritance:
        chain_links = []
        for item in inheritance:
            u = item.get("uid")
            n = escape_md_inline(item.get("name"))
            if u in known_uids:
                chain_links.append(f"[{n}](/api/{u})")
            else:
                chain_links.append(f"`{n}`")
        lines.append(f"- **Inheritance / Derived:** {' → '.join(chain_links)}")

    lines.append("\n```csharp")
    lines.append(syntax if syntax else f"public {kind.lower()} {data.get('name')}")
    lines.append("```\n")

    # Fields
    fields = data.get("fields", [])
    if fields:
        lines.append("## Fields\n")
        lines.append("| Name | Declaration | Description |")
        lines.append("| :--- | :--- | :--- |")
        for f in fields:
            decl = escape_md_inline(f.get("declaration", "").replace("|", "\\|"))
            desc = escape_md_inline(f.get("summary", "").replace("\n", " ").replace("|", "\\|"))
            lines.append(f"| **`{escape_md_inline(f.get('name'))}`** | `{decl}` | {desc} |")
        lines.append("")

    # Properties
    props = data.get("properties", [])
    if props:
        lines.append("## Properties\n")
        lines.append("| Name | Declaration | Description |")
        lines.append("| :--- | :--- | :--- |")
        for p in props:
            decl = escape_md_inline(p.get("declaration", "").replace("|", "\\|"))
            desc = escape_md_inline(p.get("summary", "").replace("\n", " ").replace("|", "\\|"))
            lines.append(f"| **`{escape_md_inline(p.get('name'))}`** | `{decl}` | {desc} |")
        lines.append("")

    # Methods
    methods = data.get("methods", [])
    if methods:
        lines.append("## Methods\n")
        for m in methods:
            safe_m_name = escape_md_inline(m.get("name", ""))
            lines.append(f"### `{safe_m_name}`\n")
            if m.get("summary"):
                lines.append(f"{escape_md_inline(m.get('summary'))}\n")
            if m.get("declaration"):
                lines.append("```csharp")
                lines.append(m.get("declaration"))
                lines.append("```\n")
            
            params = m.get("parameters", [])
            if params:
                lines.append("**Parameters:**")
                lines.append("| Name | Type | Description |")
                lines.append("| :--- | :--- | :--- |")
                for p in params:
                    p_type = p.get("type", "")
                    p_uid = p.get("type_uid", "")
                    safe_p_type = escape_md_inline(p_type)
                    p_type_display = f"[{safe_p_type}](/api/{p_uid})" if p_uid in known_uids else f"`{safe_p_type}`"
                    p_desc = escape_md_inline(p.get("description", "").replace("|", "\\|"))
                    lines.append(f"| `{escape_md_inline(p.get('name'))}` | {p_type_display} | {p_desc} |")
                lines.append("")

            if m.get("returns"):
                lines.append(f"**Returns:** `{escape_md_inline(m.get('returns'))}`\n")

    return "\n".join(lines)


def main():
    DOCS_API_DIR.mkdir(parents=True, exist_ok=True)
    
    catalog_path = DATA_DIR / "api-catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    known_uids = {item["uid"] for item in catalog}
    
    print(f"Generating VitePress docs for {len(known_uids)} types...")

    # For AI agent context (llms-full.txt)
    llm_lines = ["# Shape of Dreams API Reference for AI Agents & Modders\n"]

    for idx, item in enumerate(catalog):
        uid = item["uid"]
        json_file = API_JSON_DIR / f"{uid}.json"
        if not json_file.exists():
            continue
        data = json.loads(json_file.read_text(encoding="utf-8"))
        
        md_content = build_markdown_for_class(data, known_uids)
        md_file = DOCS_API_DIR / f"{uid}.md"
        md_file.write_text(md_content, encoding="utf-8")

        # Add brief summary to llms-full
        llm_lines.append(f"## {data.get('kind')} {data.get('name')} ({uid})")
        if data.get("summary"):
            llm_lines.append(f"Summary: {data.get('summary')}")
        if data.get("syntax"):
            llm_lines.append(f"Syntax: {data.get('syntax')}")
        methods = [m.get("declaration", m.get("name")) for m in data.get("methods", []) if m.get("declaration")]
        if methods:
            llm_lines.append("Key methods: " + "; ".join(methods[:8]))
        llm_lines.append("")

    # Save LLM context
    llm_file = DATA_DIR / "llms-full.txt"
    llm_file.write_text("\n".join(llm_lines), encoding="utf-8")
    print(f"Generated VitePress API Markdown files in {DOCS_API_DIR}")
    print(f"Generated LLM Reference Dump in {llm_file} ({llm_file.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
