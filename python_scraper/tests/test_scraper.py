from concurrent.futures import Future
from dataclasses import replace
from unittest.mock import MagicMock

import mysql.connector
import pytest

from src import scraper
from src.api_client import ApiError
from src.models import CorsoDiStudi, Dipartimento, Insegnamento, SchedaOpis
from src.scraper import (
    _consume_activity_future,
    _parse_csv_codes,
    _retry_activities,
    _retry_courses,
    _retry_questions_batch,
    _retry_single_question,
    _scrape_course,
    _scrape_department,
    assign_channels,
    process_activity,
    process_course,
    process_department,
    retry_failures,
    run_scraper,
)

_BASE_INSEGNAMENTO = Insegnamento(
    codice_gomp=1010,
    id_cds="M12",
    anno_accademico="2024/2025",
    nome="Materia X",
    docente="Mario Rossi",
    professor_tax="TAX123",
)

_BASE_CORSO = CorsoDiStudi(
    unict_id="C1",
    nome="Corso",
    classe="L-31",
    anno_accademico="2024/2025",
    dipartimento_id=7,
)

_BASE_DIPARTIMENTO = Dipartimento(
    unict_id=7,
    nome="Dipartimento di X",
    anno_accademico="2024/2025",
)


def _make_insegnamento(**overrides) -> Insegnamento:
    return replace(_BASE_INSEGNAMENTO, **overrides)


def _make_corso(**overrides) -> CorsoDiStudi:
    return replace(_BASE_CORSO, **overrides)


def _make_dipartimento(**overrides) -> Dipartimento:
    return replace(_BASE_DIPARTIMENTO, **overrides)


def _make_scheda(insegnamento_id: int = 1) -> SchedaOpis:
    # pylint: disable=duplicate-code
    return SchedaOpis(
        anno_accademico="2024/2025",
        id_insegnamento=insegnamento_id,
        totale_schede=1,
        totale_schede_nf=0,
        fc=0,
        inatt_nf=0,
        domande=[1],
        domande_nf=[],
        motivo_nf=[],
        sugg=[],
        sugg_nf=[],
    )


def _completed_future(value) -> Future:
    f: Future = Future()
    f.set_result(value)
    return f


def _failed_future(exc: Exception) -> Future:
    f: Future = Future()
    f.set_exception(exc)
    return f


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    """Disable env-driven filters and debug mode for every test."""
    monkeypatch.setattr(scraper, "FILTER_DEPT_CODES", "")
    monkeypatch.setattr(scraper, "FILTER_COURSE_CODES", "")
    monkeypatch.setattr(scraper, "FILTER_ACTIVITY_CODES", "")
    monkeypatch.setattr(scraper, "DEBUG_MODE", False)


# ---------------------------------------------------------------------------
# assign_channels (kept from earlier suite)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "input_activities, expected_canali",
    [
        ([], []),
        ([_make_insegnamento(nome="A", nome_modulo=None, canale="no")], ["no"]),
        (
            [
                _make_insegnamento(nome="A", nome_modulo=None, codice_gomp=1),
                _make_insegnamento(nome="A", nome_modulo=None, codice_gomp=2),
            ],
            ["1", "2"],
        ),
        (
            [
                _make_insegnamento(nome="A", nome_modulo="Teoria", codice_gomp=1),
                _make_insegnamento(nome="A", nome_modulo="Lab", codice_gomp=2),
            ],
            ["no", "no"],
        ),
        (
            [
                _make_insegnamento(nome="A", nome_modulo="T", codice_gomp=1),
                _make_insegnamento(nome="A", nome_modulo="L", codice_gomp=2),
                _make_insegnamento(nome="A", nome_modulo="T", codice_gomp=3),
                _make_insegnamento(nome="A", nome_modulo="L", codice_gomp=4),
            ],
            ["1", "1", "2", "2"],
        ),
    ],
)
def test_assign_channels(input_activities, expected_canali) -> None:
    result = assign_channels(input_activities)
    assert [a.canale for a in result] == expected_canali


# ---------------------------------------------------------------------------
# _parse_csv_codes
# ---------------------------------------------------------------------------


def test_parse_csv_codes_returns_none_when_blank() -> None:
    assert _parse_csv_codes("") is None


def test_parse_csv_codes_parses_set() -> None:
    assert _parse_csv_codes("1, 2,3 ,") == {"1", "2", "3"}


