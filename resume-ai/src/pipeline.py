"""
Pipeline Orchestrator
Wires Parser → Scoring Engine → Verification Engine → Question Generator into one call.
"""

import json
from dataclasses import dataclass, asdict
from src.parser.resume_parser import parse_resume, ParsedResume
from src.scoring.engine import evaluate_candidate, EvaluationResult
from src.verification.verifier import verify_candidate, VerificationReport
from src.tiering.question_generator import generate_question_set, QuestionSet


@dataclass
class PipelineResult:
    parsed: ParsedResume
    evaluation: EvaluationResult
    verification: VerificationReport
    questions: QuestionSet


def run_pipeline(
    resume_text: str,
    jd_text: str,
    parse_mode: str = "llm",
    skip_verification: bool = False,
) -> PipelineResult:
    """
    Full pipeline: parse → score → verify → tier + questions.

    Args:
        resume_text:        Raw resume text (or extracted PDF text)
        jd_text:            Job description text
        parse_mode:         "llm" (accurate) or "heuristic" (fast)
        skip_verification:  True in batch mode to avoid GitHub rate limits
    """

    # 1. Parse
    parsed = parse_resume(resume_text, mode=parse_mode)

    # 2. Score
    evaluation = evaluate_candidate(resume_text, jd_text)

    # 3. Verify (optional — skip for speed in bulk screening)
    if skip_verification:
        from src.verification.verifier import VerificationReport
        verification = VerificationReport(
            github_url=parsed.github,
            linkedin_url=parsed.linkedin,
            authenticity_score=1.0,
            summary="Verification skipped in batch mode.",
        )
    else:
        verification = verify_candidate(
            github_url=parsed.github,
            linkedin_url=parsed.linkedin,
            claimed_skills=parsed.skills,
            resume_summary=parsed.summary,
        )

    # 4. Tier + Questions
    questions = generate_question_set(
        candidate_name=evaluation.candidate_name,
        overall_score=evaluation.overall_score,
        exact_score=evaluation.exact_match.score,
        similarity_score=evaluation.semantic_similarity.score,
        achievement_score=evaluation.achievement_impact.score,
        ownership_score=evaluation.ownership_depth.score,
        exact_explanation=evaluation.exact_match.explanation,
        similarity_explanation=evaluation.semantic_similarity.explanation,
        achievement_explanation=evaluation.achievement_impact.explanation,
        ownership_explanation=evaluation.ownership_depth.explanation,
        jd_text=jd_text,
        resume_text=resume_text,
        red_flags=verification.red_flags,
    )

    return PipelineResult(
        parsed=parsed,
        evaluation=evaluation,
        verification=verification,
        questions=questions,
    )


def pipeline_result_to_dict(result: PipelineResult) -> dict:
    """Serialise full result to JSON-safe dict."""
    from dataclasses import asdict as _asdict

    def _safe(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return {k: _safe(v) for k, v in _asdict(obj).items()}
        if isinstance(obj, list):
            return [_safe(i) for i in obj]
        return obj

    return _safe(result)
