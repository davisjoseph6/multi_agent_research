"""DISPOSABLE synthetic SQLite: expose process-local FIFO limits under contention.

Each spawned process constructs its OWN store instance and (when requested)
its OWN FIFO condition/ticket counters. They share only a fresh temporary
SQLite file. No real students, accounts, HTTP server, enrollment, or VPS.

This *probe* deliberately uses a dedicated synthetic counter table rather than
running the full educational journey; it tests multi-process writer admission
and the integrity of concurrent SQL updates, not study behavior or capacity.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from queue import Empty
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter, sleep
import sqlite3

from .pilot_concurrency_rehearsal import _MeasuredSyntheticStore, _percentile
from .pilot_full_journey_rehearsal import _FIFOMeasuredSyntheticStore


def _thread_writes(store, count: int, hold_ms: int) -> list[dict]:
    records = []
    for _ in range(count):
        store.begin_action_capture()
        start = perf_counter()
        with store._transaction() as db:
            db.execute(
                "UPDATE pilot_writer_probe SET n=n+1 WHERE id=1",
            )
            sleep(hold_ms / 1000)
        total = (perf_counter() - start) * 1000
        entries = store.finish_action_capture()
        held = store.finish_transaction_hold_capture()
        queued = (store.finish_queue_capture()
                  if isinstance(store, _FIFOMeasuredSyntheticStore) else [0.0])
        if (len(entries) != 1 or len(held) != 1 or len(queued) != 1
                or "body_ms" not in held[0]
                or "finalize_ms" not in held[0]):
            raise AssertionError("missing synthetic SQLite timing")
        records.append({
            "total_ms": total,
            "entry_ms": entries[0],
            "queue_ms": queued[0],
            "body_ms": held[0]["body_ms"],
            "finalize_ms": held[0]["finalize_ms"],
        })
    return records


def _subprocess_worker(
    database: str, content_dir: str, mode: str, threads: int,
    operations: int, hold_ms: int, begin, results, worker_number: int,
):
    """Spawn target must be top-level for multiprocessing.spawn."""
    try:
        klass = (_FIFOMeasuredSyntheticStore if mode == "fifo"
                 else _MeasuredSyntheticStore)
        store = klass(
            Path(database), items_path=Path(content_dir) / "items.csv",
            resources_path=Path(content_dir) / "resources.csv",
            simulations=41,
        )
        results.put({"kind": "ready", "worker": worker_number})
        if not begin.wait(25):
            raise TimeoutError("rehearsal start gate expired")
        with ThreadPoolExecutor(max_workers=threads) as pool:
            batches = list(pool.map(
                lambda _: _thread_writes(store, operations, hold_ms),
                range(threads),
            ))
        records = [item for batch in batches for item in batch]
        results.put({
            "kind": "outcome",
            "worker": worker_number,
            "operation_count": len(records),
            "timing_records": records,
        })
    except BaseException as error:
        results.put({
            "kind": "error",
            "worker": worker_number,
            "error_type": type(error).__name__,
            # No database path or private detail is released in error text.
        })


def _metrics(values: list[float]) -> dict:
    return {
        "p50": round(_percentile(values, 50), 3),
        "p95": round(_percentile(values, 95), 3),
        "p99": round(_percentile(values, 99), 3),
        "max": round(max(values, default=0), 3),
    }


def run_multiprocess_probe(
    *, processes: int = 2, threads_per_process: int = 2,
    operations_per_thread: int = 3, hold_ms: int = 8,
    writer_admission: str = "fifo",
) -> dict:
    if (type(processes) is not int or not 2 <= processes <= 4
            or type(threads_per_process) is not int
            or not 1 <= threads_per_process <= 4
            or type(operations_per_thread) is not int
            or not 1 <= operations_per_thread <= 20
            or type(hold_ms) is not int or not 0 <= hold_ms <= 30
            or writer_admission not in ("fifo", "native")
            or type(writer_admission) is not str):
        raise ValueError("invalid disposable synthetic multiprocess test scenario")

    content = Path(__file__).resolve().parents[2] / "docs/rct_candidate_v1"
    expected = processes * threads_per_process * operations_per_thread
    outcomes, errors = [], []
    start = perf_counter()
    with TemporaryDirectory(prefix="ijcai-probe-multiprocess-synthetic-") as tmp:
        database = Path(tmp) / "synthetic_probe.sqlite3"
        # Schema initialization must occur before competing processes start.
        initial = _MeasuredSyntheticStore(
            database, items_path=content / "items.csv",
            resources_path=content / "resources.csv", simulations=41,
        )
        with initial._transaction() as db:
            db.execute(
                "CREATE TABLE pilot_writer_probe "
                "(id INTEGER PRIMARY KEY, n INTEGER NOT NULL)"
            )
            db.execute("INSERT INTO pilot_writer_probe VALUES(1,0)")

        ctx = get_context("spawn")
        begin = ctx.Event()
        messages = ctx.Queue()
        children = [
            ctx.Process(
                target=_subprocess_worker,
                args=(
                    str(database), str(content), writer_admission,
                    threads_per_process, operations_per_thread, hold_ms,
                    begin, messages, index,
                ),
            ) for index in range(processes)
        ]
        try:
            for child in children:
                child.start()
            ready = set()
            while len(ready) < processes:
                try:
                    message = messages.get(timeout=25)
                except Empty:
                    errors.append({"error_type": "WorkerInitializationTimeout"})
                    break
                if message.get("kind") == "ready":
                    ready.add(message["worker"])
                else:
                    errors.append(message)
                    break
            if not errors:
                begin.set()
                for _ in range(processes):
                    try:
                        message = messages.get(timeout=45)
                    except Empty:
                        errors.append({"error_type": "WorkerResultTimeout"})
                        break
                    if message.get("kind") == "outcome":
                        outcomes.append(message)
                    else:
                        errors.append(message)
            begin.set()  # unblock child processes even if one failed
            for child in children:
                child.join(timeout=10)
                if child.is_alive() or child.exitcode != 0:
                    errors.append({
                        "error_type": "SubprocessDidNotExitCleanly"
                    })
        finally:
            begin.set()
            for child in children:
                if child.is_alive():
                    child.terminate()
                    child.join(timeout=5)
            messages.close()
            messages.join_thread()

        with sqlite3.connect(database, timeout=5) as db:
            final_value = db.execute(
                "SELECT n FROM pilot_writer_probe WHERE id=1"
            ).fetchone()[0]
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    timings = [item for out in outcomes for item in out["timing_records"]]
    passed = (
        not errors and len(outcomes) == processes and
        final_value == expected and integrity == "ok" and
        len(timings) == expected
    )
    return {
        "kind": "MULTIPROCESS_DISPOSABLE_SQLITE_WRITER_PROBE_SYNTHETIC_ONLY",
        "result": "PASS" if passed else "FAIL",
        "journal_mode": "DELETE",
        "writer_admission": writer_admission,
        "processes": processes,
        "threads_per_process": threads_per_process,
        "separate_store_per_process": True,
        "cross_process_fifo_coordination": False,
        "expected_updates": expected,
        "observed_updates": final_value,
        "integrity_ok": integrity == "ok",
        "timing_ms": {
            name: _metrics([x[name] for x in timings])
            for name in (
                "total_ms", "entry_ms", "queue_ms",
                "body_ms", "finalize_ms",
            )
        },
        "wall_seconds": round(perf_counter() - start, 3),
        "failures": errors,
        "fictional_only": True,
        "human_enrollment_authorized": False,
        "external_https_test": False,
        "human_identity_or_consent_test": False,
        "production_capacity_established": False,
        "multi_process_test_not_a_deployment_solution": True,
    }
