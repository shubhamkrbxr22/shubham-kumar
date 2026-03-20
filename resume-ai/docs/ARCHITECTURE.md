# AI Resume Shortlisting & Interview Assistant — System Design

## 1. System Architecture

```
                         ┌─────────────────────────────────────────────┐
                         │              Ingest Layer                    │
                         │  REST API  /  File Upload  /  ATS Webhook   │
                         └──────────────────┬──────────────────────────┘
                                            │ raw PDF / text
                                            ▼
                         ┌─────────────────────────────────────────────┐
                         │           Resume Parser                      │
                         │  • PDF text extraction (pypdf)               │
                         │  • LLM entity extraction → ParsedResume JSON │
                         │  • Heuristic fast-path (batch mode)          │
                         └──────────────────┬──────────────────────────┘
                                            │ ParsedResume
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                  ▼
          ┌───────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
          │  Scoring Engine   │  │ Verification Eng. │  │  Question Generator  │
          │                   │  │                   │  │                      │
          │ • Exact Match     │  │ • GitHub API      │  │ • Tier classification│
          │ • Semantic Sim.   │  │ • LinkedIn fetch  │  │ • Personalised Qs    │
          │ • Achievement     │  │ • LLM synthesis   │  │ • Gap-probe logic    │
          │ • Ownership Depth │  │ • Red flag detect │  │ • STAR questions     │
          └────────┬──────────┘  └────────┬──────────┘  └──────────┬───────────┘
                   │                      │                         │
                   └──────────────────────▼─────────────────────────┘
                                          │
                          ┌───────────────▼──────────────┐
                          │      Pipeline Orchestrator    │
                          │      PipelineResult object    │
                          └───────────────┬───────────────┘
                                          │
                          ┌───────────────▼───────────────┐
                          │    Storage / Output Layer      │
                          │  PostgreSQL · Redis · S3       │
                          │  (or in-memory for demo)       │
                          └───────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Key Design Decision |
|---|---|---|
| **Resume Parser** | Raw text → structured `ParsedResume` JSON | Dual-mode: LLM (accurate) or regex (fast). LLM used for final candidates only. |
| **Scoring Engine** | Compute 4 scores + overall + tier | Single LLM call with structured JSON output. Alias map prevents hallucinated equivalences. |
| **Verification Engine** | GitHub API + LinkedIn check → authenticity score | Public APIs only; no credential risk. LLM synthesises signals into narrative. |
| **Question Generator** | Tier + scores → personalised interview plan | Lowest-scoring dimension drives `gap_probe` questions. Uses candidate's own project names. |
| **Orchestrator** | Wires all engines; exposes `/evaluate`, `/score`, `/batch-score` | Stateless — each call is independent. Horizontal scaling with worker pools. |

---

## 2. Data Strategy

### Unstructured PDF → Structured JSON

```
PDF bytes
  └→ pypdf.PdfReader        (text extraction, handles multi-column)
       └→ raw_text (str)
            └→ LLM parse call  (entity extraction with schema enforcement)
                 └→ ParsedResume {
                      name, email, github, linkedin,
                      skills: [],
                      experience: [{title, company, dates, bullets: []}],
                      education: [{degree, institution, year}]
                    }
```

**Schema enforcement strategy:**
- System prompt defines strict JSON schema
- Regex strips accidental markdown fences from LLM output
- `json.loads()` validates structure; validation errors trigger one retry
- Fields missing from LLM response default to empty string / empty list

**Heuristic fast-path** (for initial 10k+ batch pre-filtering):
- Regex extracts email, phone, GitHub/LinkedIn URLs
- Skills section parsed with delimiter-based tokenisation
- No LLM call = ~0 cost, ~5ms latency
- Used for pre-filter pass; LLM parse reserved for shortlisted candidates

---

## 3. AI Strategy

### LLM Selection

| Task | Model | Rationale |
|---|---|---|
| Resume parsing | `gemini-2.5-flash` | Best JSON fidelity; structured output reliability and speed |
| Scoring engine | `gemini-2.5-flash` | Reasoning required for nuanced similarity judgements |
| Verification synthesis | `gemini-2.5-flash` | Short prompt, low cost, fast |
| Question generation | `gemini-2.5-flash` | Creative + contextual |

**Alternative:** OpenAI `gpt-4o` or `gemini-2.5-pro` works as a drop-in; switch by changing the client initialisation. LangChain abstraction can be added if multi-provider routing is needed.

### Semantic Similarity — The Kafka ↔ Kinesis Problem

**Challenge:** A candidate with AWS Kinesis experience is a genuine fit for a Kafka role but an exact-match system would score them zero on that dimension.

**Solution — Three-layer approach:**

```
Layer 1: Grounding map (deterministic)
  TECH_ALIASES = {
    "kafka": ["rabbitmq", "kinesis", "pubsub", "nats", ...],
    ...
  }
  → Injected into system prompt so LLM uses confirmed equivalences,
    not hallucinated ones.

Layer 2: LLM semantic reasoning (probabilistic)
  → LLM reads both JD and resume and scores similarity WITH the alias map
    as grounding context. Produces score + explanation.

