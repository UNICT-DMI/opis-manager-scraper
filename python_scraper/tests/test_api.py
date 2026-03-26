from typing import Any, Dict, List, NamedTuple

import pytest
import requests.exceptions
from pytest_mock import MockerFixture

from src.api_client import get_activities, get_courses, get_departments, get_questions
from src.models import CorsoDiStudi, Dipartimento, Insegnamento, SchedaOpis


class GetDepartmentsCase(NamedTuple):
    year: int
    expected_payload_subset: Dict[str, Any]
    mock_response_data: List[Dict[str, Any]]
    expected_result: List[Dipartimento]


class GetCoursesCase(NamedTuple):
    year: int
    dept_code: int
    expected_payload_subset: Dict[str, Any]
    mock_response_data: List[Dict[str, Any]]
    expected_result: List[CorsoDiStudi]


class GetActivitiesCase(NamedTuple):
    year: int
    dept_code: int
    course_code: str
    expected_payload_subset: Dict[str, Any]
    mock_response_data: List[Dict[str, Any]]
    expected_result: List[Insegnamento]


class GetQuestionsCase(NamedTuple):
    year: int
    dept_code: int
    course_code: str
    activity_code: int
    prof_tax: str
    mock_response: Dict[str, Any]
    expected_payload: Dict[str, Any]
    expected_result: List[SchedaOpis]


class GetQuestionsFailureCase(NamedTuple):
    year: int
    dept_code: int
    course_code: str
    activity_code: int
    prof_tax: str


# TESTS get_departments


@pytest.mark.parametrize(
    "case",
    [
        GetDepartmentsCase(
            year=2024,
            expected_payload_subset={"surveys": "", "academicYear": 2024},
            mock_response_data=[
                {"code": "1001", "name": "Dipartimento di Matematica"},
                {"code": None, "name": "TOTALE"},
            ],
            expected_result=[
                Dipartimento(
                    unict_id=1001,
                    nome="Dipartimento di Matematica",
                    anno_accademico="2024/2025",
                )
            ],
        ),
        GetDepartmentsCase(
            year=2024,
            expected_payload_subset={"surveys": "", "academicYear": 2024},
            mock_response_data=[{"code": None, "name": "TOTALE"}],
            expected_result=[],
        ),
        GetDepartmentsCase(
            year=2021,
            expected_payload_subset={"surveys": "", "academicYear": 2021},
            mock_response_data=[
                {"code": "1002", "name": "Dipartimento di Informatica"},
                {"code": None, "name": "TOTALE"},
            ],
            expected_result=[
                Dipartimento(
                    unict_id=1002,
                    nome="Dipartimento di Informatica",
                    anno_accademico="2021/2022",
                )
            ],
        ),
    ],
)
def test_get_departments(mocker: MockerFixture, case: GetDepartmentsCase) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getDepartments"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"data": case.mock_response_data}

    # act
    result = get_departments(case.year)

    # assert
    assert len(result) == len(case.expected_result)
    assert all(isinstance(r, Dipartimento) for r in result)
    assert result == case.expected_result
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    actual_payload = kwargs["json"]
    for key, value in case.expected_payload_subset.items():
        assert actual_payload[key] == value


@pytest.mark.parametrize("year", [2024, 2023, 2022, 2021])
def test_get_departments_api_failure(mocker: MockerFixture, year: int) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getDepartments"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.side_effect = requests.exceptions.ConnectionError("API non raggiungibile")

    # act
    result = get_departments(year)

    # assert
    assert not result
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    actual_payload = kwargs["json"]
    assert actual_payload["academicYear"] == year
    assert actual_payload["surveys"] == ""


# TESTS get_courses


