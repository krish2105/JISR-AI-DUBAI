# Jisr AI — the governed bridge for India–UAE trade

**Category:** Best Business AI Agent · **Team:** solo founder (Indian handicraft export family business) · **Demo data:** synthetic

## The problem

India–UAE trade passed USD 100 billion a year, and the CEPA agreement offers preferential duty to Indian goods that
meet its origin rules (UAE MFN duty on our demo goods: 5%). But a small Jaipur exporter answers a Dubai buyer's WhatsApp enquiry by hand: reading it, pricing it in INR and
AED with freight, working out the HS code and the CEPA origin rule, preparing the documents, and replying in the
buyer's language. It takes hours, mistakes cost the duty preference, and invoice fraud ("our bank details changed")
is a constant risk.

## What Jisr does

A buyer writes or sends a **voice note** on WhatsApp, or their **procurement agent** sends an RFQ over A2A. Jisr:

1. masks personal data and screens the message for prompt injection and fraud;
2. extracts the request, prices it with live exchange rates, Incoterm charges and the owner's margin rules;
3. classifies each product in the **official UAE tariff** and finds its **CEPA origin rule**, citing the document,
   page and date, and shows the duty the preference could remove ("up to", because the preferential rate still needs
   a human);
4. drafts the invoice, packing list and certificate of origin and **checks them against each other**;
5. shows buyer-trust **signals** (never verdicts), including a UN sanctions-list name check;
6. drafts the reply in English or Arabic, and **waits for the owner's approval**.

## Why it can be trusted

- **Deterministic governance**: plain YAML policies and autonomy levels decide every outbound action; models can only
  propose. Bank-detail and payment actions are never performed; a kill switch stops everything; every step is in a
  hash-chained audit log.
- **Graded autonomy**: only a fixed-text acknowledgement is sent automatically, and only when every policy allows it.
- **Agent Passports**: each agent's tools are an enforced allow-list, shown with its measured quality.
- **Grounded answers**: every CEPA claim cites a retrieved official passage, and every number in it must appear
  verbatim in that passage, checked in code, not by a model.

## Measured, not claimed

All numbers come from reproducible eval runs (`docs/EVAL_REPORT.md`, CI gate). Synthetic data; real pilot pending.

| What | Result |
|---|---|
| Prompt-injection attacks succeeded (30 held-out, EN/AR) | **0 / 30** |
| End-to-end runs reaching the approval inbox (300 enquiries EN/AR/mixed + 2 voice notes) | **100%**, p95 1.9 s (offline model) |
| Trajectories: right agent path and actions, 50 scenarios × 3 runs | **100%**, identical path every run |
| Governance scenarios, unsafe automatic actions | **20/20**, **0** |
| CEPA answers: claims grounded / numbers verbatim | **100% / 100%** (92 test questions) |
| HS heading from a seller's phrase, top-1 / top-3 | **86.8% / 96.2%** (53 test phrases, advisor review pending) |
| Off-topic questions refused / answerable refused | 75% / 2.5% (the weak side, published) |
| Extraction F1 on 30 hand-written held-out enquiries | **0.976** |
| Document mistakes found / false alarms on clean sets | **100% / 0%** (incl. reordered, reformatted documents) |

## Interoperability

An **MCP server** lets assistants such as Claude Desktop use Jisr's analysis tools, but never approve or send.
An **A2A agent** lets a buyer's procurement agent request quotes; the quote returns only after the owner approves it,
and a hostile agent is rejected.

## Built with

Python, FastAPI, LangGraph, Claude (Opus 5.5 / Sonnet 5.5 / Haiku 5.5) in production with offline replay for the
finals; multilingual-e5 + bge reranker over the official sources; Next.js with Arabic RTL, light/dark themes and
four 3D views (agent graph, trade bridge, tariff tree, document pack), each with a 2D fallback.

## Honest limits and next steps

The UAE preferential schedule (CEPA Annex 2B) is not yet in the knowledge base, so savings are "up to". HS labels
need an advisor's review. Arabic questions over the English treaty text are the weakest retrieval case. Next: a
shadow-mode pilot with my family's export business, measuring time per quote and errors caught against the
baseline, then the Dubai AI Seal application.
