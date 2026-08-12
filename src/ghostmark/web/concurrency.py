"""Bounded, timed execution for file-processing routes.

Two protections in one small helper, both aimed at keeping a free public
instance from being exhausted by a handful of large/slow/concurrent
requests:

- A hard cap on how many processing jobs run at once (``max_concurrent``).
  Requests beyond the cap get an immediate 503 rather than queuing
  indefinitely.
- A hard wall-clock timeout per job. GhostMark's own processing is fast,
  but a hostile or malformed file could in principle make an underlying
  parser (Pillow, pikepdf) spin -- this guarantees the request thread
  doesn't hang forever.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import TypeVar

T = TypeVar("T")


class ServerBusyError(RuntimeError):
    """Raised when the concurrent-job limit is already reached."""


class ProcessingTimeoutError(RuntimeError):
    """Raised when a job exceeds its wall-clock budget."""


class BoundedRunner:
    def __init__(self, *, max_concurrent: int, timeout_seconds: int) -> None:
        self._semaphore = threading.Semaphore(max_concurrent)
        self._timeout = timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=max(4, max_concurrent * 2), thread_name_prefix="ghostmark-job")

    def run(self, fn: Callable[..., T], *args, **kwargs) -> T:
        if not self._semaphore.acquire(blocking=False):
            raise ServerBusyError("GhostMark is busy processing other requests. Please try again shortly.")
        try:
            future = self._executor.submit(fn, *args, **kwargs)
            try:
                return future.result(timeout=self._timeout)
            except FutureTimeoutError as exc:
                raise ProcessingTimeoutError("Processing this file took too long and was stopped.") from exc
        finally:
            self._semaphore.release()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
