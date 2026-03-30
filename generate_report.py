from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics import renderPDF
import datetime

# ── Colors ────────────────────────────────────────────────────────────────────
C_BG       = colors.HexColor("#0f1117")
C_ACCENT   = colors.HexColor("#00d4aa")
C_ACCENT2  = colors.HexColor("#7c83fd")
C_DARK     = colors.HexColor("#161b2e")
C_BORDER   = colors.HexColor("#2a3050")
C_TEXT     = colors.HexColor("#1a1a2e")
C_MUTED    = colors.HexColor("#64748b")
C_WHITE    = colors.white
C_YELLOW   = colors.HexColor("#f0a500")
C_RED      = colors.HexColor("#f87171")
C_GREEN    = colors.HexColor("#4ade80")
C_PURPLE   = colors.HexColor("#7c83fd")
C_TEAL     = colors.HexColor("#00d4aa")
C_ORANGE   = colors.HexColor("#ff8c69")

W, H = A4

# ── Styles ────────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, **kw)

sTitle    = S("sTitle",    fontSize=28, textColor=C_ACCENT,  alignment=TA_CENTER, fontName="Helvetica-Bold", spaceAfter=6)
sSubtitle = S("sSubtitle", fontSize=13, textColor=C_MUTED,   alignment=TA_CENTER, fontName="Helvetica",      spaceAfter=4)
sH1       = S("sH1",       fontSize=16, textColor=C_ACCENT,  fontName="Helvetica-Bold", spaceBefore=18, spaceAfter=8, borderPad=4)
sH2       = S("sH2",       fontSize=13, textColor=C_ACCENT2, fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=6)
sH3       = S("sH3",       fontSize=11, textColor=C_TEXT,    fontName="Helvetica-Bold", spaceBefore=8,  spaceAfter=4)
sBody     = S("sBody",     fontSize=9.5,textColor=C_TEXT,    fontName="Helvetica",      spaceAfter=5,   leading=15, alignment=TA_JUSTIFY)
sCode     = S("sCode",     fontSize=8,  textColor=colors.HexColor("#1e3a5f"), fontName="Courier",
               backColor=colors.HexColor("#f0f4ff"), borderPad=6, spaceAfter=6, leading=12)
sBullet   = S("sBullet",   fontSize=9.5,textColor=C_TEXT,    fontName="Helvetica", spaceAfter=3, leading=14, leftIndent=14, bulletIndent=4)
sCaption  = S("sCaption",  fontSize=8,  textColor=C_MUTED,   fontName="Helvetica-Oblique", alignment=TA_CENTER, spaceAfter=8)
sTableHdr = S("sTableHdr", fontSize=9,  textColor=C_WHITE,   fontName="Helvetica-Bold", alignment=TA_CENTER)
sTableCell= S("sTableCell",fontSize=8.5,textColor=C_TEXT,    fontName="Helvetica", leading=12)

# ── Helper flowables ──────────────────────────────────────────────────────────
def HR(color=C_ACCENT, thickness=1.5):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=8, spaceBefore=4)

def SP(h=8):
    return Spacer(1, h)

def P(text, style=None):
    return Paragraph(text, style or sBody)

def bullet(text):
    return Paragraph(f"• {text}", sBullet)

def code(text):
    return Paragraph(text.replace("\n","<br/>").replace(" ","&nbsp;"), sCode)

def tbl(data, col_widths, hdr_rows=1, row_colors=None):
    t = Table(data, colWidths=col_widths)
    style = [
        ("BACKGROUND",  (0,0), (-1, hdr_rows-1), C_DARK),
        ("TEXTCOLOR",   (0,0), (-1, hdr_rows-1), C_WHITE),
        ("FONTNAME",    (0,0), (-1, hdr_rows-1), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1, hdr_rows-1), 9),
        ("ALIGN",       (0,0), (-1,-1), "LEFT"),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,hdr_rows),(-1,-1),[colors.HexColor("#f8faff"), colors.white]),
        ("GRID",        (0,0), (-1,-1), 0.4, C_BORDER),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING",(0,0), (-1,-1), 7),
        ("FONTSIZE",    (0,hdr_rows),(-1,-1), 8.5),
    ]
    if row_colors:
        for i, c in row_colors:
            style.append(("BACKGROUND",(0,i),(-1,i), c))
    t.setStyle(TableStyle(style))
    return t