# ---------------------------------------------------------------------------
# process_activity
# ---------------------------------------------------------------------------


def test_process_activity_skips_when_no_professor_tax() -> None:
    activity = _make_insegnamento(professor_tax="")
    result = process_activity(2024, 7, "C1", activity)
    assert result == (activity, [])


def test_process_activity_returns_schede_on_success(mocker) -> None:
    schede = [_make_scheda()]
    mocker.patch("src.scraper.get_questions", return_value=schede)
    activity = _make_insegnamento()

    result = process_activity(2024, 7, "C1", activity)

    assert result == (activity, schede)


def test_process_activity_returns_empty_when_source_has_no_data(mocker) -> None:
    mocker.patch("src.scraper.get_questions", return_value=[])
    activity = _make_insegnamento()

    result = process_activity(2024, 7, "C1", activity)

    assert result == (activity, [])


def test_process_activity_logs_failure_and_returns_none_on_api_error(mocker) -> None:
    mocker.patch("src.scraper.get_questions", side_effect=ApiError("nope"))
    log_failure = mocker.patch("src.scraper.log_failure")
    activity = _make_insegnamento()

    result = process_activity(2024, 7, "C1", activity)

    assert result is None
    log_failure.assert_called_once()
    failure_arg = log_failure.call_args.args[1]
    assert failure_arg["level"] == "questions"
    assert failure_arg["activity_code"] == activity.codice_gomp


# ---------------------------------------------------------------------------
# _consume_activity_future
# ---------------------------------------------------------------------------


def test_consume_future_inserts_when_schede_present(mocker) -> None:
    insert = mocker.patch("src.scraper.insert_schede_opis")
    delete = mocker.patch("src.scraper.delete_insegnamento_if_orphan")
    schede = [_make_scheda()]
    future = _completed_future((_make_insegnamento(), schede))

    _consume_activity_future(future, ins_id=100)

    insert.assert_called_once_with(schede, 100)
    delete.assert_not_called()


def test_consume_future_deletes_orphan_when_schede_empty(mocker) -> None:
    mocker.patch("src.scraper.insert_schede_opis")
    delete = mocker.patch("src.scraper.delete_insegnamento_if_orphan")
    future = _completed_future((_make_insegnamento(), []))

    _consume_activity_future(future, ins_id=100)

    delete.assert_called_once_with(100)


def test_consume_future_keeps_orphan_on_api_error(mocker) -> None:
    insert = mocker.patch("src.scraper.insert_schede_opis")
    delete = mocker.patch("src.scraper.delete_insegnamento_if_orphan")
    future = _completed_future(None)  # process_activity returns None on ApiError

    _consume_activity_future(future, ins_id=100)

    insert.assert_not_called()
    delete.assert_not_called()


def test_consume_future_logs_runtime_error(mocker, caplog) -> None:
    future = _failed_future(RuntimeError("boom"))
    _consume_activity_future(future, ins_id=1)
    assert "Errore" in caplog.text


def test_consume_future_logs_db_error(mocker, caplog) -> None:
    future = _failed_future(mysql.connector.Error("db down"))
    _consume_activity_future(future, ins_id=1)
    assert "Errore DB" in caplog.text


# ---------------------------------------------------------------------------
# _scrape_department
# ---------------------------------------------------------------------------


def _make_bars():
    return MagicMock(), MagicMock()


def test_scrape_department_aborts_on_db_insert_failure(mocker) -> None:
    mocker.patch("src.scraper.insert_department", return_value=-1)
    get_courses = mocker.patch("src.scraper.get_courses")
    course_bar, teach_bar = _make_bars()

    _scrape_department(2024, _make_dipartimento(), course_bar, teach_bar)

    get_courses.assert_not_called()


def test_scrape_department_logs_failure_on_api_error(mocker) -> None:
    mocker.patch("src.scraper.insert_department", return_value=11)
    mocker.patch("src.scraper.get_courses", side_effect=ApiError("nope"))
    log_failure = mocker.patch("src.scraper.log_failure")
    course_bar, teach_bar = _make_bars()

    _scrape_department(2024, _make_dipartimento(), course_bar, teach_bar)

    log_failure.assert_called_once()
    assert log_failure.call_args.args[1]["level"] == "courses"