@pytest.mark.parametrize(
    "case",
    [
        GetCoursesCase(
            year=2024,
            dept_code=12345,
            expected_payload_subset={
                "surveys": "",
                "academicYear": 2024,
                "departmentCode": "12345",
            },
            mock_response_data=[
                {"code": "M12", "name": "Matematica LM-40"},
                {"code": None, "name": "TOTALE"},
            ],
            expected_result=[
                CorsoDiStudi(
                    unict_id="M12",
                    nome="Matematica",
                    classe="LM-40",
                    anno_accademico="2024/2025",
                    dipartimento_id=12345,
                )
            ],
        ),
        GetCoursesCase(
            year=2024,
            dept_code=12345,
            expected_payload_subset={
                "surveys": "",
                "academicYear": 2024,
                "departmentCode": "12345",
            },
            mock_response_data=[{"code": None, "name": "TOTALE"}],
            expected_result=[],
        ),
        GetCoursesCase(
            year=2021,
            dept_code=98765,
            expected_payload_subset={
                "surveys": "",
                "academicYear": 2021,
                "departmentCode": "98765",
            },
            mock_response_data=[
                {"code": "F34", "name": "Fisica L-30"},
                {"code": None, "name": "TOTALE"},
            ],
            expected_result=[
                CorsoDiStudi(
                    unict_id="F34",
                    nome="Fisica",
                    classe="L-30",
                    anno_accademico="2021/2022",
                    dipartimento_id=98765,
                )
            ],
        ),
    ],
)
def test_get_courses(mocker: MockerFixture, case: GetCoursesCase) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getCourses"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"data": case.mock_response_data}

    # act
    result = get_courses(case.year, case.dept_code)

    # assert
    assert len(result) == len(case.expected_result)
    assert all(isinstance(c, CorsoDiStudi) for c in result)
    assert result == case.expected_result
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    actual_payload = kwargs["json"]
    for key, value in case.expected_payload_subset.items():
        assert actual_payload[key] == value


@pytest.mark.parametrize(
    "year, dept_code",
    [
        (2024, 12345),
        (2023, 67890),
        (2022, 11121),
    ],
)
def test_get_courses_api_failure(
    mocker: MockerFixture, year: int, dept_code: int
) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getCourses"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.side_effect = requests.exceptions.ConnectionError("API non raggiungibile")

    # act
    result = get_courses(year, dept_code)

    # assert
    assert not result
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    actual_payload = kwargs["json"]
    assert actual_payload["academicYear"] == year
    assert actual_payload["departmentCode"] == str(dept_code)
    assert actual_payload["surveys"] == ""


# TESTS get_activities
@pytest.mark.parametrize(
    "case",
    [
        GetActivitiesCase(
            year=2023,
            dept_code=190141,
            course_code="W82",
            expected_payload_subset={
                "surveys": "",
                "academicYear": 2023,
                "departmentCode": "190141",
                "courseCode": "W82",
            },
            mock_response_data=[
                {
                    "activityCode": "1001829",
                    "activityName": "ULTERIORI ATTIVITA'",
                    "professorName": "FRANCESCO",
                    "professorLastName": "GUARNERA",
                    "professorTaxCode": "",
                    "channel": None,
                    "partCode": None,
                    "partName": "LABORATORIO",
                    "SSDsigla": "INF/01",
                },
                {
                    "activityCode": "A3688",
                    "activityName": "MATERIA SPORCA",
                    "professorName": "MARIO",
                    "professorLastName": "ROSSI",
                },
                {"activityCode": None, "activityName": "TOTALE"},
            ],
            expected_result=[
                Insegnamento(
                    codice_gomp=1001829,
                    id_cds="W82",
                    anno_accademico="2023/2024",
                    nome="ULTERIORI ATTIVITA'",
                    docente="GUARNERA FRANCESCO",
                    anno="",
                    semestre="",
                    cfu="",
                    canale="no",
                    id_modulo=0,
                    nome_modulo="LABORATORIO",
                    ssd="INF/01",
                    professor_tax="",
                )
            ],
        )
    ],
)
def test_get_activities(mocker: MockerFixture, case: GetActivitiesCase) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getActivities"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"data": case.mock_response_data}

    # act
    result = get_activities(case.year, case.dept_code, case.course_code)

    # assert
    assert len(result) == len(case.expected_result)
    assert all(isinstance(a, Insegnamento) for a in result)
    assert result == case.expected_result
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    actual_payload = kwargs["json"]
    for key, value in case.expected_payload_subset.items():
        assert actual_payload[key] == value