# ── Diagram: Architecture ─────────────────────────────────────────────────────
class ArchDiagram(Flowable):
    def __init__(self, w=500, h=220):
        self.w, self.h = w, h
    def wrap(self, *args): return self.w, self.h
    def draw(self):
        c = self.canv
        boxes = [
            (20,  80, 100, 50, C_ACCENT2,  "Browser\n(vis-network\nHTML/JS/CSS)"),
            (170, 80, 100, 50, C_TEAL,     "Flask\nBackend\n(app.py)"),
            (320, 80, 100, 50, C_YELLOW,   "MongoDB\nAtlas\n(Cloud DB)"),
            (170,170, 100, 35, C_ORANGE,   "SQLite\n(Fallback)"),
            (20,  10, 100, 40, C_PURPLE,   "Groq LLM\n(llama-3.3-70b)"),
            (320, 10, 100, 40, C_RED,      "spaCy NLP\n(Fallback)"),
        ]
        for x, y, bw, bh, col, label in boxes:
            c.setFillColor(col)
            c.setStrokeColor(colors.white)
            c.roundRect(x, y, bw, bh, 8, fill=1, stroke=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 7.5)
            lines = label.split("\n")
            for i, line in enumerate(lines):
                c.drawCentredString(x + bw/2, y + bh - 14 - i*11, line)

        # arrows
        arrows = [
            (120,105,170,105,"REST API"),
            (270,105,320,105,"PyMongo"),
            (220,130,220,170,"fallback"),
            (120, 30,170, 80,"AI Extract\n/ NL Query"),
            (320, 50,320, 80,"NLP\nFallback"),
        ]
        c.setStrokeColor(C_MUTED)
        c.setFillColor(C_MUTED)
        c.setFont("Helvetica", 6.5)
        for x1,y1,x2,y2,lbl in arrows:
            c.setLineWidth(1.2)
            c.line(x1,y1,x2,y2)
            # arrowhead
            dx,dy = x2-x1, y2-y1
            import math
            length = math.sqrt(dx*dx+dy*dy) or 1
            ux,uy = dx/length, dy/length
            ax,ay = x2-ux*8, y2-uy*8
            c.setFillColor(C_MUTED)
            p = c.beginPath()
            p.moveTo(x2,y2)
            p.lineTo(ax-uy*4, ay+ux*4)
            p.lineTo(ax+uy*4, ay-ux*4)
            p.close()
            c.drawPath(p, fill=1)
            mx,my = (x1+x2)/2, (y1+y2)/2
            c.setFillColor(C_TEXT)
            c.drawCentredString(mx+10, my+3, lbl.split("\n")[0])

# ── Diagram: PDF Flow ─────────────────────────────────────────────────────────
class PDFFlowDiagram(Flowable):
    def __init__(self, w=500, h=80):
        self.w, self.h = w, h
    def wrap(self, *args): return self.w, self.h
    def draw(self):
        c = self.canv
        steps = [
            (C_PURPLE,  "PDF Upload"),
            (C_TEAL,    "Text Extract\n(pdfplumber)"),
            (C_YELLOW,  "Chunk Text\n(3000 chars)"),
            (C_ORANGE,  "Groq LLM\n(llama-3.3-70b)"),
            (C_ACCENT2, "Parse JSON\nEntities+Relations"),
            (C_GREEN,   "Store in\nMongoDB"),
        ]
        bw, bh, gap = 68, 55, 12
        total = len(steps)*(bw+gap)-gap
        sx = (self.w - total)/2
        import math
        for i,(col,label) in enumerate(steps):
            x = sx + i*(bw+gap)
            c.setFillColor(col)
            c.setStrokeColor(colors.white)
            c.roundRect(x, 10, bw, bh, 6, fill=1, stroke=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 7)
            lines = label.split("\n")
            for j,line in enumerate(lines):
                c.drawCentredString(x+bw/2, 10+bh-16-j*10, line)
            if i < total-1:
                ax1 = x+bw+2; ay = 10+bh/2
                ax2 = x+bw+gap-2
                c.setStrokeColor(C_MUTED)
                c.setFillColor(C_MUTED)
                c.setLineWidth(1.5)
                c.line(ax1,ay,ax2,ay)
                p = c.beginPath()
                p.moveTo(ax2,ay); p.lineTo(ax2-6,ay-4); p.lineTo(ax2-6,ay+4); p.close()
                c.drawPath(p,fill=1)

