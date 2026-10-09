# JISR AI: Claude Code Master Build Prompt v3 (advanced agentic + advanced RAG)

> Paste this whole file into Claude Code as the first message in an empty repo named `jisr-ai`.
> Companion file: `JISR_playbook_v2.md` (strategy, rubric, timeline, claims register).
> Model routing: **Opus 5.5 at high effort** for architecture, retrieval design, governance and security (Phases 0, 1, 5, 7, and section 22). Sonnet 5.5 for bulk implementation. Haiku 5.5 for docs and tests.
> Work phase by phase (section 12, plus the new phases in section 22.10). After each phase run the tests and report. Do not skip ahead.

**What changed in v2:** a vertical slice first, three new capabilities (CEPA Duty Optimiser, Document Consistency Checker, Buyer Trust Check), a WhatsApp channel, Agent Passports with Seal-readiness, an Impact Ledger for pilot measurement, a claims register, an optional 3D hero last, and a `CLAUDE.md` for the repo.

**What changed in v3 (section 22):** agentic RAG with a planner and a grounding check; a corrective loop with query rewriting and reranking; hierarchy-aware retrieval over the tariff (section, chapter, heading, subheading, national code) and the CEPA rules of origin; Arabic-aware chunking, normalisation and cross-lingual search; a separate retrieval evaluation set; explicit autonomy levels per action; a tool layer exposed over MCP; an optional buyer-side agent talking to Jisr over the A2A protocol; trajectory-level agent evaluation; and memory design.

---

## 0. Your role and working rules

You are a senior engineer building **Jisr AI**, an entry for the Create AI Agents Championship (Dubai Chamber of Digital Economy), category **Best Business AI Agent**. The author prefers **beginner-friendly, step-by-step, fully commented code and complete end-to-end deliverables, not outlines.**

Rules you must follow:
1. **Comment everything.** Every file starts with a header comment saying what it does and why. Every function has a docstring. Non-obvious lines get inline comments written for a beginner.
2. **Tests first for risky parts:** pricing math, duty and origin calculations, policy engine, redaction, injection defence, document checks.
3. **Never claim something works until you ran it.** Show real command output.
4. **Original code only.** Do not copy from existing repositories. Use libraries as dependencies, not pasted code. (The championship requires original work.)
5. **Free-first, paid-ready.** All LLM calls go through one router so the model can be swapped by config.
6. **Safe by default.** The agent never sends a message, changes bank details or marks a payment received without passing the governance layer (section 9).
7. **Never invent facts.** Tariff rates, origin rules, HS codes and legal requirements come only from retrieved official documents, with citations, or are flagged "needs human check".
8. After every phase, update `docs/PROGRESS.md` (built, tested, next). Record choices in `docs/DECISIONS.md`.
9. If something is ambiguous, choose the simplest reasonable option, record it, and continue.
10. Keep demo and sample data clean: no political, religious or inappropriate content (championship Terms).

---

## 1. Problem statement

Small Indian exporters and traders who sell to UAE/GCC buyers lose time and money in one repeating workflow:

**Buyer enquiry -> quote -> export documents -> outreach and follow-up -> payment collection**

Typical pains: slow quotes, leads never followed up, mistakes in invoices, packing lists and HS codes that delay shipments, missed preferential duty under the India-UAE CEPA, INR/AED mistakes, unverified buyers, and no record of who approved what.

**Jisr AI** is a multi-agent system that does this work end to end, with a human approving anything that leaves the building. It is the bridge between Indian suppliers and UAE buyers, and every crossing is governed and auditable.

**Pilot context:** a family business group in Jaipur (trading, export, corporate gifting) is the first real user. The system must use a *configurable business profile*, so it is not hard-wired to one company.

**Dubai framing:** in Digital Dubai's AI Integration Matrix language, Jisr is an **external agent** (talks to buyers and suppliers) backed by an **external RAG system** (cited knowledge from official documents).

---

## 2. Success criteria

**Product (what judges see)**
- A buyer enquiry (pasted text or WhatsApp message) becomes a quote, CEPA duty analysis, document pack and bilingual drafts in **under 2 minutes** of agent time, queued for approval.
- A visible **"AED saved / risks caught"** number on every run.
- Approval inbox, audit trail, ROI panel and Agent Passports.
- A **prompt-injection demo** in which a hostile message is detected and blocked.

**Engineering**
- Tests pass in CI. Evaluation harness reports the metrics in section 13.
- One-command local run and one-command Docker run.
- **Demo mode** needs no login and no real data, plus an **offline replay mode**.

**Not goals:** a general chatbot, a full ERP, real payments, real customs filing.

---

## 3. Constraints

- Python 3.11+ (backend), TypeScript (frontend).
- **No real customer data in free-tier model calls.** Use synthetic or redacted data (section 7).
- Data protection by design: redaction before every model call, encryption at rest for pilot data, retention settings, per-organisation isolation.
- WhatsApp and email are **draft-only** by default. Real sends need a config flag, an explicit approval and an opt-in contact.
- Every compliance output carries "verify with your customs broker", its source and its document date.
- The championship requires: original agent, protection of personal and confidential data, a summary report, English-language submission materials.

---