def test_scrape_department_iterates_courses(mocker) -> None:
    mocker.patch("src.scraper.insert_department", return_value=11)
    courses = [_make_corso(unict_id="C1"), _make_corso(unict_id="C2")]
    mocker.patch("src.scraper.get_courses", return_value=courses)
    scrape_course = mocker.patch("src.scraper._scrape_course")
    course_bar, teach_bar = _make_bars()

    _scrape_department(2024, _make_dipartimento(), course_bar, teach_bar)

    assert scrape_course.call_count == 2
    course_bar.reset.assert_called_once_with(total=2)


def test_scrape_department_applies_course_filter(mocker, monkeypatch) -> None:
    monkeypatch.setattr(scraper, "FILTER_COURSE_CODES", "C2")
    mocker.patch("src.scraper.insert_department", return_value=11)
    courses = [_make_corso(unict_id="C1"), _make_corso(unict_id="C2")]
    mocker.patch("src.scraper.get_courses", return_value=courses)
    scrape_course = mocker.patch("src.scraper._scrape_course")
    course_bar, teach_bar = _make_bars()

    _scrape_department(2024, _make_dipartimento(), course_bar, teach_bar)

    assert scrape_course.call_count == 1


# ---------------------------------------------------------------------------
# _scrape_course
# ---------------------------------------------------------------------------


def test_scrape_course_aborts_on_db_failure(mocker) -> None:
    mocker.patch("src.scraper.insert_course", return_value=-1)
    get_activities = mocker.patch("src.scraper.get_activities")
    teach_bar = MagicMock()

    _scrape_course(2024, 7, _make_corso(), 11, teach_bar)

    get_activities.assert_not_called()


def test_scrape_course_logs_failure_on_api_error(mocker) -> None:
    mocker.patch("src.scraper.insert_course", return_value=22)
    mocker.patch("src.scraper.get_activities", side_effect=ApiError("nope"))
    log_failure = mocker.patch("src.scraper.log_failure")
    teach_bar = MagicMock()

    _scrape_course(2024, 7, _make_corso(), 11, teach_bar)

    log_failure.assert_called_once()
    assert log_failure.call_args.args[1]["level"] == "activities"


def test_scrape_course_resets_bar_when_no_activities(mocker) -> None:
    mocker.patch("src.scraper.insert_course", return_value=22)
    mocker.patch("src.scraper.get_activities", return_value=[])
    teach_bar = MagicMock()

    _scrape_course(2024, 7, _make_corso(), 11, teach_bar)

    teach_bar.reset.assert_called_once_with(total=0)


def test_scrape_course_processes_activities_via_pool(mocker) -> None:
    activity = _make_insegnamento()
    mocker.patch("src.scraper.insert_course", return_value=22)
    mocker.patch("src.scraper.get_activities", return_value=[activity])
    mocker.patch("src.scraper.insert_insegnamento", return_value=99)
    mocker.patch("src.scraper.get_processed_activity_codes", return_value=set())
    schede = [_make_scheda()]
    mocker.patch("src.scraper.process_activity", return_value=(activity, schede))
    insert_schede = mocker.patch("src.scraper.insert_schede_opis")
    teach_bar = MagicMock()

    _scrape_course(2024, 7, _make_corso(), 11, teach_bar)

    insert_schede.assert_called_once_with(schede, 99)
    teach_bar.update.assert_called_once_with(1)


def test_scrape_course_skips_already_processed(mocker) -> None:
    activity = _make_insegnamento(codice_gomp=42)
    mocker.patch("src.scraper.insert_course", return_value=22)
    mocker.patch("src.scraper.get_activities", return_value=[activity])
    mocker.patch("src.scraper.insert_insegnamento", return_value=99)
    mocker.patch("src.scraper.get_processed_activity_codes", return_value={42})
    process_activity_mock = mocker.patch("src.scraper.process_activity")
    teach_bar = MagicMock()

    _scrape_course(2024, 7, _make_corso(), 11, teach_bar)

    process_activity_mock.assert_not_called()


