import logging
import os
import shutil
from pathlib import Path

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)

from friends_bot_service.infra.core.config import settings

_logger = logging.getLogger(__name__)

DEFAULT_MULTIPROC_DIR = Path(".prometheus_multiproc")


def is_multiprocess_mode() -> bool:
    return settings.WORKER_COUNT > 1


def reset_multiprocess_dir(path: Path) -> None:
    """Removes stale mmap metric files before a new multi-worker run."""

    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def prepare_for_webhook_workers(worker_count: int) -> None:
    """Configures prometheus_client for uvicorn worker processes."""

    if worker_count <= 1:
        os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)
        return

    path = (
        Path(settings.PROMETHEUS_MULTIPROC_DIR)
        if settings.PROMETHEUS_MULTIPROC_DIR
        else DEFAULT_MULTIPROC_DIR
    )
    reset_multiprocess_dir(path)
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(path.resolve())
    _logger.info(
        "prometheus multiprocess metrics enabled dir=%s workers=%s",
        path,
        worker_count,
    )


def mark_current_process_dead() -> None:
    if not is_multiprocess_mode():
        return
    multiprocess.mark_process_dead(os.getpid())


def render_metrics() -> tuple[bytes, str]:
    if is_multiprocess_mode():
        multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        if not multiproc_dir:
            msg = "PROMETHEUS_MULTIPROC_DIR is required when WORKER_COUNT > 1"
            raise RuntimeError(msg)
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry), CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST
