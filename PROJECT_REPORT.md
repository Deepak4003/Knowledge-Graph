# Knowledge Graph Studio — Project Report

---

## 1. Project Overview

Knowledge Graph Studio is a full-stack web application that allows users to build, visualize, and query knowledge graphs from research papers. Users can upload PDF documents, and the system automatically extracts entities and relationships using AI (LLM) or NLP, stores them in a cloud database, and renders an interactive graph visualization in the browser.

---

## 2. Tech Stack

### Backend
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11 | Core runtime |
| Flask | 3.x | Web framework, REST API |
| PyMongo | 4.x | MongoDB driver |
| spaCy | 3.8 | NLP — NER + dependency parsing (fallback extractor) |
| pdfplumber | 0.11 | PDF text extraction |
| Groq SDK | latest | LLM API client (llama-3.3-70b) |
| owlready2 | 0.50 | OWL ontology processing |
| networkx | 3.x | Graph algorithms (shortest path, BFS) |
| python-dotenv | 1.x | Environment variable management |
| Werkzeug | 3.x | File upload handling |

### Frontend
| Technology | Purpose |
|---|---|
| HTML5 / CSS3 / Vanilla JS | UI, no framework |
| vis-network (CDN) | Interactive graph visualization |

### Database
| Technology | Purpose |
|---|---|
| MongoDB Atlas | Primary cloud database (nodes + edges) |
| SQLite | Local fallback if MongoDB is unavailable |

### AI / ML
| Service | Model | Purpose |
|---|---|---|
| Groq API | llama-3.3-70b-versatile | Entity extraction from PDFs, NL query answering |
| spaCy | en_core_web_sm | Fallback NER + SVO triple extraction |

---

## 3. Project Structure

```
research-kg/
├── app.py              → Flask app — all REST API routes
├── database.py         → MongoDB/SQLite abstraction layer
├── ai_extractor.py     → LLM-powered PDF → knowledge graph
├── extractor.py        → spaCy NLP fallback extractor
├── nl_query.py         → Natural language question answering
├── query_engine.py     → Cypher-like query language engine
├── owl_parser.py       → OWL/RDF-XML → graph JSON parser
├── processor.py        → PDF → OWL ontology (owlready2)
├── requirements.txt    → Python dependencies
├── .env                → API keys and DB credentials
├── graph.db            → SQLite fallback database
├── uploads/            → Uploaded PDF files
└── templates/
    └── index.html      → Full frontend SPA
```

---

## 4. Program Flow

### 4.1 Application Startup
```
py -3.11 app.py
    │
    ├── load_dotenv()           → load .env (MONGO_URI, GROQ_API_KEY)
    ├── init_db()               → connect MongoDB Atlas (or SQLite fallback)
    ├── migrate_json_if_needed()→ import legacy graph_db.json if exists
    └── Flask server starts on http://127.0.0.1:5000
```

### 4.2 PDF Upload & AI Extraction Flow
```
User uploads PDF
    │
    ▼
POST /upload
    │
    ├── Save file to /uploads/
    │
    ├── ai_extractor.extract_graph_ai(pdf_path)
    │       │
    │       ├── pdfplumber → extract raw text from all pages
    │       ├── Split text into 3000-char chunks (max 10 chunks)
    │       │
    │       └── For each chunk:
    │               │
    │               ├── Send to Groq API (llama-3.3-70b)
    │               │   with system prompt asking for JSON:
    │               │   { entities: [...], relations: [...] }
    │               │
    │               ├── Parse JSON response
    │               ├── Deduplicate entities and relations
    │               └── Collect all_entities + all_relations
    │
    │       [If Groq fails → fallback to spaCy extractor]
    │
    ├── For each extracted node:
    │       └── insert_node() → MongoDB nodes collection
    │
    ├── For each extracted edge:
    │       └── insert_edge() → MongoDB edges collection
    │
    └── Return { graph, stats, method } → frontend renders graph
```

