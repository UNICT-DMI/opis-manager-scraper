import mysql.connector
import pytest
from unittest.mock import MagicMock
from src import database
from src.models import Dipartimento, CorsoDiStudi, Insegnamento, SchedaOpis


@pytest.fixture(autouse=True)
def reset_db_connection():
    database._connection = None
    yield
    database._connection = None


@pytest.fixture
def mock_db_connection(mocker):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_conn.cursor.return_value = mock_cursor

    mocker.patch("src.database.mysql.connector.connect",
                 return_value=mock_conn)

    database._connection = mock_conn

    return mock_conn, mock_cursor


def test_connect_to_db(mocker):
    # act
    mock_connect = mocker.patch("src.database.mysql.connector.connect")
    database.connect_to_db()

    # assert
    mock_connect.assert_called_once()
    assert database._connection is not None


def test_insert_department_success(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (99,)

    dip = Dipartimento(unict_id=123, nome="Informatica",
                       anno_accademico="2023/2024")

    # act
    result = database.insert_department(dip)

    # assert
    assert result == 99
    assert mock_cursor.execute.call_count == 2
    mock_conn.commit.assert_called_once()
    mock_cursor.close.assert_called_once()


def test_insert_department_failure(mock_db_connection, caplog):
    _, mock_cursor = mock_db_connection
    mock_cursor.execute.side_effect = mysql.connector.Error("Errore DB")
    dip = Dipartimento(unict_id=123, nome="Informatica",
                       anno_accademico="2023/2024")

    # act
    result = database.insert_department(dip)

    # assert
    assert result == -1
    assert "Errore DB durante l'inserimento del dipartimento" in caplog.text


def test_insert_course(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (42,)

    corso = CorsoDiStudi(unict_id="M12", nome="Matematica", classe="LM-40",
                         anno_accademico="2023/2024", dipartimento_id=123)

    # act
    result = database.insert_course(corso, dipartimento_internal_id=99)

    # assert
    assert result == 42
    assert mock_cursor.execute.call_count == 2
    mock_conn.commit.assert_called_once()


def test_insert_course_failure(mock_db_connection, caplog):
    _, mock_cursor = mock_db_connection
    mock_cursor.execute.side_effect = mysql.connector.Error("Errore DB")
    corso = CorsoDiStudi(unict_id="M12", nome="Matematica", classe="LM-40",
                         anno_accademico="2023/2024", dipartimento_id=123)

    # act
    result = database.insert_course(corso, dipartimento_internal_id=99)

    # assert
    assert result == -1
    assert "Errore DB durante l'inserimento del corso" in caplog.text


def test_insert_insegnamento(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.lastrowid = 100

    ins = Insegnamento(codice_gomp=1010, id_cds="M12", anno_accademico="2023/2024",
                       nome="Analisi I", docente="Mario Rossi", professor_tax="")

    # act
    result = database.insert_insegnamento(ins, corso_internal_id=42)

    # assert
    assert result == 100
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()


def test_insert_insegnamento_failure(mock_db_connection, caplog):
    _, mock_cursor = mock_db_connection
    mock_cursor.execute.side_effect = mysql.connector.Error("Errore DB")
    ins = Insegnamento(codice_gomp=1010, id_cds="M12", anno_accademico="2023/2024",
                       nome="Analisi I", docente="Mario Rossi", professor_tax="")

    result = database.insert_insegnamento(ins, corso_internal_id=42)

    assert result == -1
    assert "Errore DB durante l'inserimento dell'insegnamento" in caplog.text


def test_insert_schede_opis(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection

    scheda = SchedaOpis(
        anno_accademico="2023/2024", id_insegnamento=1010, totale_schede=5, totale_schede_nf=0, fc=0, inatt_nf=0,
        domande=[1, 2, 3], domande_nf=[], motivo_nf=[], sugg=[], sugg_nf=[]
    )

    # act
    database.insert_schede_opis([scheda], insegnamento_internal_id=100)

    # assert
    mock_cursor.executemany.assert_called_once()
    args, _ = mock_cursor.executemany.call_args
    query_eseguita = args[0]
    valori_passati = args[1]

    assert "INSERT INTO schede_opis" in query_eseguita
    assert len(valori_passati) == 1

    riga_inserita = valori_passati[0]
    assert '[1, 2, 3]' in riga_inserita
    mock_conn.commit.assert_called_once()


def test_insert_schede_opis_failure(mock_db_connection, caplog):
    _, mock_cursor = mock_db_connection
    mock_cursor.executemany.side_effect = mysql.connector.Error("Errore DB")
    scheda = SchedaOpis(
        anno_accademico="2023/2024", id_insegnamento=1010, totale_schede=5, totale_schede_nf=0, fc=0, inatt_nf=0,
        domande=[1, 2, 3], domande_nf=[], motivo_nf=[], sugg=[], sugg_nf=[]
    )

    database.insert_schede_opis([scheda], insegnamento_internal_id=100)

    assert "Errore DB durante il salvataggio" in caplog.text
