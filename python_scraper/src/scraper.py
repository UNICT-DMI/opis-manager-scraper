import logging
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import mysql.connector
from dotenv import load_dotenv
from tqdm import tqdm

from src.api_client import (
    ApiError,
    get_activities,
    get_courses,
    get_departments,
    get_questions,
)
from src.database import (
    close_connection,
    connect_to_db,
    find_department_id,
    find_insegnamento_id,
    get_processed_activity_codes,
    insert_course,
    insert_department,
    insert_insegnamento,
    insert_schede_opis,
)
from src.failure_tracker import clear_failures, log_failure, read_failures
from src.models import CorsoDiStudi, Dipartimento, Insegnamento, SchedaOpis

logger = logging.getLogger(__name__)
load_dotenv()

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))

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

    logger.info("      [FETCH] %s...", activity.nome)

    try:
        schede_opis = get_questions(
            year, dept_code, course_code, activity.codice_gomp, activity.professor_tax
        )
    except ApiError as e:
        logger.error("      [ERRORE API] %s: %s", activity.nome, e)
        log_failure(
            year,
            {
                "level": "questions",
                "dept_code": dept_code,
                "course_code": course_code,
                "activity_code": activity.codice_gomp,
                "professor_tax": activity.professor_tax,
                "docente": activity.docente,
                "id_modulo": activity.id_modulo,
            },
        )
        return activity, []

    if schede_opis:
        logger.info("      [OK] %d schede per %s.", len(schede_opis), activity.nome)
    else:
        logger.info("      [VUOTO] Nessuna scheda per %s.", activity.nome)

    return activity, schede_opis


# ---------------------------------------------------------------------------
# Main scraper: sequential depts/courses, parallel teachings, 3 progress bars
# ---------------------------------------------------------------------------


def _scrape_department(
    year: int, department: Dipartimento, course_bar: tqdm, teach_bar: tqdm
) -> None:
    dip_internal_id = insert_department(department)
    if dip_internal_id == -1:
        logger.error("--- [ERRORE DB] Impossibile salvare %s. ---", department.nome)
        return

    try:
        courses = get_courses(year, department.unict_id)
    except ApiError as e:
        logger.error("--- [ERRORE API] Corsi per %s: %s ---", department.nome, e)
        log_failure(
            year,
            {
                "level": "courses",
                "dept_code": department.unict_id,
                "dept_name": department.nome,
            },
        )
        return

    if DEBUG_MODE and courses:
        courses = random.sample(courses, min(DEBUG_NUM_COURSES, len(courses)))

    course_bar.reset(total=len(courses))

    for course in courses:
        course_bar.set_postfix_str(course.nome[:35])
        _scrape_course(year, department.unict_id, course, dip_internal_id, teach_bar)
        course_bar.update(1)


def _scrape_course(
    year: int,
    dept_code: int,
    course: CorsoDiStudi,
    dip_internal_id: int,
    teach_bar: tqdm,
) -> None:
    corso_internal_id = insert_course(course, dip_internal_id)
    if corso_internal_id == -1:
        return

    try:
        activities = get_activities(year, dept_code, course.unict_id)
    except ApiError as e:
        logger.error("      [ERRORE API] Attività per %s: %s", course.unict_id, e)
        log_failure(
            year,
            {
                "level": "activities",
                "dept_code": dept_code,
                "course_code": course.unict_id,
                "course_name": course.nome,
                "course_classe": course.classe,
            },
        )
        return

    if not activities:
        teach_bar.reset(total=0)
        return

    if DEBUG_MODE and activities:
        activities = random.sample(
            activities, min(DEBUG_NUM_ACTIVITIES, len(activities))
        )

    activities = assign_channels(activities)

    # Resume: skip already-processed activities
    processed_codes = get_processed_activity_codes(
        corso_internal_id, course.anno_accademico
    )

    to_process: list[tuple[Insegnamento, int]] = []
    for activity in activities:
        ins_id = insert_insegnamento(activity, corso_internal_id)
        if ins_id == -1:
            continue
        if activity.codice_gomp not in processed_codes:
            to_process.append((activity, ins_id))

    if not to_process:
        teach_bar.reset(total=0)
        return

    skipped = len(activities) - len(to_process)
    if skipped > 0:
        logger.info(
            "      [RESUME] %d/%d per %s (%d già completate).",
            len(to_process),
            len(activities),
            course.nome,
            skipped,
        )

    teach_bar.reset(total=len(to_process))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                process_activity, year, dept_code, course.unict_id, activity
            ): ins_id
            for activity, ins_id in to_process
        }

        for future in as_completed(futures):
            ins_id = futures[future]
            try:
                result = future.result()
                if result:
                    _, schede_opis = result
                    if schede_opis:
                        insert_schede_opis(schede_opis, ins_id)
            except RuntimeError as e:
                logger.error("Errore: %s", e)
            except mysql.connector.Error as e:
                logger.error("Errore DB: %s", e, exc_info=True)
            teach_bar.update(1)


