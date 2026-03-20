"""
Intelligent Tiering & Question Generator — Option C
Classifies candidates into Tier A/B/C and generates personalised interview questions.
"""

import json
import os
import re
from dataclasses import dataclass, field
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

TIER_THRESHOLDS = {
    "A": 0.75,   # Fast-track to final round
    "B": 0.50,   # Technical screen required
    "C": 0.00,   # Needs evaluation / reject
}

TIER_LABELS = {
    "A": "Fast-Track",
    "B": "Technical Screen",
    "C": "Needs Evaluation",
}

TIER_ACTIONS = {
    "A": "Schedule final interview immediately. Prioritise before competitors move.",
    "B": "Assign 60-min technical screen. Focus on gaps identified in scores.",
    "C": "Hold for now. Re-evaluate if pipeline is thin or role requirements change.",
}


@dataclass
class QuestionSet:
    tier: str
    tier_label: str
    recommended_action: str
    opening_questions: list[str]    # Easy, confidence-building
    core_technical: list[str]       # Directly from JD requirements
    gap_probe: list[str]            # Target weak scores specifically
    ownership_probe: list[str]      # Dig into leadership / ownership claims
    situational: list[str]          # Behavioural / STAR format
    red_flag_followups: list[str]   # Only populated if verification flagged issues


def classify_tier(overall_score: float) -> str:
    if overall_score >= TIER_THRESHOLDS["A"]:
        return "A"
    if overall_score >= TIER_THRESHOLDS["B"]:
        return "B"
    return "C"


def generate_question_set(
    candidate_name: str,
    overall_score: float,
    exact_score: float,
    similarity_score: float,
    achievement_score: float,
    ownership_score: float,
    exact_explanation: str,
    similarity_explanation: str,
    achievement_explanation: str,
    ownership_explanation: str,
    jd_text: str,
    resume_text: str,
    red_flags: list[str] | None = None,
) -> QuestionSet:

    tier = classify_tier(overall_score)

    prompt = f"""You are a senior technical interviewer designing a tailored interview plan.

CANDIDATE: {candidate_name}
TIER: {tier} ({TIER_LABELS[tier]})

SCORE BREAKDOWN:
- Exact Match: {exact_score:.2f} — {exact_explanation}
- Semantic Similarity: {similarity_score:.2f} — {similarity_explanation}
- Achievement Impact: {achievement_score:.2f} — {achievement_explanation}
- Ownership Depth: {ownership_score:.2f} — {ownership_explanation}

VERIFICATION RED FLAGS: {json.dumps(red_flags or [])}

JOB DESCRIPTION:
{jd_text}

RESUME (excerpt):
{resume_text[:1500]}

Generate a targeted interview question set. Return ONLY valid JSON:
{{
  "opening_questions": [
    "2 easy rapport-building questions specific to their background"
  ],
  "core_technical": [
    "3 technical questions directly testing JD requirements they claimed to have"
  ],
  "gap_probe": [
    "3 questions specifically probing the LOWEST scored dimension. Be direct but fair."
  ],
  "ownership_probe": [
    "2 questions that distinguish if they led something vs just participated. Use their specific projects."
  ],
  "situational": [
    "2 STAR-format behavioural questions targeting their weakest achievement claims"
  ],
  "red_flag_followups": [
    "1-2 questions to clarify any verification red flags. Empty array if none."
  ]
}}

Rules:
- Reference the candidate's ACTUAL projects, companies, and claims — not generic questions
- For Tier C: gap_probe questions should be rigorous screening questions
- For Tier A: questions should be forward-looking and assess culture/impact fit
- For low ownership score: use questions like "Walk me through YOUR specific decisions in..."
- For low achievement score: ask "What metric moved as a direct result of your work?"
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.content[0].text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)

    return QuestionSet(
        tier=tier,
        tier_label=TIER_LABELS[tier],
        recommended_action=TIER_ACTIONS[tier],
        opening_questions=data.get("opening_questions", []),
        core_technical=data.get("core_technical", []),
        gap_probe=data.get("gap_probe", []),
        ownership_probe=data.get("ownership_probe", []),
        situational=data.get("situational", []),
        red_flag_followups=data.get("red_flag_followups", []),
    )


if __name__ == "__main__":
    qs = generate_question_set(
        candidate_name="Alex Kim",
        overall_score=0.72,
        exact_score=0.65,
        similarity_score=0.80,
        achievement_score=0.85,
        ownership_score=0.55,
        exact_explanation="Missing direct Kafka experience; has Kinesis which is equivalent",
        similarity_explanation="AWS Kinesis maps well to Kafka producer/consumer patterns",
        achievement_explanation="Strong quantified achievements: 38% latency reduction, $40k infra savings",
        ownership_explanation="Led migration project but earlier role shows 'assisted' language",
        jd_text="Senior Backend Engineer with Kafka, Kubernetes, PostgreSQL",
        resume_text="Alex Kim — Senior Engineer with Kinesis, EKS, PostgreSQL",
        red_flags=[]
    )
    print(json.dumps({
        "tier": qs.tier,
        "tier_label": qs.tier_label,
        "recommended_action": qs.recommended_action,
        "opening_questions": qs.opening_questions,
        "core_technical": qs.core_technical,
        "gap_probe": qs.gap_probe,
        "ownership_probe": qs.ownership_probe,
        "situational": qs.situational,
        "red_flag_followups": qs.red_flag_followups,
    }, indent=2))