### 4.3 Natural Language Query Flow
```
User types question in AI tab
    │
    ▼
POST /ask
    │
    ├── load_db() → fetch all nodes + edges from MongoDB
    │
    ├── nl_query.answer_question(question, db)
    │       │
    │       ├── Build compact graph summary (max 150 nodes, 150 edges)
    │       │
    │       ├── Send to Groq API:
    │       │   system: "answer question from graph, return JSON"
    │       │   user:   question + graph summary
    │       │
    │       ├── Parse response:
    │       │   { answer, relevant_node_ids, relevant_edge_ids, confidence }
    │       │
    │       └── Validate node/edge IDs exist in DB
    │
    └── Return answer + relevant node IDs → frontend highlights nodes
```

### 4.4 Manual Node/Edge CRUD Flow
```
User fills Create form → POST /node or POST /edge
    │
    ├── Validate input
    ├── Generate unique ID (next_node_id / next_edge_id)
    ├── insert_node() / insert_edge() → MongoDB
    └── Return updated full graph → re-render vis-network
```

### 4.5 Cypher-like Query Flow
```
User types query in Query tab → POST /query
    │
    ├── query_engine.run_query(q, db)
    │       │
    │       ├── MATCH (n:Person)         → filter nodes by type
    │       ├── MATCH (n)-[r]->(m)       → traverse edges
    │       ├── WHERE / RETURN / ORDER   → filter + project
    │       ├── PATH FROM "A" TO "B"     → BFS shortest path
    │       ├── NEIGHBORS "A"            → direct connections
    │       ├── COUNT (n:Person)         → count nodes/edges
    │       └── STATS                   → graph statistics
    │
    └── Return { columns, rows, graph } → render table + highlight subgraph
```

---

## 5. Database Schema

### 5.1 MongoDB Collections

Database name: `knowledge_graph`

#### Collection: `nodes`
```json
{
  "_id":        "ObjectId (auto)",
  "id":         "string  — unique snake_case identifier  e.g. john_smith",
  "label":      "string  — display name                  e.g. John Smith",
  "type":       "string  — entity type                   e.g. Person",
  "properties": "object  — key-value metadata            e.g. {born: 1879}"
}
```

Entity types: `Person`, `Organization`, `Location`, `Concept`, `Event`, `Technology`, `Method`, `Dataset`, `Metric`, `Date`, `Product`, `Group`, `Node`

#### Collection: `edges`
```json
{
  "_id":        "ObjectId (auto)",
  "id":         "string  — unique edge ID                e.g. e1",
  "from_id":    "string  — source node ID               e.g. john_smith",
  "to_id":      "string  — target node ID               e.g. stanford_university",
  "label":      "string  — relationship type            e.g. AFFILIATED_WITH",
  "properties": "object  — key-value metadata            e.g. {since: 2020}"
}
```

Relationship types (examples): `AFFILIATED_WITH`, `DEVELOPED`, `USES`, `PROPOSES`, `TRAINED_ON`, `COMPARED_WITH`, `PART_OF`, `APPLIED_TO`, `RELATED_TO`

#### MongoDB Indexes
```
nodes.id          → unique index
edges.id          → unique index
edges.(from_id, to_id, label) → compound index (prevents duplicate edges)
```

### 5.2 SQLite Schema (Fallback)

File: `graph.db`

```sql
CREATE TABLE nodes (
    id         TEXT PRIMARY KEY,
    label      TEXT NOT NULL,
    type       TEXT DEFAULT 'Node',
    properties TEXT DEFAULT '{}'    -- JSON string
);

CREATE TABLE edges (
    id         TEXT PRIMARY KEY,
    from_id    TEXT NOT NULL,
    to_id      TEXT NOT NULL,
    label      TEXT NOT NULL,
    properties TEXT DEFAULT '{}'    -- JSON string
);
```

---

