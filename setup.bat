@echo off
echo Installing dependencies...
python -m pip install -r requirements.txt
echo.
echo Downloading spaCy model...
python -m spacy download en_core_web_sm
echo.
echo Setup complete. Run: python app.py
pause
