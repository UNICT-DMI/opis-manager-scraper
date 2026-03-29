import json
import logging
import os
import threading

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error
from mysql.connector.abstracts import MySQLConnectionAbstract
from mysql.connector.pooling import PooledMySQLConnection

load_dotenv()

logger = logging.getLogger(__name__)

_connection = None
_db_lock = threading.Lock()


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
    with _db_lock:
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

            query_select = "SELECT id FROM dipartimento WHERE unict_id = %s AND anno_accademico = %s"
            cursor.execute(
                query_select, (department.unict_id, department.anno_accademico)
            )

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
    with _db_lock:
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

            query_select = "SELECT id FROM corso_di_studi WHERE unict_id = %s AND anno_accademico = %s"
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
    with _db_lock:
        if not _connection:
            return -1

        try:
            cursor = _connection.cursor()

            # Check if already exists (idempotent for retry safety)
            cursor.execute(
                "SELECT id FROM insegnamento "
                "WHERE codice_gomp = %s AND anno_accademico = %s "
                "AND id_cds = %s AND docente = %s AND id_modulo = %s LIMIT 1",
                (
                    insegnamento.codice_gomp,
                    insegnamento.anno_accademico,
                    corso_internal_id,
                    insegnamento.docente,
                    insegnamento.id_modulo,
                ),
            )
            existing = cursor.fetchone()
            if existing:
                cursor.close()
                return existing[0]

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
    with _db_lock:
        if not _connection or not schede_opis:
            return -1

        try:
            cursor = _connection.cursor()

            # Skip if schede already exist for this insegnamento (idempotent for retry)
            cursor.execute(
                "SELECT COUNT(*) FROM schede_opis WHERE id_insegnamento = %s",
                (insegnamento_internal_id,),
            )
            if cursor.fetchone()[0] > 0:  # type: ignore
                cursor.close()
                return 0

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


def get_processed_activity_codes(
    corso_internal_id: int, anno_accademico: str
) -> set[int]:
    """Return codice_gomp values that already have schede_opis data for this course."""
    with _db_lock:
        if not _connection:
            return set()
        try:
            cursor = _connection.cursor()
            cursor.execute(
                """SELECT i.codice_gomp FROM insegnamento i
                   JOIN schede_opis s ON s.id_insegnamento = i.id
                   WHERE i.id_cds = %s AND i.anno_accademico = %s""",
                (corso_internal_id, anno_accademico),
            )
            result = {row[0] for row in cursor.fetchall()}
            cursor.close()
            return result
        except Error as e:
            logger.error("Errore DB lookup attività processate: %s", e)
            return set()


def find_department_id(dept_unict_id: int, anno_accademico: str) -> int:
    with _db_lock:
        if not _connection:
            return -1
        try:
            cursor = _connection.cursor()
            cursor.execute(
                "SELECT id FROM dipartimento WHERE unict_id = %s AND anno_accademico = %s",
                (dept_unict_id, anno_accademico),
            )
            result = cursor.fetchone()
            cursor.close()
            return int(result[0]) if result else -1  # type: ignore
        except Error as e:
            logger.error("Errore DB lookup dipartimento: %s", e)
            return -1


def find_course_id(course_unict_id: str, anno_accademico: str) -> int:
    with _db_lock:
        if not _connection:
            return -1
        try:
            cursor = _connection.cursor()
            cursor.execute(
                "SELECT id FROM corso_di_studi WHERE unict_id = %s AND anno_accademico = %s",
                (course_unict_id, anno_accademico),
            )
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else -1  # type: ignore
        except Error as e:
            logger.error("Errore DB lookup corso: %s", e)
            return -1


def find_insegnamento_id(
    codice_gomp: int,
    anno_accademico: str,
    docente: str,
    id_modulo: int,
    course_unict_id: str,
) -> int:
    with _db_lock:
        if not _connection:
            return -1
        try:
            cursor = _connection.cursor()
            cursor.execute(
                """SELECT i.id FROM insegnamento i
                   JOIN corso_di_studi c ON i.id_cds = c.id
                   WHERE i.codice_gomp = %s AND i.anno_accademico = %s
                   AND i.docente = %s AND i.id_modulo = %s
                   AND c.unict_id = %s AND c.anno_accademico = %s
                   LIMIT 1""",
                (
                    codice_gomp,
                    anno_accademico,
                    docente,
                    id_modulo,
                    course_unict_id,
                    anno_accademico,
                ),
            )
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else -1  # type: ignore
        except Error as e:
            logger.error("Errore DB lookup insegnamento: %s", e)
            return -1