def run_scraper(year: int) -> None:
    logger.info("Avvio estrazione dati OPIS per l'anno %d/%d...", year, year + 1)

    connect_to_db()
    clear_failures(year)

    try:
        try:
            departments = get_departments(year)
        except ApiError as e:
            logger.error("Impossibile scaricare i dipartimenti: %s", e)
            return

        if DEBUG_MODE and departments:
            departments = random.sample(
                departments, min(DEBUG_NUM_DEPARTMENTS, len(departments))
            )

        logger.info("Trovati %d dipartimenti per l'anno %d.", len(departments), year)

        dept_bar = tqdm(
            total=len(departments), desc="Dipartimenti", unit="dip", position=0
        )
        course_bar = tqdm(
            total=0, desc="  Corsi", unit="corso", position=1, leave=False
        )
        teach_bar = tqdm(
            total=0, desc="    Insegnamenti", unit="ins", position=2, leave=False
        )

        try:
            for department in departments:
                dept_bar.set_postfix_str(department.nome[:35])
                _scrape_department(year, department, course_bar, teach_bar)
                dept_bar.update(1)
        finally:
            teach_bar.close()
            course_bar.close()
            dept_bar.close()

    finally:
        close_connection()


# ---------------------------------------------------------------------------
# Retry flow (no progress bars, uses end-to-end process_course/department)
# ---------------------------------------------------------------------------


def process_course(
    year: int, dept_code: int, course: CorsoDiStudi, dip_internal_id: int
) -> None:
    """Process a course end-to-end. Used by retry flow."""
    corso_internal_id = insert_course(course, dip_internal_id)
    if corso_internal_id == -1:
        return

    try:
        activities = get_activities(year, dept_code, course.unict_id)
    except ApiError as e:
        logger.error("      [ERRORE API] Attività per %s: %s", course.unict_id, e)
        log_failure(
            year,
            {
                "level": "activities",
                "dept_code": dept_code,
                "course_code": course.unict_id,
                "course_name": course.nome,
                "course_classe": course.classe,
            },
        )
        return

    if not activities:
        return

    if DEBUG_MODE and activities:
        activities = random.sample(
            activities, min(DEBUG_NUM_ACTIVITIES, len(activities))
        )

    activities = assign_channels(activities)

    processed_codes = get_processed_activity_codes(
        corso_internal_id, course.anno_accademico
    )

    to_process: list[tuple[Insegnamento, int]] = []
    for activity in activities:
        ins_id = insert_insegnamento(activity, corso_internal_id)
        if ins_id == -1:
            continue
        if activity.codice_gomp not in processed_codes:
            to_process.append((activity, ins_id))

    if not to_process:
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                process_activity, year, dept_code, course.unict_id, activity
            ): ins_id
            for activity, ins_id in to_process
        }
        for future in as_completed(futures):
            ins_id = futures[future]
            try:
                result = future.result()
                if result:
                    _, schede_opis = result
                    if schede_opis:
                        insert_schede_opis(schede_opis, ins_id)
            except RuntimeError as e:
                logger.error("Errore: %s", e)
            except mysql.connector.Error as e:
                logger.error("Errore DB: %s", e, exc_info=True)


def process_department(year: int, department: Dipartimento) -> None:
    """Process a department end-to-end. Used by retry flow."""
    dip_internal_id = insert_department(department)
    if dip_internal_id == -1:
        return

    try:
        courses = get_courses(year, department.unict_id)
    except ApiError as e:
        logger.error("--- [ERRORE API] Corsi per %s: %s ---", department.nome, e)
        log_failure(
            year,
            {
                "level": "courses",
                "dept_code": department.unict_id,
                "dept_name": department.nome,
            },
        )
        return

    if DEBUG_MODE and courses:
        courses = random.sample(courses, min(DEBUG_NUM_COURSES, len(courses)))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(
                process_course, year, department.unict_id, course, dip_internal_id
            )
            for course in courses
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error("Errore nel corso: %s", e)


