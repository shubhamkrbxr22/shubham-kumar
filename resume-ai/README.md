# AI Resume Shortlisting & Interview Assistant

Assignment 5 submission — implements all three options (A, B, C) plus system design.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...  # optional, increases GitHub rate limit

# Run the API server
uvicorn src.api:app --reload

# Or run individual modules
python -m src.scoring.engine
python -m src.verification.verifier
python -m src.tiering.question_generator
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/evaluate` | Full pipeline (parse → score → verify → questions) |
| POST | `/score` | Scoring only (fastest, for bulk pre-filtering) |
| POST | `/batch-score` | Score multiple candidates against one JD |
| POST | `/verify` | Verification only |
| GET | `/health` | Health check |

## Example Request

```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "resume_text": "Alex Kim — Senior Engineer...",
    "jd_text": "We need a backend engineer with Kafka, Kubernetes...",
    "github_url": "https://github.com/alexkim",
    "linkedin_url": "https://linkedin.com/in/alexkim",
    "skip_verification": false
  }'
```

## Example Response (abbreviated)

```json
{
  "evaluation": {
    "candidate_name": "Alex Kim",
    "exact_match": {
      "score": 0.65,
      "explanation": "Has Python, Kubernetes, PostgreSQL. Missing direct Kafka — has Kinesis.",
      "evidence": ["Architected AWS Kinesis-based event pipeline"]
    },
    "semantic_similarity": {
      "score": 0.82,
      "explanation": "Kinesis covers Kafka producer/consumer patterns. Strong transferable fit.",
      "evidence": ["processing 2M events/day, reducing end-to-end latency by 60ms"]
    },
    "achievement_impact": {
      "score": 0.90,
      "explanation": "Excellent quantified achievements throughout.",
      "evidence": ["reducing end-to-end latency by 60ms (38%)", "cutting infra cost by $40k/yr"]
    },
    "ownership_depth": {
      "score": 0.55,
      "explanation": "Recent role shows strong ownership. Earlier role uses 'assisted' language.",
      "evidence": ["Architected and owned AWS Kinesis-based event pipeline"]
    },
    "overall_score": 0.72,
    "tier": "B",
    "tier_rationale": "Strong technical fit with transferable Kafka/Kinesis skills. Ownership depth needs probing.",
    "interview_questions": [...]
  },
  "verification": {
    "authenticity_score": 0.85,
    "red_flags": [],
    "summary": "GitHub profile is active with evidence of Python and Go usage..."
  },
  "questions": {
    "tier": "B",
    "tier_label": "Technical Screen",
    "recommended_action": "Assign 60-min technical screen. Focus on gaps identified in scores.",
    "core_technical": [...],
    "gap_probe": [...],
    "ownership_probe": [...]
  }
}
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full system design including:
- Component interaction diagram
- Data strategy (PDF → structured JSON)  
- AI strategy (LLM selection, semantic similarity, Kafka ↔ Kinesis solution)
- Scalability design (10,000+ resumes/day, ~$10/day cost)

## What was implemented

| Part | Status | File |
|------|--------|------|
| System Design & Documentation | ✅ Complete | `docs/ARCHITECTURE.md` |
| Option A: Scoring Engine | ✅ Complete | `src/scoring/engine.py` |
| Option B: Verification Engine | ✅ Complete | `src/verification/verifier.py` |
| Option C: Tiering & Questions | ✅ Complete | `src/tiering/question_generator.py` |
| Resume Parser | ✅ Bonus | `src/parser/resume_parser.py` |
| Pipeline Orchestrator | ✅ Bonus | `src/pipeline.py` |
| REST API | ✅ Bonus | `src/api.py` |