## 4. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Orchestration | **LangGraph** | Supervisor plus worker nodes, explicit persisted state |
| LLM access | **LiteLLM router** | Roles `fast`, `smart`, `local`; profiles `dev` and `prod` |
| Dev models | Free tiers (Groq, Gemini free, Cerebras) | Synthetic data only |
| Pilot and finals models | Paid API with no-training terms, or a local open model | `LLM_PROFILE=prod` |
| Backend | **FastAPI**, Pydantic v2 | Typed models everywhere |
| Database | **PostgreSQL + pgvector** (Docker), SQLite fallback | SQLAlchemy 2 + Alembic |
| Retrieval | Hybrid BM25 + vector with citations | `rank_bm25` + pgvector |
| Embeddings | Multilingual open model (e.g. `bge-m3`) | Arabic and English |
| Messaging | WhatsApp Business Cloud API (sandbox/test mode) behind an interface, plus a **local WhatsApp simulator** | Check Meta's docs for the current test setup and pricing |
| Frontend | **Next.js 14** + TypeScript + Tailwind + Motion | Fast, legible screens |
| Optional 3D | React Three Fiber, **last phase only** | Section 12, Phase 11 |
| Jobs | APScheduler | Follow-up timers |
| Evaluation | pytest + RAGAS + custom metrics | `make eval` |
| Observability | Local JSONL traces plus a trace viewer page | Every step inspectable |
| Packaging | Docker Compose, `Makefile` | |

---

## 5. Architecture

```
        Inbound enquiry (WhatsApp / email text / form)
                          |
                 [ Ingest + Redactor ]   PII masked before any model sees it
                          |
                 [ Injection Guard ]     message body treated as UNTRUSTED DATA
                          |
                 [ Supervisor (LangGraph) ]
     ______________|________|_________|___________|__________
     |              |          |           |           |
 [Quote +       [Docs +     [Buyer      [Outreach] [Collections]
  CEPA Duty     Consistency  Trust
  Optimiser]    Checker]     Check]
     |              |          |           |           |
     +---- Tools: pricing, FX, duty/origin calc, HS lookup (RAG),
           doc builder, sanctions list match, templates, CRM, ledger,
           WhatsApp/email drafts
                          |
                [ Governance Layer ]
   policy engine | approval queue | audit chain | kill switch | passports
                          |
                 Human approves in dashboard
                          |
                 Send (or simulate) + log outcome
                          |
          [ Impact Ledger + outcome learning ]
```

Design principles to implement and explain:
- **Supervisor** plans which workers run and in what order, and can re-plan on tool errors.
- **Workers** are narrow, use typed tools, and never call the network directly.
- **Governance Layer** sits between agents and the world. Nothing leaves without it, and its rules are deterministic code, not LLM judgement.
- **State** is explicit and persisted, so a run can pause for approval and resume.

---

## 6. Repository layout

```
jisr-ai/
  CLAUDE.md                      # project memory for Claude Code (section 19)
  README.md  Makefile  docker-compose.yml  .env.example
  docs/
    PROGRESS.md  DECISIONS.md  ARCHITECTURE.md  EVAL_REPORT.md
    PITCH_NOTES.md  DATA_PROTECTION.md  VIVA_QA.md  SUBMISSION.md
    CLAIMS_REGISTER.md  SEAL_READINESS.md  IMPACT_METHOD.md
    passports/                   # one JSON + one page per agent
  backend/
    app/
      main.py  config.py
      llm/router.py
      ingest/                    # parse text, WhatsApp payloads, email, attachments
      channels/                  # whatsapp.py (cloud api), whatsapp_sim.py, email_draft.py
      security/redactor.py  security/injection_guard.py
      agents/
        state.py  supervisor.py
        quote_agent.py  duty_agent.py  docs_agent.py
        trust_agent.py  outreach_agent.py  collections_agent.py
      tools/
        pricing.py  fx.py  duty_origin.py  hs_lookup.py
        doc_builder.py  doc_checker.py  sanctions_match.py
        crm.py  ledger.py  messaging.py
      governance/
        policy_engine.py  approvals.py  audit.py  killswitch.py  passports.py
      rag/                       # ingestion, hybrid retrieval, citations
      impact/ledger.py           # time, savings, errors-caught measurement
      db/  api/
    tests/
    eval/ golden/ run_eval.py
  data/
    synthetic/  kb_sources/  sanctions_public/
  frontend/app/ (demo, runs, approvals, audit, passports, roi, settings)
  scripts/
    seed_demo.py  generate_synthetic.py  ingest_kb.py  anonymise_pilot.py
    record_demo_checklist.md  replay_demo.py
```

---

## 7. Data

**Four data sources, kept strictly separate:**

