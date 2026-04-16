from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
import os, re
from dotenv import load_dotenv
load_dotenv()
from database import (
    init_db, migrate_json_if_needed, load_db, db_to_vis,
    insert_node, update_node, delete_node, node_exists,
    insert_edge, delete_edge, edge_key_exists,
    next_node_id, next_edge_id, clear_all
)

app = Flask(__name__)
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "/tmp/uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

# ── Init DB on startup ───────────────────────────────────────────────────────
init_db()
migrate_json_if_needed()

# ── Routes ───────────────────────────────────────────────────────────────────

_last_error = {}

@app.route("/debug/last-error")
def last_error():
    return jsonify(_last_error)


@app.route("/debug/upload-test", methods=["GET"])
def debug_upload_test():
    import traceback
    try:
        from extractor import extract_graph
        test_dirs = ["/tmp/uploads", os.path.join(os.path.dirname(__file__), "uploads")]
        pdfs = []
        for d in test_dirs:
            if os.path.exists(d):
                pdfs = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith('.pdf')]
                if pdfs: break
        if not pdfs:
            return jsonify({"error": "no pdfs found", "checked": test_dirs})
        result = extract_graph(pdfs[0])
        return jsonify({"ok": True, "file": pdfs[0], "stats": result["stats"]})
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()})

@app.route("/debug/file-info", methods=["POST"])
def debug_file_info():
    import traceback
    try:
        if "pdf" not in request.files:
            return jsonify({"error": "no pdf field", "fields": list(request.files.keys())})
        f = request.files["pdf"]
        fname = secure_filename(f.filename) or "upload.pdf"
        path = f"/tmp/uploads/{fname}"
        os.makedirs("/tmp/uploads", exist_ok=True)
        f.save(path)
        size = os.path.getsize(path)
        # now try extraction
        from extractor import extract_graph
        result = extract_graph(path)
        return jsonify({"ok": True, "filename": fname, "size": size, "stats": result["stats"]})
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()})

@app.route("/health")
def health():
    from extractor import _use_spacy
    return jsonify({"status": "ok", "extractor": "spacy" if _use_spacy else "regex", "db": "mongodb" if __import__('database')._use_mongo else "sqlite"})

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/graph", methods=["GET"])
def get_graph():
    return jsonify(db_to_vis())

@app.route("/node", methods=["POST"])
def add_node():
    data  = request.get_json()
    label = data.get("label", "").strip()
    ntype = data.get("type", "Node").strip()
    props = data.get("properties", {})
    if not label:
        return jsonify({"error": "Label required"}), 400
    nid = next_node_id(label)
    while node_exists(nid):
        nid += "_"
    insert_node(nid, label, ntype, props)
    return jsonify({"id": nid, "graph": db_to_vis()})

@app.route("/node/<nid>", methods=["PUT"])
def update_node_route(nid):
    data = request.get_json()
    if not node_exists(nid):
        return jsonify({"error": "Node not found"}), 404
    db   = load_db()
    node = db["nodes"][nid]
    update_node(
        nid,
        data.get("label",      node["label"]),
        data.get("type",       node["type"]),
        data.get("properties", node["properties"]),
    )
    return jsonify({"graph": db_to_vis()})

@app.route("/node/<nid>", methods=["DELETE"])
def delete_node_route(nid):
    if not node_exists(nid):
        return jsonify({"error": "Node not found"}), 404
    delete_node(nid)
    return jsonify({"graph": db_to_vis()})

@app.route("/edge", methods=["POST"])
def add_edge():
    data    = request.get_json()
    from_id = data.get("from", "").strip()
    to_id   = data.get("to",   "").strip()
    rel     = data.get("relation", "RELATED_TO").strip()
    props   = data.get("properties", {})
    if not node_exists(from_id) or not node_exists(to_id):
        return jsonify({"error": "Both nodes must exist"}), 400
    eid = next_edge_id()
    insert_edge(eid, from_id, to_id, rel, props)
    return jsonify({"id": eid, "graph": db_to_vis()})

@app.route("/edge/<eid>", methods=["DELETE"])
def delete_edge_route(eid):
    delete_edge(eid)
    return jsonify({"graph": db_to_vis()})

@app.route("/query", methods=["POST"])
def query():
    from query_engine import run_query
    data   = request.get_json()
    q      = data.get("q", "").strip()
    result = run_query(q, load_db())
    return jsonify(result)

@app.route("/ask", methods=["POST"])
def ask():
    from nl_query import answer_question
    data     = request.get_json()
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Question required"}), 400
    result = answer_question(question, load_db())
    return jsonify(result)