def retry_failures(year: int) -> None:
    failures = read_failures(year)

    if not failures:
        logger.info("Nessun fallimento da riprovare per l'anno %d.", year)
        return

    logger.info(
        "Trovati %d fallimenti da riprovare per l'anno %d.", len(failures), year
    )

    connect_to_db()
    clear_failures(year)
    formatted_year = f"{year}/{year + 1}"

    try:
        failed_depts: set[int] = set()
        failed_courses: set[tuple[int, str]] = set()

        courses_failures = []
        activities_failures = []
        questions_failures = []

        for failure in failures:
            level = failure.get("level")
            if level == "courses":
                failed_depts.add(failure["dept_code"])
                courses_failures.append(failure)
            elif level == "activities":
                failed_courses.add((failure["dept_code"], failure["course_code"]))
                activities_failures.append(failure)
            elif level == "questions":
                questions_failures.append(failure)

        activities_failures = [
            f for f in activities_failures if f["dept_code"] not in failed_depts
        ]
        questions_failures = [
            f
            for f in questions_failures
            if f["dept_code"] not in failed_depts
            and (f["dept_code"], f["course_code"]) not in failed_courses
        ]

        for failure in courses_failures:
            _retry_courses(year, formatted_year, failure)

        for failure in activities_failures:
            _retry_activities(year, formatted_year, failure)

        if questions_failures:
            _retry_questions_batch(year, formatted_year, questions_failures)

    finally:
        close_connection()


def _retry_courses(year: int, formatted_year: str, failure: dict) -> None:
    dept_code = failure["dept_code"]
    dept_name = failure.get("dept_name", "")
    logger.info("[RETRY] Dipartimento %s (%d)", dept_name, dept_code)

    dept = Dipartimento(
        unict_id=dept_code, nome=dept_name, anno_accademico=formatted_year
    )
    process_department(year, dept)


def _retry_activities(year: int, formatted_year: str, failure: dict) -> None:
    dept_code = failure["dept_code"]
    course_code = failure["course_code"]
    logger.info("[RETRY] Corso %s (Dip: %d)", course_code, dept_code)

    dip_internal_id = find_department_id(dept_code, formatted_year)
    if dip_internal_id == -1:
        logger.warning("[RETRY SKIP] Dipartimento %d non trovato nel DB.", dept_code)
        log_failure(year, failure)
        return

    course = CorsoDiStudi(
        unict_id=course_code,
        nome=failure.get("course_name", ""),
        classe=failure.get("course_classe", ""),
        anno_accademico=formatted_year,
        dipartimento_id=dept_code,
    )
    process_course(year, dept_code, course, dip_internal_id)


def _retry_questions_batch(year: int, formatted_year: str, failures: list) -> None:
    logger.info("[RETRY] %d richieste questions da riprovare.", len(failures))

    with tqdm(total=len(failures), desc="Retry questions", unit="req") as pbar:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    _retry_single_question, year, formatted_year, failure
                ): failure
                for failure in failures
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error("[RETRY] Errore: %s", e)
                pbar.update(1)


def _retry_single_question(year: int, formatted_year: str, failure: dict) -> None:
    dept_code = failure["dept_code"]
    course_code = failure["course_code"]
    activity_code = failure["activity_code"]
    professor_tax = failure["professor_tax"]

    try:
        schede_opis = get_questions(
            year, dept_code, course_code, activity_code, professor_tax
        )
    except ApiError as e:
        logger.error("[RETRY FAIL] questions %d: %s", activity_code, e)
        log_failure(year, failure)
        return

    if not schede_opis:
        return

    insegnamento_id = find_insegnamento_id(
        codice_gomp=activity_code,
        anno_accademico=formatted_year,
        docente=failure.get("docente", ""),
        id_modulo=failure.get("id_modulo", 0),
        course_unict_id=course_code,
    )

    if insegnamento_id != -1:
        insert_schede_opis(schede_opis, insegnamento_id)
        logger.info("[RETRY OK] Schede inserite per activity %d.", activity_code)
    else:
        logger.warning(
            "[RETRY SKIP] Insegnamento non trovato nel DB per activity %d.",
            activity_code,
        )
