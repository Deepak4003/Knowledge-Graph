"""
nl_query.py – Natural Language Query using Groq LLM
Converts plain English questions into graph queries and returns answers.
"""
import os, json, re
from dotenv import load_dotenv
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

SYSTEM_PROMPT = """You are a knowledge graph query assistant.
Given a user question and a knowledge graph (nodes + edges), answer the question.

You will receive:
1. The user's question
2. The graph data as JSON

Your response must be valid JSON in this exact format:
{
  "answer": "A clear, concise natural language answer to the question",
  "relevant_node_ids": ["id1", "id2"],
  "relevant_edge_ids": ["e1", "e2"],
  "confidence": "high|medium|low"
}

Rules:
- answer must be a helpful, human-readable response (1-3 sentences)
- relevant_node_ids: list of node ids that are relevant to the answer
- relevant_edge_ids: list of edge ids that are relevant to the answer
- if the answer is not in the graph, say so clearly in the answer field
- return empty lists if no specific nodes/edges are relevant
- no explanation outside the JSON"""


def _build_graph_summary(db):
    """Build a compact graph representation for the LLM prompt."""
    nodes = db.get("nodes", {})
    edges = db.get("edges", [])

    # limit to avoid token overflow — send max 150 nodes, 150 edges
    node_items = list(nodes.items())[:150]
    edge_items  = edges[:150]

    node_str = "\n".join(
        f'  {{"id":"{nid}","label":"{n["label"]}","type":"{n.get("type","Concept")}"}}'
        for nid, n in node_items
    )
    edge_str = "\n".join(
        f'  {{"id":"{e["id"]}","from":"{e["from"]}","to":"{e["to"]}","label":"{e["label"]}"}}'
        for e in edge_items
    )
    return f"NODES:\n{node_str}\n\nEDGES:\n{edge_str}"


def answer_question(question, db):
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        return {
            "answer": "AI query requires a Groq API key. Please add GROQ_API_KEY to your .env file.",
            "relevant_node_ids": [],
            "relevant_edge_ids": [],
            "confidence": "low"
        }

    nodes = db.get("nodes", {})
    edges = db.get("edges", [])

    if not nodes:
        return {
            "answer": "The knowledge graph is empty. Please upload a PDF or add nodes first.",
            "relevant_node_ids": [],
            "relevant_edge_ids": [],
            "confidence": "low"
        }

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        graph_summary = _build_graph_summary(db)
        user_msg = f"Question: {question}\n\nKnowledge Graph:\n{graph_summary}"

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg}
            ],
            temperature=0.1,
            max_tokens=1024,
        )

        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        result = json.loads(raw)

        # validate node/edge ids exist
        valid_nodes = [nid for nid in result.get("relevant_node_ids", []) if nid in nodes]
        valid_edges = [e["id"] for e in edges if e["id"] in result.get("relevant_edge_ids", [])]

        # build subgraph for highlighting
        sub_nodes = [{"id": nid, **nodes[nid]} for nid in valid_nodes]
        sub_edges = [e for e in edges if e["id"] in valid_edges]

        return {
            "answer":    result.get("answer", "No answer found."),
            "confidence": result.get("confidence", "medium"),
            "relevant_node_ids": valid_nodes,
            "relevant_edge_ids": valid_edges,
            "subgraph": {"nodes": sub_nodes, "edges": sub_edges}
        }

    except Exception as e:
        return {
            "answer": f"Error processing question: {str(e)}",
            "relevant_node_ids": [],
            "relevant_edge_ids": [],
            "confidence": "low"
        }
