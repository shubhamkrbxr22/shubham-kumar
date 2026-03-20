"""
FastAPI server — exposes the pipeline as REST endpoints.
Run: uvicorn src.api:app --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json

from src.pipeline import run_pipeline, pipeline_result_to_dict
from src.scoring.engine import evaluate_candidate
from src.verification.verifier import verify_candidate
from src.tiering.question_generator import generate_question_set, classify_tier

app = FastAPI(
    title="AI Resume Shortlisting API",
    description="Multi-dimensional resume evaluation against job descriptions",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    resume_text: str
    jd_text: str
    github_url: str = ""
    linkedin_url: str = ""
    skip_verification: bool = False


class BatchEvaluateRequest(BaseModel):
    candidates: list[dict]   # [{resume_text: str, name: str}]
    jd_text: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    import google.generativeai as genai
    import os
    try:
        models = [m.name for m in genai.list_models()]
        return {"status": "ok", "models_available": models}
    except Exception as e:
        return {"status": "ok", "error": str(e)}


@app.post("/evaluate")
async def evaluate(req: EvaluateRequest):
    """
    Full pipeline: parse → score → verify → tier → questions.
    Returns complete structured evaluation.
    """
    try:
        result = run_pipeline(
            resume_text=req.resume_text,
            jd_text=req.jd_text,
            skip_verification=req.skip_verification,
        )
        return pipeline_result_to_dict(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/score")
async def score_only(req: EvaluateRequest):
    """
    Scoring only — fastest endpoint for pre-filtering at scale.
    No verification, no question generation.
    """
    try:
        result = evaluate_candidate(req.resume_text, req.jd_text)
        from dataclasses import asdict
        return asdict(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch-score")
async def batch_score(req: BatchEvaluateRequest):
    """
    Score multiple candidates against one JD.
    Returns ranked list with tier assignments.
    Designed for 10k+/day volume — stateless, horizontally scalable.
    """
    results = []
    for c in req.candidates:
        try:
            r = evaluate_candidate(c["resume_text"], req.jd_text)
            from dataclasses import asdict
            results.append({"input_name": c.get("name", ""), **asdict(r)})
        except Exception as e:
            results.append({"input_name": c.get("name", ""), "error": str(e)})

    results.sort(key=lambda x: x.get("overall_score", 0), reverse=True)
    return {
        "total": len(results),
        "tier_a": sum(1 for r in results if r.get("tier") == "A"),
        "tier_b": sum(1 for r in results if r.get("tier") == "B"),
        "tier_c": sum(1 for r in results if r.get("tier") == "C"),
        "ranked": results,
    }


@app.post("/verify")
async def verify(req: EvaluateRequest):
    """Verification only — check GitHub/LinkedIn authenticity."""
    try:
        report = verify_candidate(
            github_url=req.github_url,
            linkedin_url=req.linkedin_url,
            claimed_skills=[],
        )
        from dataclasses import asdict
        return asdict(report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
