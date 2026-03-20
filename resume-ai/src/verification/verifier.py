"""
Claim Verification Engine — Option B
Checks GitHub profile activity and LinkedIn presence for authenticity signals.
Flags inconsistencies between resume claims and public profiles.
"""

import json
import os
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
model = genai.GenerativeModel("gemini-flash-latest")


@dataclass
class VerificationSignal:
    check: str
    status: str          # "verified" | "partial" | "unverified" | "mismatch"
    detail: str


@dataclass
class VerificationReport:
    github_url: str
    linkedin_url: str
    signals: list[VerificationSignal] = field(default_factory=list)
    authenticity_score: float = 0.0   # 0.0 – 1.0
    red_flags: list[str] = field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# GitHub checks (public API, no auth required for basic data)
# ---------------------------------------------------------------------------

def _gh_api(path: str) -> dict | list | None:
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "ResumeVerifier/1.0",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError):
        return None


def verify_github(github_url: str, claimed_skills: list[str]) -> list[VerificationSignal]:
    signals = []

    username_m = re.search(r"github\.com/([^/\s?]+)", github_url, re.I)
    if not username_m:
        signals.append(VerificationSignal("github_url", "unverified", "Could not extract username from URL"))
        return signals

    username = username_m.group(1)

    # 1. Profile exists?
    profile = _gh_api(f"/users/{username}")
    if not profile or "login" not in profile:
        signals.append(VerificationSignal("github_profile", "unverified", f"Profile @{username} not found or API error"))
        return signals

    signals.append(VerificationSignal(
        "github_profile", "verified",
        f"Profile exists: {profile.get('public_repos', 0)} public repos, "
        f"{profile.get('followers', 0)} followers, account created {profile.get('created_at', 'unknown')[:10]}"
    ))

    # 2. Account age (< 6 months is suspicious)
    created_at_str = profile.get("created_at", "")
    if created_at_str:
        created = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).days
        if age_days < 180:
            signals.append(VerificationSignal(
                "github_account_age", "partial",
                f"Account only {age_days} days old — may not reflect full career history"
            ))
        else:
            signals.append(VerificationSignal(
                "github_account_age", "verified",
                f"Account is {age_days // 365}y {(age_days % 365) // 30}m old"
            ))

    # 3. Repo language coverage vs claimed skills
    repos = _gh_api(f"/users/{username}/repos?per_page=30&sort=updated") or []
    languages_seen = set()
    for repo in repos:
        lang = repo.get("language")
        if lang:
            languages_seen.add(lang.lower())

    claimed_lower = {s.lower() for s in claimed_skills}
    language_skills = {s for s in claimed_lower if s in {
        "python", "javascript", "typescript", "go", "java", "rust",
        "c++", "c#", "ruby", "kotlin", "swift", "scala", "php"
    }}
    matched_langs = language_skills & languages_seen

    if language_skills:
        coverage = len(matched_langs) / len(language_skills)
        signals.append(VerificationSignal(
            "language_claims",
            "verified" if coverage >= 0.6 else "partial" if coverage > 0 else "mismatch",
            f"Claimed languages {sorted(language_skills)} — found evidence of {sorted(matched_langs)} in repos"
        ))

    # 4. Recent activity
    recent_active = sum(1 for r in repos if r.get("pushed_at", "") > "2024-01-01")
    signals.append(VerificationSignal(
        "recent_activity",
        "verified" if recent_active >= 3 else "partial" if recent_active > 0 else "unverified",
        f"{recent_active} repos updated in the past year"
    ))

    return signals


# ---------------------------------------------------------------------------
# LinkedIn checks (public page fetch — no API needed)
# ---------------------------------------------------------------------------

def verify_linkedin(linkedin_url: str) -> list[VerificationSignal]:
    signals = []
    if not linkedin_url or "linkedin.com" not in linkedin_url:
        signals.append(VerificationSignal("linkedin_url", "unverified", "No valid LinkedIn URL provided"))
        return signals

    try:
        req = urllib.request.Request(linkedin_url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ResumeVerifier/1.0)"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Check profile exists (LinkedIn returns 999 or redirect if blocked)
        if "Page not found" in html or len(html) < 500:
            signals.append(VerificationSignal("linkedin_profile", "unverified", "Profile not publicly accessible"))
        else:
            signals.append(VerificationSignal("linkedin_profile", "partial",
                "URL is reachable (full data requires authenticated scraping)"))

    except Exception as e:
        signals.append(VerificationSignal("linkedin_profile", "partial",
            f"URL check inconclusive: {str(e)[:80]} — manual review recommended"))

    return signals


# ---------------------------------------------------------------------------
# LLM-powered cross-reference
# ---------------------------------------------------------------------------

def cross_reference_with_llm(
    resume_claims: str,
    github_signals: list[VerificationSignal],
    linkedin_signals: list[VerificationSignal]
) -> tuple[float, list[str], str]:
    """
    Ask Claude to synthesise all signals and detect inconsistencies.
    Returns (authenticity_score, red_flags, summary).
    """
    signals_text = json.dumps(
        [{"check": s.check, "status": s.status, "detail": s.detail}
         for s in github_signals + linkedin_signals],
        indent=2
    )

    prompt = f"""You are a candidate verification specialist.

Resume claims (summary):
{resume_claims}

Verification signals collected:
{signals_text}

Assess authenticity. Return JSON only:
{{
  "authenticity_score": 0.0-1.0,
  "red_flags": ["list of specific concerns, empty if none"],
  "summary": "2-3 sentence plain-English verdict"
}}

Scoring guide:
- 0.8-1.0: strong evidence supports claims
- 0.5-0.79: partial evidence, minor gaps
- 0.2-0.49: significant gaps or inconsistencies
- 0.0-0.19: major red flags or unverifiable claims
"""
    response = model.generate_content(prompt)
    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(text, strict=False)
    except Exception as e:
        reason = response.candidates[0].finish_reason if response.candidates else 'None'
        raise ValueError(f"JSON Decode Error in Verifier: {str(e)} | Finish Reason: {reason} | Raw output: {repr(text)}")
    
    return data["authenticity_score"], data["red_flags"], data["summary"]


# ---------------------------------------------------------------------------
# Main verification function
# ---------------------------------------------------------------------------

def verify_candidate(
    github_url: str,
    linkedin_url: str,
    claimed_skills: list[str],
    resume_summary: str = ""
) -> VerificationReport:

    report = VerificationReport(github_url=github_url, linkedin_url=linkedin_url)

    gh_signals = verify_github(github_url, claimed_skills) if github_url else []
    li_signals = verify_linkedin(linkedin_url) if linkedin_url else []

    report.signals = gh_signals + li_signals

    resume_claims = resume_summary or f"Skills: {', '.join(claimed_skills)}"
    score, flags, summary = cross_reference_with_llm(resume_claims, gh_signals, li_signals)

    report.authenticity_score = score
    report.red_flags = flags
    report.summary = summary

    return report


if __name__ == "__main__":
    report = verify_candidate(
        github_url="https://github.com/torvalds",
        linkedin_url="https://linkedin.com/in/linustorvalds",
        claimed_skills=["C", "Linux", "Python", "Git"],
        resume_summary="Creator of Linux kernel and Git, 30+ years systems programming"
    )
    print(json.dumps({
        "authenticity_score": report.authenticity_score,
        "red_flags": report.red_flags,
        "summary": report.summary,
        "signals": [{"check": s.check, "status": s.status, "detail": s.detail} for s in report.signals]
    }, indent=2))