## 6. REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Serve frontend SPA |
| GET | `/graph` | Fetch all nodes + edges |
| POST | `/node` | Create a node |
| PUT | `/node/<id>` | Update a node |
| DELETE | `/node/<id>` | Delete a node + its edges |
| POST | `/edge` | Create an edge |
| DELETE | `/edge/<id>` | Delete an edge |
| POST | `/upload` | Upload PDF → AI extract → import graph |
| POST | `/query` | Run Cypher-like query |
| POST | `/ask` | Natural language AI question |
| POST | `/owl/parse` | Parse OWL/RDF-XML → preview graph |
| POST | `/owl/import` | Parse OWL/RDF-XML → import to DB |
| POST | `/clear` | Delete all nodes and edges |

---

## 7. How Data is Stored

### Node ID Generation
```
next_node_id("John Smith")
→ "n{count+1}_{first12chars}"
→ "n5_JohnSmith"
```

### Edge ID Generation
```
next_edge_id()
→ "e{count+1}"
→ "e12"
```

### Duplicate Prevention
- Nodes: `upsert=True` on `id` field — same ID never creates duplicate
- Edges: `edge_key_exists(from_id, to_id, label)` checked before insert — same relationship never duplicated

### Data Flow: PDF → MongoDB
```
PDF text
  → chunked (3000 chars each)
  → Groq LLM extracts JSON {entities, relations}
  → entities → nodes collection (upsert by id)
  → relations → edges collection (insert if not exists)
```

---

## 8. AI Features

### Feature 1: Smart PDF Extraction
- Model: `llama-3.3-70b-versatile` via Groq API
- Input: PDF text split into 3000-char chunks
- Output: Structured JSON with entities and typed relationships
- Fallback: spaCy NER + SVO dependency parsing if Groq unavailable
- Max chunks per PDF: 10 (to control API usage)

### Feature 2: Natural Language Query
- Model: `llama-3.3-70b-versatile` via Groq API
- Input: Plain English question + graph summary (max 150 nodes/edges)
- Output: Natural language answer + list of relevant node IDs
- Frontend: Highlights relevant nodes on graph, dims others
- Confidence levels: high / medium / low

---

## 9. Frontend Architecture

Single-page application in `templates/index.html` (~1000 lines).

### Layout
```
┌─────────────────────────────────────────────────────┐
│  Header (stats + export + clear)                    │
├──────────────┬──────────────────────────┬───────────┤
│  Sidebar     │  Graph Canvas            │  Detail   │
│  ─────────   │  (vis-network)           │  Panel    │
│  + Create    │                          │  (node    │
│  ◉ Nodes     │  Interactive force-      │   info +  │
│  ⌕ Query     │  directed graph          │   edit)   │
│  🤖 AI       │                          │           │
│  📄 PDF      │                          │           │
│  🦉 OWL      │                          │           │
├──────────────┴──────────────────────────┴───────────┤
│  Toolbar (layout selector, edge labels, fit)        │
└─────────────────────────────────────────────────────┘
```

### Graph Rendering
- Library: `vis-network` (standalone UMD build from CDN)
- Physics: `forceAtlas2Based` solver
- Node shapes vary by entity type (Person=ellipse, Org=box, Location=triangle, etc.)
- Node size scales with degree (number of connections)
- Node colors vary by type

---

## 10. Environment Configuration

File: `.env`
```
MONGO_URI=mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/
MONGO_DB=knowledge_graph
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

---

## 11. How to Run

```bash
# Install dependencies
py -3.11 -m pip install -r requirements.txt

# Run the app
py -3.11 app.py

# Open browser
http://127.0.0.1:5000
```

---

## 12. Key Design Decisions

| Decision | Reason |
|---|---|
| MongoDB Atlas as primary DB | Cloud persistence, accessible from anywhere, scales easily |
| SQLite as fallback | App works offline or if MongoDB is down |
| Groq + llama-3.3-70b | Free tier, very fast inference, excellent extraction quality |
| spaCy as fallback extractor | Works offline, no API key needed |
| Chunked PDF processing | Avoids LLM token limits, processes large papers reliably |
| vis-network for graph | Mature library, physics simulation, interactive, no build step needed |
| Vanilla JS frontend | No build toolchain needed, simple deployment |
| Upsert on node insert | Prevents duplicates when same PDF is uploaded twice |