@pytest.mark.parametrize(
    "year, dept_code, course_code",
    [
        (2024, 12345, "M12"),
        (2023, 67890, "F34"),
    ],
)
def test_get_activities_api_failure(
    mocker: MockerFixture, year: int, dept_code: int, course_code: str
) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getActivities"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.side_effect = requests.exceptions.ConnectionError("API non raggiungibile")

    # act
    result = get_activities(year, dept_code, course_code)

    # assert
    assert not result
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    actual_payload = kwargs["json"]
    assert actual_payload["academicYear"] == year
    assert actual_payload["departmentCode"] == str(dept_code)
    assert actual_payload["courseCode"] == course_code
    assert actual_payload["surveys"] == ""


# TESTS get_questions
@pytest.mark.parametrize(
    "case",
    [
        # CASO 1: Successo
        GetQuestionsCase(
            year=2023,
            dept_code=190141,
            course_code="W82",
            activity_code=1014456,
            prof_tax="PROFCF123",
            mock_response={
                "clusterData": [
                    {
                        "cluster": {"Text": "Test Cluster"},
                        "questions": [
                            {"questionCode": "1", "submissions": 10, "answers": []}
                        ],
                    }
                ],
                "graphPieList": [],
            },
            expected_payload={
                "surveys": "",
                "academicYear": 2023,
                "departmentCode": "190141",
                "courseCode": "W82",
                "activityCode": "1014456",
                "partCode": "null",
                "professor": "PROFCF123",
            },
            expected_result=[
                SchedaOpis(
                    anno_accademico="2023/2024",
                    id_insegnamento=1014456,
                    totale_schede=10,
                    totale_schede_nf=0,
                    fc=0,
                    inatt_nf=0,
                    domande=[0] * 60,
                    domande_nf=[0] * 60,
                    motivo_nf=[],
                    sugg=[],
                    sugg_nf=[],
                )
            ],
        ),
        # CASO 2: Nessun dato trovato
        GetQuestionsCase(
            year=2023,
            dept_code=190141,
            course_code="W82",
            activity_code=9999999,
            prof_tax="",
            mock_response={"clusterData": [], "graphPieList": []},
            expected_payload={
                "surveys": "",
                "academicYear": 2023,
                "departmentCode": "190141",
                "courseCode": "W82",
                "activityCode": "9999999",
                "partCode": "null",
                "professor": "",
            },
            expected_result=[
                SchedaOpis(
                    anno_accademico="2023/2024",
                    id_insegnamento=9999999,
                    totale_schede=0,
                    totale_schede_nf=0,
                    fc=0,
                    inatt_nf=0,
                    domande=[0] * 60,
                    domande_nf=[0] * 60,
                    motivo_nf=[],
                    sugg=[],
                    sugg_nf=[],
                )
            ],
        ),
    ],
)
def test_get_questions(mocker: MockerFixture, case: GetQuestionsCase) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getQuestions"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = case.mock_response

    # act
    result = get_questions(
        case.year, case.dept_code, case.course_code, case.activity_code, case.prof_tax
    )

    # assert
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    assert kwargs["json"] == case.expected_payload
    assert result == case.expected_result


@pytest.mark.parametrize(
    "case",
    [
        GetQuestionsFailureCase(2024, 12345, "M12", 987654, "PROFCF1"),
        GetQuestionsFailureCase(2023, 67890, "F34", 112233, "PROFCF2"),
    ],
)
def test_get_questions_failure(
    mocker: MockerFixture, case: GetQuestionsFailureCase
) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getQuestions"
    mock_post = mocker.patch("src.api_client.session.post")

    mock_post.side_effect = requests.exceptions.ConnectionError("API non raggiungibile")

    # act
    result = get_questions(
        case.year, case.dept_code, case.course_code, case.activity_code, case.prof_tax
    )

    # assert
    assert not result
    mock_post.assert_called_once()

    args, kwargs = mock_post.call_args
    assert args[0] == expected_url

    actual_payload = kwargs["json"]
    assert actual_payload["academicYear"] == case.year
    assert actual_payload["departmentCode"] == str(case.dept_code)
    assert actual_payload["courseCode"] == case.course_code
    assert actual_payload["activityCode"] == str(case.activity_code)
    assert actual_payload["professor"] == case.prof_tax
    assert actual_payload["surveys"] == ""