def test_scrape_course_applies_activity_filter(mocker, monkeypatch) -> None:
    monkeypatch.setattr(scraper, "FILTER_ACTIVITY_CODES", "99")
    activity = _make_insegnamento(codice_gomp=10)
    mocker.patch("src.scraper.insert_course", return_value=22)
    mocker.patch("src.scraper.get_activities", return_value=[activity])
    insert_ins = mocker.patch("src.scraper.insert_insegnamento")
    teach_bar = MagicMock()

    _scrape_course(2024, 7, _make_corso(), 11, teach_bar)

    insert_ins.assert_not_called()


def test_scrape_course_skips_insegnamento_insert_failure(mocker) -> None:
    activity = _make_insegnamento()
    mocker.patch("src.scraper.insert_course", return_value=22)
    mocker.patch("src.scraper.get_activities", return_value=[activity])
    mocker.patch("src.scraper.insert_insegnamento", return_value=-1)
    mocker.patch("src.scraper.get_processed_activity_codes", return_value=set())
    process_activity_mock = mocker.patch("src.scraper.process_activity")
    teach_bar = MagicMock()

    _scrape_course(2024, 7, _make_corso(), 11, teach_bar)

    process_activity_mock.assert_not_called()


# ---------------------------------------------------------------------------
# run_scraper
# ---------------------------------------------------------------------------


def test_run_scraper_handles_departments_api_error(mocker) -> None:
    mocker.patch("src.scraper.connect_to_db")
    mocker.patch("src.scraper.seed_domande")
    mocker.patch("src.scraper.clear_failures")
    mocker.patch("src.scraper.get_departments", side_effect=ApiError("down"))
    close = mocker.patch("src.scraper.close_connection")

    run_scraper(2024)

    close.assert_called_once()


def test_run_scraper_processes_departments(mocker) -> None:
    mocker.patch("src.scraper.connect_to_db")
    mocker.patch("src.scraper.seed_domande")
    mocker.patch("src.scraper.clear_failures")
    depts = [_make_dipartimento(unict_id=1), _make_dipartimento(unict_id=2)]
    mocker.patch("src.scraper.get_departments", return_value=depts)
    scrape_dept = mocker.patch("src.scraper._scrape_department")
    mocker.patch("src.scraper.close_connection")

    run_scraper(2024)

    assert scrape_dept.call_count == 2


def test_run_scraper_applies_dept_filter(mocker, monkeypatch) -> None:
    monkeypatch.setattr(scraper, "FILTER_DEPT_CODES", "2")
    mocker.patch("src.scraper.connect_to_db")
    mocker.patch("src.scraper.seed_domande")
    mocker.patch("src.scraper.clear_failures")
    depts = [_make_dipartimento(unict_id=1), _make_dipartimento(unict_id=2)]
    mocker.patch("src.scraper.get_departments", return_value=depts)
    scrape_dept = mocker.patch("src.scraper._scrape_department")
    mocker.patch("src.scraper.close_connection")

    run_scraper(2024)

    assert scrape_dept.call_count == 1


# ---------------------------------------------------------------------------
# process_course (retry-flow variant)
# ---------------------------------------------------------------------------


def test_process_course_aborts_on_db_failure(mocker) -> None:
    mocker.patch("src.scraper.insert_course", return_value=-1)
    get_activities = mocker.patch("src.scraper.get_activities")

    process_course(2024, 7, _make_corso(), 11)

    get_activities.assert_not_called()


def test_process_course_logs_failure_on_api_error(mocker) -> None:
    mocker.patch("src.scraper.insert_course", return_value=22)
    mocker.patch("src.scraper.get_activities", side_effect=ApiError("nope"))
    log_failure = mocker.patch("src.scraper.log_failure")

    process_course(2024, 7, _make_corso(), 11)

    log_failure.assert_called_once()


def test_process_course_short_circuits_on_empty_activities(mocker) -> None:
    mocker.patch("src.scraper.insert_course", return_value=22)
    mocker.patch("src.scraper.get_activities", return_value=[])
    process_act = mocker.patch("src.scraper.process_activity")

    process_course(2024, 7, _make_corso(), 11)

    process_act.assert_not_called()


def test_process_course_runs_pool(mocker) -> None:
    activity = _make_insegnamento()
    mocker.patch("src.scraper.insert_course", return_value=22)
    mocker.patch("src.scraper.get_activities", return_value=[activity])
    mocker.patch("src.scraper.insert_insegnamento", return_value=99)
    mocker.patch("src.scraper.get_processed_activity_codes", return_value=set())
    schede = [_make_scheda()]
    mocker.patch("src.scraper.process_activity", return_value=(activity, schede))
    insert_schede = mocker.patch("src.scraper.insert_schede_opis")

    process_course(2024, 7, _make_corso(), 11)

    insert_schede.assert_called_once_with(schede, 99)


