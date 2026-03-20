"""
Resume Parser — converts raw PDF/text into structured JSON.
Uses Claude for entity extraction; falls back to heuristic regex for speed.
"""

import json
import re
import os
from dataclasses import dataclass, field
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
model = genai.GenerativeModel("gemini-flash-latest")


@dataclass
class ParsedResume:
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    experience: list[dict] = field(default_factory=list)  # {title, company, dates, bullets}
    education: list[dict] = field(default_factory=list)   # {degree, institution, year}
    certifications: list[str] = field(default_factory=list)
    raw_text: str = ""


_PARSE_SYSTEM = """You are a resume parser. Extract structured data from resume text.
Return ONLY valid JSON. No prose, no markdown fences."""

_PARSE_PROMPT = """Parse this resume into the following JSON schema:
{{
  "name": "string",
  "email": "string",
  "phone": "string",
  "linkedin": "url or empty string",
  "github": "url or empty string",
  "summary": "professional summary if present",
  "skills": ["list", "of", "technical", "skills"],
  "experience": [
    {{
      "title": "job title",
      "company": "company name",
      "dates": "date range string",
      "bullets": ["achievement or responsibility"]
    }}
  ],
  "education": [
    {{
      "degree": "degree name",
      "institution": "school name",
      "year": "graduation year or empty"
    }}
  ],
  "certifications": ["list of certs"]
}}

RESUME TEXT:
{resume_text}
"""


def parse_resume_llm(raw_text: str) -> ParsedResume:
    """LLM-powered parse — accurate but costs a token call."""
    prompt = f"{_PARSE_SYSTEM}\n\n{_PARSE_PROMPT.format(resume_text=raw_text)}"
    response = model.generate_content(prompt)
    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(text, strict=False)
    except Exception as e:
        reason = response.candidates[0].finish_reason if response.candidates else 'None'
        raise ValueError(f"JSON Decode Error in Parser: {str(e)} | Finish Reason: {reason} | Raw output: {repr(text)}")
    
    parsed = ParsedResume(**{k: data.get(k, v) for k, v in ParsedResume().__dict__.items()})
    parsed.raw_text = raw_text
    return parsed


def parse_resume_heuristic(raw_text: str) -> ParsedResume:
    """
    Fast regex-based fallback for high-volume batch scenarios.
    Used when cost optimisation matters more than extraction quality.
    """
    p = ParsedResume(raw_text=raw_text)

    # Email
    email_m = re.search(r"[\w.+-]+@[\w-]+\.\w+", raw_text)
    if email_m:
        p.email = email_m.group()

    # Phone
    phone_m = re.search(r"(\+?\d[\d\s\-().]{7,}\d)", raw_text)
    if phone_m:
        p.phone = phone_m.group().strip()

    # LinkedIn / GitHub
    gh = re.search(r"github\.com/[\w-]+", raw_text, re.I)
    li = re.search(r"linkedin\.com/in/[\w-]+", raw_text, re.I)
    if gh:
        p.github = "https://" + gh.group()
    if li:
        p.linkedin = "https://" + li.group()

    # Name heuristic: first non-empty line
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    if lines:
        p.name = lines[0]

    # Skills section (naive keyword list)
    skills_section = re.search(
        r"(?:skills?|technologies|tech stack)[:\n](.*?)(?:\n\n|\Z)",
        raw_text, re.I | re.S
    )
    if skills_section:
        raw_skills = skills_section.group(1)
        p.skills = [s.strip() for s in re.split(r"[,\n|/]", raw_skills) if s.strip()][:30]

    return p


def parse_resume(raw_text: str, mode: str = "llm") -> ParsedResume:
    """
    mode="llm"       → accurate, uses Claude
    mode="heuristic" → fast, no API call (good for pre-filtering at scale)
    """
    if mode == "llm":
        return parse_resume_llm(raw_text)
    return parse_resume_heuristic(raw_text)


# PDF extraction helper (requires pypdf, optional dependency)
def extract_text_from_pdf(pdf_path: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        raise RuntimeError(
            "pypdf not installed. Run: pip install pypdf  "
            "Or pass raw text directly to parse_resume()."
        )
