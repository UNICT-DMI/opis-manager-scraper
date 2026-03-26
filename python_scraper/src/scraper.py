import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import mysql.connector
from dotenv import load_dotenv

from src.api_client import get_activities, get_courses, get_departments, get_questions
from src.database import (
    close_connection,
    connect_to_db,
    insert_course,
    insert_department,
    insert_insegnamento,
    insert_schede_opis,
)
from src.models import CorsoDiStudi, Dipartimento, Insegnamento, SchedaOpis

logger = logging.getLogger(__name__)
load_dotenv()

ACCADEMIC_YEARS = [2021, 2022, 2023, 2024]
DELAY = 1.0

MAX_WORKERS = 3
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "t")
DEBUG_NUM_ACTIVITIES = int(os.getenv("DEBUG_NUM_ACTIVITIES", "5"))
DEBUG_NUM_COURSES = int(os.getenv("DEBUG_NUM_COURSES", "1"))
DEBUG_NUM_DEPARTMENTS = int(os.getenv("DEBUG_NUM_DEPARTMENTS", "1"))


def assign_channels(activities: List[Insegnamento]) -> List[Insegnamento]:
    grouped_activities: dict[str, list[Insegnamento]] = {}

    for activity in activities:
        grouped_activities.setdefault(activity.nome, []).append(activity)

    for _, group in grouped_activities.items():
        channel_content: dict[int, set[str]] = {}
        for activity in group:
            current_module = (
                activity.nome_modulo if activity.nome_modulo else "MODULO_UNICO"
            )
            assigned_channel = None

            for num_channel, modules_list in channel_content.items():
                if current_module not in modules_list:
                    assigned_channel = num_channel
                    break

            if assigned_channel is None:
                assigned_channel = len(channel_content) + 1
                channel_content[assigned_channel] = set()

            channel_content[assigned_channel].add(current_module)
            activity.canale = str(assigned_channel)

        if len(channel_content) == 1:
            for activity in group:
                activity.canale = "no"
    return activities


def process_activity(
    year: int, dept_code: int, course_code: str, activity: Insegnamento
) -> tuple[Insegnamento, List[SchedaOpis]]:
    if not activity.professor_tax:
        logger.warning("      [SKIP] %s: codice docente mancante.", activity.nome)
        return activity, []

    logger.info("      [FETCH] Chiamata in corso per: %s...", activity.nome)

    schede_opis = get_questions(
        year, dept_code, course_code, activity.codice_gomp, activity.professor_tax
    )
    time.sleep(0.5)

    if schede_opis:
        logger.info(
            "      [OK] Scaricate %d schede per %s.", len(schede_opis), activity.nome
        )
    else:
        logger.info("      [VUOTO] Nessuna scheda per %s.", activity.nome)

    return activity, schede_opis


def process_course(
    year: int, dept_code: int, course: CorsoDiStudi, dip_internal_id: int
) -> None:
    corso_internal_id = insert_course(course, dip_internal_id)
    if corso_internal_id == -1:
        logger.error(
            "      [ERRORE DB] Impossibile salvare il corso %s. Salto materie.",
            course.nome,
        )
        return
    logger.info(
        "  > Analisi Corso: %s (%s) (ID DB: %d)",
        course.nome,
        course.unict_id,
        corso_internal_id,
    )

    activities = get_activities(year, dept_code, course.unict_id)
    time.sleep(DELAY)

    if not activities:
        logger.info(
            "      [SKIP CORSO] Nessuna materia trovata per %s nell'anno %d.",
            course.unict_id,
            year,
        )
        return

    if DEBUG_MODE and activities:
        campione = min(DEBUG_NUM_ACTIVITIES, len(activities))
        activities = random.sample(activities, campione)

    activities = assign_channels(activities)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(
                process_activity, year, dept_code, course.unict_id, activity
            )
            for activity in activities
        ]

        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    activity, schede_opis = result

                    insegnamento_internal_id = insert_insegnamento(
                        activity, corso_internal_id
                    )

                    if insegnamento_internal_id != -1 and schede_opis:
                        insert_schede_opis(schede_opis, insegnamento_internal_id)

            except RuntimeError as e:
                logger.error("Errore inatteso durante l'analisi di una materia: %s", e)
            except mysql.connector.Error as e:
                logger.error("Errore di database: %s", e, exc_info=True)


def process_department(year: int, department: Dipartimento) -> None:
    dip_internal_id = insert_department(department)
    if dip_internal_id == -1:
        logger.error(
            "--- [ERRORE DB] Impossibile salvare %s. Salto. ---", department.nome
        )
        return
    logger.info(
        "--- Analisi Dipartimento: %s (%s) (ID DB: %d)---",
        department.nome,
        department.unict_id,
        dip_internal_id,
    )

    courses = get_courses(year, department.unict_id)
    time.sleep(DELAY)

    if DEBUG_MODE and courses:
        campione = min(DEBUG_NUM_COURSES, len(courses))
        courses = random.sample(courses, campione)

    for course in courses:
        process_course(year, department.unict_id, course, dip_internal_id)


def run_scraper() -> None:
    logger.info("Avvio estrazione dati OPIS (Anni 2021-2024)...")

    connect_to_db()

    try:
        for year in ACCADEMIC_YEARS:
            logger.info("==========================================")
            logger.info(" INIZIO ELABORAZIONE ANNO ACCADEMICO %d/%d ", year, year + 1)
            logger.info("==========================================")
            logger.info(
                "Chiamata API in corso per scaricare i dipartimenti del %d...", year
            )

            departments = get_departments(year)
            time.sleep(DELAY)

            if DEBUG_MODE and departments:
                campione = min(DEBUG_NUM_DEPARTMENTS, len(departments))
                departments = random.sample(departments, campione)

            logger.info(
                "Trovati %d dipartimenti per l'anno %d.", len(departments), year
            )

            for department in departments:
                process_department(year, department)
    finally:
        close_connection()