# ── Diagram: DB Schema ────────────────────────────────────────────────────────
class DBSchemaDiagram(Flowable):
    def __init__(self, w=500, h=160):
        self.w, self.h = w, h
    def wrap(self, *args): return self.w, self.h
    def draw(self):
        c = self.canv
        # nodes table
        def draw_table(x, y, title, fields, col):
            tw, rh = 180, 18
            c.setFillColor(col); c.setStrokeColor(colors.white)
            c.roundRect(x, y, tw, rh+4, 4, fill=1, stroke=0)
            c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(x+tw/2, y+7, title)
            c.setStrokeColor(C_BORDER); c.setLineWidth(0.5)
            for i,(fname,ftype,pk) in enumerate(fields):
                fy = y - (i+1)*rh
                bg = colors.HexColor("#f0f4ff") if i%2==0 else colors.white
                c.setFillColor(bg); c.rect(x, fy, tw, rh, fill=1, stroke=0)
                c.setStrokeColor(C_BORDER); c.rect(x, fy, tw, rh, fill=0, stroke=1)
                c.setFillColor(C_TEXT if not pk else col)
                c.setFont("Helvetica-Bold" if pk else "Helvetica", 8)
                c.drawString(x+6, fy+5, fname)
                c.setFillColor(C_MUTED); c.setFont("Helvetica", 7.5)
                c.drawRightString(x+tw-6, fy+5, ftype)
            c.setStrokeColor(C_BORDER); c.setLineWidth(1)
            c.rect(x, y-(len(fields))*rh, tw, rh*len(fields), fill=0, stroke=1)

        nodes_fields = [
            ("_id",        "ObjectId (auto)", False),
            ("id",         "String (unique)",  True),
            ("label",      "String",           False),
            ("type",       "String",           False),
            ("properties", "Object {}",        False),
        ]
        edges_fields = [
            ("_id",        "ObjectId (auto)", False),
            ("id",         "String (unique)",  True),
            ("from_id",    "String → nodes.id",True),
            ("to_id",      "String → nodes.id",True),
            ("label",      "String",           False),
            ("properties", "Object {}",        False),
        ]
        draw_table(30,  self.h-10, "nodes",  nodes_fields,  C_TEAL)
        draw_table(290, self.h-10, "edges",  edges_fields,  C_ACCENT2)

        # relationship arrow
        c.setStrokeColor(C_MUTED); c.setLineWidth(1.2)
        c.line(210, self.h-60, 290, self.h-60)
        c.line(210, self.h-78, 290, self.h-78)
        c.setFillColor(C_MUTED)
        for ay in [self.h-60, self.h-78]:
            p = c.beginPath()
            p.moveTo(290,ay); p.lineTo(284,ay-4); p.lineTo(284,ay+4); p.close()
            c.drawPath(p,fill=1)
        c.setFont("Helvetica", 7); c.setFillColor(C_MUTED)
        c.drawCentredString(250, self.h-55, "from_id")
        c.drawCentredString(250, self.h-73, "to_id")

# ── Diagram: NL Query Flow ────────────────────────────────────────────────────
class NLQueryDiagram(Flowable):
    def __init__(self, w=500, h=70):
        self.w, self.h = w, h
    def wrap(self, *args): return self.w, self.h
    def draw(self):
        c = self.canv
        steps = [
            (C_PURPLE,  "User Question\n(plain English)"),
            (C_TEAL,    "Load Graph\nfrom MongoDB"),
            (C_ORANGE,  "Groq LLM\n(llama-3.3-70b)"),
            (C_ACCENT2, "Parse Answer\n+ Node IDs"),
            (C_GREEN,   "Highlight\nGraph Nodes"),
        ]
        bw, bh, gap = 78, 55, 12
        total = len(steps)*(bw+gap)-gap
        sx = (self.w - total)/2
        for i,(col,label) in enumerate(steps):
            x = sx + i*(bw+gap)
            c.setFillColor(col); c.setStrokeColor(colors.white)
            c.roundRect(x, 8, bw, bh, 6, fill=1, stroke=1)
            c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 7)
            lines = label.split("\n")
            for j,line in enumerate(lines):
                c.drawCentredString(x+bw/2, 8+bh-16-j*10, line)
            if i < len(steps)-1:
                ax1=x+bw+2; ay=8+bh/2; ax2=x+bw+gap-2
                c.setStrokeColor(C_MUTED); c.setFillColor(C_MUTED); c.setLineWidth(1.5)
                c.line(ax1,ay,ax2,ay)
                p=c.beginPath(); p.moveTo(ax2,ay); p.lineTo(ax2-6,ay-4); p.lineTo(ax2-6,ay+4); p.close()
                c.drawPath(p,fill=1)

