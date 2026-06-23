import os
import subprocess
import sys
from pathlib import Path

from friends_bot_service.infra.observability.multiproc import (
    prepare_for_webhook_workers,
    reset_multiprocess_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_prepare_unsets_multiproc_for_single_worker(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "/tmp/foo")

    prepare_for_webhook_workers(1)

    assert "PROMETHEUS_MULTIPROC_DIR" not in os.environ


def test_prepare_enables_multiproc_for_multiple_workers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    prepare_for_webhook_workers(2)

    assert os.environ["PROMETHEUS_MULTIPROC_DIR"] == str(
        (tmp_path / ".prometheus_multiproc").resolve(),
    )
    assert (tmp_path / ".prometheus_multiproc").is_dir()


def test_reset_multiprocess_dir_removes_stale_files(tmp_path):
    reset_multiprocess_dir(tmp_path)
    stale = tmp_path / "counter_123.db"
    stale.write_bytes(b"stale")
    assert stale.exists()

    reset_multiprocess_dir(tmp_path)

    assert not list(tmp_path.glob("*.db"))


def test_render_metrics_aggregates_multiprocess_counter(tmp_path):
    script = f"""
import os
from pathlib import Path
from prometheus_client import Counter

from friends_bot_service.infra.observability.multiproc import (
    render_metrics,
    reset_multiprocess_dir,
)

path = Path({str(tmp_path)!r})
reset_multiprocess_dir(path)
os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(path)
os.environ["WORKER_COUNT"] = "2"

Counter("friends_bot_test_mp_total", "multiprocess test counter").inc(3)
body, _ = render_metrics()
assert b"friends_bot_test_mp_total" in body
assert b"3.0" in body
"""
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        cwd=REPO_ROOT,
    )
