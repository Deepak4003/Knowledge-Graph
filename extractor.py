"""
extractor.py  –  PDF → graph nodes + edges (no owlready2, no metaclass issues)
Uses spaCy NER + dependency parsing only.
"""
import re
import pdfplumber
import spacy

_nlp = None

def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True)
            _nlp = spacy.load("en_core_web_sm")
    return _nlp

NER_TYPE_MAP = {
    "PERSON":"Person","ORG":"Organization","GPE":"Location","LOC":"Location",
    "DATE":"Date","TIME":"Date","EVENT":"Event","PRODUCT":"Product",
    "WORK_OF_ART":"Concept","LAW":"Concept","LANGUAGE":"Concept",
    "NORP":"Group","FAC":"Location","MONEY":"Concept",
    "PERCENT":"Concept","QUANTITY":"Concept","CARDINAL":"Concept",
}

def _safe_id(text):
    s = re.sub(r"[^a-zA-Z0-9_]", "_", text.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s: s = "entity"
    if s[0].isdigit(): s = "e_" + s
    return s[:60]

def _clean(t):
    # remove (cid:xxx) font encoding artifacts
    t = re.sub(r"\(cid:\d+\)", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def extract_graph(pdf_path):
    # extract text
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                t = re.sub(r"\(cid:\d+\)", " ", t)  # fix font encoding artifacts
                pages.append(t)
    text = "\n".join(pages)[:50_000]  # limit to 50k chars on server

    if not text.strip():
        return {"nodes": [], "edges": [], "stats": {"nodes": 0, "edges": 0, "error": "No text could be extracted from this PDF. It may be image-based."}}

    doc       = get_nlp()(text[:50_000])  # limit to 50k chars to save memory
    ent_types = {_clean(e.text): NER_TYPE_MAP.get(e.label_, "Concept") for e in doc.ents if len(_clean(e.text)) > 1}

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

    # cap
    edge_list = edges[:800]
    # keep only nodes referenced by edges
    used = {e["from"] for e in edge_list} | {e["to"] for e in edge_list}
    node_list = [n for n in nodes.values() if n["id"] in used]

    return {
        "nodes": node_list,
        "edges": edge_list,
        "stats": {"nodes": len(node_list), "edges": len(edge_list)},
    }
