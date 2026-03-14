import pytest
from pytest_mock import MockerFixture
from typing import Dict, Any, List
from src.api_client import get_courses, get_departments, get_activities, get_questions
from src.models import CorsoDiStudi, Dipartimento, Insegnamento, SchedaOpis
import requests.exceptions

# TESTS get_departments


@pytest.mark.parametrize(
    "year, expected_payload_subset, mock_response_data, expected_result",
    [
        (2024, {"surveys": "", "academicYear": 2024}, [
         {"code": "1001", "name": "Dipartimento di Matematica"}, {"code": None, "name": "TOTALE"}],
         [
            Dipartimento(
                unict_id=1001,
                nome="Dipartimento di Matematica",
                anno_accademico="2024/2025"
            )
        ]),
        (2024, {"surveys": "", "academicYear": 2024}, [
         {"code": None, "name": "TOTALE"}], []),
        (2021, {"surveys": "", "academicYear": 2021}, [
         {"code": "1002", "name": "Dipartimento di Informatica"}, {"code": None, "name": "TOTALE"}],
         [
            Dipartimento(
                unict_id=1002,
                nome="Dipartimento di Informatica",
                anno_accademico="2021/2022"
            )
        ]),
    ]
)
def test_get_departments(
    mocker: MockerFixture,
    year: int,
    expected_payload_subset: Dict[str, Any],
    mock_response_data: List[Dict[str, Any]],
    expected_result: List[Dipartimento]
) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getDepartments"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"data": mock_response_data}

    # act
    result = get_departments(year)

    # assert
    assert len(result) == len(expected_result)
    assert all(isinstance(r, Dipartimento) for r in result)
    assert result == expected_result
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    actual_payload = kwargs["json"]
    for key, value in expected_payload_subset.items():
        assert actual_payload[key] == value


@pytest.mark.parametrize(
    "year", [2024, 2023, 2022, 2021]
)
def test_get_departments_api_failure(
    mocker: MockerFixture,
    year: int
) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getDepartments"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.side_effect = requests.exceptions.ConnectionError(
        "API non raggiungibile")

    # act
    result = get_departments(year)

    # assert
    assert result == []
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    actual_payload = kwargs["json"]
    assert actual_payload["academicYear"] == year
    assert actual_payload["surveys"] == ""


# TESTS get_courses
@pytest.mark.parametrize(
    "year, dept_code, expected_payload_subset, mock_response_data, expected_result",
    [
        (
            2024,
            12345,
            {"surveys": "", "academicYear": 2024, "departmentCode": "12345"},
            [{"code": "M12", "name": "Matematica LM-40"},
                {"code": None, "name": "TOTALE"}],
            [CorsoDiStudi(
                unict_id="M12",
                nome="Matematica",
                classe="LM-40",
                anno_accademico="2024/2025",
                dipartimento_id=12345)
             ]
        ),
        (
            2024,
            12345,
            {"surveys": "", "academicYear": 2024, "departmentCode": "12345"},
            [{"code": None, "name": "TOTALE"}],
            []
        ),
        (
            2021,
            98765,
            {"surveys": "", "academicYear": 2021, "departmentCode": "98765"},
            [{"code": "F34", "name": "Fisica L-30"},
                {"code": None, "name": "TOTALE"}],
            [CorsoDiStudi(
                unict_id="F34",
                nome="Fisica",
                classe="L-30",
                anno_accademico="2021/2022",
                dipartimento_id=98765)
             ]
        )
    ],
)
def test_get_courses(
    mocker: MockerFixture,
    year: int,
    dept_code: int,
    expected_payload_subset: Dict[str, Any],
    mock_response_data: List[Dict[str, Any]],
    expected_result: List[CorsoDiStudi]
) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getCourses"

    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"data": mock_response_data}

    # act
    result = get_courses(year, dept_code)

    # assert
    assert len(result) == len(expected_result)
    assert all(isinstance(c, CorsoDiStudi) for c in result)
    assert result == expected_result
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    actual_payload = kwargs["json"]
    for key, value in expected_payload_subset.items():
        assert actual_payload[key] == value


@pytest.mark.parametrize(
    "year, dept_code",
    [
        (2024, 12345),
        (2023, 67890),
        (2022, 11121),
    ]
)
def test_get_courses_api_failure(
    mocker: MockerFixture,
    year: int,
    dept_code: int
) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getCourses"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.side_effect = requests.exceptions.ConnectionError(
        "API non raggiungibile")

    # act
    result = get_courses(year, dept_code)

    # assert
    assert result == []
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    actual_payload = kwargs["json"]
    assert actual_payload["academicYear"] == year
    assert actual_payload["departmentCode"] == str(dept_code)
    assert actual_payload["surveys"] == ""


