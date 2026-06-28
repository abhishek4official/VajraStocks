"""Tests for the background job runner (V2.0 spec M1).

A DB-backed queue so long work (sync/recompute/backtest) runs off the request thread with
progress, cancel, and retry. The deterministic unit is run_next() — claim the oldest
PENDING job and execute its handler synchronously; the threaded worker just loops on it.
"""

import pytest

from stocks.services.jobs.runner import JobCancelled, JobRunner, register_handler


@register_handler("echo")
def _echo(job, session, set_progress, is_cancelled):
    set_progress(1, 2)
    set_progress(2, 2)
    return {"echoed": job.kind}


@register_handler("boom")
def _boom(job, session, set_progress, is_cancelled):
    raise ValueError("kaboom")


@register_handler("cancellable")
def _cancellable(job, session, set_progress, is_cancelled):
    for i in range(10):
        if is_cancelled():
            raise JobCancelled()
        set_progress(i + 1, 10)
    return {"done": True}


@pytest.fixture
def runner(db_session):
    return JobRunner(db_session)


def test_enqueue_creates_pending(runner):
    job = runner.enqueue("echo", {"x": 1})
    assert job.id is not None
    assert job.status == "PENDING"


def test_run_next_success(runner):
    job = runner.enqueue("echo")
    done = runner.run_next()
    assert done.id == job.id
    assert done.status == "SUCCESS"
    assert done.progress_current == 2 and done.progress_total == 2
    assert done.result_json and "echoed" in done.result_json
    assert done.finished_at is not None


def test_run_next_none_when_empty(runner):
    assert runner.run_next() is None


def test_handler_failure_marks_failed(runner):
    runner.enqueue("boom")
    done = runner.run_next()
    assert done.status == "FAILED"
    assert "kaboom" in done.error


def test_unknown_kind_fails_cleanly(runner):
    runner.enqueue("nope")
    done = runner.run_next()
    assert done.status == "FAILED"
    assert "handler" in done.error.lower()


def test_cancellation(runner):
    job = runner.enqueue("cancellable")
    assert runner.cancel(job.id) is True   # request cancel before it runs
    done = runner.run_next()
    assert done.status == "CANCELLED"


def test_retry_failed_job(runner):
    job = runner.enqueue("boom")
    runner.run_next()
    assert runner.get(job.id).status == "FAILED"
    # Retry re-queues it (clears error); make it succeed by swapping kind to a good handler.
    assert runner.retry(job.id) is True
    requeued = runner.get(job.id)
    assert requeued.status == "PENDING"
    assert requeued.error is None


def test_fifo_order(runner):
    a = runner.enqueue("echo")
    b = runner.enqueue("echo")
    assert runner.run_next().id == a.id   # oldest first
    assert runner.run_next().id == b.id
