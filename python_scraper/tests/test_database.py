import logging
from typing import Generator
from unittest.mock import MagicMock

import mysql.connector
import pytest

from src import database
from src.models import CorsoDiStudi, Dipartimento, Insegnamento, SchedaOpis


@pytest.fixture(autouse=True)
def reset_db_connection() -> Generator[None, None, None]:
    database.set_connection(None)
    yield
    database.set_connection(None)


@pytest.fixture
def mock_db_connection(mocker) -> tuple[MagicMock, MagicMock]:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_conn.cursor.return_value = mock_cursor

    mocker.patch("src.database.mysql.connector.connect", return_value=mock_conn)

    database.set_connection(mock_conn)

    return mock_conn, mock_cursor


def test_connect_to_db(mocker) -> None:
    # act
    mock_connect = mocker.patch("src.database.mysql.connector.connect")
    database.connect_to_db()

    # assert
    mock_connect.assert_called_once()
    assert database.get_connection() is not None


def test_insert_department_success(mock_db_connection) -> None:
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (99,)

    dip = Dipartimento(unict_id=123, nome="Informatica", anno_accademico="2023/2024")

    # act
    result = database.insert_department(dip)

    # assert
    assert result == 99
    assert mock_cursor.execute.call_count == 2
    mock_conn.commit.assert_called_once()
    mock_cursor.close.assert_called_once()


def test_insert_department_failure(mock_db_connection, caplog) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.execute.side_effect = mysql.connector.Error("Errore DB")
    dip = Dipartimento(unict_id=123, nome="Informatica", anno_accademico="2023/2024")

    # act
    result = database.insert_department(dip)

    # assert
    assert result == -1
    assert "Errore DB durante l'inserimento del dipartimento" in caplog.text


def test_insert_course(mock_db_connection) -> None:
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (42,)

    corso = CorsoDiStudi(
        unict_id="M12",
        nome="Matematica",
        classe="LM-40",
        anno_accademico="2023/2024",
        dipartimento_id=123,
    )

    # act
    result = database.insert_course(corso, dipartimento_internal_id=99)

    # assert
    assert result == 42
    assert mock_cursor.execute.call_count == 2
    mock_conn.commit.assert_called_once()


def test_insert_course_failure(mock_db_connection, caplog) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.execute.side_effect = mysql.connector.Error("Errore DB")
    corso = CorsoDiStudi(
        unict_id="M12",
        nome="Matematica",
        classe="LM-40",
        anno_accademico="2023/2024",
        dipartimento_id=123,
    )

    # act
    result = database.insert_course(corso, dipartimento_internal_id=99)

    # assert
    assert result == -1
    assert "Errore DB durante l'inserimento del corso" in caplog.text


def test_insert_insegnamento(mock_db_connection) -> None:
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = None  # existence check: not found
    mock_cursor.lastrowid = 100

    ins = Insegnamento(
        codice_gomp=1010,
        id_cds="M12",
        anno_accademico="2023/2024",
        nome="Analisi I",
        docente="Mario Rossi",
        professor_tax="",
    )

    # act
    result = database.insert_insegnamento(ins, corso_internal_id=42)

    # assert
    assert result == 100
    assert mock_cursor.execute.call_count == 2  # SELECT check + INSERT
    mock_conn.commit.assert_called_once()


def test_insert_insegnamento_failure(mock_db_connection, caplog) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.execute.side_effect = mysql.connector.Error("Errore DB")
    ins = Insegnamento(
        codice_gomp=1010,
        id_cds="M12",
        anno_accademico="2023/2024",
        nome="Analisi I",
        docente="Mario Rossi",
        professor_tax="",
    )

    result = database.insert_insegnamento(ins, corso_internal_id=42)

    assert result == -1
    assert "Errore DB durante l'inserimento dell'insegnamento" in caplog.text


def test_insert_schede_opis(mock_db_connection) -> None:
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (0,)  # COUNT(*) check: no existing records
    mock_cursor.rowcount = 1

    scheda = SchedaOpis(
        anno_accademico="2023/2024",
        id_insegnamento=1010,
        totale_schede=5,
        totale_schede_nf=0,
        fc=0,
        inatt_nf=0,
        domande=[1, 2, 3],
        domande_nf=[],
        motivo_nf=[],
        sugg=[],
        sugg_nf=[],
    )

    # act
    result = database.insert_schede_opis([scheda], insegnamento_internal_id=100)

    # assert
    assert result == 1
    mock_cursor.executemany.assert_called_once()
    args, _ = mock_cursor.executemany.call_args
    query_eseguita = args[0]
    valori_passati = args[1]

    assert "INSERT INTO schede_opis" in query_eseguita
    assert len(valori_passati) == 1

    riga_inserita = valori_passati[0]
    assert "[1, 2, 3]" in riga_inserita
    mock_conn.commit.assert_called_once()