@app.route("/swrl/apply", methods=["POST"])
def swrl_apply():
    data  = request.get_json()
    rules = data.get("rules", [])
    if not rules:
        return jsonify({"error": "No rules provided"}), 400
    db       = load_db()
    nodes    = db["nodes"]
    edges    = db["edges"]
    inferred = []

    def get_vals(nid, prop):
        """Return values for a property: edges where from=nid and label=prop"""
        return [e["to"] for e in edges if e["from"] == nid and e["label"] == prop]

    def node_has_type(nid, t):
        return nodes.get(nid, {}).get("type","").lower() == t.lower() or \
               nodes.get(nid, {}).get("label","").lower() == t.lower()

    import re as _re
    for rule in rules:
        rule = rule.strip()
        if not rule: continue
        sep = "→" if "→" in rule else "->"
        body_str, head_str = rule.split(sep, 1)
        # parse atoms like Pred(?x,?y) or Type(?x)
        def parse_atoms(s):
            return _re.findall(r'(\w+)\(([^)]+)\)', s)
        body_atoms = parse_atoms(body_str)
        head_atoms = parse_atoms(head_str)
        if not head_atoms: continue

        # simple forward-chain over all node pairs
        for nid in list(nodes.keys()):
            bindings = {"?x": nid}
            satisfied = True
            for pred, args in body_atoms:
                arg_list = [a.strip() for a in args.split(",")]
                if len(arg_list) == 1:
                    # type check
                    var = arg_list[0]
                    bound = bindings.get(var, var)
                    if not node_has_type(bound, pred):
                        satisfied = False; break
                elif len(arg_list) == 2:
                    v1, v2 = arg_list
                    b1 = bindings.get(v1, v1)
                    targets = get_vals(b1, pred)
                    if not targets:
                        satisfied = False; break
                    if v2 not in bindings:
                        bindings[v2] = targets[0]
                    elif bindings[v2] not in targets:
                        satisfied = False; break
            if not satisfied: continue
            for pred, args in head_atoms:
                arg_list = [a.strip() for a in args.split(",")]
                if len(arg_list) == 2:
                    s = bindings.get(arg_list[0], arg_list[0])
                    o = bindings.get(arg_list[1], arg_list[1])
                    if s in nodes and o in nodes and not edge_key_exists(s, o, pred):
                        insert_edge(next_edge_id(), s, o, pred, {})
                        inferred.append({"subject": nodes[s]["label"], "predicate": pred, "object": nodes[o]["label"]})

    return jsonify({"graph": db_to_vis(), "inferred": inferred})

@app.route("/clear", methods=["POST"])
def clear():
    clear_all()
    return jsonify({"graph": db_to_vis()})

# ── OWL ──────────────────────────────────────────────────────────────────────

@app.route("/owl/parse", methods=["POST"])
def owl_parse():
    from owl_parser import owl_to_graph, validate_owl
    data = request.get_json()
    err  = validate_owl(data.get("owl",""))
    if err:
        return jsonify({"error": err}), 400
    graph = owl_to_graph(data["owl"])
    return jsonify({"graph": {"nodes": graph["nodes"], "edges": graph["edges"]}})

@app.route("/owl/import", methods=["POST"])
def owl_import():
    from owl_parser import owl_to_graph, validate_owl
    data = request.get_json()
    err  = validate_owl(data.get("owl",""))
    if err:
        return jsonify({"error": err}), 400
    graph = owl_to_graph(data["owl"])
    added_nodes = added_edges = 0
    for n in graph["nodes"]:
        nid = re.sub(r"\W+", "_", n["id"])
        if not node_exists(nid):
            insert_node(nid, n.get("label", n["id"]), n.get("ner","Concept"), {})
            added_nodes += 1
    for e in graph["edges"]:
        fid = re.sub(r"\W+", "_", e["from"])
        tid = re.sub(r"\W+", "_", e["to"])
        if node_exists(fid) and node_exists(tid) and not edge_key_exists(fid, tid, e["label"]):
            insert_edge(next_edge_id(), fid, tid, e["label"], {})
            added_edges += 1
    return jsonify({"graph": db_to_vis(), "added_nodes": added_nodes, "added_edges": added_edges})

# ── PDF ───────────────────────────────────────────────────────────────────────

@app.route("/upload", methods=["POST"])
def upload():
    if "pdf" not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files["pdf"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "PDF only"}), 400
    path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename) or "upload.pdf")
    file.save(path)
    try:
        from ai_extractor import extract_graph_ai
        result = extract_graph_ai(path)
        for n in result["nodes"]:
            nid = n["id"]
            if not node_exists(nid):
                insert_node(nid, n["label"], n.get("type","Concept"), {})
        for e in result["edges"]:
            if node_exists(e["from"]) and node_exists(e["to"]):
                if not edge_key_exists(e["from"], e["to"], e["label"]):
                    insert_edge(next_edge_id(), e["from"], e["to"], e["label"], {})
        method = result.get("method", "ai")
        return jsonify({"graph": db_to_vis(), "stats": result["stats"], "method": method})
    except Exception as ex:
        import traceback
        tb = traceback.format_exc()
        _last_error.update({"error": str(ex), "trace": tb})
        print(f"UPLOAD ERROR: {ex}\n{tb}")
        return jsonify({"error": str(ex), "trace": tb}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(debug=False, host="0.0.0.0", port=port)
