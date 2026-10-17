"""Publish the Jisr API to a Hugging Face Docker Space (free CPU: 2 vCPU, 16 GB RAM, no card).

Usage (from the repo root):
    uv run --with huggingface_hub python scripts/hf_space_deploy.py --dry-run     # stage + report only
    uv run --with huggingface_hub python scripts/hf_space_deploy.py               # create the Space and upload

The first real run asks for a Hugging Face *write* token (hidden input, kept in Hugging Face's own token cache,
never in this repo). Secrets such as DATABASE_URL are NOT uploaded: set them in the Space settings.
Only the paths the API image needs are staged (same list as deploy/api.Dockerfile); nothing else leaves the repo.
"""

from __future__ import annotations

import argparse
import getpass
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / ".hf-space-stage"
SPACE_NAME = "jisr-ai-api"

INCLUDE = [
    "backend/pyproject.toml",
    "backend/uv.lock",
    "backend/app",
    "backend/alembic.ini",
    "backend/migrations",
    "backend/eval",
    "data/kb_index",
    "data/kb_sources/sources.csv",
    "data/kb_sources/download_status.csv",
    "data/gold",
    "data/synthetic",
    "replay",
]
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", ".pytest_cache", ".ruff_cache", ".DS_Store", "*.db")

README = """---
title: Jisr AI API
emoji: 🌉
colorFrom: indigo
colorTo: yellow
sdk: docker
app_port: 8000
pinned: false
short_description: Governed India-UAE trade agent API (demo backend)
---

Backend for the Jisr AI dashboard: a governed multi-agent assistant that turns an India to UAE buyer enquiry into a
priced quote, a cited CEPA duty analysis, checked draft documents and buyer signals, with human approval before
anything is sent. Demo organisation, synthetic data only. Health check: `/health`.
"""

DOCKER_ENV = """# --- Hugging Face Space settings (non-secret; secrets go in the Space settings) ---
ENV APP_ENV=prod LLM_PROFILE=fake FX_PROVIDER=live DEMO_STEP_DELAY_MS=300 \\
    PUBLIC_RUNS_PER_HOUR=20 LLM_DAILY_TOKEN_BUDGET=2000000 TRACE_DIR=/tmp/traces
# Spaces run the container as a non-root user: make the app and model cache readable and the app dir writable.
RUN mkdir -p /tmp/traces && chmod -R a+rwX /app /models
"""


def stage() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    for rel in INCLUDE:
        src, dst = ROOT / rel, STAGE / rel
        if not src.exists():
            sys.exit(f"missing {rel}: run `make kb` first" if "kb_index" in rel else f"missing {rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, ignore=SKIP) if src.is_dir() else shutil.copy2(src, dst)
    dockerfile = (ROOT / "deploy" / "api.Dockerfile").read_text()
    if "EXPOSE 8000" not in dockerfile:
        sys.exit("deploy/api.Dockerfile changed shape (no EXPOSE 8000); update this script")
    (STAGE / "Dockerfile").write_text(dockerfile.replace("EXPOSE 8000", DOCKER_ENV + "\nEXPOSE 8000", 1))
    (STAGE / "README.md").write_text(README)


def report() -> None:
    files = [p for p in STAGE.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print(f"staged {len(files)} files, {total / 1e6:.0f} MB in {STAGE}")
    for p in sorted(files, key=lambda q: -q.stat().st_size)[:5]:
        print(f"  {p.stat().st_size / 1e6:6.1f} MB  {p.relative_to(STAGE)}")
    risky = [p for p in files if p.name.startswith(".env") or p.suffix in {".pem", ".key"}]
    if risky:
        sys.exit(f"refusing to upload secret-looking files: {[str(p.relative_to(STAGE)) for p in risky]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="stage and report, do not upload")
    ap.add_argument("--space", help="owner/name (default: <your user>/jisr-ai-api)")
    args = ap.parse_args()

    stage()
    report()
    if args.dry_run:
        print("dry run: nothing uploaded")
        return

    from huggingface_hub import HfApi, get_token, login

    token = get_token()
    if not token:
        token = getpass.getpass("Hugging Face WRITE token (input hidden): ").strip()
        login(token=token, add_to_git_credential=False)
    api = HfApi(token=token)
    owner = api.whoami()["name"]
    repo_id = args.space or f"{owner}/{SPACE_NAME}"
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
    api.upload_folder(folder_path=str(STAGE), repo_id=repo_id, repo_type="space", commit_message="Deploy Jisr API")
    slug = repo_id.replace("/", "-").replace("_", "-").lower()
    print(f"uploaded. Settings: https://huggingface.co/spaces/{repo_id}/settings")
    print(f"API (after the build): https://{slug}.hf.space/health")


if __name__ == "__main__":
    main()