def test_process_course_activity_filter_drops_all(mocker, monkeypatch) -> None:
    monkeypatch.setattr(scraper, "FILTER_ACTIVITY_CODES", "999")
    activity = _make_insegnamento(codice_gomp=10)
    mocker.patch("src.scraper.insert_course", return_value=22)
    mocker.patch("src.scraper.get_activities", return_value=[activity])
    insert_ins = mocker.patch("src.scraper.insert_insegnamento")

    process_course(2024, 7, _make_corso(), 11)

    insert_ins.assert_not_called()


# ---------------------------------------------------------------------------
# process_department (retry-flow variant)
# ---------------------------------------------------------------------------


def test_process_department_aborts_on_db_failure(mocker) -> None:
    mocker.patch("src.scraper.insert_department", return_value=-1)
    get_courses = mocker.patch("src.scraper.get_courses")

    process_department(2024, _make_dipartimento())

    get_courses.assert_not_called()


def test_process_department_logs_failure_on_api_error(mocker) -> None:
    mocker.patch("src.scraper.insert_department", return_value=11)
    mocker.patch("src.scraper.get_courses", side_effect=ApiError("nope"))
    log_failure = mocker.patch("src.scraper.log_failure")

    process_department(2024, _make_dipartimento())

    log_failure.assert_called_once()


def test_process_department_runs_pool(mocker) -> None:
    mocker.patch("src.scraper.insert_department", return_value=11)
    courses = [_make_corso(unict_id="C1"), _make_corso(unict_id="C2")]
    mocker.patch("src.scraper.get_courses", return_value=courses)
    process_course_mock = mocker.patch("src.scraper.process_course")

    process_department(2024, _make_dipartimento())

    assert process_course_mock.call_count == 2


def test_process_department_logs_worker_runtime_error(mocker, caplog) -> None:
    mocker.patch("src.scraper.insert_department", return_value=11)
    mocker.patch("src.scraper.get_courses", return_value=[_make_corso()])
    mocker.patch("src.scraper.process_course", side_effect=RuntimeError("kaboom"))

    process_department(2024, _make_dipartimento())

    assert "Errore nel corso" in caplog.text


# ---------------------------------------------------------------------------
# retry_failures + helpers
# ---------------------------------------------------------------------------


def test_retry_failures_returns_when_no_failures(mocker) -> None:
    mocker.patch("src.scraper.read_failures", return_value=[])
    connect = mocker.patch("src.scraper.connect_to_db")

    retry_failures(2024)

    connect.assert_not_called()


def test_retry_failures_partitions_and_dedups(mocker) -> None:
    failures = [
        {"level": "courses", "dept_code": 1, "dept_name": "D1"},
        # activities under failed dept are dropped:
        {"level": "activities", "dept_code": 1, "course_code": "X"},
        {"level": "activities", "dept_code": 2, "course_code": "C2"},
        # questions under failed dept dropped:
        {"level": "questions", "dept_code": 1, "course_code": "X", "activity_code": 1},
        # questions under failed course dropped:
        {"level": "questions", "dept_code": 2, "course_code": "C2", "activity_code": 2},
        # surviving question:
        {"level": "questions", "dept_code": 3, "course_code": "C3", "activity_code": 3},
    ]
    mocker.patch("src.scraper.read_failures", return_value=failures)
    mocker.patch("src.scraper.connect_to_db")
    mocker.patch("src.scraper.seed_domande")
    mocker.patch("src.scraper.clear_failures")
    mocker.patch("src.scraper.close_connection")
    retry_courses = mocker.patch("src.scraper._retry_courses")
    retry_activities = mocker.patch("src.scraper._retry_activities")
    retry_questions = mocker.patch("src.scraper._retry_questions_batch")

    retry_failures(2024)

    assert retry_courses.call_count == 1
    assert retry_activities.call_count == 1
    # only one question (dept_code=3) survived dedup
    retry_questions.assert_called_once()
    assert len(retry_questions.call_args.args[2]) == 1


