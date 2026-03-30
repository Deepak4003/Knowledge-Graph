"""
query_engine.py
---------------
Mini Cypher-like query language for the graph DB.

Supported syntax:

  MATCH (n)                              → all nodes
  MATCH (n:Person)                       → nodes by type
  MATCH (n) WHERE n.label = "Einstein"   → exact label match
  MATCH (n) WHERE n.label CONTAINS "ein" → partial match
  MATCH (n) WHERE n.type = "Person"      → type filter
  MATCH (n) WHERE n.field = "Physics"    → property filter
  MATCH (n)-[r]->(m)                     → all relationships
  MATCH (n)-[r:DISCOVERED]->(m)          → filter by relation type
  MATCH (n:Person)-[r]->(m)              → typed node + any relation
  MATCH (n:Person)-[r:WON]->(m:Event)    → full pattern
  MATCH (n)-[r]->(m) WHERE n.label = "Einstein"
  MATCH (n)-[r]->(m) WHERE m.type = "Concept"
  MATCH (n)-[r]->(m) RETURN n,r,m        → explicit return (default)
  MATCH (n) RETURN n.label, n.type       → return specific fields
  MATCH (n:Person) RETURN n.label ORDER BY n.label
  MATCH (n:Person) RETURN n.label LIMIT 5
  COUNT (n:Person)                       → count nodes
  COUNT (n)-[r:WON]->(m)                → count relationships
  PATH FROM "Einstein" TO "Nobel Prize"  → shortest path
  NEIGHBORS "Einstein"                   → all direct neighbors
  STATS                                  → graph statistics
"""

import re

# ─────────────────────────────────────────────────────────────────────────────

