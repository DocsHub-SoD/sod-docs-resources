"""
Compiles the normalized JSON API data into:
1. SQLite Database (data/api.db) for instant exact-match SQL queries.
2. Lightweight JSON Knowledge Graph (data/api-graph.json) for fast zero-overhead traversal.
3. Class Index Map (data/api-index.json) mapping exact class/method names to signatures.
"""

import sqlite3
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
API_JSON_DIR = DATA_DIR / "api"
CATALOG_PATH = DATA_DIR / "api-catalog.json"
DB_PATH = DATA_DIR / "api.db"
GRAPH_PATH = DATA_DIR / "api-graph.json"


def build_databases():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Types table
    cur.execute("""
    CREATE TABLE types (
        uid TEXT PRIMARY KEY,
        name TEXT,
        kind TEXT,
        namespace TEXT,
        summary TEXT,
        syntax TEXT
    )
    """)

    # 2. Hierarchy table (Inheritance & Interfaces)
    cur.execute("""
    CREATE TABLE hierarchy (
        child_uid TEXT,
        parent_uid TEXT,
        relation_type TEXT, -- 'extends' or 'implements'
        PRIMARY KEY (child_uid, parent_uid, relation_type)
    )
    """)

    # 3. Members table (Methods, Fields, Properties)
    cur.execute("""
    CREATE TABLE members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type_uid TEXT,
        member_type TEXT, -- 'method', 'field', 'property', 'event'
        name TEXT,
        declaration TEXT,
        summary TEXT,
        returns TEXT,
        FOREIGN KEY(type_uid) REFERENCES types(uid)
    )
    """)

    # 4. Parameters table (For tracing which methods accept or return specific types)
    cur.execute("""
    CREATE TABLE parameters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER,
        name TEXT,
        param_type TEXT,
        param_type_uid TEXT,
        description TEXT,
        FOREIGN KEY(member_id) REFERENCES members(id)
    )
    """)

    # Indexes for lightning-fast lookups
    cur.execute("CREATE INDEX idx_members_name ON members(name)")
    cur.execute("CREATE INDEX idx_members_type ON members(type_uid)")
    cur.execute("CREATE INDEX idx_hierarchy_child ON hierarchy(child_uid)")
    cur.execute("CREATE INDEX idx_hierarchy_parent ON hierarchy(parent_uid)")
    cur.execute("CREATE INDEX idx_params_type_uid ON parameters(param_type_uid)")

    # Data structures for JSON graph
    graph = {
        "nodes": {},
        "edges": []
    }

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    
    for item in catalog:
        uid = item["uid"]
        json_file = API_JSON_DIR / f"{uid}.json"
        if not json_file.exists():
            continue

        data = json.loads(json_file.read_text(encoding="utf-8"))

        cur.execute("""
        INSERT INTO types (uid, name, kind, namespace, summary, syntax)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data.get("uid"),
            data.get("name"),
            data.get("kind"),
            data.get("namespace"),
            data.get("summary"),
            data.get("syntax")
        ))

        graph["nodes"][uid] = {
            "name": data.get("name"),
            "kind": data.get("kind"),
            "summary": data.get("summary"),
            "methods": [m.get("name") for m in data.get("methods", [])],
            "extends": [i.get("uid") for i in data.get("inheritance", [])],
            "implements": [i.get("uid") for i in data.get("implements", [])]
        }

        # Hierarchy
        for inh in data.get("inheritance", []):
            p_uid = inh.get("uid")
            if p_uid:
                cur.execute("INSERT OR IGNORE INTO hierarchy VALUES (?, ?, 'extends')", (uid, p_uid))
                graph["edges"].append({"source": uid, "target": p_uid, "type": "extends"})

        for imp in data.get("implements", []):
            i_uid = imp.get("uid")
            if i_uid:
                cur.execute("INSERT OR IGNORE INTO hierarchy VALUES (?, ?, 'implements')", (uid, i_uid))
                graph["edges"].append({"source": uid, "target": i_uid, "type": "implements"})

        # Members
        for m in data.get("methods", []):
            cur.execute("""
            INSERT INTO members (type_uid, member_type, name, declaration, summary, returns)
            VALUES (?, 'method', ?, ?, ?, ?)
            """, (uid, m.get("name"), m.get("declaration"), m.get("summary"), m.get("returns")))
            m_id = cur.lastrowid

            for p in m.get("parameters", []):
                cur.execute("""
                INSERT INTO parameters (member_id, name, param_type, param_type_uid, description)
                VALUES (?, ?, ?, ?, ?)
                """, (m_id, p.get("name"), p.get("type"), p.get("type_uid"), p.get("description")))

        for f in data.get("fields", []):
            cur.execute("""
            INSERT INTO members (type_uid, member_type, name, declaration, summary, returns)
            VALUES (?, 'field', ?, ?, ?, ?)
            """, (uid, f.get("name"), f.get("declaration"), f.get("summary"), None))

        for p in data.get("properties", []):
            cur.execute("""
            INSERT INTO members (type_uid, member_type, name, declaration, summary, returns)
            VALUES (?, 'property', ?, ?, ?, ?)
            """, (uid, p.get("name"), p.get("declaration"), p.get("summary"), None))

    conn.commit()
    conn.close()

    GRAPH_PATH.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Built SQLite Database: {DB_PATH} ({DB_PATH.stat().st_size / 1024:.1f} KB)")
    print(f"Built JSON Knowledge Graph: {GRAPH_PATH} ({GRAPH_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    build_databases()
