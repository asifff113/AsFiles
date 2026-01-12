# DocFlow Studio

Modern document toolbox UI with a FastAPI backend. The UI mirrors the tool grid in your reference image and ships an operational PPTX merge flow.

## Run the backend

```bash
cd server
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Run the frontend

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173`.

## Notes

PPTX merging uses python-pptx and works best with slides containing standard text and images. Complex charts, embedded media, or custom fonts may need manual review after merging.
