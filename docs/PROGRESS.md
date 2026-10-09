# Progress

Updated after every phase: what was built, what was tested, what is next.

## Phase 1 — Vertical slice ✅ (2026-10-09)

**Built**
- **Contracts frozen** (`docs/CONTRACTS.md`): `RunEvent` (13 kinds), REST routes, `RunState`.
- **Agent graph** (LangGraph): ingest → guard → supervisor → quote → duty → docs → trust → outreach → governance, with a conditional shortcut to governance for bank-change attacks. Quote does RFQ extraction through the LLM router plus stub pricing. Outreach drafts EN/AR through the router. Duty, docs and trust are honest placeholders marked `stub`.
- **Governance v0**: `policies.yaml` + deterministic `policy_engine.py` (P-BANK-001 block, P-OUT-001 approval, P-INJ-001 high risk; strongest effect wins; safe default). Approval queue with approve/edit/reject. **Hash-chained audit log** per org with `verify_chain`. A simulated channel "sends" approved messages.
- **Security v0**: redactor (email/phone/IBAN tokens; raw messages never stored) and injection guard (EN + AR patterns). Hardened in Phase 3.
- **Live events**: persisted events, an in-process bus, an SSE endpoint with resume (`?after=` and `Last-Event-ID`).
- **Offline replay**: `replay` LLM profile + `make record` cassette. The whole pipeline (governance, approvals, audit) still runs for real; only model answers are replayed.
- **Dashboard** (Next.js 16): pearl light / midnight dark tokens with a no-flash theme toggle, `/en` + `/ar` static routes with true RTL, the live 2D agent graph (mirrors in Arabic), timeline with stub badges, counters, quote table, inline approval card, `/approvals` inbox, `/audit` with chain-verified badge, landing page with the bridge illustration (static fallback for the Phase 7 3D hero).
- `make demo`, `make replay`, `make record`, `make build`.

**Tested** (real output)
- `make test` → backend `54 passed` (policy trigger/non-trigger per rule, audit tamper + delete detection, per-org chains, UTC timestamps, redaction, guard on EN/AR/hostile samples, full slice EN/AR/hostile, approve/reject/edit, no double decision, cross-org 404s, SSE incl. resume, replay identical outputs, real data never recorded). Clean with `-W error::ResourceWarning`. Frontend `tsc` and `eslint` clean.
- `npm run build` → all pages prerendered statically for `en` and `ar`.
- **Browser check** (in-app browser): English run → graph lights up → quote → approve → "sent via simulator" → `done`. Arabic + dark theme hostile run → governance node red, attack shortcut highlighted, "3 risks caught", blocked. Audit page "Chain verified · 8 entries". Theme persists across reloads via cookie.
- Offline: API with `LLM_PROFILE=replay` ran all three samples from the cassette (`replay:fake-worker`), hostile still blocked.

**Bugs found and fixed in the browser check**
1. Timeline showed "+19800s": SQLite returned naive datetimes, read by the browser as IST. Fixed with a `UTCDateTime` column type (+ test).
2. Quote line total ≠ unit × qty (11,968.20 vs 23.94 × 500). Fixed: round the unit price first (+ to-the-cent test). Exactly the kind of error the Phase 6 consistency checker must catch.
3. SQLite "database is locked" when governance emitted events inside its own write transaction. Fixed: commit first, then emit; WAL mode.
4. React dev warning for the theme script. Fixed: Client Component `InlineScript` per the Next 16 docs.

**Known gaps (planned)**
- Agent "why" explanations are English even in the Arabic UI (rendered with `dir="auto"`). Bilingual explanations come with the real agents (Phases 4–9).
- The cassette currently holds `fake` answers. Run `LLM_PROFILE=prod make record` once an Anthropic key is in `.env`.
- No auth yet (demo org via `X-Org-Id`); real auth before the pilot (Phase 10).
- Postgres path tested in Phase 0 (`make up`), not yet with the Phase 1 tables; it is exercised in Phase 2.

**Next: Phase 2, data and eval first**
- Synthetic generator: 300 enquiries (EN/AR/mixed), 30 adversarial, 40 document sets with seeded mistakes, labels.
- Golden set + `make eval` harness printing a metrics table (and the CI regression gate skeleton).