1. **Synthetic dataset (primary for development).** `generate_synthetic.py` creates 300 realistic enquiries (English, some Arabic, some mixed) for handicrafts, textiles, corporate gifting and general trading goods, with quantities, Incoterms, UAE/GCC destinations, urgency and messy phrasing. Include **30 adversarial messages** (prompt injection, bank-detail change requests, fake urgency, hidden instructions in attachment text). Include **40 document sets** (invoice, packing list, origin certificate data) of which about half contain seeded mistakes (HS-code mismatch, missing certificate, missing tax declaration, inconsistent quantities, bad consignment info). Label ground truth for each.
2. **Pilot data (real, anonymised).** The user exports 30-50 past enquiries, quotes and invoices. `anonymise_pilot.py` strips names, phones, emails, addresses and bank details and replaces them with consistent tokens. **Only the anonymised set enters the repo or any non-local model call.**
3. **Knowledge base (public, official sources).** The user downloads into `data/kb_sources/`: the GCC common customs tariff or HS nomenclature, India-UAE CEPA text and rules of origin, Dubai Customs import guides, India export documentation guides (DGFT / ICEGATE), Incoterms summaries, UAE VAT basics for imports. `ingest_kb.py` chunks, embeds and indexes them with source, page and **document date**. Every answer cites chunk and date. No supporting chunk means "I don't know, needs human check".
4. **Public sanctions lists (public).** The user downloads publicly available sanctions lists (for example the UN consolidated list) into `data/sanctions_public/`. Used only for the Buyer Trust Check signal.

Never invent tariff rates, HS codes, origin rules or legal requirements.

---

## 8. Agent specifications

### 8.1 State schema (`agents/state.py`)

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class LineItem(BaseModel):
    description: str
    quantity: float
    unit: str
    target_price: Optional[float] = None

class RFQ(BaseModel):
    """Structured enquiry extracted from buyer text."""
    buyer_name: str
    buyer_country: str
    items: list[LineItem]
    incoterm: Optional[str] = None
    deadline: Optional[str] = None
    language: Literal["en", "ar", "mixed"] = "en"
    channel: Literal["whatsapp", "email", "form"] = "form"

class RunState(BaseModel):
    """Everything a run needs; persisted so it can pause for approval and resume."""
    run_id: str
    org_id: str                              # per-organisation isolation
    raw_message_redacted: str                # models only ever see redacted text
    injection_flags: list[str] = Field(default_factory=list)
    rfq: Optional[RFQ] = None
    plan: list[str] = Field(default_factory=list)
    quote: Optional[dict] = None             # INR + AED, margin, FX source/time
    duty: Optional[dict] = None              # CEPA analysis, savings, evidence list
    docs: Optional[dict] = None              # generated document pack
    doc_issues: list[dict] = Field(default_factory=list)   # consistency findings
    buyer_signals: list[dict] = Field(default_factory=list)  # trust signals, not verdicts
    drafts: list[dict] = Field(default_factory=list)
    pending_actions: list[dict] = Field(default_factory=list)  # go to governance
    citations: list[dict] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)
    impact: dict = Field(default_factory=dict)  # minutes saved, AED saved, errors caught
    status: Literal["new","planning","needs_approval","approved","sent","blocked","done"] = "new"