Layer 3: Explainability
  → "evidence" field in ScoreBreakdown contains direct resume quotes
    proving WHY the similarity score was awarded.
```

**Why not vector embeddings?**
- Embedding similarity (cosine distance) can surface misleading matches
  (e.g., "managed Kafka cluster" ≠ "deep Kafka producer expertise")
- LLM reasoning on the full text gives better precision with explainability
- At 10k+/day scale, embeddings could be used for a **pre-filter pass**
  (fast, cheap) before the LLM scoring pass (thorough, expensive)

### Prompt Engineering Patterns

| Pattern | Used Where | Purpose |
|---|---|---|
| Schema-in-prompt | All structured outputs | Forces valid JSON; field names act as self-documentation |
| Grounding context | Scoring engine | Prevents hallucinated tech equivalences |
| Evidence quotes | All score dimensions | Enables explainability — human reviewer can verify |
| Dual-instruction | Question generator | Tier-conditional instructions in same prompt |

---

## 4. Scalability — 10,000+ Resumes/Day

### Throughput calculation

```
10,000 resumes/day = ~420/hr = ~7/min = ~0.12/sec (steady state)
Peak (morning batch upload): assume 3x = ~1,260/hr = 21/min

Per-resume pipeline:
  Parse:    1 LLM call × ~1s    = 1s
  Score:    1 LLM call × ~2s    = 2s
  Verify:   1 HTTP call × ~1s   = 1s  (skippable for bulk)
  Questions:1 LLM call × ~2s    = 2s
  ─────────────────────────────────
  Total sequential: ~6s/resume
  With concurrency (asyncio, 20 workers): 20 × 0.17/s = ~3.4/s → 12,000/hr ✓
```

### Architecture for scale

```
                    ┌──────────────────────────────────────────┐
                    │         Ingest Queue (SQS / Redis)        │
                    │   Decouples upload bursts from processing  │
                    └───────────────────┬──────────────────────┘
                                        │
               ┌────────────────────────┼────────────────────────┐
               ▼                        ▼                         ▼
        Worker Pod 1             Worker Pod 2              Worker Pod N
        (async Python)           (async Python)            (async Python)
        20 concurrent tasks      20 concurrent tasks       20 concurrent tasks
               │                        │                         │
               └────────────────────────┼─────────────────────────┘
                                        ▼
                              ┌─────────────────┐
                              │   PostgreSQL     │  ← results, audit log
                              │   Redis          │  ← job status, short cache
                              │   S3             │  ← raw PDFs, parsed JSON
                              └─────────────────┘
```

### Cost optimisation strategy

```
All 10,000 resumes →  heuristic parse + embedding pre-filter (cheap)
        │
        ├── Bottom 60%  →  auto-Tier-C  (no LLM scoring call)
        │
        └── Top 40%  →  full LLM pipeline (4,000 resumes)
              │
              ├── Top 20% of those  →  verification + question gen
              │
              └── Rest  →  scoring + tier only
```

**Estimated daily LLM cost at 10k volume:**
- Pre-filter: ~$0 (heuristic)
- Scoring (4,000 × ~1,500 tokens): ~$6
- Verification synthesis (2,000 × ~500 tokens): ~$1
- Question generation (2,000 × ~1,500 tokens): ~$3
- **Total: ~$10/day for 10,000 resumes**

### Horizontal scaling

- All pipeline components are **stateless** — no shared mutable state
- FastAPI workers can scale horizontally behind a load balancer
- Kubernetes HPA on CPU/queue depth triggers new pods during bursts
- Redis used for deduplication (resume hash → skip if seen in last 30 days)

---

## 5. Directory Structure

```
resume-ai/
├── src/
│   ├── parser/
│   │   └── resume_parser.py      # PDF → ParsedResume JSON
│   ├── scoring/
│   │   └── engine.py             # 4-dimensional scoring + tier
│   ├── verification/
│   │   └── verifier.py           # GitHub + LinkedIn authenticity
│   ├── tiering/
│   │   └── question_generator.py # Tier classification + interview Qs
│   ├── pipeline.py               # Orchestrator
│   └── api.py                    # FastAPI REST layer
├── docs/
│   └── ARCHITECTURE.md           # This document
├── tests/
│   └── test_*.py                 # Unit tests per module
├── requirements.txt
└── README.md
```

---

## 6. Implementation Checklist

- [x] **Option A** — Scoring Engine: 4 dimensions, explainability, tier classification
- [x] **Option B** — Verification Engine: GitHub API, LinkedIn fetch, LLM synthesis, red flags
- [x] **Option C** — Question Generator: personalised per candidate, gap-probe logic, tier-conditional
- [x] **Parser** — LLM + heuristic dual-mode
- [x] **Orchestrator** — single `run_pipeline()` call wires all engines
- [x] **REST API** — `/evaluate`, `/score`, `/batch-score`, `/verify`
- [x] **Scalability design** — queue-based, stateless workers, cost optimisation
- [x] **Explainability** — every score has `explanation` + `evidence` quotes
- [x] **Semantic similarity** — alias map + LLM reasoning (Kafka ↔ Kinesis)
