import logging
import os
import threading
from typing import List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.models import CorsoDiStudi, Dipartimento, Insegnamento, SchedaOpis
from src.transformers import (
    parse_course_name,
    parse_insegnamento_data,
    parse_scheda_opis_data,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://public.smartedu.unict.it/EnqaDataViewer"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

TIMEOUT = 120

MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "20"))
_request_semaphore = threading.Semaphore(MAX_CONCURRENT_REQUESTS)

retry_strategy = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST"],
)
adapter = HTTPAdapter(max_retries=retry_strategy)


session = requests.Session()
session.headers.update(HEADERS)
session.mount("https://", adapter)
session.mount("http://", adapter)


class ApiError(Exception):
    """Raised when an API request fails after retries."""


def get_departments(year: int) -> List[Dipartimento]:
    url = f"{BASE_URL}/getDepartments"

    payload = {"surveys": "", "academicYear": year}

    with _request_semaphore:
        try:
            response = session.post(url, json=payload, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise ApiError(f"Errore API dipartimenti (Anno: {year}): {e}") from e

    items = data.get("data", [])

    departments = []
    formatted_year = f"{year}/{year + 1}"

    for item in items:
        if item.get("code") is None:
            continue

        dip = Dipartimento(
            unict_id=int(item["code"]),
            nome=item["name"],
            anno_accademico=formatted_year,
        )
        departments.append(dip)

    return departments


def get_courses(year: int, department_code: int) -> List[CorsoDiStudi]:

    url = f"{BASE_URL}/getCourses"

    payload = {
        "surveys": "",
        "academicYear": year,
        "departmentCode": str(department_code),
    }

    with _request_semaphore:
        try:
            response = session.post(url, json=payload, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise ApiError(
                f"Errore API Corsi (Dip: {department_code}, Anno: {year}): {e}"
            ) from e

    items = data.get("data", [])

    corsi = []
    formatted_year = f"{year}/{year + 1}"

    for item in items:

        if item.get("code") is None:
            continue

        full_name = item["name"]
        nome_pulito, classe = parse_course_name(full_name)

        corso = CorsoDiStudi(
            unict_id=item["code"],
            nome=nome_pulito,
            classe=classe,
            anno_accademico=formatted_year,
            dipartimento_id=department_code,
        )
        corsi.append(corso)

    return corsi


def get_activities(year: int, dept_code: int, course_code: str) -> List[Insegnamento]:

    url = f"{BASE_URL}/getActivities"

    payload = {
        "surveys": "",
        "academicYear": year,
        "departmentCode": str(dept_code),
        "courseCode": course_code,
    }

    with _request_semaphore:
        try:
            response = session.post(url, json=payload, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise ApiError(
                f"Errore API Insegnamenti (Corso: {course_code}, "
                f"Dip: {dept_code}, Anno: {year}): {e}"
            ) from e

    items = data.get("data", [])

    insegnamenti = []
    formatted_year = f"{year}/{year + 1}"

    for item in items:

        insegnamento_data = parse_insegnamento_data(item)

        if not insegnamento_data:
            logger.warning(
                "      [SKIP MATERIA] '%s' ignorata. "
                "Codice GOMP vuoto o alfanumerico: %s",
                item.get("activityName"),
                item.get("activityCode"),
            )
            continue

        insegnamento = Insegnamento(
            codice_gomp=insegnamento_data["codice_gomp"],
            id_cds=course_code,
            anno_accademico=formatted_year,
            nome=insegnamento_data["nome"],
            docente=insegnamento_data["docente"],
            professor_tax=insegnamento_data["professor_tax"],
            canale=insegnamento_data["canale"],
            id_modulo=insegnamento_data["id_modulo"],
            nome_modulo=insegnamento_data["nome_modulo"],
            ssd=insegnamento_data["ssd"],
        )
        insegnamenti.append(insegnamento)

    return insegnamenti


def get_questions(
    year: int, dept_code: int, course_code: str, activity_code: int, professor_tax: str
) -> List[SchedaOpis]:

    url = f"{BASE_URL}/getQuestions"

    payload = {
        "surveys": "",
        "academicYear": year,
        "departmentCode": str(dept_code),
        "courseCode": course_code,
        "activityCode": str(activity_code),
        "partCode": "null",
        "professor": professor_tax,
    }

    with _request_semaphore:
        try:
            response = session.post(url, json=payload, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise ApiError(
                f"Errore API Schede Opis (Activity: {activity_code}, "
                f"Corso: {course_code}, Dip: {dept_code}, Anno: {year}): {e}"
            ) from e

    schede_opis_data = parse_scheda_opis_data(data)

    results = []
    formatted_year = f"{year}/{year + 1}"

    for item in schede_opis_data:
        item["anno_accademico"] = formatted_year
        item["id_insegnamento"] = activity_code
        results.append(SchedaOpis(**item))

    return results
