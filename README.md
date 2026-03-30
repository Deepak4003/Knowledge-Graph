# Research Paper → Knowledge Graph

Converts any research paper PDF into an interactive knowledge graph with OWL ontology export.

## Quick Start

**Windows:**
```
setup.bat
python app.py
```

**Mac/Linux:**
```
bash setup.sh
python3 app.py
```

Then open → http://localhost:5000

## What it does

| Step | Tool | Output |
|------|------|--------|
| PDF text extraction | pdfplumber | Raw text per page |
| Named Entity Recognition | spaCy NER | PERSON, ORG, GPE, LOC, DATE… |
| Relation extraction | spaCy dependency parse | Subject → Verb → Object triples |
| Co-occurrence | sentence-level NER pairs | `related_to` edges |
| OWL Ontology | owlready2 | RDF/XML `.owl` file |
| Graph visualization | vis-network | Interactive force-directed graph |

## Features

- Drag & drop PDF upload
- Interactive graph: zoom, pan, click nodes
- Node shapes & colours by entity type (PERSON=ellipse, ORG=box, GPE=diamond…)
- Click any node → right panel shows all incoming/outgoing relations
- Click relation in sidebar → highlights that pair in graph
- Layout switcher: Force-directed / Hierarchical / Circular
- Edge label font size slider
- Entity search/filter
- Download generated OWL ontology (open in Protégé)

## OWL Ontology Structure

```
ResearchEntity (owl:Class)
  ├── Person
  ├── Organization
  ├── GeopoliticalEntity
  ├── Location
  ├── Date / Time / Event …
  └── GenericConcept

ObjectProperties (one per unique relation verb):
  :uses, :proposes, :related_to, :evaluates …

Named Individuals:
  :bert  rdf:type :Organization ; rdfs:label "BERT"
  :bert  :proposes  :transformer_architecture
```
