import json
import logging
import os
import threading
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

FAILURES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "failures"
)
_lock = threading.Lock()


def _get_failures_file(year: int) -> str:
    os.makedirs(FAILURES_DIR, exist_ok=True)
    return os.path.join(FAILURES_DIR, f"failures_{year}.txt")


def log_failure(year: int, failure_data: Dict[str, Any]) -> None:
    filepath = _get_failures_file(year)
    line = json.dumps(failure_data, ensure_ascii=False)
    with _lock:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    logger.warning(
        "[FAILURE] %s: %s",
        failure_data.get("level", "unknown"),
        {k: v for k, v in failure_data.items() if k != "level"},
    )


def read_failures(year: int) -> List[Dict[str, Any]]:
    filepath = _get_failures_file(year)
    if not os.path.exists(filepath):
        return []

    failures: List[Dict[str, Any]] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                failures.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.warning("Riga %d non valida nel file failures: %s", line_num, e)
    return failures


def clear_failures(year: int) -> None:
    filepath = _get_failures_file(year)
    if os.path.exists(filepath):
        os.remove(filepath)
        logger.info("File failures per l'anno %d cancellato.", year)