def run_query(q: str, db: dict) -> dict:
    """Entry point. Returns {columns, rows, graph, message, error}"""
    q = q.strip()
    if not q:
        return _err("Empty query")

    upper = q.upper()

    try:
        if upper.startswith("STATS"):
            return _stats(db)
        if upper.startswith("NEIGHBORS"):
            return _neighbors(q, db)
        if upper.startswith("PATH"):
            return _path(q, db)
        if upper.startswith("COUNT"):
            return _count(q, db)
        if upper.startswith("MATCH"):
            return _match(q, db)
        return _err(f'Unknown command. Start with MATCH, COUNT, PATH, NEIGHBORS or STATS.')
    except Exception as e:
        return _err(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# MATCH
# ─────────────────────────────────────────────────────────────────────────────

def _match(q: str, db: dict) -> dict:
    nodes  = db["nodes"]   # {id: {label, type, properties}}
    edges  = db["edges"]   # [{id, from, to, label, properties}]

    # ── parse pattern ────────────────────────────────────────────────────────
    rel_pattern = re.search(r'\((\w*):?(\w*)\)\s*-\[(\w*):?(\w*)\]->\s*\((\w*):?(\w*)\)', q)
    node_pattern = re.search(r'\((\w+):?(\w*)\)', q) if not rel_pattern else None

    # ── parse WHERE ──────────────────────────────────────────────────────────
    where_clause = None
    where_m = re.search(r'\bWHERE\b(.+?)(?:\bRETURN\b|\bORDER\b|\bLIMIT\b|$)', q, re.IGNORECASE)
    if where_m:
        where_clause = where_m.group(1).strip()

    # ── parse RETURN ─────────────────────────────────────────────────────────
    return_fields = None
    ret_m = re.search(r'\bRETURN\b(.+?)(?:\bORDER\b|\bLIMIT\b|$)', q, re.IGNORECASE)
    if ret_m:
        return_fields = [f.strip() for f in ret_m.group(1).split(",")]

    # ── parse ORDER BY ───────────────────────────────────────────────────────
    order_field = None
    order_m = re.search(r'\bORDER BY\b\s+(\S+)', q, re.IGNORECASE)
    if order_m:
        order_field = order_m.group(1).strip()

    # ── parse LIMIT ──────────────────────────────────────────────────────────
    limit = None
    lim_m = re.search(r'\bLIMIT\b\s+(\d+)', q, re.IGNORECASE)
    if lim_m:
        limit = int(lim_m.group(1))

    # ── RELATIONSHIP MATCH ───────────────────────────────────────────────────
    if rel_pattern:
        n_var, n_type, r_var, r_type, m_var, m_type = rel_pattern.groups()
        results = []
        for e in edges:
            if r_type and e["label"].upper() != r_type.upper():
                continue
            s_node = nodes.get(e["from"])
            t_node = nodes.get(e["to"])
            if not s_node or not t_node:
                continue
            if n_type and s_node.get("type","").lower() != n_type.lower():
                continue
            if m_type and t_node.get("type","").lower() != m_type.lower():
                continue
            row = {"n": {"id": e["from"], **s_node},
                   "r": {"type": e["label"], "id": e["id"]},
                   "m": {"id": e["to"],   **t_node}}
            if where_clause and not _eval_where(where_clause, row):
                continue
            results.append(row)

        if order_field:
            results = _sort(results, order_field)
        if limit:
            results = results[:limit]

        # build graph subset
        used_nids = set()
        used_eids = set()
        for row in results:
            used_nids.add(row["n"]["id"]); used_nids.add(row["m"]["id"])
            used_eids.add(row["r"]["id"])

        graph = {
            "nodes": [{"id": nid, **nodes[nid]} for nid in used_nids if nid in nodes],
            "edges": [e for e in edges if e["id"] in used_eids],
        }

        if return_fields:
            columns, rows = _project(results, return_fields)
        else:
            columns = ["n.label", "r.type", "m.label"]
            rows    = [[r["n"]["label"], r["r"]["type"], r["m"]["label"]] for r in results]

        return {"columns": columns, "rows": rows, "graph": graph,
                "message": f"{len(rows)} relationship(s) found"}

    # ── NODE MATCH ───────────────────────────────────────────────────────────
    n_type = ""
    if node_pattern:
        n_type = node_pattern.group(2)

    matched = {}
    for nid, ndata in nodes.items():
        if n_type and ndata.get("type","").lower() != n_type.lower():
            continue
        row = {"n": {"id": nid, **ndata}}
        if where_clause and not _eval_where(where_clause, row):
            continue
        matched[nid] = row

    results = list(matched.values())

    if order_field:
        results = _sort(results, order_field)
    if limit:
        results = results[:limit]

    used_ids = {r["n"]["id"] for r in results}
    graph = {
        "nodes": [{"id": nid, **nodes[nid]} for nid in used_ids if nid in nodes],
        "edges": [e for e in edges if e["from"] in used_ids and e["to"] in used_ids],
    }

    if return_fields:
        columns, rows = _project(results, return_fields)
    else:
        columns = ["id", "label", "type", "properties"]
        rows    = [[r["n"]["id"], r["n"]["label"], r["n"].get("type",""), r["n"].get("properties",{})] for r in results]

    return {"columns": columns, "rows": rows, "graph": graph,
            "message": f"{len(rows)} node(s) found"}


# ─────────────────────────────────────────────────────────────────────────────
# WHERE evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _eval_where(clause: str, row: dict) -> bool:
    """Evaluate a simple WHERE clause against a result row."""
    # handle AND / OR
    if re.search(r'\bAND\b', clause, re.IGNORECASE):
        parts = re.split(r'\bAND\b', clause, flags=re.IGNORECASE)
        return all(_eval_where(p.strip(), row) for p in parts)
    if re.search(r'\bOR\b', clause, re.IGNORECASE):
        parts = re.split(r'\bOR\b', clause, flags=re.IGNORECASE)
        return any(_eval_where(p.strip(), row) for p in parts)

    # CONTAINS
    m = re.match(r'(\w+)\.(\w+)\s+CONTAINS\s+"([^"]*)"', clause, re.IGNORECASE)
    if m:
        var, field, val = m.groups()
        return val.lower() in str(_get_field(row, var, field)).lower()

    # STARTS WITH
    m = re.match(r'(\w+)\.(\w+)\s+STARTS WITH\s+"([^"]*)"', clause, re.IGNORECASE)
    if m:
        var, field, val = m.groups()
        return str(_get_field(row, var, field)).lower().startswith(val.lower())

    # = (equals)
    m = re.match(r'(\w+)\.(\w+)\s*=\s*"([^"]*)"', clause, re.IGNORECASE)
    if m:
        var, field, val = m.groups()
        return str(_get_field(row, var, field)).lower() == val.lower()

    # != (not equals)
    m = re.match(r'(\w+)\.(\w+)\s*!=\s*"([^"]*)"', clause, re.IGNORECASE)
    if m:
        var, field, val = m.groups()
        return str(_get_field(row, var, field)).lower() != val.lower()

    return True  # unknown clause → pass


def _get_field(row: dict, var: str, field: str):
    node = row.get(var, {})
    if field == "label":  return node.get("label", "")
    if field == "type":   return node.get("type",  "")
    if field == "id":     return node.get("id",    "")
    return node.get("properties", {}).get(field, "")


# ─────────────────────────────────────────────────────────────────────────────
# RETURN projection
# ─────────────────────────────────────────────────────────────────────────────

def _project(results, fields):
    rows = []
    for row in results:
        r = []
        for f in fields:
            if "." in f:
                var, field = f.split(".", 1)
                r.append(_get_field(row, var.strip(), field.strip()))
            else:
                r.append(str(row.get(f.strip(), "")))
        rows.append(r)
    return fields, rows


def _sort(results, field):
    if "." in field:
        var, f = field.split(".", 1)
        return sorted(results, key=lambda r: str(_get_field(r, var, f)).lower())
    return results


# ─────────────────────────────────────────────────────────────────────────────
# COUNT
# ─────────────────────────────────────────────────────────────────────────────

def _count(q: str, db: dict) -> dict:
    nodes, edges = db["nodes"], db["edges"]

    rel_m = re.search(r'\((\w*):?(\w*)\)\s*-\[(\w*):?(\w*)\]->\s*\((\w*):?(\w*)\)', q)
    if rel_m:
        _, n_type, _, r_type, _, m_type = rel_m.groups()
        count = sum(
            1 for e in edges
            if (not r_type or e["label"].upper() == r_type.upper())
            and (not n_type or nodes.get(e["from"],{}).get("type","").lower() == n_type.lower())
            and (not m_type or nodes.get(e["to"],  {}).get("type","").lower() == m_type.lower())
        )
        label = f"({n_type or '*'})-[{r_type or '*'}]->({m_type or '*'})"
        return {"columns":["pattern","count"], "rows":[[label, count]],
                "graph":{"nodes":[],"edges":[]}, "message": f"Count: {count}"}

    node_m = re.search(r'\((\w*):?(\w*)\)', q)
    n_type = node_m.group(2) if node_m else ""
    count  = sum(1 for n in nodes.values() if not n_type or n.get("type","").lower()==n_type.lower())
    label  = f"(:{n_type})" if n_type else "(*)"
    return {"columns":["pattern","count"], "rows":[[label, count]],
            "graph":{"nodes":[],"edges":[]}, "message": f"Count: {count}"}


# ─────────────────────────────────────────────────────────────────────────────
# PATH
# ─────────────────────────────────────────────────────────────────────────────

def _path(q: str, db: dict) -> dict:
    m = re.search(r'PATH\s+FROM\s+"([^"]+)"\s+TO\s+"([^"]+)"', q, re.IGNORECASE)
    if not m:
        return _err('Syntax: PATH FROM "NodeA" TO "NodeB"')

    src_label, dst_label = m.group(1), m.group(2)
    nodes, edges = db["nodes"], db["edges"]

    # find node IDs by label
    src_id = next((nid for nid, n in nodes.items() if n["label"].lower()==src_label.lower()), None)
    dst_id = next((nid for nid, n in nodes.items() if n["label"].lower()==dst_label.lower()), None)
    if not src_id: return _err(f'Node "{src_label}" not found')
    if not dst_id: return _err(f'Node "{dst_label}" not found')

    # BFS
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], []).append((e["to"],   e["label"], e["id"]))
        adj.setdefault(e["to"],   []).append((e["from"], e["label"], e["id"]))  # undirected BFS

    from collections import deque
    queue   = deque([(src_id, [src_id], [])])
    visited = {src_id}
    while queue:
        cur, path_nodes, path_edges = queue.popleft()
        if cur == dst_id:
            # build result
            g_nodes = [{"id": nid, **nodes[nid]} for nid in path_nodes if nid in nodes]
            g_edges = [e for e in edges if e["id"] in set(path_edges)]
            steps   = []
            for i in range(len(path_nodes)-1):
                s = nodes.get(path_nodes[i],{}).get("label", path_nodes[i])
                t = nodes.get(path_nodes[i+1],{}).get("label", path_nodes[i+1])
                rel = next((e["label"] for e in edges if e["id"]==path_edges[i]), "?")
                steps.append([s, rel, t])
            return {"columns":["from","relation","to"], "rows": steps,
                    "graph":{"nodes":g_nodes,"edges":g_edges},
                    "message": f"Path length: {len(path_nodes)-1} hops"}
        for nbr, rel, eid in adj.get(cur, []):
            if nbr not in visited:
                visited.add(nbr)
                queue.append((nbr, path_nodes+[nbr], path_edges+[eid]))

    return {"columns":[], "rows":[], "graph":{"nodes":[],"edges":[]},
            "message": f'No path found between "{src_label}" and "{dst_label}"'}