def test_insert_schede_opis_failure(mock_db_connection, caplog) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (0,)  # COUNT(*) check: no existing records
    mock_cursor.executemany.side_effect = mysql.connector.Error("Errore DB")
    scheda = SchedaOpis(
        anno_accademico="2023/2024",
        id_insegnamento=1010,
        totale_schede=5,
        totale_schede_nf=0,
        fc=0,
        inatt_nf=0,
        domande=[1, 2, 3],
        domande_nf=[],
        motivo_nf=[],
        sugg=[],
        sugg_nf=[],
    )

    assert database.insert_schede_opis([scheda], insegnamento_internal_id=100) == -1

    assert "Errore DB durante il salvataggio" in caplog.text


def test_connect_to_db_failure(mocker, caplog) -> None:
    mock_connect = mocker.patch("src.database.mysql.connector.connect")
    mock_connect.side_effect = mysql.connector.Error("Credenziali errate")

    with pytest.raises(mysql.connector.Error):
        database.connect_to_db()

    assert "Errore di connessione a MySQL" in caplog.text


def test_close_connection() -> None:
    mock_conn = MagicMock()
    mock_conn.is_connected.return_value = True
    database.set_connection(mock_conn)

    database.close_connection()

    mock_conn.close.assert_called_once()


def test_inserts_without_connection(caplog) -> None:
    database.set_connection(None)
    dip = Dipartimento(unict_id=1, nome="Dipartimento", anno_accademico="23/24")
    corso = CorsoDiStudi(
        unict_id="C1",
        nome="Corso",
        classe="L",
        anno_accademico="23/24",
        dipartimento_id=1,
    )
    ins = Insegnamento(
        codice_gomp=1,
        id_cds="C1",
        anno_accademico="23/24",
        nome="Materia",
        docente="Doc",
        professor_tax="",
    )
    scheda = SchedaOpis(
        anno_accademico="23/24",
        id_insegnamento=1010,
        totale_schede=5,
        totale_schede_nf=0,
        fc=0,
        inatt_nf=0,
        domande=[1, 2],
        domande_nf=[],
        motivo_nf=[],
        sugg=[],
        sugg_nf=[],
    )

    assert database.insert_department(dip) == -1
    assert "Database non connesso" in caplog.text
    assert database.insert_course(corso, 1) == -1
    assert database.insert_insegnamento(ins, 1) == -1
    assert database.insert_schede_opis([scheda], 1) == -1


# ---------------------------------------------------------------------------
# seed_domande
# ---------------------------------------------------------------------------


def test_seed_domande_inserts_default_rows(mock_db_connection, caplog) -> None:
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.rowcount = 12
    caplog.set_level(logging.INFO, logger="src.database")

    database.seed_domande()

    mock_cursor.executemany.assert_called_once()
    mock_conn.commit.assert_called_once()
    assert "12 righe inserite" in caplog.text


def test_seed_domande_idempotent_when_table_full(mock_db_connection, caplog) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.rowcount = 0
    caplog.set_level(logging.INFO, logger="src.database")

    database.seed_domande()

    assert "già popolata" in caplog.text


def test_seed_domande_logs_db_error(mock_db_connection, caplog) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.executemany.side_effect = mysql.connector.Error("Errore DB")

    database.seed_domande()

    assert "Errore DB durante il seeding" in caplog.text


def test_seed_domande_no_connection(caplog) -> None:
    database.set_connection(None)
    database.seed_domande()
    assert "Database non connesso" in caplog.text


# ---------------------------------------------------------------------------
# insert_insegnamento — existing-row branch & lookups
# ---------------------------------------------------------------------------


def test_insert_insegnamento_returns_existing_id(mock_db_connection) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (777,)  # existence check finds row
    ins = Insegnamento(
        codice_gomp=1010,
        id_cds="M12",
        anno_accademico="2023/2024",
        nome="Analisi I",
        docente="Mario Rossi",
        professor_tax="",
    )

    result = database.insert_insegnamento(ins, corso_internal_id=42)

    assert result == 777
    # Only the existence SELECT was executed — no INSERT.
    assert mock_cursor.execute.call_count == 1


# ---------------------------------------------------------------------------
# insert_schede_opis — idempotent branch (rows already exist)
# ---------------------------------------------------------------------------


def test_insert_schede_opis_skips_when_already_present(mock_db_connection) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (5,)  # already 5 schede in DB
    scheda = SchedaOpis(
        anno_accademico="2023/2024",
        id_insegnamento=1010,
        totale_schede=5,
        totale_schede_nf=0,
        fc=0,
        inatt_nf=0,
        domande=[1],
        domande_nf=[],
        motivo_nf=[],
        sugg=[],
        sugg_nf=[],
    )

    result = database.insert_schede_opis([scheda], insegnamento_internal_id=100)

    assert result == 0
    mock_cursor.executemany.assert_not_called()


# ---------------------------------------------------------------------------
# delete_insegnamento_if_orphan
# ---------------------------------------------------------------------------


