"""
processor.py  –  PDF → triples → graph JSON
Avoids owlready2 metaclass conflicts by using a fresh unique IRI per call
and destroying the world cache between runs.
"""

import re
import types
import uuid
import pdfplumber
import spacy
import networkx as nx
import owlready2

# ---------------------------------------------------------------------------
# NLP model
# ---------------------------------------------------------------------------
try:
    nlp = spacy.load("en_core_web_lg")
except OSError:
    try:
        nlp = spacy.load("en_core_web_md")
    except OSError:
        nlp = spacy.load("en_core_web_sm")

OWL_FILE = "research_ontology.owl"

NER_CLASS_MAP = {
    "PERSON": "Person", "ORG": "Organization", "GPE": "GeopoliticalEntity",
    "LOC": "Location", "DATE": "Date", "TIME": "Time", "MONEY": "Money",
    "PERCENT": "Percentage", "PRODUCT": "Product", "EVENT": "Event",
    "WORK_OF_ART": "WorkOfArt", "LAW": "Law", "LANGUAGE": "Language",
    "NORP": "NationalityOrGroup", "FAC": "Facility",
    "QUANTITY": "Quantity", "ORDINAL": "Ordinal", "CARDINAL": "Cardinal",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_id(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]", "_", text.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "entity"
    if s[0].isdigit():
        s = "e_" + s
    return s[:80]

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_text(pdf_path: str) -> str:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
    return "\n".join(pages)

# ---------------------------------------------------------------------------
# Triple extraction
# ---------------------------------------------------------------------------

def _svo_triples(doc):
    triples = []
    for sent in doc.sents:
        for token in sent:
            if token.pos_ != "VERB":
                continue
            subjects = [c for c in token.children if c.dep_ in ("nsubj", "nsubjpass", "csubj")]
            objects  = [c for c in token.children if c.dep_ in ("dobj", "attr", "pobj", "iobj", "oprd")]
            for s in subjects:
                for o in objects:
                    st = _clean(s.text)
                    ot = _clean(o.text)
                    if st and ot and st != ot:
                        triples.append((st, token.lemma_.lower(), ot))
    return triples

def _cooccurrence_triples(doc):
    triples = []
    for sent in doc.sents:
        ents = [_clean(e.text) for e in sent.ents if len(_clean(e.text)) > 1]
        for i in range(len(ents) - 1):
            if ents[i] != ents[i + 1]:
                triples.append((ents[i], "related_to", ents[i + 1]))
    return triples

def extract_triples(text: str):
    doc = nlp(text[:80_000])
    ent_types = {_clean(e.text): e.label_ for e in doc.ents if len(_clean(e.text)) > 1}
    raw = _svo_triples(doc) + _cooccurrence_triples(doc)
    seen, triples = set(), []
    for t in raw:
        if t not in seen:
            seen.add(t)
            triples.append(t)
    return triples[:300], ent_types

# ---------------------------------------------------------------------------
# OWL ontology  –  fresh world every call to avoid metaclass conflicts
# ---------------------------------------------------------------------------

def build_ontology(triples: list, ent_types: dict) -> str:
    # ── Wipe owlready2's global cache so classes don't collide ──────────────
    owlready2.default_world.ontologies.clear()
    # Also reset the namespace registry to avoid stale class objects
    try:
        owlready2.default_world._destroy()
    except Exception:
        pass
    owlready2.default_world = owlready2.World()

    # Use a unique IRI so owlready2 never reuses a cached ontology
    unique_iri = f"http://research-kg.org/ontology/{uuid.uuid4().hex}#"
    onto = owlready2.get_ontology(unique_iri)

    with onto:
        # Top-level class
        class ResearchEntity(owlready2.Thing):
            pass

        # NER subclasses
        ner_classes: dict[str, type] = {}
        for label, cls_name in NER_CLASS_MAP.items():
            cls = types.new_class(cls_name, (ResearchEntity,))
            cls.namespace = onto
            ner_classes[label] = cls

        class GenericConcept(ResearchEntity):
            pass

        # Object properties – one per unique relation verb
        rel_props: dict[str, type] = {}
        for rel in {t[1] for t in triples}:
            prop_name = _safe_id(rel)
            if prop_name not in rel_props:
                prop = types.new_class(prop_name, (owlready2.ObjectProperty,))
                prop.namespace = onto
                prop.label     = [rel]
                prop.domain    = [ResearchEntity]
                prop.range     = [ResearchEntity]
                rel_props[prop_name] = prop

        # Named individuals
        individuals: dict[str, object] = {}

        def get_or_create(name: str):
            key = _safe_id(name)
            if key in individuals:
                return individuals[key]
            ner_label  = ent_types.get(name, "")
            parent_cls = ner_classes.get(ner_label, GenericConcept)
            ind        = parent_cls(key)
            ind.label  = [name]
            individuals[key] = ind
            return ind

        for subj, rel, obj in triples:
            s_ind = get_or_create(subj)
            o_ind = get_or_create(obj)
            prop  = rel_props.get(_safe_id(rel))
            if prop:
                getattr(s_ind, prop.python_name).append(o_ind)

    onto.save(file=OWL_FILE, format="rdfxml")
    return OWL_FILE

# ---------------------------------------------------------------------------
# NetworkX graph
# ---------------------------------------------------------------------------

def build_graph(triples, ent_types):
    G = nx.DiGraph()
    for subj, rel, obj in triples:
        G.add_node(subj, ner=ent_types.get(subj, "CONCEPT"))
        G.add_node(obj,  ner=ent_types.get(obj,  "CONCEPT"))
        G.add_edge(subj, obj, label=rel)
    return G

def graph_to_json(G):
    return {
        "nodes": [{"id": n, "label": n, "ner": d.get("ner", "CONCEPT")} for n, d in G.nodes(data=True)],
        "edges": [{"from": u, "to": v, "label": d.get("label", "")} for u, v, d in G.edges(data=True)],
    }

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_pdf(pdf_path: str) -> dict:
    text             = extract_text(pdf_path)
    triples, ent_types = extract_triples(text)
    G                = build_graph(triples, ent_types)
    build_ontology(triples, ent_types)

    return {
        "graph":     graph_to_json(G),
        "relations": [{"subject": s, "relation": r, "object": o} for s, r, o in triples],
        "owl_path":  OWL_FILE,
        "stats": {
            "nodes":    G.number_of_nodes(),
            "edges":    G.number_of_edges(),
            "triples":  len(triples),
            "entities": len(ent_types),
        },
        "ner_types": ent_types,
    }