```

### 8.2 Workers

| Agent | Goal | Tools | Output |
|---|---|---|---|
| **Supervisor** | Turn an enquiry into a plan, route work, re-plan on failure | all | `plan`, status |
| **Quote** | Price each line in INR and AED with margin rules, Incoterm costs, FX source and timestamp | `pricing`, `fx`, `crm` | Quote with a transparent cost breakdown |
| **Duty (CEPA Duty Optimiser)** | Check whether UAE preferential duty may apply under the India-UAE CEPA, estimate the saving, list the origin evidence needed. Uses retrieved official texts and deterministic origin calculations (change-in-tariff-classification and regional-value-content tests). Always labels output "indicative, verify with a customs broker" | `hs_lookup` (RAG), `duty_origin` | Duty analysis with citations and AED saving estimate |
| **Docs** | Suggest HS codes (top 3 with confidence) and build the document pack (commercial invoice, packing list, origin-certificate checklist, import-requirements checklist) | `hs_lookup`, `doc_builder` | Documents plus cited requirements |
| **Document Consistency Checker** (inside Docs) | Cross-check the pack for mismatches: HS codes across documents, quantities and values, missing origin certificate, missing export-tax declaration, consignment and routing gaps, currency mistakes | `doc_checker` | List of findings with severity and fix suggestion |
| **Buyer Trust** | Produce **signals** for human review: public-sanctions-list name match, missing or odd company details, free-mail domain, mismatch between claimed and past behaviour. Never a verdict. | `sanctions_match`, `crm` | Signals with evidence and risk level |
| **Outreach** | Draft the reply and follow-ups in English and Arabic matching the buyer's language, via WhatsApp or email (draft-only) | `messaging`, `crm` | Drafts queued for approval |
| **Collections** | Track due dates, draft polite reminders, escalate overdue | `ledger`, `messaging` | Reminder drafts, ageing report |

### 8.3 Behavioural requirements
- Each worker returns **structured output** and a **confidence** score. Below the configured threshold, mark the item *needs human check*.
- Each worker gives a short "why" shown in the dashboard.
- Tool error handling: one retry, then re-plan, then escalate to a human. No silent failure.
- **Outcome learning:** when a human edits a draft or quote, store the diff and use it as a few-shot hint for similar future runs (simple, inspectable, per organisation).
- Every run writes an **Impact Ledger** entry (section 14).

---

## 9. Governance layer (the differentiator)

1. **Policy engine** (`policy_engine.py`): rules stored as YAML, evaluated deterministically, never by the LLM. Examples:
   - Any outbound message requires approval.
   - Quote margin below X% requires owner approval.
   - Any action touching bank details, payment instructions or account changes is **blocked** and escalated.
   - Messages to contacts not on the opt-in list are blocked.
   - Discount above Y% requires approval.
   - Any buyer with a sanctions-list name match is **held** for human review before any quote leaves.
   - Any duty-saving claim without a cited source is blocked from the buyer-facing draft.
2. **Approval queue:** each pending action shows what, why, evidence, risk level, and one-click approve, edit or reject.
3. **Audit log:** append-only and hash-chained so tampering is detectable. Records who or what did what, when, with which inputs and model.
4. **Kill switch:** pauses all agent actions per organisation.
5. **Risk scoring:** low, medium, high per action.
6. **Agent Passports (`passports.py`, `docs/passports/`):** for every agent, a machine-readable and human-readable one-pager: purpose, allowed tools, data it can touch, actions it can request, actions it can never take, risk class, owner, evaluation results, last review date. The UI has a Passports page.
7. **Seal-readiness (`docs/SEAL_READINESS.md`):** a checklist mapping Jisr's controls (transparency, accountability, data protection, human oversight, testing) so the team can apply for the Dubai AI Seal after obtaining a Dubai licence. Do not claim certification.
8. **Data protection report page:** data categories held, retention, redaction statistics.

For every rule, write one test that proves it triggers and one that proves it does not over-trigger.

---

## 10. Channels

- **WhatsApp:** implement a `Channel` interface with two backends: `whatsapp_sim.py` (local simulator with a chat UI, used for development and demos) and `whatsapp.py` (Cloud API, sandbox or test mode). The agent reads inbound messages, drafts replies, and a human approves. Replies inside the 24-hour customer-service window are the normal path. Template messages are a paid category and need pre-approval by Meta, so keep them minimal and configurable. Check Meta's current pricing page and developer docs before building the real backend, and record what you find in `docs/DECISIONS.md`.
- **Email:** draft-only (save as drafts or export), never auto-send.
- Verify webhook signatures on inbound messages and treat all inbound content as untrusted.

---

## 11. Frontend (Next.js)

Pages:
- **/demo:** one-click demo with a sample enquiry, visible agent timeline, "AED saved / risks caught" counter, and a hostile-message button.
- **/runs:** list and detail with a step-by-step trace (inputs, tool calls, outputs, cost).
- **/approvals:** the approval inbox (hero screen).
- **/audit:** searchable audit log with a hash-chain "verified" indicator.
- **/passports:** one card per agent.
- **/roi:** time saved, quotes produced, duty savings identified, document errors caught, baseline vs agent.
- **/chat:** WhatsApp simulator view.
- **/settings:** business profile (products, margins, currencies), policies, opt-in list, kill switch.

Design brief: clean, trustworthy, fast. Light and dark mode. Arabic (RTL) support for drafts. Every screen must be readable at a distance on a projector. No heavy effects on core screens.

---

## 12. Build phases and acceptance criteria

**Phase 0: Scaffold (day 1).** Repo, `CLAUDE.md`, Makefile, Docker, config, LLM router with a fake model. *Accept:* `make test` passes, `make run` shows a health endpoint.

**Phase 1: Vertical slice (days 2-4).** A thin, partly faked path from enquiry to approval to audit, running in the dashboard with stub agents. *Accept:* `make demo` shows an enquiry becoming a (fake) quote, going to the approval inbox, and writing an audit entry. This is the skeleton every later phase deepens, and it guarantees there is always a working demo.

**Phase 2: Data and eval first.** Synthetic generator (enquiries, adversarial, document sets), golden set, eval harness. *Accept:* `make eval` runs against the stub and prints a metrics table.

**Phase 3: Security core.** Redactor, injection guard, tests. *Accept:* all 30 adversarial samples flagged. PII never reaches a model in a captured-call test.

**Phase 4: Quote agent.** Extraction, pricing, FX, margin rules. *Accept:* extraction F1 above 0.9 on the synthetic set. Pricing math tested to the cent.

**Phase 5: Knowledge base, Duty agent, Docs agent.** KB ingestion, hybrid retrieval, HS top-3, origin calculations, document pack. *Accept:* every claim cited with document date. HS top-3 and duty-flag accuracy reported honestly. Unknowns flagged.

**Phase 6: Document Consistency Checker and Buyer Trust.** *Accept:* checker finds at least 90% of seeded mistakes with low false positives. Sanctions matching tested with near-miss names (no verdicts, signals only).

**Phase 7: Governance layer.** Policy engine, approvals, audit chain, kill switch, passports, Seal-readiness doc. *Accept:* every policy has trigger and non-trigger tests. Audit verification passes and detects a tampered row. All agents have passports.

**Phase 8: Channels, Outreach and Collections.** WhatsApp simulator, bilingual drafts, follow-up scheduler, ledger. *Accept:* drafts match buyer language. No send without approval.

**Phase 9: Supervisor and end-to-end.** Full run from enquiry to approved pack. *Accept:* the demo scenario completes in under 2 minutes with a paid model, and in a reasonable time with free models.

**Phase 10: Dashboard and pilot kit.** All pages, anonymiser, shadow mode (agent drafts, humans act), Impact Ledger, ROI page. *Accept:* a week of shadow-mode data produces a baseline-vs-agent report with method and sample size.

**Phase 11 (optional, only after Phase 12 works offline): 3D hero.** A small React Three Fiber "bridge" scene on the landing page only, lazy-loaded, with a static fallback. *Accept:* core screens unaffected, page still fast on a modest laptop. Cut this first if time is short.

**Phase 12: Submission and finals pack.** Docs, recorded demo checklist, pitch notes, `SUBMISSION.md` (the championship's required summary report), claims register, offline replay mode. *Accept:* the demo runs offline from replay with no network.

---

## 13. Evaluation (in the repo and in the pitch)

Report each metric honestly, including bad ones, in `docs/EVAL_REPORT.md`.

| Metric | Method |
|---|---|
| Extraction F1 | Field-level match against golden labels |
| Quote accuracy | Within tolerance of human quotes on pilot samples |
| HS top-1 and top-3 accuracy | Against labelled set |
| Duty-flag accuracy and citation precision | Against labelled cases and a manual review of 50 outputs |
| Document-mistake detection | Recall and false-positive rate on seeded sets |
| Groundedness | RAGAS plus manual spot-check |
| Injection and fraud detection | Recall and false-positive rate on adversarial set |
| Policy correctness | Policy test pass rate |
| Tool-call success and recovery rate | From traces |
| Latency and cost per run | Router log, per model profile |
| **Pilot impact** | Baseline vs agent: minutes per quote, % of leads followed up within 24h, document errors per 100 shipments, duty savings identified |

Include an **error analysis**: the five worst failures and what changed.

---

## 14. Impact Ledger and pilot method (`impact/ledger.py`, `docs/IMPACT_METHOD.md`)

Judges reward measured impact. Build a simple, honest measurement system:

- **Baseline (weeks 1-2):** the family business logs, for 10-20 real enquiries, the minutes spent on each step, whether the lead got a follow-up within 24 hours, and any document errors found later.
- **Shadow mode (weeks 6-7):** for new enquiries, Jisr drafts and humans act as usual. Log agent time, human edit time, differences between agent and human output, and what the agent caught that humans missed.
- **Per-run ledger fields:** `minutes_manual_est`, `minutes_agent_assisted`, `duty_saving_identified_aed` (indicative), `doc_errors_caught`, `risks_flagged`, `human_edits`, `accepted_as_is`.
- **Reporting:** show means and ranges and the **sample size**. Do not claim more than the data supports. Write limits in `IMPACT_METHOD.md`.
- Keep only anonymised records in the repo.

---

## 15. Security and prompt-injection design

- Treat every inbound message and attachment text as **untrusted data**. Wrap it in delimiters and tell the model that content inside is data, never instructions.
- The injection guard runs first (pattern checks plus a classifier prompt) and flags attempts to change instructions, reveal prompts, alter bank details or bypass approval.
- Even if the model is fooled, the **policy engine is deterministic** and still blocks the action. Say this in the pitch.
- Secrets live only in environment variables. Never log secrets or raw PII.
- Per-organisation row-level isolation, with a test that org A cannot read org B.
- Verify webhook signatures. Add a dependency audit step in CI.

---

## 16. Run instructions and expected output (write these in the README)

```
# first time
cp .env.example .env            # add free-tier keys for dev
make setup                      # installs backend and frontend deps
make db                         # starts Postgres+pgvector, runs migrations
make seed                       # synthetic data + KB ingestion

