# Demo checklist (run through it the day before and 1 hour before)

## Machine
- [ ] `git status` clean, on the submission commit; `make test` green; `make eval-gate` PASSED.
- [ ] Knowledge base built (`make kb`); `/health` shows the profile you expect (`prod` on stage, `replay` as fallback).
- [ ] `ANTHROPIC_API_KEY` set (prod); `LLM_DAILY_TOKEN_BUDGET` set; `budget.fallback_active` is false.
- [ ] `make record` done with `LLM_PROFILE=prod` after the last prompt change (refreshes the offline cassette).
- [ ] `make replay` tested with Wi-Fi OFF: all four samples and both voice notes work.
- [ ] Browser: zoom 100%, notifications off, `/en/demo` and `/ar/demo` open in tabs, 3D on, light theme.
- [ ] Second laptop: same commit, `make demo` running, same tabs.

## Data
- [ ] Demo organisation only (synthetic data); no real buyer data on screen.
- [ ] Approval inbox emptied or tidy; collections invoices seeded (3).
- [ ] Kill switch OFF before starting (check `/governance`).

## Flow (time it: ≤ 2 min 10 s)
- [ ] Arabic voice note → quote → CEPA card → document-mismatch sample → 3D doc pack → approve → audit verified.
- [ ] Hostile sample blocked (red gate) → `/governance` passports.
- [ ] Optional A2A: `uv --directory backend run python ../scripts/buyer_agent.py` in a visible terminal.

## Accessibility and polish
- [ ] Toggle dark theme once (3D re-colours), toggle Arabic once (RTL).
- [ ] Reduced-motion fallback known: 2D button.
