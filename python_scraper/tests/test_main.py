import logging

import mysql.connector
import pytest

from src import main
from src.api_client import ApiError


def test_tqdm_logging_handler_emits_via_tqdm_write(mocker) -> None:
    mock_write = mocker.patch("src.main.tqdm.write")
    handler = main.TqdmLoggingHandler()
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    mock_write.assert_called_once()
    assert "hello" in mock_write.call_args.args[0]


def test_tqdm_logging_handler_falls_back_on_error(mocker) -> None:
    mocker.patch("src.main.tqdm.write", side_effect=OSError("boom"))
    handler = main.TqdmLoggingHandler()
    handle_error = mocker.patch.object(handler, "handleError")
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="x",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    handle_error.assert_called_once_with(record)


def test_main_runs_scraper_when_retry_not_set(mocker) -> None:
    run = mocker.patch("src.main.run_scraper")
    retry = mocker.patch("src.main.retry_failures")
    mocker.patch("sys.argv", ["prog", "--year", "2024"])

    main.main()

    run.assert_called_once_with(2024)
    retry.assert_not_called()


def test_main_runs_retry_when_flag_set(mocker) -> None:
    run = mocker.patch("src.main.run_scraper")
    retry = mocker.patch("src.main.retry_failures")
    mocker.patch("sys.argv", ["prog", "--year", "2024", "--retry"])

    main.main()

    retry.assert_called_once_with(2024)
    run.assert_not_called()


def test_main_requires_year(mocker) -> None:
    mocker.patch("sys.argv", ["prog"])

    with pytest.raises(SystemExit):
        main.main()


@pytest.mark.parametrize(
    "exc",
    [
        KeyboardInterrupt(),
        ApiError("api down"),
        RuntimeError("kaboom"),
        mysql.connector.Error("db down"),
    ],
)
def test_main_handles_known_exceptions(mocker, caplog, exc) -> None:
    mocker.patch("src.main.run_scraper", side_effect=exc)
    mocker.patch("sys.argv", ["prog", "--year", "2024"])

    # act — should not propagate
    main.main()

    # assert — something was logged at error/warning level
    assert caplog.records, "expected an error/warning log entry"