# ─────────────────────────────────────────────────────────────────────────────
# NEIGHBORS
# ─────────────────────────────────────────────────────────────────────────────

def _neighbors(q: str, db: dict) -> dict:
    m = re.search(r'NEIGHBORS\s+"([^"]+)"', q, re.IGNORECASE)
    if not m:
        return _err('Syntax: NEIGHBORS "NodeLabel"')
    label  = m.group(1)
    nodes, edges = db["nodes"], db["edges"]
    nid    = next((i for i, n in nodes.items() if n["label"].lower()==label.lower()), None)
    if not nid: return _err(f'Node "{label}" not found')

    rel_edges = [e for e in edges if e["from"]==nid or e["to"]==nid]
    nbr_ids   = {e["to"] if e["from"]==nid else e["from"] for e in rel_edges}
    nbr_ids.add(nid)

    rows = []
    for e in rel_edges:
        other_id  = e["to"] if e["from"]==nid else e["from"]
        direction = "→" if e["from"]==nid else "←"
        other_lbl = nodes.get(other_id,{}).get("label", other_id)
        other_typ = nodes.get(other_id,{}).get("type",  "?")
        rows.append([label, direction, e["label"], other_lbl, other_typ])

    g_nodes = [{"id": i, **nodes[i]} for i in nbr_ids if i in nodes]
    g_edges = rel_edges

    return {"columns":["node","dir","relation","neighbor","type"], "rows": rows,
            "graph":{"nodes":g_nodes,"edges":g_edges},
            "message": f"{len(nbr_ids)-1} neighbor(s) of \"{label}\""}


# ─────────────────────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────────────────────

def _stats(db: dict) -> dict:
    nodes, edges = db["nodes"], db["edges"]
    type_counts  = {}
    for n in nodes.values():
        t = n.get("type","Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    rel_counts = {}
    for e in edges:
        rel_counts[e["label"]] = rel_counts.get(e["label"], 0) + 1

    rows = [["Total Nodes",         len(nodes)],
            ["Total Relationships",  len(edges)]]
    for t, c in sorted(type_counts.items()):
        rows.append([f"  Nodes of type {t}", c])
    for r, c in sorted(rel_counts.items(), key=lambda x:-x[1]):
        rows.append([f"  Relation {r}", c])

    return {"columns":["metric","value"], "rows": rows,
            "graph": {"nodes":[], "edges":[]},
            "message": "Graph statistics"}


# ─────────────────────────────────────────────────────────────────────────────

def _err(msg):
    return {"columns":[], "rows":[], "graph":{"nodes":[],"edges":[]},
            "error": msg, "message": ""}