def test_retry_courses_dispatches_to_process_department(mocker) -> None:
    process_dept = mocker.patch("src.scraper.process_department")
    failure = {"dept_code": 7, "dept_name": "Dip"}

    _retry_courses(2024, "2024/2025", failure)

    process_dept.assert_called_once()
    dept_arg = process_dept.call_args.args[1]
    assert dept_arg.unict_id == 7
    assert dept_arg.anno_accademico == "2024/2025"


def test_retry_activities_skips_when_dept_missing(mocker) -> None:
    mocker.patch("src.scraper.find_department_id", return_value=-1)
    log_failure = mocker.patch("src.scraper.log_failure")
    process_course_mock = mocker.patch("src.scraper.process_course")
    failure = {"dept_code": 7, "course_code": "C1"}

    _retry_activities(2024, "2024/2025", failure)

    log_failure.assert_called_once()
    process_course_mock.assert_not_called()


def test_retry_activities_dispatches_to_process_course(mocker) -> None:
    mocker.patch("src.scraper.find_department_id", return_value=11)
    process_course_mock = mocker.patch("src.scraper.process_course")
    failure = {
        "dept_code": 7,
        "course_code": "C1",
        "course_name": "N",
        "course_classe": "L",
    }

    _retry_activities(2024, "2024/2025", failure)

    process_course_mock.assert_called_once()


def test_retry_questions_batch_runs_each(mocker) -> None:
    retry_single = mocker.patch("src.scraper._retry_single_question")
    failures = [
        {"dept_code": 1, "course_code": "C", "activity_code": 1, "professor_tax": "T"},
        {"dept_code": 1, "course_code": "C", "activity_code": 2, "professor_tax": "T"},
    ]

    _retry_questions_batch(2024, "2024/2025", failures)

    assert retry_single.call_count == 2


def test_retry_questions_batch_logs_worker_runtime_error(mocker, caplog) -> None:
    mocker.patch("src.scraper._retry_single_question", side_effect=RuntimeError("x"))
    failures = [
        {"dept_code": 1, "course_code": "C", "activity_code": 1, "professor_tax": "T"},
    ]

    _retry_questions_batch(2024, "2024/2025", failures)

    assert "[RETRY] Errore" in caplog.text


def test_retry_single_question_logs_failure_on_api_error(mocker) -> None:
    mocker.patch("src.scraper.get_questions", side_effect=ApiError("nope"))
    log_failure = mocker.patch("src.scraper.log_failure")
    failure = {
        "dept_code": 7,
        "course_code": "C1",
        "activity_code": 5,
        "professor_tax": "T",
    }

    _retry_single_question(2024, "2024/2025", failure)

    log_failure.assert_called_once()


def test_retry_single_question_skips_when_insegnamento_missing(mocker) -> None:
    mocker.patch("src.scraper.get_questions", return_value=[_make_scheda()])
    mocker.patch("src.scraper.find_insegnamento_id", return_value=-1)
    insert_schede = mocker.patch("src.scraper.insert_schede_opis")
    failure = {
        "dept_code": 7,
        "course_code": "C1",
        "activity_code": 5,
        "professor_tax": "T",
    }

    _retry_single_question(2024, "2024/2025", failure)

    insert_schede.assert_not_called()


def test_retry_single_question_inserts_schede(mocker) -> None:
    schede = [_make_scheda()]
    mocker.patch("src.scraper.get_questions", return_value=schede)
    mocker.patch("src.scraper.find_insegnamento_id", return_value=42)
    insert_schede = mocker.patch("src.scraper.insert_schede_opis")
    failure = {
        "dept_code": 7,
        "course_code": "C1",
        "activity_code": 5,
        "professor_tax": "T",
    }

    _retry_single_question(2024, "2024/2025", failure)

    insert_schede.assert_called_once_with(schede, 42)


def test_retry_single_question_deletes_orphan_on_empty_schede(mocker) -> None:
    mocker.patch("src.scraper.get_questions", return_value=[])
    mocker.patch("src.scraper.find_insegnamento_id", return_value=42)
    delete = mocker.patch(
        "src.scraper.delete_insegnamento_if_orphan", return_value=True
    )
    failure = {
        "dept_code": 7,
        "course_code": "C1",
        "activity_code": 5,
        "professor_tax": "T",
    }

    _retry_single_question(2024, "2024/2025", failure)

    delete.assert_called_once_with(42)
