import logging
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.api_client import get_departments, get_courses, get_activities, get_questions
from src.database import connect_to_db, close_connection, insert_department, insert_course, insert_insegnamento, insert_schede_opis
from dotenv import load_dotenv
import os

logger = logging.getLogger(__name__)
load_dotenv()

ACCADEMIC_YEARS = [2021, 2022, 2023, 2024]
DELAY = 1.0

MAX_WORKERS = 3
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "t")


def process_activity(year: int, dept_code: str, course_code: str, activity):
    if not activity.professor_tax:
        logger.warning(
            f"      [SKIP] {activity.nome}: codice docente mancante.")
        return

    logger.info(f"      [FETCH] Chiamata in corso per: {activity.nome}...")

    schede_opis = get_questions(
        year, dept_code, course_code, activity.codice_gomp, activity.professor_tax)
    time.sleep(0.5)

    if schede_opis:
        logger.info(
            f"      [OK] Scaricate {len(schede_opis)} schede per {activity.nome}.")
    else:
        logger.info(f"      [VUOTO] Nessuna scheda per {activity.nome}.")

    return activity, schede_opis


def process_course(year: int, dept_code: str, course, dip_internal_id: int):
    corso_internal_id = insert_course(course, dip_internal_id)
    if corso_internal_id == -1:
        logger.error(
            f"      [ERRORE DB] Impossibile salvare il corso {course.nome}. Salto materie.")
        return
    logger.info(
        f"  > Analisi Corso: {course.nome} ({course.unict_id}) (ID DB: {corso_internal_id})")

    activities = get_activities(year, dept_code, course.unict_id)
    time.sleep(DELAY)

    if not activities:
        logger.info(
            f"      [SKIP CORSO] Nessuna materia trovata per {course.unict_id} nell'anno {year}.")
        return

    if DEBUG_MODE and activities:
        campione = min(5, len(activities))
        activities = random.sample(activities, campione)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(process_activity, year, dept_code,
                            course.unict_id, activity)
            for activity in activities
        ]

        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    activity, schede_opis = result

                    insegnamento_internal_id = insert_insegnamento(
                        activity, corso_internal_id)

                    if insegnamento_internal_id != -1 and schede_opis:
                        insert_schede_opis(
                            schede_opis, insegnamento_internal_id)

            except Exception as e:
                logger.error(
                    f"Errore inatteso durante l'analisi di una materia: {e}")


def process_department(year: int, department):
    dip_internal_id = insert_department(department)
    if dip_internal_id == -1:
        logger.error(
            f"--- [ERRORE DB] Impossibile salvare {department.nome}. Salto. ---")
        return
    logger.info(
        f"--- Analisi Dipartimento: {department.nome} ({department.unict_id}) (ID DB: {dip_internal_id})---")

    courses = get_courses(year, department.unict_id)
    time.sleep(DELAY)

    if DEBUG_MODE and courses:
        courses = [random.choice(courses)]

    for course in courses:
        process_course(year, department.unict_id, course, dip_internal_id)


def run_scraper():
    logger.info("Avvio estrazione dati OPIS (Anni 2021-2024)...")

    connect_to_db()

    try:
        for year in ACCADEMIC_YEARS:
            logger.info(f"==========================================")
            logger.info(
                f" INIZIO ELABORAZIONE ANNO ACCADEMICO {year}/{year+1}")
            logger.info(f"==========================================")
            logger.info(
                f"Chiamata API in corso per scaricare i dipartimenti del {year}...")

            departments = get_departments(year)
            time.sleep(DELAY)

            if DEBUG_MODE and departments:
                departments = [random.choice(departments)]

            logger.info(
                f"Trovati {len(departments)} dipartimenti per l'anno {year}.")

            for department in departments:
                process_department(year, department)
    finally:
        close_connection()
