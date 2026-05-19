import json

import pytest

from src import failure_tracker


@pytest.fixture
def failures_dir(tmp_path, mocker):
    mocker.patch.object(failure_tracker, "FAILURES_DIR", str(tmp_path))
    return tmp_path


def test_log_failure_writes_jsonl(failures_dir) -> None:
    failure_tracker.log_failure(2024, {"level": "courses", "dept_code": 1})
    failure_tracker.log_failure(2024, {"level": "questions", "activity_code": 9})

    filepath = failures_dir / "failures_2024.txt"
    assert filepath.exists()
    lines = filepath.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"level": "courses", "dept_code": 1}
    assert json.loads(lines[1]) == {"level": "questions", "activity_code": 9}


def test_read_failures_returns_empty_when_no_file(failures_dir) -> None:
    assert failure_tracker.read_failures(2099) == []


def test_read_failures_parses_jsonl_and_skips_invalid(failures_dir, caplog) -> None:
    filepath = failures_dir / "failures_2024.txt"
    filepath.write_text(
        '{"level": "courses", "dept_code": 1}\n'
        "\n"
        "not-valid-json\n"
        '{"level": "questions"}\n',
        encoding="utf-8",
    )

    result = failure_tracker.read_failures(2024)

    assert result == [
        {"level": "courses", "dept_code": 1},
        {"level": "questions"},
    ]
    assert "non valida" in caplog.text


def test_clear_failures_removes_existing_file(failures_dir) -> None:
    filepath = failures_dir / "failures_2024.txt"
    filepath.write_text("anything", encoding="utf-8")

    failure_tracker.clear_failures(2024)

    assert not filepath.exists()


def test_clear_failures_no_op_when_missing(failures_dir) -> None:
    failure_tracker.clear_failures(2099)