# ── Cover Page ────────────────────────────────────────────────────────────────
def cover_page():
    elems = []
    elems.append(SP(60))
    # big colored title block
    d = Drawing(500, 120)
    d.add(Rect(0, 0, 500, 120, fillColor=C_DARK, strokeColor=C_ACCENT, strokeWidth=2, rx=12, ry=12))
    d.add(String(250, 80, "Knowledge Graph Studio", fontSize=26, fillColor=C_ACCENT,
                 fontName="Helvetica-Bold", textAnchor="middle"))
    d.add(String(250, 52, "Project Report", fontSize=16, fillColor=C_ACCENT2,
                 fontName="Helvetica", textAnchor="middle"))
    d.add(String(250, 28, "AI-Powered Research Paper Knowledge Graph Builder",
                 fontSize=10, fillColor=C_MUTED, fontName="Helvetica", textAnchor="middle"))
    elems.append(d)
    elems.append(SP(30))

    info = [
        ["Project",   "Knowledge Graph Studio"],
        ["Version",   "2.0 (AI Enhanced)"],
        ["Backend",   "Python 3.11 + Flask"],
        ["Database",  "MongoDB Atlas + SQLite Fallback"],
        ["AI Model",  "Groq llama-3.3-70b-versatile"],
        ["Frontend",  "HTML5 + vis-network"],
        ["Date",      datetime.date.today().strftime("%B %d, %Y")],
    ]
    t = tbl(
        [[P(k, S("k", fontSize=9, fontName="Helvetica-Bold", textColor=C_ACCENT2)),
          P(v, S("v", fontSize=9, fontName="Helvetica", textColor=C_TEXT))]
         for k,v in info],
        [120, 280]
    )
    elems.append(t)
    elems.append(PageBreak())
    return elems

# ── Section 1: Overview ───────────────────────────────────────────────────────
def section_overview():
    e = []
    e.append(P("1. Project Overview", sH1)); e.append(HR())
    e.append(P("""Knowledge Graph Studio is a full-stack web application that enables users to build,
    visualize, and query knowledge graphs from research papers. Users upload PDF documents and the
    system automatically extracts entities and relationships using AI (Groq LLM) or NLP (spaCy),
    stores them in MongoDB Atlas, and renders an interactive force-directed graph in the browser."""))
    e.append(SP(8))
    e.append(P("Key Capabilities", sH2))
    for cap in [
        "AI-powered entity & relationship extraction from PDF research papers",
        "Natural language querying — ask plain English questions about your graph",
        "Manual node and edge creation with custom properties",
        "Cypher-like query language (MATCH, PATH, NEIGHBORS, STATS)",
        "OWL/RDF-XML ontology import and visualization",
        "Cloud persistence via MongoDB Atlas with SQLite offline fallback",
        "Interactive graph visualization with zoom, pan, physics simulation",
    ]:
        e.append(bullet(cap))
    return e

# ── Section 2: Tech Stack ─────────────────────────────────────────────────────
def section_techstack():
    e = []
    e.append(P("2. Technology Stack", sH1)); e.append(HR())

    e.append(P("Backend", sH2))
    data = [
        [P("Technology",sTableHdr), P("Version",sTableHdr), P("Purpose",sTableHdr)],
        ["Python",       "3.11",    "Core runtime — chosen for LLM/NLP library compatibility"],
        ["Flask",        "3.x",     "Lightweight web framework, REST API routing"],
        ["PyMongo",      "4.x",     "MongoDB driver with Atlas cloud connection"],
        ["spaCy",        "3.8",     "NLP — Named Entity Recognition + dependency parsing"],
        ["pdfplumber",   "0.11",    "PDF text extraction (handles multi-page, tables)"],
        ["Groq SDK",     "latest",  "LLM API client for llama-3.3-70b-versatile"],
        ["owlready2",    "0.50",    "OWL ontology processing and RDF/XML parsing"],
        ["networkx",     "3.x",     "Graph algorithms — BFS shortest path"],
        ["python-dotenv","1.x",     "Environment variable management (.env file)"],
        ["Werkzeug",     "3.x",     "Secure file upload handling"],
    ]
    e.append(tbl(data, [100,60,280]))
    e.append(SP(10))

    e.append(P("Frontend", sH2))
    data2 = [
        [P("Technology",sTableHdr), P("Purpose",sTableHdr)],
        ["HTML5 / CSS3 / Vanilla JS", "Single-page application UI — no build toolchain needed"],
        ["vis-network (CDN)",         "Interactive graph visualization with physics simulation"],
    ]
    e.append(tbl(data2, [180,260]))
    e.append(SP(10))

    e.append(P("Database & AI", sH2))
    data3 = [
        [P("Service",sTableHdr), P("Details",sTableHdr), P("Purpose",sTableHdr)],
        ["MongoDB Atlas",  "Cloud NoSQL (Free M0 tier)",       "Primary persistent storage"],
        ["SQLite",         "Local file (graph.db)",            "Offline fallback database"],
        ["Groq API",       "llama-3.3-70b-versatile",          "PDF extraction + NL query answering"],
        ["spaCy",          "en_core_web_sm",                   "Fallback NER when Groq unavailable"],
    ]
    e.append(tbl(data3, [110,150,180]))
    return e

