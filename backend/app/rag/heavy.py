"""
heavy.py — Run CPU-heavy retrieval work (embeddings, cross-encoder reranking) in worker threads, a few at a time.

Why (Phase 20 load test, DECISIONS H6): the ONNX models already use every core for one query. Twenty enquiries
arriving together started twenty such computations at once and the machine thrashed (requests stalled for tens of
seconds). A small semaphore queues the heavy steps instead, so each finishes quickly and the API stays responsive.
"""

import asyncio
from collections.abc import Callable

from app.config import get_settings

_semaphores: dict[int, asyncio.Semaphore] = {}


def _semaphore() -> asyncio.Semaphore:
    """One semaphore per event loop (tests create several loops)."""
    loop = asyncio.get_running_loop()
    key = id(loop)
    if key not in _semaphores:
        _semaphores[key] = asyncio.Semaphore(max(1, get_settings().retrieval_concurrency))
    return _semaphores[key]


async def run_heavy[T](fn: Callable[..., T], *args) -> T:
    """Run `fn(*args)` in a worker thread, at most RETRIEVAL_CONCURRENCY at a time."""
    async with _semaphore():
        return await asyncio.to_thread(fn, *args)
