# Jisr dashboard (Next.js 16)

Pages: `/[lang]` overview, `/[lang]/demo` live demo, `/[lang]/approvals` inbox, `/[lang]/audit` audit log,
where `lang` is `en` or `ar` (right-to-left).

- Run with the API: `make demo` from the repo root (API :8000 + dashboard :3000).
- API URL: `NEXT_PUBLIC_API_URL` (see `.env.local.example`), default `http://localhost:8000`.
- Design tokens: `src/app/globals.css` (pearl light default, midnight dark via `<html data-theme>`).
- Strings: `src/i18n/dictionaries.ts` (English and Arabic must have the same keys; TypeScript enforces it).
- Live data: `src/lib/useRunEvents.ts` (SSE) → `src/lib/runView.ts` (pure reducer) → graph, timeline, counters.
- Contracts with the backend: `../docs/CONTRACTS.md`.
