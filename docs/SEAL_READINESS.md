# Dubai AI Seal — readiness

The **Dubai AI Seal** is issued by the Dubai Centre for Artificial Intelligence (DCAI, Dubai Future Foundation) to
**companies licensed in Dubai** that offer AI products or services. It is free to apply (dub.ai/ai-seal), gives a
serial number and a classification, and is required to partner on UAE / Dubai government projects. Public sources
describe the assessment areas below; **the exact current criteria and tiers must be confirmed on dub.ai before
applying** (secondary sources disagree on tiers).

Sources: WAM, "Dubai Centre for Artificial Intelligence launches 'AI Seal'" (Jan 2025); Dubai Media Office,
"Dubai AI Seal sets industry standard for trusted AI" (15 May 2025); Gulf News, "'AI Seal' now mandatory for UAE,
Dubai government partnerships" (2025).

## What only the founder can supply

| Requirement | Status |
|---|---|
| A Dubai trade licence covering AI products/services | **to obtain** (also needed for the championship's eligibility check) |
| Team: number of AI specialists, roles | to describe (solo founder + advisor) |
| Current and future projects, public/private partnerships | pilot with the family export business (shadow mode); Dubai buyers/forwarders interviewed |

## What the product can evidence (each row points to something that runs)

| Assessment area (public sources) | Jisr evidence | Where |
|---|---|---|
| Nature of AI activity | Multi-agent system for India→UAE trade: quote, CEPA duty, documents, buyer trust, bilingual replies | `backend/app/agents/`, `docs/PLAN.md` |
| Data security | Personal data masked before any model sees it (redaction recall 1.000); free-tier models only ever get synthetic data (enforced in the router); org isolation on every table | `app/security/redactor.py`, `app/llm/router.py`, `docs/EVAL_REPORT.md` |
| Transparency | Every CEPA fact cites the official document, issuer, date and page; numbers must appear verbatim in the cited passage (grounded 1.000 on the test split); live timeline of every agent step | `app/rag/agentic.py` (grounding), DutyCard, Timeline |
| Accountability | Deterministic policy engine + autonomy levels (NEVER/L0–L3); human approval for every price or document; hash-chained audit log with a verify endpoint; kill switch | `app/governance/`, `/governance`, `/audit` |
| Safety / robustness | Injection guard (30/30 held-out attacks caught, 0 succeeded); bank-detail changes are blocked by policy whatever a model says; tool allow-lists enforced per agent (Agent Passports) | `app/security/`, `eval/suites/redteam.py`, `passports.yaml` |
| Fairness | Buyer trust shows *signals with evidence*, never a score or verdict; sanctions matching says "possible match, for review"; positive signals shown too | `app/tools/buyer_trust.py`, DECISIONS D8 |
| Measured quality (maturity) | Every quality number comes from a reproducible eval run with a CI gate; known weaknesses are reported (Arabic→English treaty retrieval, "no tariff line fits" detection) | `backend/eval/`, `docs/EVAL_REPORT.md` |
| Human oversight | Approval inbox with edit-before-send; "what the agent did on its own" view (only fixed-text acknowledgements qualify) | `/approvals`, `/governance` |

## Before applying

1. Confirm the criteria and tiers on dub.ai/ai-seal and adjust this table to their wording.
2. Obtain the Dubai licence (DED / free zone) that covers AI services.
3. Attach: this file, `docs/EVAL_REPORT.md`, the data-protection page (Phase 12) and a short pilot summary.
