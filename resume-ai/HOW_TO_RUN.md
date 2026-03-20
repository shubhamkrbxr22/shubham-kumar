# How to Run — AI Resume Shortlisting System

## Prerequisites
- Python 3.10 or higher
- A Google Gemini API key → https://aistudio.google.com/app/apikey
- (Optional) A GitHub token → https://github.com/settings/tokens

---

## Step 1 — Download & Unzip

Download the project zip and unzip it. Open a terminal and navigate into the folder:

```
cd resume-ai
```

---

## Step 2 — Create a Virtual Environment

```
python -m venv venv
```

Activate it:

Windows:
```
venv\Scripts\activate
```

Mac / Linux:
```
source venv/bin/activate
```

---

## Step 3 — Install Dependencies

```
pip install -r requirements.txt
```

---

## Step 4 — Set Your API Key

Windows (Command Prompt):
```
set GEMINI_API_KEY=your-gemini-key-here
```

Windows (PowerShell):
```
$env:GEMINI_API_KEY="your-gemini-key-here"
```

Mac / Linux:
```
export GEMINI_API_KEY=your-gemini-key-here
```

Optional — GitHub token (increases rate limit for verification):

Windows:
```
set GITHUB_TOKEN=ghp_your-token-here
```

Mac / Linux:
```
export GITHUB_TOKEN=ghp_your-token-here
```

---

## Step 5 — Run the API Server

```
uvicorn src.api:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

Open your browser and go to:
```
http://127.0.0.1:8000/health
```

It should return: {"status": "ok"}

Interactive API docs (auto-generated):
```
http://127.0.0.1:8000/docs
```

---

## Step 6 — Open the UI Demo

Open the file directly in your browser — no server needed:

```
ui/demo.html
```

Just double-click demo.html or drag it into Chrome/Edge/Firefox.

The UI connects directly to the Gemini API from your browser.
Make sure you paste your API key into the browser prompt if prompted,
or it will use the environment key set above.

---

## Step 7 — Test via Command Line (Optional)

Run the scoring engine directly:
```
python -m src.scoring.engine
```

Run the verification engine:
```
python -m src.verification.verifier
```

Run the question generator:
```
python -m src.tiering.question_generator
```

Run the full pipeline:
```
python -c "
from src.pipeline import run_pipeline, pipeline_result_to_dict
import json

result = run_pipeline(
    resume_text='Alex Kim — Senior Engineer. Skills: Python, Kinesis, Kubernetes, PostgreSQL.',
    jd_text='Senior Backend Engineer. Requires Kafka, Kubernetes, PostgreSQL, Python.',
    skip_verification=True
)
print(json.dumps(pipeline_result_to_dict(result), indent=2))
"
```

---

## Step 8 — Test the API with curl

Health check:
```
curl http://localhost:8000/health
```

Score a candidate:
```
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d "{\"resume_text\": \"Alex Kim. Skills: Python, Kinesis, Kubernetes.\", \"jd_text\": \"Need Kafka, Kubernetes, Python engineer.\"}"
```

Full evaluation:
```
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d "{\"resume_text\": \"Alex Kim. Skills: Python, Kinesis, Kubernetes, PostgreSQL.\", \"jd_text\": \"Senior Backend Engineer with Kafka, Kubernetes, PostgreSQL.\", \"skip_verification\": true}"
```

---

## Project Structure

```
resume-ai/
├── src/
│   ├── parser/
│   │   └── resume_parser.py      # PDF + text → structured JSON
│   ├── scoring/
│   │   └── engine.py             # 4-dimensional scoring engine
│   ├── verification/
│   │   └── verifier.py           # GitHub + LinkedIn authenticity checks
│   ├── tiering/
│   │   └── question_generator.py # Tier classification + interview questions
│   ├── pipeline.py               # Orchestrates all engines
│   └── api.py                    # FastAPI REST endpoints
├── docs/
│   └── ARCHITECTURE.md           # Full system design document
├── ui/
│   └── demo.html                 # Interactive browser UI (open directly)
├── requirements.txt
├── HOW_TO_RUN.md                 # This file
└── README.md
```

---

## API Endpoints Reference

| Method | URL                   | Description                              |
|--------|-----------------------|------------------------------------------|
| GET    | /health               | Health check                             |
| POST   | /evaluate             | Full pipeline (parse + score + questions)|
| POST   | /score                | Scoring only (fastest)                   |
| POST   | /batch-score          | Score multiple candidates vs one JD      |
| POST   | /verify               | GitHub + LinkedIn verification only     |
| GET    | /docs                 | Auto-generated Swagger UI                |

---

## Troubleshooting

Problem: "ModuleNotFoundError"
Solution: Make sure your virtual environment is activated and you ran pip install -r requirements.txt

Problem: "AuthenticationError" or 401
Solution: Check that GEMINI_API_KEY is set correctly in your terminal session

Problem: "Could not import uvicorn"
Solution: Run: pip install uvicorn[standard]

Problem: Demo UI shows API error
Solution: Open browser console (F12) and check the error message. Most common cause is the API key not being set.

Problem: GitHub verification returns "API error"
Solution: Set GITHUB_TOKEN to avoid rate limiting (60 req/hr unauthenticated vs 5000/hr with token)
