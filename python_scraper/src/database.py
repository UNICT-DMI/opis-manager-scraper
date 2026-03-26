import json
import logging
import os

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error
from mysql.connector.abstracts import MySQLConnectionAbstract
from mysql.connector.pooling import PooledMySQLConnection

load_dotenv()

logger = logging.getLogger(__name__)

_connection = None


def get_connection() -> MySQLConnectionAbstract | PooledMySQLConnection | None:
    return _connection


def set_connection(conn) -> None:
    global _connection
    _connection = conn


def connect_to_db() -> None:
    global _connection

    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "opis_manager")

    try:
        _connection = mysql.connector.connect(
            host=host, port=port, user=user, password=password, database=database
        )
        logger.info(
            "Connessione al database MySQL '%s' stabilita con successo.", database
        )
    except Error as e:
        logger.error("Errore di connessione a MySQL: %s", e)
        raise


def close_connection() -> None:
    if _connection and _connection.is_connected():
        _connection.close()
        logger.info("Connessione al database chiusa.")


def insert_department(department) -> int:
    if not _connection:
        logger.error("Database non connesso. Chiama connect_to_db() prima.")
        return -1

    try:
        cursor = _connection.cursor()

        query_insert = """
            INSERT IGNORE INTO dipartimento (nome, unict_id, anno_accademico)
            VALUES (%s, %s, %s)
        """

        valori_insert = (
            department.nome,
            department.unict_id,
            department.anno_accademico,
        )

        cursor.execute(query_insert, valori_insert)
        _connection.commit()

        query_select = (
            "SELECT id FROM dipartimento WHERE unict_id = %s AND anno_accademico = %s"
        )
        cursor.execute(query_select, (department.unict_id, department.anno_accademico))

        result = cursor.fetchone()
        cursor.close()

        return int(result[0]) if result else -1  # type: ignore
    except Error as e:
        logger.error(
            "Errore DB durante l'inserimento del dipartimento '%s': %s",
            department.nome,
            e,
        )
        return -1


def insert_course(course, dipartimento_internal_id: int) -> int:
    if not _connection:
        return -1

    try:
        cursor = _connection.cursor()

        query_insert = """
            INSERT IGNORE INTO corso_di_studi (unict_id, anno_accademico, nome, classe, id_dipartimento)
            VALUES (%s, %s, %s, %s, %s)
        """
        valori_insert = (
            course.unict_id,
            course.anno_accademico,
            course.nome,
            course.classe,
            dipartimento_internal_id,
        )

        cursor.execute(query_insert, valori_insert)
        _connection.commit()

        query_select = (
            "SELECT id FROM corso_di_studi WHERE unict_id = %s AND anno_accademico = %s"
        )
        cursor.execute(query_select, (course.unict_id, course.anno_accademico))

        result = cursor.fetchone()
        cursor.close()

        return result[0] if result else -1  # type: ignore
    except Error as e:
        logger.error(
            "Errore DB durante l'inserimento del corso '%s': %s", course.nome, e
        )
        return -1


def insert_insegnamento(insegnamento, corso_internal_id: int) -> int:
    if not _connection:
        return -1

    try:
        cursor = _connection.cursor()

        sql = """
            INSERT INTO insegnamento
            (anno_accademico, anno, semestre, nome, docente, codice_gomp, cfu, canale, id_modulo, nome_modulo, ssd, id_cds)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        val = (
            insegnamento.anno_accademico,
            insegnamento.anno,
            insegnamento.semestre,
            insegnamento.nome,
            insegnamento.docente,
            insegnamento.codice_gomp,
            insegnamento.cfu,
            insegnamento.canale,
            insegnamento.id_modulo,
            insegnamento.nome_modulo,
            insegnamento.ssd,
            corso_internal_id,
        )
        cursor.execute(sql, val)
        _connection.commit()
        insegnamento_internal_id = cursor.lastrowid
        cursor.close()

        return insegnamento_internal_id  # type: ignore

    except Error as e:
        logger.error(
            "Errore DB durante l'inserimento dell'insegnamento '%s': %s",
            insegnamento.nome,
            e,
        )
        return -1


def insert_schede_opis(schede_opis: list, insegnamento_internal_id: int) -> int:
    if not _connection or not schede_opis:
        return -1

    try:
        cursor = _connection.cursor()
        first_scheda_dict = vars(schede_opis[0]).copy()
        first_scheda_dict["id_insegnamento"] = insegnamento_internal_id
        columns = list(first_scheda_dict.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        cols_string = ", ".join(columns)
        sql = f"INSERT INTO schede_opis ({cols_string}) VALUES ({placeholders})"
        val_list = []

        for scheda in schede_opis:
            s_dict = vars(scheda).copy()
            s_dict["id_insegnamento"] = insegnamento_internal_id
            row_tuple = []

            for col in columns:
                valore = s_dict.get(col)

                if isinstance(valore, (list, dict)):
                    row_tuple.append(json.dumps(valore))
                else:
                    row_tuple.append(valore)

            val_list.append(tuple(row_tuple))

        cursor.executemany(sql, val_list)
        _connection.commit()
        inserted_rows = cursor.rowcount
        cursor.close()

        return inserted_rows

    except Error as e:
        logger.error(
            "Errore DB durante il salvataggio di %d schede OPIS: %s",
            len(schede_opis),
            e,
        )
        return -1
