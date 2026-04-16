"""
extractor.py - PDF → graph nodes + edges
Uses spaCy NER + dependency parsing locally.
Falls back to regex if spaCy not available (for Render free tier).
"""
import re
import pdfplumber

NER_TYPE_MAP = {
    "PERSON":"Person","ORG":"Organization","GPE":"Location","LOC":"Location",
    "DATE":"Date","TIME":"Date","EVENT":"Event","PRODUCT":"Product",
    "WORK_OF_ART":"Concept","LAW":"Concept","LANGUAGE":"Concept",
    "NORP":"Group","FAC":"Location","MONEY":"Concept",
    "PERCENT":"Concept","QUANTITY":"Concept","CARDINAL":"Concept",
}

# Try loading spaCy
_nlp = None
_use_spacy = False

def _get_nlp():
    global _nlp, _use_spacy
    if _nlp is not None:
        return _nlp
    try:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_lg", disable=["lemmatizer"])
        except OSError:
            try:
                _nlp = spacy.load("en_core_web_md", disable=["lemmatizer"])
            except OSError:
                _nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"])
        _use_spacy = True
        print("[extractor] Using spaCy NLP")
    except Exception as e:
        print(f"[extractor] spaCy not available ({e}), using regex fallback")
        _nlp = None
        _use_spacy = False
    return _nlp

def _safe_id(text):
    s = re.sub(r"[^a-zA-Z0-9_]", "_", text.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s: s = "entity"
    if s[0].isdigit(): s = "e_" + s
    return s[:60]

def _clean(t):
    t = re.sub(r"\(cid:\d+\)", " ", t)
    return re.sub(r"\s+", " ", t).strip()

# ── spaCy-based extraction ────────────────────────────────────────────────────

def _extract_spacy(text):
    nlp = _get_nlp()
    doc = nlp(text[:60_000])
    ent_types = {_clean(e.text): NER_TYPE_MAP.get(e.label_, "Concept")
                 for e in doc.ents if len(_clean(e.text)) > 1}

    nodes = {}
    edges = []
    seen_edges = set()

    def add_node(name):
        nid = _safe_id(name)
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": name, "type": ent_types.get(name, "Concept")}
        return nid

    def add_edge(s, rel, o):
        sid, oid = add_node(s), add_node(o)
        key = (sid, oid, rel)
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append({"from": sid, "to": oid, "label": rel})

    # SVO triples
    for sent in doc.sents:
        for token in sent:
            if token.pos_ != "VERB": continue
            subjs = [c for c in token.children if c.dep_ in ("nsubj","nsubjpass")]
            objs  = [c for c in token.children if c.dep_ in ("dobj","attr","pobj")]
            for s in subjs:
                for o in objs:
                    st, ot = _clean(s.text), _clean(o.text)
                    if st and ot and st != ot and len(st) > 1 and len(ot) > 1:
                        add_edge(st, token.lemma_.lower(), ot)

    # entity co-occurrence
    for sent in doc.sents:
        ents = [_clean(e.text) for e in sent.ents if len(_clean(e.text)) > 1]
        for i in range(len(ents) - 1):
            if ents[i] != ents[i+1]:
                add_edge(ents[i], "related_to", ents[i+1])

    edge_list = edges[:800]
    used = {e["from"] for e in edge_list} | {e["to"] for e in edge_list}
    node_list = [n for n in nodes.values() if n["id"] in used]
    return node_list, edge_list

# ── Regex-based extraction (fallback) ────────────────────────────────────────

STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "by","from","is","are","was","were","be","been","have","has","had",
    "do","does","did","will","would","could","should","may","might",
    "this","that","these","those","it","its","we","our","they","their",
    "he","she","his","her","as","if","then","than","so","not","no",
    "can","also","just","more","about","into","only","same","very","i","you"
}

PATTERNS = {
    "Person":       r'\b([A-Z][a-z]+ (?:[A-Z][a-z]+ )*[A-Z][a-z]+)\b',
    "Organization": r'\b([A-Z][A-Za-z&\s]{2,30}(?:University|Institute|College|Corp|Inc|Ltd|Lab|Center|School|Department|Foundation|Association|Society|Group))\b',
    "Technology":   r'\b(Python|Java|JavaScript|TypeScript|React|Angular|Vue|Node\.js|Flask|Django|FastAPI|MongoDB|PostgreSQL|MySQL|Redis|Docker|Kubernetes|AWS|Azure|GCP|TensorFlow|PyTorch|spaCy|BERT|GPT|LLM|NLP|ML|AI|API|REST|GraphQL|SQL|NoSQL|HTML|CSS|Git|GitHub|Linux)\b',
    "Concept":      r'\b([A-Z][a-z]{3,}(?:\s[A-Z][a-z]{3,}){0,2})\b',
}

def _extract_regex(text):
    nodes = {}
    edges = []
    seen_edges = set()

    def add_node(name, ntype="Concept"):
        nid = _safe_id(name)
        if nid and nid not in nodes and len(name) > 2:
            nodes[nid] = {"id": nid, "label": name, "type": ntype}
        return nid

    for ntype, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            name = _clean(match.group(1))
            if any(w in STOPWORDS for w in name.lower().split()):
                continue
            if 2 < len(name) < 60:
                add_node(name, ntype)

    sentences = re.split(r'[.!?\n]', text)
    for sent in sentences[:300]:
        sent = _clean(sent)
        if len(sent) < 10: continue
        caps = re.findall(r'\b([A-Z][a-zA-Z]{2,}(?:\s[A-Z][a-zA-Z]{2,})?)\b', sent)
        caps = [c for c in caps if c.lower() not in STOPWORDS and len(c) > 2]
        for i in range(len(caps) - 1):
            s, o = caps[i], caps[i+1]
            if s == o: continue
            sid, oid = _safe_id(s), _safe_id(o)
            if sid in nodes and oid in nodes:
                key = (sid, oid, "related_to")
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append({"from": sid, "to": oid, "label": "related_to"})

    edge_list = edges[:500]
    used = {e["from"] for e in edge_list} | {e["to"] for e in edge_list}
    node_list = [n for n in nodes.values() if n["id"] in used]
    if len(node_list) < 5:
        node_list = list(nodes.values())[:50]
    return node_list, edge_list

# ── Main entry point ──────────────────────────────────────────────────────────

def extract_graph(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:20]:
            t = page.extract_text()
            if t:
                t = re.sub(r"\(cid:\d+\)", " ", t)
                pages.append(t)

    text = "\n".join(pages)

    if not text.strip():
        return {"nodes": [], "edges": [], "stats": {"nodes": 0, "edges": 0,
                "error": "No text extracted. PDF may be image-based."}}

    # Try spaCy first, fall back to regex
    nlp = _get_nlp()
    if nlp is not None:
        node_list, edge_list = _extract_spacy(text)
    else:
        node_list, edge_list = _extract_regex(text[:20_000])

    return {
        "nodes": node_list,
        "edges": edge_list,
        "stats": {"nodes": len(node_list), "edges": len(edge_list)},
    }