# TESTS get_activities
@pytest.mark.parametrize(
    "year, dept_code, course_code, expected_payload_subset, mock_response_data, expected_result",
    [
        (
            2023, 190141, "W82",
            {"surveys": "", "academicYear": 2023,
                "departmentCode": "190141", "courseCode": "W82"},
            [
                {
                    "activityCode": "1001829",
                    "activityName": "ULTERIORI ATTIVITA'",
                    "professorName": "FRANCESCO",
                    "professorLastName": "GUARNERA",
                    "professorTaxCode": "",
                    "channel": None,
                    "partCode": None,
                    "SSDsigla": "INF/01"
                },
                {
                    "activityCode": "A3688",
                    "activityName": "MATERIA SPORCA",
                    "professorName": "MARIO",
                    "professorLastName": "ROSSI"
                },
                {"activityCode": None, "activityName": "TOTALE"}],
            [Insegnamento(
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
                ssd="INF/01",
                professor_tax=""
            )]
        )
    ]
)
def test_get_activities(
    mocker: MockerFixture,
    year: int,
    dept_code: int,
    course_code: str,
    expected_payload_subset: Dict[str, Any],
    mock_response_data: List[Dict[str, Any]],
    expected_result: List[Insegnamento]
) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getActivities"

    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"data": mock_response_data}

    # act
    result = get_activities(year, dept_code, course_code)

    # assert
    assert len(result) == len(expected_result)
    assert all(isinstance(a, Insegnamento) for a in result)
    assert result == expected_result
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    actual_payload = kwargs["json"]
    for key, value in expected_payload_subset.items():
        assert actual_payload[key] == value


@pytest.mark.parametrize(
    "year, dept_code, course_code",
    [
        (2024, 12345, "M12"),
        (2023, 67890, "F34"),
    ]
)
def test_get_activities_api_failure(
    mocker: MockerFixture,
    year: int,
    dept_code: int,
    course_code: str
) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getActivities"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.side_effect = requests.exceptions.ConnectionError(
        "API non raggiungibile")

    # act
    result = get_activities(year, dept_code, course_code)

    # assert
    assert result == []
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
    "year, dept_code, course_code, activity_code, prof_tax, mock_response, expected_payload, expected_result",
    [
        # CASO 1: Successo
        (
            2023, 190141, "W82", 1014456, "PROFCF123",
            {
                "clusterData": [{
                    "cluster": {"Text": "Test Cluster"},
                    "questions": [
                        {"questionCode": "1", "submissions": 10, "answers": []}
                    ]
                }],
                "graphPieList": []
            },
            {
                "surveys": "",
                "academicYear": 2023,
                "departmentCode": "190141",
                "courseCode": "W82",
                "activityCode": "1014456",
                "partCode": "null",
                "professor": "PROFCF123"
            },
            [
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
                    sugg_nf=[]
                )
            ]
        ),
        # CASO 2: Nessun dato trovato
        (
            2023, 190141, "W82", 9999999, "",
            {"clusterData": [], "graphPieList": []},
            {
                "surveys": "",
                "academicYear": 2023,
                "departmentCode": "190141",
                "courseCode": "W82",
                "activityCode": "9999999",
                "partCode": "null",
                "professor": ""
            },
            [
                SchedaOpis(
                    anno_accademico="2023/2024",
                    id_insegnamento=9999999,
                    totale_schede=0,  # Nessuna scheda
                    totale_schede_nf=0,
                    fc=0,
                    inatt_nf=0,
                    domande=[0] * 60,
                    domande_nf=[0] * 60,
                    motivo_nf=[],
                    sugg=[],
                    sugg_nf=[]
                )]
        )
    ]
)
def test_get_questions(
    mocker: MockerFixture,
    year: int,
    dept_code: int,
    course_code: str,
    activity_code: int,
    prof_tax: str,
    mock_response: Dict[str, Any],
    expected_payload: Dict[str, Any],
    expected_result: List[SchedaOpis]
) -> None:
    # arange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getQuestions"
    mock_post = mocker.patch("src.api_client.session.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = mock_response

    # act
    result = get_questions(year, dept_code, course_code,
                           activity_code, prof_tax)

    # assert
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == expected_url
    assert kwargs["json"] == expected_payload
    assert result == expected_result


@pytest.mark.parametrize(
    "year, dept_code, course_code, activity_code, prof_tax",
    [
        (2024, 12345, "M12", 987654, "PROFCF1"),
        (2023, 67890, "F34", 112233, "PROFCF2"),
    ]
)
def test_get_questions_failure(
    mocker: MockerFixture,
    year: int,
    dept_code: int,
    course_code: str,
    activity_code: int,
    prof_tax: str
) -> None:
    # arrange
    expected_url = "https://public.smartedu.unict.it/EnqaDataViewer/getQuestions"
    mock_post = mocker.patch("src.api_client.session.post")

    import requests
    mock_post.side_effect = requests.exceptions.ConnectionError(
        "API non raggiungibile")

    # act
    result = get_questions(year, dept_code, course_code,
                           activity_code, prof_tax)

    # assert
    assert result == []
    mock_post.assert_called_once()

    args, kwargs = mock_post.call_args
    assert args[0] == expected_url

    actual_payload = kwargs["json"]
    assert actual_payload["academicYear"] == year
    assert actual_payload["departmentCode"] == str(dept_code)
    assert actual_payload["courseCode"] == course_code
    assert actual_payload["activityCode"] == str(activity_code)
    assert actual_payload["professor"] == prof_tax
    assert actual_payload["surveys"] == ""