# run
make run                        # API on :8000, dashboard on :3000
make demo                       # opens /demo with a sample enquiry preloaded
make replay                     # offline replay of a recorded run (no network)

# verify
make test                       # unit and policy tests
make eval                       # metrics table, writes docs/EVAL_REPORT.md
```

**Expected output of the demo scenario:**
1. The enquiry arrives in the WhatsApp simulator, with PII masked in the trace view.
2. The timeline shows: Ingest, Guard (clean), Supervisor plan, Quote, Duty, Docs and Checker, Buyer Trust, Outreach.
3. The approval inbox shows a quote (INR and AED, margin visible), a CEPA analysis with citations and an indicative AED saving, the document pack with one flagged inconsistency, trust signals, and bilingual drafts.
4. Clicking **approve** writes an audit entry and marks the draft ready (or sent in simulator mode).
5. Clicking **hostile message** shows the guard flag and a blocked-by-policy audit entry.
6. The ROI page updates with the run's time saved, duty saving identified and errors caught.

---

## 17. Pilot kit (the user runs this with the family business)

**Baseline interview questions (60 minutes):**
1. Walk me through the last three enquiries, from first message to payment.
2. How long did each quote take, start to finish? Who is involved?
3. How many leads in the last 30 days were never followed up, and why?
4. What document mistakes delayed shipments in the last 6 months?
5. Do you use CEPA preferential duty on shipments to the UAE? How do you check eligibility and prepare origin documents?
6. How do you decide price and margin? What rules are in your head?
7. Which currencies and payment terms do you use? How do you check a new buyer?
8. What would you never let software send without checking?
9. What would make you trust this enough to use it weekly?

**Independent validation:** 3-5 interviews with UAE or GCC buyers and freight forwarders. Ask what slows them down when buying from Indian SMEs and what they check about a new supplier. Store only quotes you have permission to use.

**Teammates and ownership:** before anyone contributes code, agree in writing who owns what (the championship requires that you are the sole owner of the entered agent).

---

## 18. Limitations, future improvements, claims register

**Limitations to state honestly:** customs, tariff and origin guidance depends on the quality and date of the source documents and is indicative only; Arabic dialect handling is limited; WhatsApp production use needs Meta business verification; the pilot is one business, so results may not generalise; sanctions matching on public lists is a signal, not a legal screening; free-tier models are never used on real data.

**Future improvements:** more corridors, freight-booking agent, trade-finance and invoice-financing integrations, supplier discovery, voice agent for calls, e-invoicing integrations, Dubai AI Seal certification, two-sided buyer portal.

**Claims register (`docs/CLAIMS_REGISTER.md`):** a table with every number or fact used in the deck, video or report: the claim, source, date, and status (sourced / verify / own data). Seed it with:
- India-UAE trade USD 101.25B in FY 2025-26, about two-thirds non-oil, target USD 200B by 2032 (Times of Oman/ANI, 21 May 2026).
- CEPA in force 1 May 2022.
- Duty and origin-rule figures from vendor guides: mark **verify** until confirmed from official texts.
- WhatsApp pricing: mark **verify** until confirmed on Meta's current page.
No claim goes into the pitch unless it has a source or is the team's own measured data.

---

## 19. `CLAUDE.md` for the repo (create this in Phase 0)

```markdown
# Jisr AI: project memory for Claude Code
- Goal: championship entry (Best Business AI Agent). Priorities: working demo path, honest metrics, governance, clean code.
- Always keep `make demo` and `make replay` working. Never break the demo path.
- Every file: header comment, docstrings, beginner-friendly inline comments.
- Never invent tariff, origin, HS or legal facts. Cite retrieved sources with document date, or flag "needs human check".
- All LLM calls go through `backend/app/llm/router.py`. Never hardcode a model.
- Policy rules are deterministic code/YAML. Never move a safety decision into a prompt.
- No real customer data in repo or in free-tier calls. Only anonymised or synthetic data.
- After each phase: run `make test` and `make eval`, update docs/PROGRESS.md, then stop and report.
- Use subagents for parallel, independent work (for example tests vs docs), never for edits to the same file.
```

---

## 20. Viva Q&A and submission-ready explanation

Create `docs/VIVA_QA.md` with at least 30 questions and strong answers covering: why multi-agent, why LangGraph, how retrieval avoids hallucination, how the duty optimiser is checked, why the policy engine is deterministic, how redaction works, how the audit chain detects tampering, what the Agent Passport is, how evaluation was done, what the pilot measured and its limits, how the business makes money, what happens to IP, and how the grant would be used.

Create `docs/SUBMISSION.md`: the **summary report** the championship requires, in plain professional English (max 700 words):
- the problem and who has it,
- what the agent does (reason, plan, use tools, act) and its components,
- governance and data-protection approach,
- measured pilot results with sample size,
- business model and grant plan.

Also create `docs/PITCH_NOTES.md` with the 5-minute pitch script, a 2-3 minute video script with shot list, and a 12-slide deck outline, all using only claims from the claims register.

---

## 21. First instructions to Claude Code

1. Read this entire file and restate the plan in 10 lines.
2. Create `CLAUDE.md`, `docs/DECISIONS.md` and `docs/PROGRESS.md`.
3. Start **Phase 0 only.** Show the test output when done and wait for my go-ahead before Phase 1.

---

## 22. v3 upgrade: advanced agentic AI and advanced RAG

> Context for Claude Code: the UAE federal programme aims to move 50% of government services and operations to agentic AI within two years under the principle "human leads, AI enables", and Dubai is training its private sector in agentic AI. Jisr must show **real agentic depth** and **state-of-the-art retrieval**, while staying safe and governed. Every item below has acceptance tests. Build in the order given in 22.10.

### 22.1 Agentic RAG (the agent decides how to retrieve)

Replace "retrieve once, then answer" with a **retrieval agent** (`rag/agentic.py`), implemented as its own LangGraph subgraph:

1. **Plan:** given a question (e.g. "Does this item qualify for CEPA preferential duty?"), the planner splits it into sub-questions: *what is the HS code? what is the origin rule for that heading? what evidence is required? what is the UAE duty rate?*
2. **Route:** for each sub-question, choose the right source and tool: tariff hierarchy index, rules-of-origin index, procedures index, the deterministic `duty_origin` calculator, or "ask the human".
3. **Retrieve:** run several searches (hybrid BM25 + vector), in parallel where independent.
4. **Grade:** a grader scores each retrieved passage for relevance (structured output: `relevant | partially | irrelevant` plus reason).
5. **Answer with claims:** the answer is a list of atomic **claims**, each linked to one or more passage IDs.
6. **Grounding check:** a verifier checks each claim against its cited passages (`supported | unsupported | contradicted`). Unsupported claims are removed or the answer becomes "needs human check". **Numbers (rates, thresholds, percentages) must appear verbatim in a cited passage**, checked by code, not by the model.
7. **Budget:** hard limits on steps, searches and tokens per question (config). If the budget runs out, return what is supported plus a clear "incomplete" flag.

*Accept:* on the retrieval eval set (22.5), grounded-claim rate ≥ 95%; every numeric claim passes the verbatim check; budget limits enforced in tests.

### 22.2 Corrective loop, query rewriting and reranking

- **Two-stage retrieval:** stage 1 fetches a wide candidate set (e.g. top 50 hybrid); stage 2 **reranks** with a multilingual cross-encoder (e.g. a `bge-reranker-v2-m3`-class model run locally, behind an interface so it can be swapped) and keeps the top 5-8.
- **Fusion:** combine BM25 and vector results with Reciprocal Rank Fusion before reranking.
- **Corrective loop:** if the grader finds no relevant passage, or the best rerank score is below a threshold, the agent:
  1. rewrites the query (synonyms, product-description → tariff wording, English ↔ Arabic),
  2. tries query decomposition or a hypothetical-answer query,
  3. widens or narrows the filter (e.g. go up one level in the tariff hierarchy),
  4. retries at most N times (config), then escalates to "needs human check".
- Log every attempt in the trace so judges can watch the agent self-correct.

*Accept:* ablation table in `EVAL_REPORT.md` comparing (a) vector only, (b) hybrid, (c) hybrid + RRF, (d) + reranker, (e) + corrective loop, on recall@5, MRR and grounded-answer rate. Report honest numbers even if a step does not help.

### 22.3 Structure-aware (hierarchical) retrieval

Tariff and rules-of-origin texts are trees, not prose. Build `rag/structured/`:

- **Tariff tree parser:** section → chapter (2-digit) → heading (4-digit) → subheading (6-digit) → national line (8-digit or longer as used in the source). Each node stores code, description, parent, notes, duty rate if stated, source page and document date.
- **Rules-of-origin table parser:** for each product-specific rule, store the heading or subheading range it applies to, the rule type (wholly obtained, change in tariff classification, regional value content with threshold), and the source passage.
- **Index both as nodes**, not only as text chunks, with parent-child links.
- **Hierarchical search:** classify top-down (chapter → heading → subheading), keeping the top 3 at each level with scores. When a node is retrieved, automatically attach its parent notes and chapter notes (these often change meaning).
- **Exact-code lookup:** if the user or document gives a code, look it up directly before any semantic search.
- **Cross-reference resolver:** follow "see note X" and "excluding heading Y" references.
- **Consistency rule:** the HS code chosen in the quote, the invoice, the packing list and the origin checklist must be identical. The Document Consistency Checker enforces it.

*Accept:* HS top-1/top-3 accuracy at chapter, heading and subheading level reported separately; the correct rule of origin retrieved for ≥ 90% of labelled items; parent notes always attached (test).

### 22.4 Arabic-aware chunking and bilingual search

Research on mixed Arabic-English RAG reports that retrieval can be biased towards one language and can miss relevant passages in the other. Design for this:

- **Normalisation** (both indexing and query time, as a separate analyser so the original text is kept for display): remove tashkeel (diacritics) and tatweel, unify alef forms (أ إ آ → ا), unify ya/alef maqsura and ta marbuta variants for matching, normalise Arabic-Indic digits to Western digits, and keep both forms in the index.
- **Arabic BM25:** use an Arabic-aware tokenizer and light stemming (configurable), not an English analyser.
- **Chunking:** split on structural boundaries (article, clause, tariff node), never mid-sentence; handle right-to-left text and mixed-direction lines; keep tables as tables (row-wise chunks with headers repeated).
- **Bilingual pairing:** where a document exists in both Arabic and English, link the matching chunks so a hit in one language returns its pair.
- **Cross-lingual retrieval:** multilingual embeddings for both languages; for weak results, translate the query and search again (part of the corrective loop); merge with RRF.
- **Language-balanced results:** if the corpus has both languages, make sure the final set is not silently all one language when relevant passages exist in the other (measure it).
- **Display:** RTL rendering for Arabic in the dashboard; citations show the original-language text.

*Accept:* separate retrieval metrics for English queries, Arabic queries and cross-lingual queries; normalisation unit tests (diacritics, alef forms, digits); no regression on English.

### 22.5 Retrieval evaluation (separate from answer quality)

Build `eval/retrieval/`:

- **Labelled set:** at least 150 questions (≈ 40% English, 40% Arabic, 20% cross-lingual), each with the IDs of the passages that *must* be retrieved. Include tariff classification, rules-of-origin, procedure and document-requirement questions. Include ~20 "unanswerable" questions where the right behaviour is "I don't know".
- **Retrieval metrics:** recall@k (k = 5, 10), precision@k, MRR, nDCG@10, hierarchy-level accuracy.
- **Answer metrics (separate):** grounded-claim rate, numeric-claim verbatim pass rate, citation precision, correct refusal rate on unanswerable questions, RAGAS faithfulness and answer relevance.
- **Ablations** as in 22.2, per language.
- **Regression gate:** `make eval` fails CI if recall@5 or grounded-claim rate drops more than a set margin from the last committed baseline.
- The labelled set must be built by hand from the official documents (with help from the trade advisor), not generated by the same model that is being evaluated.

### 22.6 Autonomy levels (explicit and visible)

Define autonomy per action type in `governance/autonomy.yaml`, enforced by the policy engine, shown in each Agent Passport and on the dashboard:

| Level | Meaning | Examples in Jisr |
|---|---|---|
| L0 | Suggest only | Buyer trust signals, duty-saving estimates |
| L1 | Draft, human must approve before anything leaves | Quotes, buyer messages, document packs |
| L2 | Act automatically inside strict limits, human can undo | Internal reminders, re-computing FX, scheduling a follow-up draft |
| L3 | Act automatically, report after | Internal data tidying, re-indexing the knowledge base |
| Never | Blocked for agents | Bank-detail changes, payment status, messages to non-opted-in contacts |

- The organisation can raise or lower levels in Settings (owner only), with every change audited.
- Show a **"what the agent did on its own today"** panel.

*Accept:* tests that each action type is enforced at its level; changing a level writes an audit entry; "Never" actions cannot be enabled from the UI.

### 22.7 Interoperability: MCP tools and an A2A buyer-side agent

- **MCP tool server (`interop/mcp_server.py`):** expose Jisr's safe, read-only or draft-only tools (HS lookup, CEPA rule lookup, document consistency check, quote draft) as a Model Context Protocol server, so other agents and assistants can use them. Every MCP call passes through the same redaction, policy engine and audit log. Write tools stay behind approval.
- **Optional A2A demo (only after core phases pass):** a small **buyer-side agent** in `interop/buyer_agent/` (a UAE importer's procurement agent) that:
  1. discovers Jisr through an **Agent Card** (name, skills, auth, endpoint),
  2. sends an RFQ as an A2A task,
  3. receives status updates and the approved quote,
  4. can ask follow-up questions.
  Use the A2A protocol (now hosted at the Linux Foundation; check the current spec version and SDK before building, and record it in `DECISIONS.md`). The Jisr side treats everything arriving over A2A as **untrusted input** and still requires human approval before replying.
- Demo line: "Agents from different companies can trade safely, with humans still in charge."

*Accept:* MCP server passes a client test and every call appears in the audit log; the A2A demo runs end to end locally; a malicious A2A message is blocked by the injection guard and policy engine.

### 22.8 Agent evaluation beyond final answers (trajectories)

Research on tool-using agents shows that checking only the final answer misses wrong or unsafe steps. Add `eval/agent/`:

- **Scenario suite:** 50 end-to-end scenarios (normal, messy, Arabic, adversarial, tool failure, missing data) with expected outcomes **and** expected key steps.
- **Trajectory metrics:** correct tool chosen, correct arguments, unnecessary tool calls, steps to completion, recovery after an injected tool failure, policy violations attempted (must be zero allowed through), escalations when expected.
- **Outcome metrics:** task success, quote accuracy, document errors caught, latency, cost.
- **Judge:** use deterministic checks first; where an LLM judge is needed, use a different model from the one under test, give it a written rubric, and spot-check 20% by hand. Report judge agreement with human labels.
- **Repeatability:** run each scenario several times and report pass rate (agents are non-deterministic).

### 22.9 Memory design

- **Working memory:** the LangGraph state for one run.
- **Episodic memory:** past runs and outcomes per organisation (won/lost, human edits), retrievable as few-shot hints. Stored redacted.
- **Semantic memory:** the business profile, product catalogue, price rules, buyer preferences (owner-editable).
- **Rules:** memory never stores raw PII; each memory item has a source, a date and an expiry; the owner can view and delete memory in Settings; memory reads and writes are audited.

### 22.10 Updated phase plan (inserts into section 12)

| Phase | New work | Model / effort |
|---|---|---|
| 5a | Tariff tree and rules-of-origin parsers, hierarchical index, exact-code lookup | Opus 5.5, high |
| 5b | Arabic normalisation, analysers, bilingual pairing, cross-lingual search | Opus 5.5, high |
| 5c | Two-stage retrieval: RRF + reranker | Sonnet 5.5, medium |
| 5d | Agentic RAG subgraph: planner, router, grader, claim-level grounding, budgets | Opus 5.5, high |
| 5e | Corrective loop and query rewriting | Sonnet 5.5, medium |
| 5f | Retrieval eval set, metrics, ablation table, CI regression gate | Opus 5.5 to design, Haiku 5.5 to scaffold |
| 7a | Autonomy levels and "what the agent did on its own" panel | Opus 5.5, high |
| 9a | Trajectory evaluation suite | Opus 5.5, high |
| 9b | Memory design (episodic + semantic) | Sonnet 5.5, medium |
| 10a | MCP tool server | Sonnet 5.5, medium |
| 12a (optional) | A2A buyer-side agent demo | Sonnet 5.5, medium; only if all earlier phases pass |

Keep the **vertical slice (Phase 1) working at every step.** If time is short, cut in this order: 12a A2A demo → 11 3D hero → 10a MCP server → 5b cross-lingual extras (keep normalisation). Never cut: grounding check, policy engine, retrieval eval, offline replay.

### 22.11 New viva questions (add to `VIVA_QA.md`)

1. What is the difference between plain RAG and agentic RAG in Jisr?
2. How does the corrective loop decide that retrieval failed?
3. Why rerank, and what did the ablation show?
4. Why index the tariff as a tree instead of text chunks?
5. How do you stop the model inventing a duty rate?
6. How do you handle Arabic diacritics, alef forms and mixed-direction text?
7. How do you measure retrieval separately from answer quality?
8. What are your autonomy levels and who can change them?
9. What is MCP used for here, and how are MCP calls governed?
10. What does the A2A demo prove, and why is A2A input untrusted?
11. Why evaluate trajectories and not only final answers?
12. What does the agent remember, and how can the owner delete it?

### 22.12 First instruction for v3 if Phases 0-4 are already done

"Read section 22. Restate the new phases in 8 lines. Then start Phase 5a only, using plan mode first. Show the test output and wait for my go-ahead."
