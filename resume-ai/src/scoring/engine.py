"""
Evaluation & Scoring Engine — Assignment 5
Computes multi-dimensional scores: Exact Match, Semantic Similarity,
Achievement Impact, and Ownership Depth.
"""

import json
import os
import re
from dataclasses import dataclass, asdict
from typing import Optional
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ScoreBreakdown:
    score: float          # 0.0 – 1.0
    explanation: str
    evidence: list[str]   # quoted snippets from resume


@dataclass
class EvaluationResult:
    candidate_name: str
    exact_match: ScoreBreakdown
    semantic_similarity: ScoreBreakdown
    achievement_impact: ScoreBreakdown
    ownership_depth: ScoreBreakdown
    overall_score: float
    tier: str             # A | B | C
    tier_rationale: str
    interview_questions: list[str]


# ---------------------------------------------------------------------------
# Semantic alias map (technology equivalences)
# Used as grounding context so the LLM doesn't hallucinate mappings.
# ---------------------------------------------------------------------------

TECH_ALIASES = {
    "kafka": ["rabbitmq", "kinesis", "pubsub", "nats", "activemq", "sqs"],
    "kubernetes": ["k8s", "openshift", "nomad", "ecs"],
    "postgresql": ["postgres", "mysql", "aurora", "cockroachdb"],
    "redis": ["memcached", "elasticache", "dragonfly"],
    "react": ["vue", "angular", "svelte", "next.js", "nuxt"],
    "spark": ["flink", "databricks", "dbt", "airflow"],
    "aws": ["gcp", "azure", "cloud"],
    "docker": ["podman", "containerd", "buildah"],
    "tensorflow": ["pytorch", "jax", "keras"],
    "elasticsearch": ["opensearch", "solr", "typesense"],
}


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert technical recruiter and engineering evaluator.
You evaluate resumes against job descriptions with precision and fairness.

You MUST respond ONLY with valid JSON matching the schema provided.
No markdown fences, no explanatory prose outside JSON.

Technology equivalence context (treat these as partial matches, not full matches):
""" + json.dumps(TECH_ALIASES, indent=2)


def _build_scoring_prompt(resume_text: str, jd_text: str) -> str:
    return f"""Evaluate the following resume against the job description.

JOB DESCRIPTION:
{jd_text}

RESUME:
{resume_text}

Return a JSON object with this exact schema:
{{
  "candidate_name": "string",
  "exact_match": {{
    "score": 0.0-1.0,
    "explanation": "concise explanation of what matched exactly and what didn't",
    "evidence": ["direct quote from resume", ...]
  }},
  "semantic_similarity": {{
    "score": 0.0-1.0,
    "explanation": "explain transferable skills and technology equivalences found",
    "evidence": ["direct quote from resume showing the similar skill", ...]
  }},
  "achievement_impact": {{
    "score": 0.0-1.0,
    "explanation": "explain quality of quantified achievements vs vague claims",
    "evidence": ["direct quote of strongest achievement", ...]
  }},
  "ownership_depth": {{
    "score": 0.0-1.0,
    "explanation": "explain whether candidate led/owned work vs assisted/contributed",
    "evidence": ["direct quote showing ownership language", ...]
  }},
  "overall_score": 0.0-1.0,
  "tier": "A|B|C",
  "tier_rationale": "1-2 sentence justification for tier placement",
  "interview_questions": [
    "5 specific technical questions tailored to THIS candidate's profile and gaps"
  ]
}}

Scoring guidance:
- exact_match: literal skill/tool/language overlap
- semantic_similarity: transferable concepts (e.g. Kafka→Kinesis counts partial credit)
- achievement_impact: penalize "worked on", reward "reduced latency by 40%"
- ownership_depth: penalize "assisted/supported", reward "led/architected/owned"
- Tier A: overall >= 0.75 (fast-track to final)
- Tier B: overall 0.50-0.74 (technical screen)
- Tier C: overall < 0.50 (needs further evaluation)
"""


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------

def evaluate_candidate(resume_text: str, jd_text: str) -> EvaluationResult:
    """
    Main entry point. Sends resume + JD to Claude and parses structured output.
    """
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": _build_scoring_prompt(resume_text, jd_text)}
        ]
    )

    raw = message.content[0].text.strip()

    # Strip accidental markdown fences
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)

    return EvaluationResult(
        candidate_name=data["candidate_name"],
        exact_match=ScoreBreakdown(**data["exact_match"]),
        semantic_similarity=ScoreBreakdown(**data["semantic_similarity"]),
        achievement_impact=ScoreBreakdown(**data["achievement_impact"]),
        ownership_depth=ScoreBreakdown(**data["ownership_depth"]),
        overall_score=data["overall_score"],
        tier=data["tier"],
        tier_rationale=data["tier_rationale"],
        interview_questions=data["interview_questions"],
    )


def evaluate_batch(candidates: list[dict], jd_text: str) -> list[EvaluationResult]:
    """
    Evaluate multiple resumes against one JD.
    In production this would use asyncio + rate limiting.
    """
    results = []
    for c in candidates:
        result = evaluate_candidate(c["resume_text"], jd_text)
        results.append(result)
    return sorted(results, key=lambda r: r.overall_score, reverse=True)


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_jd = """
    Senior Backend Engineer — Distributed Systems
    We're looking for an engineer to own our data streaming pipeline.
    Requirements:
    - 4+ years Python or Go
    - Apache Kafka (producer/consumer, exactly-once semantics)
    - Kubernetes cluster operations
    - PostgreSQL query optimisation
    - Experience leading cross-functional projects
    - Quantifiable performance improvements in prior roles
    """

    sample_resume = """
    Alex Kim — Senior Software Engineer
    alex.kim@email.com | github.com/alexkim

    Experience:
    Senior Engineer, DataFlow Inc (2021–present)
    - Architected and owned AWS Kinesis-based event pipeline processing 2M events/day,
      reducing end-to-end latency by 60ms (38% improvement)
    - Led migration of 3 microservices from EC2 to EKS (Kubernetes), cutting infra cost by $40k/yr
    - Designed PostgreSQL sharding strategy that improved p99 query time from 800ms to 120ms

    Engineer, StartupXYZ (2019–2021)
    - Assisted team in building internal dashboard using Python/Django
    - Worked on Redis caching layer

    Skills: Python, Go, AWS Kinesis, EKS/Kubernetes, PostgreSQL, Redis, Docker
    """

    result = evaluate_candidate(sample_resume, sample_jd)
    print(json.dumps(asdict(result), indent=2))
