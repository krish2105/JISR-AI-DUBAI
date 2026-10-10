"""
passports.py — Agent Passports: identity, permissions, autonomy and measured quality of every agent.

Why this file exists:
    A business owner (or a judge, or an auditor) should be able to ask "what is this agent allowed to do, and how
    good is it?" and get an answer backed by configuration and measurements, not a slide. The tool list is
    ENFORCED: RunEmitter refuses a tool call that is not in the agent's passport. Autonomy comes from
    autonomy.yaml, metrics from the latest eval results, activity from the event log.
"""

from functools import lru_cache
from pathlib import Path

import yaml

PASSPORTS_PATH = Path(__file__).with_name("passports.yaml")
SYSTEM_ACTORS = {"system", "channel"}                # infrastructure events, not agents


class ToolNotAllowed(PermissionError):
    """An agent tried to call a tool outside its passport."""


@lru_cache
def load_passports(path: Path = PASSPORTS_PATH) -> dict[str, dict]:
    """agent id -> passport (as written in passports.yaml)."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))["agents"]


def check_tool(agent: str, tool: str) -> None:
    """Raise ToolNotAllowed unless the agent's passport lists the tool (unknown agents may call nothing)."""
    if agent in SYSTEM_ACTORS or agent.startswith("human:"):
        return
    passport = load_passports().get(agent)
    if passport is None or tool not in (passport.get("tools") or []):
        raise ToolNotAllowed(f"Agent '{agent}' is not allowed to call '{tool}' (not in its passport).")


def passports_view(latest_results: dict[str, dict], autonomy_for, activity: dict[str, dict]) -> list[dict]:
    """Passports enriched with autonomy levels, live eval metrics and recent activity, for the dashboard."""
    out = []
    for agent_id, p in load_passports().items():
        metrics = []
        for suite, names in (p.get("metrics") or {}).items():
            res = latest_results.get(suite)
            for name in names:
                value = (res or {}).get("metrics", {}).get(name)
                metrics.append({"suite": suite, "metric": name, "value": value,
                                "result_file": f"{suite} @ {res['timestamp']}" if res else None,
                                "git_sha": (res or {}).get("git_sha")})
        out.append({"id": agent_id, **{k: v for k, v in p.items() if k != "metrics"},
                    "autonomy": {a: autonomy_for(a) for a in p.get("actions", [])},
                    "metrics": metrics, "activity_24h": activity.get(agent_id, {})})
    return out
