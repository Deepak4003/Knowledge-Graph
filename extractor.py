"""
extractor.py - Lightweight PDF → graph (no spaCy, regex-based)
Designed to work within 512MB RAM on Render free tier.
"""
import re
import pdfplumber

def _clean(t):
    t = re.sub(r"\(cid:\d+\)", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _safe_id(text):
    s = re.sub(r"[^a-zA-Z0-9_]", "_", text.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s: s = "entity"
    if s[0].isdigit(): s = "e_" + s
    return s[:60]

# Common English stopwords to filter out
STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "by","from","is","are","was","were","be","been","being","have","has",
    "had","do","does","did","will","would","could","should","may","might",
    "this","that","these","those","it","its","we","our","they","their",
    "he","she","his","her","as","if","then","than","so","yet","both",
    "not","no","nor","can","also","just","more","about","into","through",
    "during","before","after","above","below","between","each","other",
    "such","when","where","which","who","whom","how","all","any","both",
    "few","more","most","other","some","such","only","own","same","too",
    "very","s","t","can","will","just","don","should","now","i","you"
}

# Patterns to extract named entities
PATTERNS = {
    "Person":       r'\b([A-Z][a-z]+ (?:[A-Z][a-z]+ )*[A-Z][a-z]+)\b',
    "Organization": r'\b([A-Z][A-Za-z&\s]{2,30}(?:University|Institute|College|Corp|Inc|Ltd|Lab|Center|Centre|School|Department|Ministry|Agency|Foundation|Association|Society|Group|Team))\b',
    "Technology":   r'\b(Python|Java|JavaScript|TypeScript|React|Angular|Vue|Node\.js|Flask|Django|FastAPI|MongoDB|PostgreSQL|MySQL|Redis|Docker|Kubernetes|AWS|Azure|GCP|TensorFlow|PyTorch|spaCy|BERT|GPT|LLM|NLP|ML|AI|API|REST|GraphQL|SQL|NoSQL|HTML|CSS|Git|GitHub|Linux|Windows)\b',
    "Concept":      r'\b([A-Z][a-z]{3,}(?:\s[A-Z][a-z]{3,}){0,2})\b',
}

def extract_graph(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:10]:  # max 10 pages
            t = page.extract_text()
            if t:
                t = re.sub(r"\(cid:\d+\)", " ", t)
                pages.append(t)

    text = "\n".join(pages)[:20_000]

    if not text.strip():
        return {"nodes": [], "edges": [], "stats": {"nodes": 0, "edges": 0}}

    nodes = {}
    edges = []
    seen_edges = set()

    def add_node(name, ntype="Concept"):
        nid = _safe_id(name)
        if nid and nid not in nodes and len(name) > 2:
            nodes[nid] = {"id": nid, "label": name, "type": ntype}
        return nid

    # Extract entities using regex patterns
    for ntype, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            name = _clean(match.group(1))
            words = name.lower().split()
            if any(w in STOPWORDS for w in words):
                continue
            if len(name) > 2 and len(name) < 60:
                add_node(name, ntype)

    # Extract relationships from sentences
    sentences = re.split(r'[.!?\n]', text)
    for sent in sentences[:300]:
        sent = _clean(sent)
        if len(sent) < 10:
            continue
        # find capitalized phrases in sentence
        caps = re.findall(r'\b([A-Z][a-zA-Z]{2,}(?:\s[A-Z][a-zA-Z]{2,})?)\b', sent)
        caps = [c for c in caps if c.lower() not in STOPWORDS and len(c) > 2]
        # link consecutive capitalized entities
        for i in range(len(caps) - 1):
            s, o = caps[i], caps[i+1]
            if s == o: continue
            sid, oid = _safe_id(s), _safe_id(o)
            if sid in nodes and oid in nodes:
                key = (sid, oid, "related_to")
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append({"from": sid, "to": oid, "label": "related_to"})

        # verb-based relations: X <verb> Y
        verb_match = re.search(
            r'\b([A-Z][a-zA-Z]{2,}(?:\s[A-Z][a-zA-Z]{2,})?)\s+(?:is|are|was|were|uses|used|has|have|includes|contains|provides|supports|enables|requires|develops|developed|created|builds|built)\s+([A-Z][a-zA-Z]{2,}(?:\s[A-Z][a-zA-Z]{2,})?)\b',
            sent
        )
        if verb_match:
            s, o = verb_match.group(1), verb_match.group(2)
            sid, oid = add_node(s), add_node(o)
            verb = re.search(r'\b(is|are|was|uses|has|includes|provides|supports|requires|develops|created|builds)\b', sent)
            rel = verb.group(1).upper() if verb else "RELATED_TO"
            key = (sid, oid, rel)
            if key not in seen_edges and sid in nodes and oid in nodes:
                seen_edges.add(key)
                edges.append({"from": sid, "to": oid, "label": rel})

    # keep only nodes referenced by edges
    edge_list = edges[:500]
    used = {e["from"] for e in edge_list} | {e["to"] for e in edge_list}
    # also keep top isolated nodes
    node_list = [n for n in nodes.values() if n["id"] in used]
    if len(node_list) < 5:
        node_list = list(nodes.values())[:50]

    return {
        "nodes": node_list,
        "edges": edge_list,
        "stats": {"nodes": len(node_list), "edges": len(edge_list)},
    }
