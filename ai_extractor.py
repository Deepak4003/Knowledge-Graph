"""
ai_extractor.py – LLM-powered PDF → knowledge graph using Groq
Falls back to spaCy extractor if Groq key is missing or fails.
"""
import os, re, json
import pdfplumber
from dotenv import load_dotenv
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CHUNK_SIZE   = 3000   # chars per chunk sent to LLM
MAX_CHUNKS   = 10     # max chunks to process (avoid huge bills)

SYSTEM_PROMPT = """You are a knowledge graph extraction expert.
Given a text chunk from a research paper, extract entities and relationships.

Return ONLY valid JSON in this exact format:
{
  "entities": [
    {"id": "unique_snake_case_id", "label": "Entity Name", "type": "Person|Organization|Location|Concept|Event|Technology|Method|Dataset|Metric"}
  ],
  "relations": [
    {"from": "entity_id", "relation": "RELATION_TYPE", "to": "entity_id"}
  ]
}

Rules:
- entity id must be lowercase snake_case, max 40 chars
- extract meaningful entities only (no stopwords, no single letters)
- relation types should be uppercase snake_case like USES, PROPOSES, ACHIEVES, TRAINED_ON, COMPARED_WITH, PART_OF, DEVELOPED_BY, APPLIED_TO
- only create relations between entities you extracted in this chunk
- return 5-20 entities and 5-20 relations per chunk
- no explanation, no markdown, just raw JSON"""


def _safe_id(text):
    s = re.sub(r"[^a-zA-Z0-9]", "_", text.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s: s = "entity"
    if s[0].isdigit(): s = "e_" + s
    return s[:40]


def _extract_text(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t: pages.append(t)
    return "\n".join(pages)


def _chunk_text(text, size=CHUNK_SIZE):
    # split on sentence boundaries roughly
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) > size and current:
            chunks.append(current.strip())
            current = s
        else:
            current += " " + s
    if current.strip():
        chunks.append(current.strip())
    return chunks[:MAX_CHUNKS]


def _call_groq(chunk):
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Extract knowledge graph from this text:\n\n{chunk}"}
        ],
        temperature=0.1,
        max_tokens=2048,
    )
    return resp.choices[0].message.content.strip()


def _parse_llm_response(raw):
    # strip markdown code fences if present
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)


def extract_graph_ai(pdf_path):
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        from extractor import extract_graph
        try:
            return extract_graph(pdf_path)
        except Exception as e:
            raise RuntimeError(f"Extraction failed: {e}")

    text = _extract_text(pdf_path)
    if not text.strip():
        return {"nodes": [], "edges": [], "stats": {"nodes": 0, "edges": 0}, "method": "ai"}

    chunks = _chunk_text(text)
    all_entities = {}   # id -> node dict
    all_relations = []
    seen_edges = set()
    errors = 0

    for i, chunk in enumerate(chunks):
        try:
            raw  = _call_groq(chunk)
            data = _parse_llm_response(raw)

            for ent in data.get("entities", []):
                eid   = _safe_id(ent.get("id") or ent.get("label", ""))
                label = ent.get("label", eid).strip()
                etype = ent.get("type", "Concept")
                if eid and label and eid not in all_entities:
                    all_entities[eid] = {"id": eid, "label": label, "type": etype}

            for rel in data.get("relations", []):
                fid = _safe_id(rel.get("from", ""))
                tid = _safe_id(rel.get("to", ""))
                rel_type = rel.get("relation", "RELATED_TO").upper().replace(" ", "_")
                key = (fid, tid, rel_type)
                if fid and tid and fid != tid and key not in seen_edges:
                    seen_edges.add(key)
                    all_relations.append({"from": fid, "to": tid, "label": rel_type})

        except Exception as e:
            errors += 1
            print(f"[AI extractor] chunk {i+1} error: {e}")
            continue

    # if too many errors or no results, fallback to spaCy
    if errors == len(chunks) or (len(all_entities) == 0 and len(all_relations) == 0):
        from extractor import extract_graph
        result = extract_graph(pdf_path)
        result["method"] = "spacy_fallback"
        return result

    # keep only nodes referenced by edges
    used = {e["from"] for e in all_relations} | {e["to"] for e in all_relations}
    # also add isolated entities that are important
    node_list = [n for n in all_entities.values() if n["id"] in used]

    return {
        "nodes": node_list,
        "edges": all_relations,
        "stats": {"nodes": len(node_list), "edges": len(all_relations)},
        "method": "ai",
        "chunks_processed": len(chunks) - errors,
    }