# ── Section 3: Architecture ───────────────────────────────────────────────────
def section_architecture():
    e = []
    e.append(P("3. System Architecture", sH1)); e.append(HR())
    e.append(P("""The application follows a classic three-tier architecture: a browser-based frontend,
    a Python/Flask backend, and a cloud database. The AI layer (Groq) sits between the backend
    and the data pipeline, enhancing extraction and query capabilities."""))
    e.append(SP(10))
    e.append(P("Architecture Diagram", sH2))
    e.append(ArchDiagram(500, 230))
    e.append(P("Figure 1: System Architecture — Component Interaction", sCaption))
    e.append(SP(10))

    e.append(P("Project File Structure", sH2))
    e.append(code(
"research-kg/\n"
"├── app.py           → Flask app — all REST API routes\n"
"├── database.py      → MongoDB / SQLite abstraction layer\n"
"├── ai_extractor.py  → LLM-powered PDF → knowledge graph\n"
"├── extractor.py     → spaCy NLP fallback extractor\n"
"├── nl_query.py      → Natural language question answering\n"
"├── query_engine.py  → Cypher-like query language engine\n"
"├── owl_parser.py    → OWL/RDF-XML → graph JSON parser\n"
"├── processor.py     → PDF → OWL ontology (owlready2)\n"
"├── requirements.txt → Python dependencies\n"
"├── .env             → API keys and DB credentials\n"
"├── graph.db         → SQLite fallback database\n"
"├── uploads/         → Uploaded PDF files\n"
"└── templates/\n"
"    └── index.html   → Full frontend SPA (~1000 lines)"
    ))
    return e

# ── Section 4: Program Flow ───────────────────────────────────────────────────
def section_flow():
    e = []
    e.append(P("4. Program Flow", sH1)); e.append(HR())

    e.append(P("4.1  Application Startup", sH2))
    e.append(code(
"py -3.11 app.py\n"
"  ├── load_dotenv()            → load .env (MONGO_URI, GROQ_API_KEY)\n"
"  ├── init_db()                → connect MongoDB Atlas (or SQLite fallback)\n"
"  ├── migrate_json_if_needed() → import legacy graph_db.json if exists\n"
"  └── Flask server starts on http://127.0.0.1:5000"
    ))

    e.append(P("4.2  PDF Upload & AI Extraction", sH2))
    e.append(PDFFlowDiagram(500, 80))
    e.append(P("Figure 2: PDF to Knowledge Graph — AI Extraction Pipeline", sCaption))
    e.append(SP(6))
    e.append(code(
"POST /upload\n"
"  ├── Save file to /uploads/\n"
"  ├── ai_extractor.extract_graph_ai(pdf_path)\n"
"  │     ├── pdfplumber  → extract raw text from all pages\n"
"  │     ├── Split text into 3000-char chunks (max 10 chunks)\n"
"  │     └── For each chunk:\n"
"  │           ├── Send to Groq API (llama-3.3-70b)\n"
"  │           ├── Receive JSON: { entities:[...], relations:[...] }\n"
"  │           └── Deduplicate + collect all entities & relations\n"
"  │     [If Groq fails → fallback to spaCy NER + SVO parsing]\n"
"  ├── insert_node() for each entity  → MongoDB nodes collection\n"
"  ├── insert_edge() for each relation → MongoDB edges collection\n"
"  └── Return { graph, stats, method } → frontend renders graph"
    ))

    e.append(P("4.3  Natural Language Query", sH2))
    e.append(NLQueryDiagram(500, 75))
    e.append(P("Figure 3: Natural Language Query Flow", sCaption))
    e.append(SP(6))
    e.append(code(
"POST /ask\n"
"  ├── load_db()  → fetch all nodes + edges from MongoDB\n"
"  ├── nl_query.answer_question(question, db)\n"
"  │     ├── Build compact graph summary (max 150 nodes, 150 edges)\n"
"  │     ├── Send to Groq: question + graph summary\n"
"  │     └── Parse: { answer, relevant_node_ids, confidence }\n"
"  └── Return answer + node IDs → frontend highlights relevant nodes"
    ))

    e.append(P("4.4  Cypher-like Query Engine", sH2))
    e.append(P("The built-in query engine supports a subset of Cypher syntax:"))
    data = [
        [P("Query",sTableHdr), P("Description",sTableHdr)],
        ["STATS",                              "Graph statistics (node/edge counts by type)"],
        ['MATCH (n:Person)',                   "Filter nodes by entity type"],
        ['MATCH (n) WHERE n.label CONTAINS "X"',"Search nodes by label"],
        ['MATCH (n)-[r:USES]->(m)',            "Traverse edges by relationship type"],
        ['PATH FROM "A" TO "B"',               "BFS shortest path between two nodes"],
        ['NEIGHBORS "Einstein"',               "All direct connections of a node"],
        ['COUNT (n:Person)',                   "Count nodes or edges matching a pattern"],
    ]
    e.append(tbl(data, [190,250]))
    return e

