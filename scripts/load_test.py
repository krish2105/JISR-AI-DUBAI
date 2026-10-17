"""
load_test.py — Concurrent enquiries against a running Jisr API (Phase 20).

Creates a demo sandbox, starts N enquiries at once, waits until each reaches the approval step (or ends), and reports
latency p50/p95/max and errors. Run against a server started with DEMO_STEP_DELAY_MS=0 to measure the pipeline,
not the demo pacing:

    DEMO_STEP_DELAY_MS=0 uv --directory backend run uvicorn app.main:app --port 8010 &
    uv --directory backend run python ../scripts/load_test.py --api http://localhost:8010 --concurrency 20

Restart the server between measurements: retrieval results are cached in memory, so a second run looks faster.
"""

import argparse
import asyncio
import statistics
import time

import httpx

# Distinct products per enquiry, so the HS/CEPA retrieval cache does not hide the real cost (each pair is new).
PRODUCTS = ["brass diya lamps", "cotton table runners", "jute shopping bags", "embroidered cushion covers",
            "marble coasters", "pottery vases", "pashmina shawls", "silk scarves", "wooden gift boxes",
            "leather journals", "sandalwood incense", "brass serving trays", "cotton bath towels",
            "terracotta planters", "copper water bottles", "quilted bedspreads", "block-printed tablecloths",
            "carved wooden elephants", "glass bangles", "camel bone boxes"]
TERMS = ["CIF Jebel Ali", "FOB Mundra", "DAP Dubai", "CIF Dammam"]


def message(i: int) -> str:
    a, b = PRODUCTS[i % len(PRODUCTS)], PRODUCTS[(i * 7 + 3) % len(PRODUCTS)]
    return f"We need {100 + 10 * i} {a} and {50 + 5 * i} {b}, {TERMS[i % len(TERMS)]}. Please quote."

TERMINAL = {"needs_approval", "sent", "done", "blocked"}


async def one(client: httpx.AsyncClient, headers: dict, i: int) -> tuple[float, str]:
    started = time.perf_counter()
    try:
        return await _one(client, headers, i, started)
    except httpx.HTTPError as exc:                      # report, don't crash: errors are part of the result
        return time.perf_counter() - started, f"error:{type(exc).__name__}"


async def _one(client: httpx.AsyncClient, headers: dict, i: int, started: float) -> tuple[float, str]:
    r = await client.post("/runs", json={"message": message(i)}, headers=headers)
    if r.status_code != 201:
        return time.perf_counter() - started, f"start {r.status_code}"
    run_id = r.json()["run_id"]
    for _ in range(600):
        status = (await client.get(f"/runs/{run_id}", headers=headers)).json().get("status")
        if status in TERMINAL:
            return time.perf_counter() - started, status
        await asyncio.sleep(0.2)
    return time.perf_counter() - started, "timeout"


async def main(api: str, concurrency: int) -> None:
    async with httpx.AsyncClient(base_url=api, timeout=60) as client:
        token = (await client.post("/auth/demo")).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        started = time.perf_counter()
        results = await asyncio.gather(*(one(client, headers, i) for i in range(concurrency)))
        wall = time.perf_counter() - started
    latencies = sorted(t for t, _ in results)
    outcomes: dict[str, int] = {}
    for _, status in results:
        outcomes[status] = outcomes.get(status, 0) + 1
    p95 = latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))]
    print(f"concurrency={concurrency} wall={wall:.1f}s p50={statistics.median(latencies):.2f}s p95={p95:.2f}s "
          f"max={latencies[-1]:.2f}s outcomes={outcomes}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(main(args.api, args.concurrency))
