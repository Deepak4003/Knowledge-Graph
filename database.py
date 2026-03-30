"""
database.py  –  MongoDB persistence with SQLite fallback
"""
import os, re, json, sqlite3, ssl
from dotenv import load_dotenv
load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME   = os.environ.get("MONGO_DB", "knowledge_graph")
DB_PATH   = os.path.join(os.path.dirname(__file__), "graph.db")

_client = None
_db     = None
_use_mongo = False

def get_db():
    global _client, _db, _use_mongo
    if _db is not None:
        return _db
    if MONGO_URI:
        try:
            from pymongo import MongoClient, ASCENDING
            _client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=10000,
                tlsInsecure=True,
            )
            # force connection test
            _client.admin.command("ping")
            _db = _client[DB_NAME]
            _use_mongo = True
            print(f"MongoDB connected → {DB_NAME}")
            return _db
        except Exception as e:
            print(f"MongoDB failed ({e}), falling back to SQLite")
    _use_mongo = False
    _db = "sqlite"
    return _db

def _is_mongo():
    get_db()
    return _use_mongo

# ── SQLite helpers ────────────────────────────────────────────────────────────

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _sqlite_init():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY, label TEXT NOT NULL,
            type TEXT DEFAULT 'Node', properties TEXT DEFAULT '{}')""")
        c.execute("""CREATE TABLE IF NOT EXISTS edges (
            id TEXT PRIMARY KEY, from_id TEXT NOT NULL, to_id TEXT NOT NULL,
            label TEXT NOT NULL, properties TEXT DEFAULT '{}')""")

# ── Public API ────────────────────────────────────────────────────────────────

def init_db():
    if _is_mongo():
        from pymongo import ASCENDING
        _db.nodes.create_index("id", unique=True)
        _db.edges.create_index("id", unique=True)
        _db.edges.create_index([("from_id", ASCENDING), ("to_id", ASCENDING), ("label", ASCENDING)])
    else:
        _sqlite_init()
        print(f"SQLite connected → {DB_PATH}")

def migrate_json_if_needed():
    json_path = os.path.join(os.path.dirname(__file__), "graph_db.json")
    if not os.path.exists(json_path):
        return
    with open(json_path) as f:
        old = json.load(f)
    for nid, ndata in old.get("nodes", {}).items():
        insert_node(nid, ndata["label"], ndata.get("type","Node"), ndata.get("properties",{}))
    for e in old.get("edges", []):
        insert_edge(e["id"], e["from"], e["to"], e["label"], e.get("properties",{}))

def load_db():
    if _is_mongo():
        nodes = {}
        for doc in _db.nodes.find({}, {"_id": 0}):
            nodes[doc["id"]] = {"label": doc["label"], "type": doc.get("type","Node"), "properties": doc.get("properties",{})}
        edges = [{"id": d["id"], "from": d["from_id"], "to": d["to_id"], "label": d["label"], "properties": d.get("properties",{})}
                 for d in _db.edges.find({}, {"_id": 0})]
        return {"nodes": nodes, "edges": edges}
    else:
        with _conn() as c:
            nodes = {r["id"]: {"label": r["label"], "type": r["type"], "properties": json.loads(r["properties"])}
                     for r in c.execute("SELECT * FROM nodes")}
            edges = [{"id": r["id"], "from": r["from_id"], "to": r["to_id"], "label": r["label"], "properties": json.loads(r["properties"])}
                     for r in c.execute("SELECT * FROM edges")]
        return {"nodes": nodes, "edges": edges}

def db_to_vis(db=None):
    if db is None:
        db = load_db()
    return {"nodes": [{"id": nid, **ndata} for nid, ndata in db["nodes"].items()], "edges": db["edges"]}

def insert_node(nid, label, ntype, properties):
    if _is_mongo():
        _db.nodes.update_one({"id": nid}, {"$set": {"id": nid, "label": label, "type": ntype, "properties": properties}}, upsert=True)
    else:
        with _conn() as c:
            c.execute("INSERT OR REPLACE INTO nodes (id,label,type,properties) VALUES (?,?,?,?)",
                      (nid, label, ntype, json.dumps(properties)))

def update_node(nid, label, ntype, properties):
    if _is_mongo():
        _db.nodes.update_one({"id": nid}, {"$set": {"label": label, "type": ntype, "properties": properties}})
    else:
        with _conn() as c:
            c.execute("UPDATE nodes SET label=?,type=?,properties=? WHERE id=?",
                      (label, ntype, json.dumps(properties), nid))

def delete_node(nid):
    if _is_mongo():
        _db.nodes.delete_one({"id": nid})
        _db.edges.delete_many({"$or": [{"from_id": nid}, {"to_id": nid}]})
    else:
        with _conn() as c:
            c.execute("DELETE FROM nodes WHERE id=?", (nid,))
            c.execute("DELETE FROM edges WHERE from_id=? OR to_id=?", (nid, nid))

def node_exists(nid):
    if _is_mongo():
        return _db.nodes.find_one({"id": nid}, {"_id": 1}) is not None
    with _conn() as c:
        return c.execute("SELECT 1 FROM nodes WHERE id=?", (nid,)).fetchone() is not None

def insert_edge(eid, from_id, to_id, label, properties):
    if _is_mongo():
        _db.edges.update_one({"id": eid}, {"$set": {"id": eid, "from_id": from_id, "to_id": to_id, "label": label, "properties": properties}}, upsert=True)
    else:
        with _conn() as c:
            c.execute("INSERT OR REPLACE INTO edges (id,from_id,to_id,label,properties) VALUES (?,?,?,?,?)",
                      (eid, from_id, to_id, label, json.dumps(properties)))

def delete_edge(eid):
    if _is_mongo():
        _db.edges.delete_one({"id": eid})
    else:
        with _conn() as c:
            c.execute("DELETE FROM edges WHERE id=?", (eid,))

def edge_key_exists(from_id, to_id, label):
    if _is_mongo():
        return _db.edges.find_one({"from_id": from_id, "to_id": to_id, "label": label}, {"_id": 1}) is not None
    with _conn() as c:
        return c.execute("SELECT 1 FROM edges WHERE from_id=? AND to_id=? AND label=?",
                         (from_id, to_id, label)).fetchone() is not None

def next_node_id(label):
    if _is_mongo():
        count = _db.nodes.count_documents({})
    else:
        with _conn() as c:
            count = c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    return "n" + str(count + 1) + "_" + re.sub(r"\W+", "", label)[:12]

def next_edge_id():
    if _is_mongo():
        count = _db.edges.count_documents({})
    else:
        with _conn() as c:
            count = c.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    return "e" + str(count + 1)

def clear_all():
    if _is_mongo():
        _db.nodes.delete_many({})
        _db.edges.delete_many({})
    else:
        with _conn() as c:
            c.execute("DELETE FROM nodes")
            c.execute("DELETE FROM edges")
