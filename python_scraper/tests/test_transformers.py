import pytest
from typing import Any, Optional
from src.transformers import parse_course_name, parse_insegnamento_data, parse_scheda_opis_data


@pytest.mark.parametrize(
    "input_str, expected_nome, expected_classe",
    [
        ("Informatica L-31", "Informatica", "L-31"),
        ("Matematica LM-40", "Matematica", "LM-40"),
        ("Informatica   L-31", "Informatica", "L-31"),
        ("Storia Romana", "Storia Romana", ""),
        ("", "", ""),
        (None, "", ""),
    ],
)
def test_parse_course_name(
    input_str: Optional[str],
    expected_nome: str,
    expected_classe: str,
) -> None:

    # act
    nome, classe = parse_course_name(input_str)

    # assert
    assert nome == expected_nome
    assert classe == expected_classe
    assert nome == expected_nome
    assert classe == expected_classe


@pytest.mark.parametrize(
    "input_data, expected_dict",
    [
        (
            {
                "activityCode": "1001",
                "activityName": "TEST NULL",
                "professorName": "MARIO",
                "professorLastName": "ROSSI",
                "channel": None,
                "partCode": None,
                "SSDsigla": None
            },
            {
                "codice_gomp": 1001,
                "nome": "TEST NULL",
                "docente": "ROSSI MARIO",
                "canale": "no",
                "id_modulo": 0,
                "ssd": None
            }
        ),
        (
            {
                "activityCode": "9999",
                "activityName": "TEST FULL",
                "professorName": "LUIGI",
                "professorLastName": "VERDI",
                "channel": "A-L",
                "partCode": "123",
                "SSDsigla": "INF/01"
            },
            {
                "codice_gomp": 9999,
                "nome": "TEST FULL",
                "docente": "VERDI LUIGI",
                "canale": "A-L",
                "id_modulo": 123,
                "ssd": "INF/01"
            }
        ),
        (
            {
                "activityCode": 1234,
                "activityName": "TEST id_modulo EXCEPTION",
                "professorName": "ANNA",
                "professorLastName": "BIONDI",
                "channel": "",
                "partCode": "abc",
                "SSDsigla": "MAT/02"
            },
            {
                "codice_gomp": 1234,
                "nome": "TEST id_modulo EXCEPTION",
                "docente": "BIONDI ANNA",
                "canale": "no",
                "id_modulo": 0,
                "ssd": "MAT/02"
            }
        )
    ]
)
def test_parse_insegnamento_data(
    input_data: dict,
    expected_dict: dict
) -> None:

    # act
    result = parse_insegnamento_data(input_data)

    # assert
    assert result == expected_dict


@pytest.fixture
def mock_opis_json() -> dict[str, Any]:
    return {
        "clusterData": [
            {
                "cluster": {"Text": "Studenti Frequentanti"},
                "questions": [
                    {
                        "questionCode": "1",
                        "submissions": 10,
                        "answers": [
                            {"answerCode": "R1", "count": 2},
                            {"answerCode": "R4", "count": 8}
                        ]
                    },
                    {
                        "questionCode": "2",
                        "submissions": 10,
                        "answers": [
                            {"answerCode": "R3", "count": 5},
                            {"answerCode": "R6", "count": 99}
                        ]
                    },
                    {
                        "questionCode": "3", 
                        "submissions": 12,
                        "answers": []
                    },
                    {
                        "questionCode": "abc", 
                        "submissions": 0,
                        "answers": []
                    },
                    {
                        "questionCode": "15", 
                        "submissions": 0,
                        "answers": []
                    },
                    {
                        "questionCode": None,
                        "submissions": 0,
                        "answers": []
                    }
                ]
            }
        ],
        "graphPieList": [
            {
                "name": "Studenti Frequentanti",
                "dataPie": [
                    {
                        "datasets": [
                            {
                                "label": "Distribuzione -Età anagrafica",
                                "data": [5.0, 3.0]
                            }
                        ],
                        "labels": ["20-21", "22-23"]
                    }
                ]
            },
            {
                "name": "Non Frequentanti",
                "dataPie": [{"datasets": [{"label": "Età", "data": [100.0]}], "labels": ["99"]}]
            }
        ]
    }

def test_parse_scheda_opis_data(mock_opis_json: dict[str, Any]) -> None:
    
    # act
    results = parse_scheda_opis_data(mock_opis_json)
    
    # assert
    assert len(results) == 1
    scheda = results[0]
    assert scheda["tipo_scheda"] == "Studenti Frequentanti"
    assert scheda["totale_schede"] == 12
    assert len(scheda["domande"]) == 60
    assert scheda["domande"][0] == 2
    assert scheda["domande"][1] == 0
    assert scheda["domande"][3] == 8
    assert scheda["domande"][7] == 5
    assert sum(scheda["domande"]) == 15
    assert scheda["eta"] is not None
    assert isinstance(scheda["eta"], dict)
    assert scheda["eta"]["20-21"] == 5
    assert scheda["eta"]["22-23"] == 3
    assert "99" not in scheda["eta"]