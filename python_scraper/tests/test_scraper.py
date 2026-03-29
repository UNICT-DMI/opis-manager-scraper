import pytest

from src.models import Insegnamento
from src.scraper import assign_channels


@pytest.mark.parametrize(
    "input_activities, expected_canali",
    [
        # Caso 1: Lista vuota
        ([], []),
        # Caso 2: Singolo insegnamento senza moduli
        (
            [
                Insegnamento(
                    nome="Analisi 1",
                    nome_modulo=None,
                    canale="no",
                    docente="Pippo",
                    codice_gomp=12345,
                    id_cds="123",
                    anno_accademico="2022",
                    professor_tax="sdad",
                )
            ],
            ["no"],
        ),
        # Caso 3: Insegnamento multiplo senza moduli (diventa canale 1, 2, 3)
        (
            [
                Insegnamento(
                    nome="Analisi 1",
                    nome_modulo=None,
                    canale="no",
                    docente="Pippo",
                    codice_gomp=12345,
                    id_cds="123",
                    anno_accademico="2022",
                    professor_tax="sdad",
                ),
                Insegnamento(
                    nome="Analisi 1",
                    nome_modulo=None,
                    canale="no",
                    docente="Caio",
                    codice_gomp=12346,
                    id_cds="123",
                    anno_accademico="2022",
                    professor_tax="sdad",
                ),
                Insegnamento(
                    nome="Analisi 1",
                    nome_modulo=None,
                    canale="no",
                    docente="Sempronio",
                    codice_gomp=12347,
                    id_cds="123",
                    anno_accademico="2022",
                    professor_tax="sdad",
                ),
            ],
            ["1", "2", "3"],
        ),
        # Caso 4: Insegnamento singolo diviso in moduli (rimane "no")
        (
            [
                Insegnamento(
                    nome="Programmazione 2",
                    nome_modulo="Teoria",
                    canale="no",
                    docente="Faro",
                    codice_gomp=12348,
                    id_cds="123",
                    anno_accademico="2022",
                    professor_tax="sdad",
                ),
                Insegnamento(
                    nome="Programmazione 2",
                    nome_modulo="Laboratorio",
                    canale="no",
                    docente="Faro",
                    codice_gomp=12349,
                    id_cds="123",
                    anno_accademico="2022",
                    professor_tax="sdad",
                ),
            ],
            ["no", "no"],
        ),
        # Caso 5: Insegnamento multiplo diviso in moduli (diventa canale 1 e 2)
        (
            [
                Insegnamento(
                    nome="Programmazione 2",
                    nome_modulo="Teoria",
                    canale="no",
                    docente="Faro",
                    codice_gomp=12348,
                    id_cds="123",
                    anno_accademico="2022",
                    professor_tax="sdad",
                ),  # Canale 1
                Insegnamento(
                    nome="Programmazione 2",
                    nome_modulo="Laboratorio",
                    canale="no",
                    docente="Moltisanti",
                    codice_gomp=12349,
                    id_cds="123",
                    anno_accademico="2022",
                    professor_tax="sdad",
                ),  # Canale 1
                Insegnamento(
                    nome="Programmazione 2",
                    nome_modulo="Teoria",
                    canale="no",
                    docente="Faro",
                    codice_gomp=12348,
                    id_cds="123",
                    anno_accademico="2022",
                    professor_tax="sdad",
                ),  # Canale 2
                Insegnamento(
                    nome="Programmazione 2",
                    nome_modulo="Laboratorio",
                    canale="no",
                    docente="Santoro",
                    codice_gomp=12349,
                    id_cds="123",
                    anno_accademico="2022",
                    professor_tax="sdad",
                ),  # Canale 2
            ],
            ["1", "1", "2", "2"],
        ),
    ],
    ids=[
        "lista_vuota",
        "singolo_senza_moduli",
        "multiplo_senza_moduli",
        "singolo_con_moduli",
        "multiplo_con_moduli",
    ],
)
def test_assign_channels(input_activities, expected_canali) -> None:
    # act
    result = assign_channels(input_activities)

    # assert
    assert len(result) == len(expected_canali)
    assert [activity.canale for activity in result] == expected_canali
