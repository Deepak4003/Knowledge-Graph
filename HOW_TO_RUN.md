# Knowledge Graph Studio — How to Run

## Prerequisites
- Python 3.10+ installed → https://python.org/downloads
- VS Code installed → https://code.visualstudio.com

---

## Step 1 — Open Project in VS Code

```
File → Open Folder → select the "research-kg" folder
```

Or from terminal:
```bash
code research-kg
```

---

## Step 2 — Open Terminal in VS Code

```
Terminal → New Terminal   (or Ctrl + `)
```

---

## Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs Flask, spaCy, MongoDB driver, PDF parser, and everything else.

---

## Step 4 — Create .env File

Create a file named `.env` in the project root and add:

```
MONGO_URI=mongodb+srv://YOUR_USERNAME:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/
MONGO_DB=knowledge_graph
```

Replace with your own MongoDB Atlas connection string.
Get one free at → https://cloud.mongodb.com

---

## Step 5 — Run the App

```bash
python app.py
```

---

## Step 6 — Open in Browser

```
http://localhost:5000
```

---

## All Commands (Quick Reference)

| Task                        | Command                          |
|-----------------------------|----------------------------------|
| Install dependencies        | pip install -r requirements.txt  |
| Run the app                 | python app.py                    |
| Run with gunicorn (prod)    | gunicorn app:app                 |
| Generate sample PDF         | python make_paper.py             |
| Test query engine           | python test_query.py             |

---

## Project Structure

```
research-kg/
├── app.py              → Flask backend (all API routes)
├── database.py         → MongoDB connection & queries
├── extractor.py        → PDF → graph (spaCy NLP)
├── processor.py        → PDF → OWL ontology (owlready2)
├── owl_parser.py       → OWL/RDF-XML → graph JSON
├── query_engine.py     → Cypher-like query language
├── requirements.txt    → All Python dependencies
├── Procfile            → For deployment (gunicorn)
├── render.yaml         → Render.com deploy config
├── .env                → Your MongoDB credentials (create this)
└── templates/
    └── index.html      → Full frontend UI
```

---

## Features

- Create nodes and relationships manually
- Upload PDF → auto-extract knowledge graph
- Write OWL/RDF-XML ontology in built-in editor
- Query the graph with Cypher-like language
- Visualize graph interactively (zoom, pan, click)
- Data stored in MongoDB Atlas (cloud)

---

## Query Examples (in the Query tab)

```
STATS
MATCH (n)
MATCH (n:Person)
MATCH (n) WHERE n.label CONTAINS "Google"
MATCH (n)-[r]->(m)
MATCH (n)-[r:DISCOVERED]->(m)
MATCH (n:Person)-[r:WON]->(m:Event)
COUNT (n:Person)
PATH FROM "Albert Einstein" TO "Nobel Prize"
NEIGHBORS "Albert Einstein"
```

---

## Deploy to Render (free)

1. Push code to GitHub
2. Go to https://render.com → New Web Service → connect repo
3. Add environment variable: MONGO_URI = your Atlas connection string
4. Deploy — live in ~3 minutes

---

## Troubleshooting

| Problem                        | Fix                                              |
|--------------------------------|--------------------------------------------------|
| ModuleNotFoundError            | Run: pip install -r requirements.txt             |
| MongoDB connection error       | Check your .env file has correct MONGO_URI       |
| spaCy model not found          | Run: python -m spacy download en_core_web_sm     |
| Port 5000 already in use       | Change port in app.py: app.run(port=8000)        |
| PDF gives empty graph          | PDF might be scanned/image-based (no text layer) |
