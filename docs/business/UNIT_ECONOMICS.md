# Unit economics (Phase 19) — formulas now, measured inputs after the pilot

Rule: every number below is either a published price (dated), a plan price from `backend/app/billing/plans.yaml`
(a hypothesis), or a **measured** value from a result file. Nothing is typed in from memory.

## Inputs

| Input | Value | Source |
|---|---|---|
| Plan price (INR / month) | Starter 4,999 · Growth 14,999 | `plans.yaml` (hypothesis, to validate) |
| Included enquiries | Starter 150 · Growth 750 | `plans.yaml` |
| Model cost per enquiry (C_q) | **to measure** | `cost_per_quote_usd` in `backend/eval/results/e2e_*.json` with `EVAL_PROFILE=prod` |
| Model prices | Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50 per MTok | `backend/app/llm/pricing.yaml` (as of 2026-10-06) |
| Hosting per month (H) | **to measure** (one 4 GB API machine, Postgres, dashboard) | host invoices once deployed |
| Customers on the platform (N) | — | |
| USD→INR rate (r) | use the rate on the invoice date | |

## Formulas

- Variable cost per customer per month = `enquiries_used × C_q × r`
- Shared cost per customer per month = `H / N`
- Gross margin per customer = `(price − variable − shared) / price`
- Break-even customers = `H / (price − enquiries_used × C_q × r)`

## Worked example (illustrative, replace every bracket with a measured value)

Starter customer using all 150 enquiries: variable cost = `150 × [C_q] × [r]`. With N customers sharing hosting
of `[H]`, gross margin = `(4,999 − 150·[C_q]·[r] − [H]/N) / 4,999`. Fill this table after the Claude evaluation run and the
first hosting invoice, and quote only the filled version.

## Levers if margin is thin

Prompt caching on the fixed system prompts; Haiku for classification steps; lower effort on routine extraction;
offline answers for repeated enquiries (the retrieval cache already avoids repeated reranking); a hosted reranker
instead of a bigger CPU machine (see the load test, DECISIONS H6).
