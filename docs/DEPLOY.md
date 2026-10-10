# Deploying the hosted demo (founder steps)

Target: dashboard on **Vercel**, API on **Fly.io**, database on **Neon** (Postgres). A no-login demo for judges,
protected by a per-visitor rate limit and a daily model budget. Nothing here is automatic: you run these steps with
your accounts. Status: the configuration is written and tested locally; the image has not been built on this
machine (it downloads ~3 GB of models).

## 1. Database: Neon
1. Create a Neon project (region close to Mumbai or Frankfurt), copy the connection string.
2. Use it as `DATABASE_URL` in the form `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`.
   Tables are created on first start (additive upgrades only, DECISIONS C1).

## 2. API: Fly.io
Prerequisites: `fly` CLI, logged in; the knowledge base built locally (`make kb`; the image copies `data/kb_index`).
```bash
fly launch --no-deploy --copy-config        # keeps fly.toml; pick an app name, then edit `app` in fly.toml
```
```bash
fly secrets set ANTHROPIC_API_KEY=... DATABASE_URL=... CORS_ORIGINS=https://<your-vercel-domain> MCP_TOKEN=<long random> MCP_HOST=<app>.fly.dev
```
```bash
fly deploy
```
Check `https://<app>.fly.dev/health`: `llm_profile` must be `prod` and `budget.fallback_active` false.

Optional: WhatsApp (`WHATSAPP_*` secrets, docs/WHATSAPP_SETUP.md), sanctions list (`make sanctions` before deploying,
then add `data/sanctions_public` to the image).

## 3. Dashboard: Vercel
1. Import the repository, root directory `frontend`.
2. Environment variable `NEXT_PUBLIC_API_URL=https://<app>.fly.dev`.
3. Deploy; open `/en/demo`.

## 4. Before sharing the link
- Run `make record` with `LLM_PROFILE=prod` locally to refresh the offline cassette (finals fallback).
- Try the three sample enquiries and both voice notes on the hosted link, in light and dark, EN and AR.
- Confirm the rate limit: the 21st run within an hour from one address returns "Demo limit".
- Keep `PUBLIC_RUNS_PER_HOUR` and `LLM_DAILY_TOKEN_BUDGET` conservative; past the budget, answers come from the offline
  model and are labelled `budget-fallback`, so the demo never breaks.

## MCP (optional)
Assistants that speak MCP can connect to `https://<app>.fly.dev/mcp/` with `Authorization: Bearer <MCP_TOKEN>`.
Locally (Claude Desktop, stdio): `uv --directory backend run python -m app.interop.mcp_server`.
The MCP tools can analyse and read, never approve or send (DECISIONS I1).