def test_delete_insegnamento_if_orphan_returns_true_when_deleted(
    mock_db_connection,
) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.rowcount = 1

    assert database.delete_insegnamento_if_orphan(42) is True


def test_delete_insegnamento_if_orphan_returns_false_when_nothing_deleted(
    mock_db_connection,
) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.rowcount = 0

    assert database.delete_insegnamento_if_orphan(42) is False


def test_delete_insegnamento_if_orphan_invalid_id() -> None:
    database.set_connection(MagicMock())
    assert database.delete_insegnamento_if_orphan(0) is False
    assert database.delete_insegnamento_if_orphan(-1) is False


def test_delete_insegnamento_if_orphan_no_connection() -> None:
    database.set_connection(None)
    assert database.delete_insegnamento_if_orphan(42) is False


def test_delete_insegnamento_if_orphan_logs_db_error(
    mock_db_connection, caplog
) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.execute.side_effect = mysql.connector.Error("Errore DB")

    assert database.delete_insegnamento_if_orphan(42) is False
    assert "insegnamento orfano" in caplog.text


# ---------------------------------------------------------------------------
# get_processed_activity_codes
# ---------------------------------------------------------------------------


def test_get_processed_activity_codes_returns_set(mock_db_connection) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.fetchall.return_value = [(101,), (102,), (103,)]

    result = database.get_processed_activity_codes(42, "2024/2025")

    assert result == {101, 102, 103}


def test_get_processed_activity_codes_empty_set_on_db_error(
    mock_db_connection, caplog
) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.execute.side_effect = mysql.connector.Error("Errore DB")

    assert database.get_processed_activity_codes(42, "2024/2025") == set()
    assert "lookup attività processate" in caplog.text


def test_get_processed_activity_codes_no_connection() -> None:
    database.set_connection(None)
    assert database.get_processed_activity_codes(42, "2024/2025") == set()


# ---------------------------------------------------------------------------
# find_* lookups
# ---------------------------------------------------------------------------


def test_find_department_id_returns_id(mock_db_connection) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (11,)
    assert database.find_department_id(123, "2024/2025") == 11


def test_find_department_id_returns_minus_one_when_missing(mock_db_connection) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = None
    assert database.find_department_id(123, "2024/2025") == -1


def test_find_department_id_logs_db_error(mock_db_connection, caplog) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.execute.side_effect = mysql.connector.Error("Errore DB")
    assert database.find_department_id(123, "2024/2025") == -1
    assert "lookup dipartimento" in caplog.text


def test_find_department_id_no_connection() -> None:
    database.set_connection(None)
    assert database.find_department_id(1, "2024/2025") == -1


def test_find_course_id_returns_id(mock_db_connection) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (42,)
    assert database.find_course_id("C1", "2024/2025") == 42


def test_find_course_id_returns_minus_one_when_missing(mock_db_connection) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = None
    assert database.find_course_id("C1", "2024/2025") == -1


def test_find_course_id_logs_db_error(mock_db_connection, caplog) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.execute.side_effect = mysql.connector.Error("Errore DB")
    assert database.find_course_id("C1", "2024/2025") == -1
    assert "lookup corso" in caplog.text


def test_find_course_id_no_connection() -> None:
    database.set_connection(None)
    assert database.find_course_id("C1", "2024/2025") == -1


def test_find_insegnamento_id_returns_id(mock_db_connection) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (99,)
    assert (
        database.find_insegnamento_id(
            codice_gomp=1,
            anno_accademico="2024/2025",
            docente="Rossi",
            id_modulo=0,
            course_unict_id="C1",
        )
        == 99
    )


def test_find_insegnamento_id_returns_minus_one_when_missing(
    mock_db_connection,
) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = None
    assert (
        database.find_insegnamento_id(
            codice_gomp=1,
            anno_accademico="2024/2025",
            docente="Rossi",
            id_modulo=0,
            course_unict_id="C1",
        )
        == -1
    )


def test_find_insegnamento_id_logs_db_error(mock_db_connection, caplog) -> None:
    _, mock_cursor = mock_db_connection
    mock_cursor.execute.side_effect = mysql.connector.Error("Errore DB")
    assert (
        database.find_insegnamento_id(
            codice_gomp=1,
            anno_accademico="2024/2025",
            docente="Rossi",
            id_modulo=0,
            course_unict_id="C1",
        )
        == -1
    )
    assert "lookup insegnamento" in caplog.text


def test_find_insegnamento_id_no_connection() -> None:
    database.set_connection(None)
    assert (
        database.find_insegnamento_id(
            codice_gomp=1,
            anno_accademico="2024/2025",
            docente="Rossi",
            id_modulo=0,
            course_unict_id="C1",
        )
        == -1
    )


def test_close_connection_skips_when_already_closed() -> None:
    mock_conn = MagicMock()
    mock_conn.is_connected.return_value = False
    database.set_connection(mock_conn)

    database.close_connection()

    mock_conn.close.assert_not_called()
