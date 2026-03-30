#!/bin/bash
echo "Installing dependencies..."
python3 -m pip install -r requirements.txt
echo "Downloading spaCy model..."
python3 -m spacy download en_core_web_sm
echo "Done. Run: python3 app.py"
