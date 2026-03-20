import pytest
from typing import Any, Optional
from src.transformers import (
    parse_course_name,
    parse_insegnamento_data,
    parse_scheda_opis_data,
)


@pytest.mark.parametrize(
    "input_str, expected_nome, expected_classe",
    [
        # --- CASI CLASSICI ---
        ("Informatica L-31", "Informatica", "L-31"),
        ("Matematica LM-40", "Matematica", "LM-40"),
        ("Informatica   L-31", "Informatica", "L-31"),
        # --- CASI CON TRATTINI O SPAZI EXTRA ---
        ("Fisica L-30 ", "Fisica", "L-30"),
        ("Informatica - L-31", "Informatica", "L-31"),
        # --- CASI CON PARENTESI ---
        ("Informatica (L-31)", "Informatica", "L-31"),
        ("Scienze Agrarie (LM-69)", "Scienze Agrarie", "LM-69"),
        # --- CASI CON R (RIFORMATO) ---
        (
            "Viticoltura, Enologia ed Enomarketing L-26 R",
            "Viticoltura, Enologia ed Enomarketing",
            "L-26 R",
        ),
        ("Biotecnologie Agrarie (LM-7 R)", "Biotecnologie Agrarie", "LM-7 R"),
        # --- CASI CON PROFESSIONI SANITARIE (L/SNT) ---
        (
            "Ostetricia (abilitante alla professione sanitaria di Ostetrica/o) L/SNT1",
            "Ostetricia (abilitante alla professione sanitaria di Ostetrica/o)",
            "L/SNT1",
        ),
        ("Infermieristica (L/SNT1)", "Infermieristica", "L/SNT1"),
        # --- CASI CON MAGISTRALE A CICLO UNICO (LMCU) ---
        ("Medicina e Chirurgia LMCU-41", "Medicina e Chirurgia", "LMCU-41"),
        # --- CASI MINUSCOLI (re.IGNORECASE) ---
        ("scienze motorie l/snt2", "scienze motorie", "L/SNT2"),
        ("biologia l-13 r", "biologia", "L-13 R"),
        # --- CASI SENZA CLASSE O VUOTI ---
        ("Storia Romana", "Storia Romana", ""),
        ("", "", ""),
        (None, "", ""),
        # --- CASI CON C.U. (Ciclo Unico esplicito) ---
        ("Architettura LM-4 c.u. R", "Architettura", "LM-4 C.U. R"),
        ("Farmacia (LM-41 cu)", "Farmacia", "LM-41 CU"),
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


@pytest.mark.parametrize(
    "input_data, expected_dict",
    [
        (
            {
                "activityCode": "1001",
                "activityName": "TEST NULL",
                "professorName": "MARIO",
                "professorLastName": "ROSSI",
                "professorTaxCode": "",
                "channel": None,
                "partCode": None,
                "partName": None,
                "SSDsigla": None,
            },
            {
                "codice_gomp": 1001,
                "nome": "TEST NULL",
                "docente": "ROSSI MARIO",
                "canale": "no",
                "id_modulo": 0,
                "nome_modulo": None,
                "ssd": None,
                "professor_tax": "",
            },
        ),
        (
            {
                "activityCode": "9999",
                "activityName": "TEST FULL",
                "professorName": "LUIGI",
                "professorLastName": "VERDI",
                "professorTaxCode": "",
                "channel": "A-L",
                "partCode": "123",
                "partName": "TEST MODULE",
                "SSDsigla": "INF/01",
            },
            {
                "codice_gomp": 9999,
                "nome": "TEST FULL",
                "docente": "VERDI LUIGI",
                "canale": "A-L",
                "id_modulo": 123,
                "nome_modulo": "TEST MODULE",
                "ssd": "INF/01",
                "professor_tax": "",
            },
        ),
        (
            {
                "activityCode": 1234,
                "activityName": "TEST id_modulo EXCEPTION",
                "professorName": "ANNA",
                "professorLastName": "BIONDI",
                "professorTaxCode": "",
                "channel": "",
                "partCode": "abc",
                "partName": None,
                "SSDsigla": "MAT/02",
            },
            {
                "codice_gomp": 1234,
                "nome": "TEST id_modulo EXCEPTION",
                "docente": "BIONDI ANNA",
                "canale": "no",
                "id_modulo": 0,
                "nome_modulo": None,
                "ssd": "MAT/02",
                "professor_tax": "",
            },
        ),
        (
            {
                "activityCode": "A3688",
                "activityName": "MATERIA DA SALTARE",
            },
            None,
        ),
        (
            {
                "activityCode": None,
                "activityName": "TOTALE",
            },
            None,
        ),
        (
            {
                "activityCode": "",
                "activityName": "VUOTA",
            },
            None,
        ),
    ],
)
def test_parse_insegnamento_data(
    input_data: dict, expected_dict: Optional[dict]
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
                            {"answerCode": "R4", "count": 8},
                        ],
                    },
                    {
                        "questionCode": "2",
                        "submissions": 12,
                        "answers": [
                            {"answerCode": "R3", "count": 5},
                            {"answerCode": "R5", "count": 7},
                        ],
                    },
                    {"questionCode": None, "submissions": 1, "answers": []},
                    {"questionCode": "ABC", "submissions": 1, "answers": []},
                    {"questionCode": "15", "submissions": 1, "answers": []},
                ],
            },
            {
                "cluster": {"Text": "Studenti Non Frequentanti"},
                "questions": [
                    {
                        "questionCode": "1",
                        "submissions": 5,
                        "answers": [{"answerCode": "R5", "count": 5}],
                    }
                ],
            },
        ],
        "graphPieList": [
            {
                "name": "Studenti Frequentanti",
                "dataPie": [
                    {
                        "datasets": [
                            {
                                "label": "Distribuzione -Età anagrafica",
                                "data": [5.0, 3.0],
                            }
                        ],
                        "labels": ["20-21", "22-23"],
                    },
                    {
                        "datasets": [
                            {"label": "Genere degli studenti", "data": [10.0, 15.0]}
                        ],
                        "labels": ["M", "F"],
                    },
                    {
                        "datasets": [
                            {
                                "label": "A - Numero medio di studenti che hanno frequentato",
                                "data": [6.0],
                            }
                        ],
                        "labels": ["Fino a 25"],
                    },
                    {
                        "datasets": [
                            {"label": "Anno di iscrizione", "data": [20.0, 4.0]}
                        ],
                        "labels": ["In corso", "Fuori corso"],
                    },
                    {
                        "datasets": [
                            {
                                "label": "Quanto tempo impiega per arrivare dal domicilio",
                                "data": [20.0],
                            }
                        ],
                        "labels": ["Da 1 a 30 minuti"],
                    },
                    {
                        "datasets": [
                            {"label": "Studio autonomo giornalmente", "data": [8.0]}
                        ],
                        "labels": ["2 ore"],
                    },
                    {"datasets": []},
                    {
                        "datasets": [{"label": "Grafico Sconosciuto", "data": [1.0]}],
                        "labels": ["X"],
                    },
                    {
                        "datasets": [
                            {"label": "Quante ore di studio, in totale", "data": []}
                        ],
                        "labels": [],
                    },
                ],
            },
            {
                "name": "Non Frequentanti",
                "dataPie": [
                    {"datasets": [{"label": "Età", "data": [100.0]}], "labels": ["99"]},
                    {"datasets": [{"label": "Genere", "data": [5.0]}], "labels": ["F"]},
                ],
            },
        ],
    }


def test_parse_scheda_opis_data(mock_opis_json: dict[str, Any]) -> None:
    # act
    results = parse_scheda_opis_data(mock_opis_json)

    # assert
    assert len(results) == 1
    scheda = results[0]
    assert scheda["totale_schede"] == 12
    assert len(scheda["domande"]) == 60
    assert scheda["domande"][0] == 2
    assert scheda["domande"][3] == 8
    assert scheda["domande"][7] == 5
    assert scheda["domande"][9] == 7
    assert scheda["eta"] is not None
    assert isinstance(scheda["eta"], dict)
    assert scheda["eta"]["20-21"] == 5
    assert scheda["eta"]["22-23"] == 3
    assert scheda["eta"]["99"] == 100
    assert scheda["femmine"] == 15
    assert scheda["num_studenti"] is not None
    assert scheda["num_studenti"]["Fino a 25"] == 6
    assert scheda["fc"] == 4
    assert scheda["ragg_uni"]["Da 1 a 30 minuti"] == 20
    assert scheda["studio_gg"]["2 ore"] == 8
    assert scheda["femmine_nf"] == 5
    assert scheda["studio_tot"] is None