# ── Section 5: Database Schema ────────────────────────────────────────────────
def section_database():
    e = []
    e.append(P("5. Database Schema", sH1)); e.append(HR())
    e.append(P("""The application uses MongoDB Atlas as the primary database with two collections:
    <b>nodes</b> and <b>edges</b>. SQLite is used as an automatic fallback when MongoDB is unavailable."""))
    e.append(SP(10))

    e.append(P("5.1  MongoDB Collections Schema", sH2))
    e.append(DBSchemaDiagram(500, 160))
    e.append(P("Figure 4: MongoDB Collections — nodes and edges with relationship", sCaption))
    e.append(SP(8))

    e.append(P("nodes Collection", sH3))
    data = [
        [P("Field",sTableHdr),      P("Type",sTableHdr),       P("Description",sTableHdr)],
        ["_id",        "ObjectId",  "Auto-generated MongoDB primary key"],
        ["id",         "String",    "Unique snake_case identifier  e.g. john_smith  (indexed)"],
        ["label",      "String",    "Human-readable display name  e.g. John Smith"],
        ["type",       "String",    "Entity type: Person | Organization | Location | Concept | ..."],
        ["properties", "Object",    "Key-value metadata  e.g. { born: 1879, field: Physics }"],
    ]
    e.append(tbl(data, [80,80,280], row_colors=[(1, colors.HexColor("#e8fff8"))]))
    e.append(SP(8))

    e.append(P("edges Collection", sH3))
    data2 = [
        [P("Field",sTableHdr),      P("Type",sTableHdr),       P("Description",sTableHdr)],
        ["_id",        "ObjectId",  "Auto-generated MongoDB primary key"],
        ["id",         "String",    "Unique edge ID  e.g. e1, e2  (indexed)"],
        ["from_id",    "String",    "Source node ID — references nodes.id"],
        ["to_id",      "String",    "Target node ID — references nodes.id"],
        ["label",      "String",    "Relationship type  e.g. AFFILIATED_WITH, DEVELOPED, USES"],
        ["properties", "Object",    "Key-value metadata  e.g. { since: 2020 }"],
    ]
    e.append(tbl(data2, [80,80,280], row_colors=[(1, colors.HexColor("#eef0ff"))]))
    e.append(SP(8))

    e.append(P("MongoDB Indexes", sH3))
    data3 = [
        [P("Collection",sTableHdr), P("Index",sTableHdr), P("Type",sTableHdr)],
        ["nodes", "id",                          "Unique"],
        ["edges", "id",                          "Unique"],
        ["edges", "(from_id, to_id, label)",     "Compound — prevents duplicate edges"],
    ]
    e.append(tbl(data3, [100,200,140]))
    e.append(SP(10))

    e.append(P("5.2  SQLite Schema (Fallback)", sH2))
    e.append(code(
"CREATE TABLE nodes (\n"
"    id         TEXT PRIMARY KEY,\n"
"    label      TEXT NOT NULL,\n"
"    type       TEXT DEFAULT 'Node',\n"
"    properties TEXT DEFAULT '{}'   -- stored as JSON string\n"
");\n\n"
"CREATE TABLE edges (\n"
"    id         TEXT PRIMARY KEY,\n"
"    from_id    TEXT NOT NULL,\n"
"    to_id      TEXT NOT NULL,\n"
"    label      TEXT NOT NULL,\n"
"    properties TEXT DEFAULT '{}'   -- stored as JSON string\n"
");"
    ))

    e.append(P("5.3  Entity Types Supported", sH2))
    types = [
        ["Person","Organization","Location","Concept","Event"],
        ["Technology","Method","Dataset","Metric","Date"],
        ["Product","Group","Node","Facility","Law"],
    ]
    data4 = [[P(t, S("t",fontSize=8.5,fontName="Helvetica",textColor=C_TEXT)) for t in row] for row in types]
    t4 = Table(data4, colWidths=[88]*5)
    colors_list = [C_TEAL, C_ACCENT2, C_ORANGE, C_PURPLE, C_YELLOW,
                   C_RED, C_GREEN, C_ACCENT, C_MUTED, C_TEAL,
                   C_ACCENT2, C_ORANGE, C_PURPLE, C_YELLOW, C_RED]
    style4 = []
    for i,row in enumerate(types):
        for j,_ in enumerate(row):
            idx = i*5+j
            style4.append(("BACKGROUND",(j,i),(j,i), colors_list[idx % len(colors_list)]))
            style4.append(("TEXTCOLOR",(j,i),(j,i), colors.white))
            style4.append(("FONTNAME",(j,i),(j,i),"Helvetica-Bold"))
    style4 += [("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
               ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
               ("GRID",(0,0),(-1,-1),0.5,colors.white),("ROUNDEDCORNERS",[4,4,4,4])]
    t4.setStyle(TableStyle(style4))
    e.append(t4)
    return e

# ── Section 6: API Endpoints ──────────────────────────────────────────────────
def section_api():
    e = []
    e.append(P("6. REST API Endpoints", sH1)); e.append(HR())
    data = [
        [P("Method",sTableHdr), P("Endpoint",sTableHdr), P("Description",sTableHdr)],
        ["GET",    "/",              "Serve frontend single-page application"],
        ["GET",    "/graph",         "Fetch all nodes + edges for visualization"],
        ["POST",   "/node",          "Create a new node with label, type, properties"],
        ["PUT",    "/node/<id>",     "Update node label, type, or properties"],
        ["DELETE", "/node/<id>",     "Delete node and all its connected edges"],
        ["POST",   "/edge",          "Create a directed edge between two nodes"],
        ["DELETE", "/edge/<id>",     "Delete a specific edge by ID"],
        ["POST",   "/upload",        "Upload PDF → AI extract entities → import to graph"],
        ["POST",   "/query",         "Run Cypher-like query against the graph"],
        ["POST",   "/ask",           "Natural language AI question about the graph"],
        ["POST",   "/owl/parse",     "Parse OWL/RDF-XML → preview graph (no save)"],
        ["POST",   "/owl/import",    "Parse OWL/RDF-XML → import nodes+edges to DB"],
        ["POST",   "/clear",         "Delete all nodes and edges from the database"],
    ]
    method_colors = {
        "GET":    colors.HexColor("#e8fff8"),
        "POST":   colors.HexColor("#eef0ff"),
        "PUT":    colors.HexColor("#fff8e8"),
        "DELETE": colors.HexColor("#fff0f0"),
    }
    row_c = [(i+1, method_colors.get(row[0], colors.white)) for i,row in enumerate(data[1:])]
    e.append(tbl(data, [55,130,255], row_colors=row_c))
    return e

# ── Section 7: AI Features ────────────────────────────────────────────────────
def section_ai():
    e = []
    e.append(P("7. AI Features", sH1)); e.append(HR())

    e.append(P("7.1  Smart PDF Extraction", sH2))
    e.append(P("""The AI extractor uses Groq's llama-3.3-70b-versatile model to extract structured
    knowledge from research papers. Unlike traditional NLP which relies on grammar rules, the LLM
    understands context and domain-specific terminology."""))
    e.append(SP(6))
    data = [
        [P("Parameter",sTableHdr), P("Value",sTableHdr)],
        ["Model",           "llama-3.3-70b-versatile (Groq)"],
        ["Chunk size",      "3,000 characters per chunk"],
        ["Max chunks",      "10 per PDF (controls API usage)"],
        ["Temperature",     "0.1 (deterministic, factual output)"],
        ["Max tokens",      "2,048 per chunk response"],
        ["Output format",   "JSON: { entities: [...], relations: [...] }"],
        ["Fallback",        "spaCy NER + SVO dependency parsing"],
    ]
    e.append(tbl(data, [140,300]))
    e.append(SP(10))

    e.append(P("7.2  Natural Language Query", sH2))
    e.append(P("""Users can ask plain English questions about their knowledge graph. The LLM receives
    the question along with a compact graph summary and returns a natural language answer plus
    the IDs of relevant nodes, which are then highlighted on the visualization."""))
    e.append(SP(6))
    data2 = [
        [P("Example Question",sTableHdr), P("What AI Does",sTableHdr)],
        ["Who are the key researchers?",      "Finds Person nodes, returns names + highlights them"],
        ["What methods were proposed?",       "Finds Method/Technology nodes and their relations"],
        ["How is BERT related to Transformers?","Traces path between two concept nodes"],
        ["What datasets were used?",          "Finds Dataset nodes and TRAINED_ON edges"],
    ]
    e.append(tbl(data2, [200,240]))
    return e

# ── Section 8: How to Run ─────────────────────────────────────────────────────
def section_run():
    e = []
    e.append(P("8. How to Run", sH1)); e.append(HR())
    e.append(P("Prerequisites", sH2))
    for req in ["Python 3.11 (required — 3.14 has TLS incompatibility with MongoDB Atlas)",
                "MongoDB Atlas account (free tier at cloud.mongodb.com)",
                "Groq API key (free at console.groq.com)"]:
        e.append(bullet(req))
    e.append(SP(8))
    e.append(P("Setup & Run", sH2))
    e.append(code(
"# 1. Install dependencies\n"
"py -3.11 -m pip install -r requirements.txt\n\n"
"# 2. Configure .env file\n"
"MONGO_URI=mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/\n"
"MONGO_DB=knowledge_graph\n"
"GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx\n\n"
"# 3. Run the application\n"
"py -3.11 app.py\n\n"
"# 4. Open in browser\n"
"http://127.0.0.1:5000"
    ))
    e.append(SP(8))
    e.append(P("Troubleshooting", sH2))
    data = [
        [P("Problem",sTableHdr), P("Fix",sTableHdr)],
        ["MongoDB SSL error",         "Use Python 3.11 (not 3.14). Add tlsInsecure=True in database.py"],
        ["ModuleNotFoundError",       "Run: py -3.11 -m pip install -r requirements.txt"],
        ["spaCy model not found",     "Run: py -3.11 -m spacy download en_core_web_sm"],
        ["Old data after Clear All",  "Hard refresh browser: Ctrl+Shift+R"],
        ["PDF gives empty graph",     "PDF may be image-based (no text layer). Try a different PDF"],
        ["Groq API error",            "Check GROQ_API_KEY in .env. Get free key at console.groq.com"],
    ]
    e.append(tbl(data, [160,280]))
    return e

# ── Section 9: Design Decisions ───────────────────────────────────────────────
def section_design():
    e = []
    e.append(P("9. Key Design Decisions", sH1)); e.append(HR())
    data = [
        [P("Decision",sTableHdr), P("Reason",sTableHdr)],
        ["MongoDB Atlas as primary DB",    "Cloud persistence, accessible anywhere, free tier available"],
        ["SQLite as fallback",             "App works offline or if MongoDB is down — zero config"],
        ["Groq + llama-3.3-70b",          "Free tier, very fast inference, excellent extraction quality"],
        ["spaCy as fallback extractor",    "Works offline, no API key needed, handles basic NER well"],
        ["Chunked PDF processing",         "Avoids LLM token limits, processes large papers reliably"],
        ["vis-network for graph",          "Mature library, physics simulation, interactive, CDN delivery"],
        ["Vanilla JS frontend",            "No build toolchain needed, simple deployment, fast load"],
        ["Upsert on node insert",          "Prevents duplicates when same PDF is uploaded twice"],
        ["Python 3.11 requirement",        "3.14 has TLS incompatibility with MongoDB Atlas SSL"],
        ["tlsInsecure=True for MongoDB",   "Bypasses strict TLS validation that fails on some networks"],
    ]
    e.append(tbl(data, [180,260]))
    return e

# ── Build PDF ─────────────────────────────────────────────────────────────────
def build_pdf(filename="Knowledge_Graph_Studio_Report.pdf"):
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="Knowledge Graph Studio — Project Report",
        author="Knowledge Graph Studio",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        # header line
        canvas.setStrokeColor(C_ACCENT); canvas.setLineWidth(0.5)
        canvas.line(2*cm, H-1.4*cm, W-2*cm, H-1.4*cm)
        canvas.setFont("Helvetica", 7.5); canvas.setFillColor(C_MUTED)
        canvas.drawString(2*cm, H-1.2*cm, "Knowledge Graph Studio — Project Report")
        canvas.drawRightString(W-2*cm, H-1.2*cm, f"Page {doc.page}")
        # footer line
        canvas.setStrokeColor(C_BORDER)
        canvas.line(2*cm, 1.2*cm, W-2*cm, 1.2*cm)
        canvas.setFont("Helvetica", 7); canvas.setFillColor(C_MUTED)
        canvas.drawCentredString(W/2, 0.8*cm, "AI-Powered Research Knowledge Graph Builder")
        canvas.restoreState()

    story = []
    story += cover_page()
    story += section_overview()
    story.append(PageBreak())
    story += section_techstack()
    story.append(PageBreak())
    story += section_architecture()
    story.append(PageBreak())
    story += section_flow()
    story.append(PageBreak())
    story += section_database()
    story.append(PageBreak())
    story += section_api()
    story += section_ai()
    story.append(PageBreak())
    story += section_run()
    story += section_design()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF generated: {filename}")

if __name__ == "__main__":
    build_pdf()
