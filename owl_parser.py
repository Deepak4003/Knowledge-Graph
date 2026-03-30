"""
owl_parser.py
Parse RDF/XML OWL text → graph JSON for vis-network.
No owlready2 needed here — uses xml.etree for speed.
"""
import re
import xml.etree.ElementTree as ET

RDF  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL  = "http://www.w3.org/2002/07/owl#"
ONTO = "http://research-kg.org/ontology#"

def _local(uri):
    """Extract local name from URI or prefixed name."""
    if not uri:
        return ""
    for sep in ["#", "/"]:
        if sep in uri:
            return uri.rsplit(sep, 1)[-1]
    return uri

def validate_owl(text):
    """Return error string or None."""
    try:
        # strip DOCTYPE before parsing (ET doesn't support it)
        clean = re.sub(r'<!DOCTYPE[^>]*>', '', text)
        clean = re.sub(r'<!ENTITY[^>]*>', '', clean)
        ET.fromstring(clean)
        return None
    except ET.ParseError as e:
        return f"XML parse error: {e}"

def owl_to_graph(text):
    """Parse OWL/RDF XML and return {nodes, edges}."""
    try:
        clean = re.sub(r'<!DOCTYPE[^>]*\[.*?\]>', '', text, flags=re.DOTALL)
        clean = re.sub(r'<!ENTITY\s+\w+\s+"[^"]*">', '', clean)
        root  = ET.fromstring(clean)
    except ET.ParseError:
        return {"nodes": [], "edges": []}

    nodes = {}   # id → {id, label, type}
    edges = []   # {from, to, label}
    props = set()  # known object property local names

    def resolve(uri):
        """Resolve &onto; style refs that survived stripping."""
        if uri and uri.startswith("&onto;"):
            return ONTO + uri[6:]
        return uri

    # ── Collect object properties ────────────────────────────────────────────
    for el in root.findall(f"{{{OWL}}}ObjectProperty"):
        about = el.get(f"{{{RDF}}}about", "")
        props.add(_local(resolve(about)))

    # ── Collect classes ──────────────────────────────────────────────────────
    classes = set()
    for el in root.findall(f"{{{OWL}}}Class"):
        about = el.get(f"{{{RDF}}}about", "")
        name  = _local(resolve(about))
        if name:
            classes.add(name)

    # ── Collect named individuals ────────────────────────────────────────────
    for el in root.findall(f"{{{OWL}}}NamedIndividual"):
        about = el.get(f"{{{RDF}}}about", "")
        ind_id = _local(resolve(about))
        if not ind_id:
            continue
        label_el = el.find(f"{{{RDFS}}}label")
        label    = label_el.text if label_el is not None else ind_id
        # get rdf:type
        type_el  = el.find(f"{{{RDF}}}type")
        etype    = "GenericConcept"
        if type_el is not None:
            etype = _local(resolve(type_el.get(f"{{{RDF}}}resource", ""))) or "GenericConcept"
        nodes[ind_id] = {"id": ind_id, "label": label, "ner": etype}

        # inline property assertions
        for child in el:
            tag = _local(child.tag)
            if tag in ("type", "label"):
                continue
            res = child.get(f"{{{RDF}}}resource", "")
            if res:
                obj_id = _local(resolve(res))
                if obj_id:
                    edges.append({"from": ind_id, "to": obj_id, "label": tag})

    # ── Collect rdf:Description blocks (property assertions) ─────────────────
    for el in root.findall(f"{{{RDF}}}Description"):
        about  = el.get(f"{{{RDF}}}about", "")
        s_id   = _local(resolve(about))
        if not s_id:
            continue
        # ensure node exists
        if s_id not in nodes:
            nodes[s_id] = {"id": s_id, "label": s_id, "ner": "GenericConcept"}
        for child in el:
            ns_uri = child.tag.split("}")[0].lstrip("{") if "}" in child.tag else ""
            tag    = _local(child.tag)
            res    = child.get(f"{{{RDF}}}resource", "")
            if res:
                o_id = _local(resolve(res))
                if o_id and o_id != s_id:
                    if o_id not in nodes:
                        nodes[o_id] = {"id": o_id, "label": o_id, "ner": "GenericConcept"}
                    edges.append({"from": s_id, "to": o_id, "label": tag})

    # deduplicate edges
    seen_e = set()
    uniq_edges = []
    for e in edges:
        key = (e["from"], e["to"], e["label"])
        if key not in seen_e:
            seen_e.add(key)
            uniq_edges.append(e)

    return {
        "nodes": list(nodes.values()),
        "edges": uniq_edges,
        "classes": sorted(classes),
        "properties": sorted(props),
    }
