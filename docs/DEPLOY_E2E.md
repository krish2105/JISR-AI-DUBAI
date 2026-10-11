# Deploy end to end (founder checklist, with links)

Status on 2026-10-11: the **dashboard is already live** on Vercel (https://jisr-ai-eta.vercel.app), but the demo says
"Could not reach the Jisr API" until the API exists. Order matters: Neon -> Fly -> Vercel env var -> verify.
Detail and reasoning: `docs/DEPLOY.md`. Secrets (database URL, keys) you type yourself; never paste them into chat.

## 0. Already done
- [x] Vercel account, CLI logged in, project `jisr-ai` created, frontend deployed.
- [x] Fly CLI installed (`fly version`).
- [x] Knowledge-base index built (`data/kb_index`, 96 MB) and committed config (`fly.toml`, `deploy/api.Dockerfile`).

## 1. Database: Neon (free)
1. Sign up: https://console.neon.tech/signup (GitHub or Google login is fine).
2. Create project `jisr-ai`, Postgres 17, region **AWS Asia Pacific (Singapore)** or Europe (Frankfurt) - nearest to Mumbai/UAE
   that Neon offers. Dashboard: https://console.neon.tech/app/projects
3. Open **Connect** (top of the project page), choose the **pooled** connection string, copy it. Docs:
   https://neon.com/docs/connect/connect-from-any-app
4. Change the start from `postgresql://` to `postgresql+psycopg://`. Final shape:
   `postgresql+psycopg://USER:PASSWORD@ep-xxxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require`
   Keep it private. Tables are created on the first API start.

## 2. Hosting: Fly.io
1. Sign up: https://fly.io/app/sign-up . A card is required (https://fly.io/dashboard -> Billing). Pricing:
   https://fly.io/docs/about/pricing/ . This app runs one `shared-cpu-2x` machine with 4 GB, always on (judges).
2. Log in on this Mac:
   ```bash
   fly auth login
   ```
3. Create the app (the name is global; if `jisr-ai-api` is taken, add a suffix and put the same name in `fly.toml`, line `app = "..."`):
   ```bash
   cd "/Users/krishnamathurm4pro/Desktop/JISR AI DUBAI WIN/jisr-ai"
   fly apps create jisr-ai-api
   ```
4. Set the secrets (one command; replace the values; generate the token with `openssl rand -hex 32`):
   ```bash
   fly secrets set --app jisr-ai-api \
     DATABASE_URL='postgresql+psycopg://...' \
     CORS_ORIGINS='https://jisr-ai-eta.vercel.app' \
     MCP_TOKEN='<64 hex chars from openssl rand -hex 32>' \
     MCP_HOST='jisr-ai-api.fly.dev' \
     PUBLIC_BASE_URL='https://jisr-ai-api.fly.dev'
   ```
   Docs: https://fly.io/docs/flyctl/secrets-set/
5. Deploy from the repo root (remote builder; first build downloads ~3 GB of models, allow 15-30 min):
   ```bash
   fly deploy --app jisr-ai-api
   ```
6. Check it: https://jisr-ai-api.fly.dev/health . Expect `status: ok`, `llm_profile: fake` (offline model, free).
   Logs if needed: `fly logs --app jisr-ai-api`.

## 3. Connect the dashboard: Vercel
1. Set the API address (public value, not a secret):
   ```bash
   cd "/Users/krishnamathurm4pro/Desktop/JISR AI DUBAI WIN/jisr-ai/frontend"
   printf 'https://jisr-ai-api.fly.dev' | vercel env add NEXT_PUBLIC_API_URL production
   vercel deploy --prod --yes
   ```
   Or in the browser: https://vercel.com/krishnamathur008-1499s-projects/jisr-ai/settings/environment-variables ,
   then Deployments -> Redeploy. `NEXT_PUBLIC_*` is baked in at build time, so a redeploy is required.
2. Open https://jisr-ai-eta.vercel.app/en/demo and run a sample enquiry.

## 4. Verify (10 minutes)
- [ ] `/en/demo`: run the three samples; the timeline streams; approvals appear.
- [ ] `/ar/demo`: Arabic voice note sample; RTL layout.
- [ ] Approve one action, then `/en/audit`: chain shows "verified".
- [ ] `/en/governance`: passports load; hostile sample is blocked.
- [ ] Light and dark theme, 3D view and 2D fallback.
- [ ] Rate limit: the 21st run in an hour from one address returns "Demo limit".

## 5. Real Claude answers (optional, recommended before judging)
1. Key: https://console.anthropic.com/settings/keys (add credit: https://console.anthropic.com/settings/billing).
2. ```bash
   fly secrets set --app jisr-ai-api ANTHROPIC_API_KEY='sk-ant-...'
   fly deploy --app jisr-ai-api --env LLM_PROFILE=prod
   ```
3. `/health` must now show `llm_profile: prod` and `budget.fallback_active: false`.
4. Refresh the offline fallback with real answers: `LLM_PROFILE=prod make record`, commit `replay/`, redeploy.
5. Re-measure with the real model (extraction F1, latency, cost per quote) and add the numbers to `EVAL_REPORT.md`.

## 6. WhatsApp and voice notes (optional)
Follow `docs/WHATSAPP_SETUP.md`. Meta: https://developers.facebook.com/apps and
https://developers.facebook.com/docs/whatsapp/cloud-api/get-started . Needs `WHATSAPP_*` secrets on Fly and the webhook
URL in the Meta app.

## 7. Before the link goes to judges
- [ ] Phase 13 demo lock (no approve / no kill-switch for visitors): `docs/PLAN_95.md`. **Do this first.**
- [ ] Sanctions list: `make sanctions`, add `data/sanctions_public` to the image, redeploy (optional).
- [ ] Second laptop with `make replay` ready (finals need a live agent; this is the fallback).
- [ ] `docs/DEMO_CHECKLIST.md` the day before and one hour before.
- [ ] Spending: keep `LLM_DAILY_TOKEN_BUDGET` and `PUBLIC_RUNS_PER_HOUR` low; check https://fly.io/dashboard billing weekly.

## Useful commands
```bash
fly status --app jisr-ai-api          # machine state
fly logs --app jisr-ai-api            # live logs
fly secrets list --app jisr-ai-api    # names only, never values
fly scale memory 4096 --app jisr-ai-api
vercel ls                             # deployments
vercel rollback                       # previous production deployment
```

## Alternative host (free, no card): Hugging Face Space
Used when Fly needs a card. Same image, 2 vCPU / 16 GB RAM, sleeps after ~48 h without traffic.
1. Account + write token: https://huggingface.co/settings/tokens (role: Write).
2. Upload (asks for the token once, hidden input):
   ```bash
   cd "/Users/krishnamathurm4pro/Desktop/JISR AI DUBAI WIN/jisr-ai"
   uv run --with huggingface_hub python scripts/hf_space_deploy.py
   ```
3. Space -> Settings -> **Variables and secrets**:
   - Secret `DATABASE_URL` = the Neon pooled string (as copied; the backend adds `+psycopg`).
   - Secret `MCP_TOKEN` = `openssl rand -hex 32`.
   - Variables `CORS_ORIGINS=https://jisr-ai-eta.vercel.app`, `MCP_HOST=<user>-jisr-ai-api.hf.space`,
     `PUBLIC_BASE_URL=https://<user>-jisr-ai-api.hf.space`.
4. Wait for the build (15-30 min), then open `https://<user>-jisr-ai-api.hf.space/health`.
5. Vercel: `NEXT_PUBLIC_API_URL=https://<user>-jisr-ai-api.hf.space`, redeploy with `vercel deploy --prod`.
Caveat: a free Space is public, so the staged code, the public-document index and synthetic data are visible.
