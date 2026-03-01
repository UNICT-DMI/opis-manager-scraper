import requests
from typing import List
from .models import Dipartimento, CorsoDiStudi, Insegnamento, SchedaOpis
from src.transformers import parse_course_name, parse_insegnamento_data, parse_scheda_opis_data


BASE_URL = "https://public.smartedu.unict.it/EnqaDataViewer"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def get_departments(year: int) -> List[Dipartimento]:
    url = f"{BASE_URL}/getDepartments"

    payload = {
        "surveys": "",
        "academicYear": year
    }

    try:
        response = requests.post(
            url, json=payload, headers=HEADERS, timeout=10)
        response.raise_for_status()

        data = response.json()

        items = data.get("data", [])

        departments = []
        formatted_year = f"{year}/{year + 1}"

        for item in items:
            if item.get("code") is None:
                continue

            dip = Dipartimento(
                unict_id=int(item["code"]),
                nome=item["name"],
                anno_accademico=formatted_year
            )
            departments.append(dip)

        return departments

    except requests.exceptions.RequestException as e:
        print(f"Errore durante la richiesta API per l'anno {year}: {e}")
        return []


def get_courses(year: int, department_code: int) -> List[CorsoDiStudi]:

    url = f"{BASE_URL}/getCourses"

    payload = {
        "surveys": "",
        "academicYear": year,
        "departmentCode": str(department_code)
    }

    try:
        response = requests.post(
            url, json=payload, headers=HEADERS, timeout=10)
        response.raise_for_status()

        data = response.json()
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
                dipartimento_id=department_code
            )
            corsi.append(corso)

        return corsi

    except requests.exceptions.RequestException as e:
        print(f"Errore API Corsi (Dip: {department_code}, Anno: {year}): {e}")
        return []


def get_activities(year: int, dept_code: int, course_code: str) -> List[Insegnamento]:

    url = f"{BASE_URL}/getActivities"

    payload = {
        "surveys": "",
        "academicYear": year,
        "departmentCode": str(dept_code),
        "courseCode": course_code
    }

    try:
        response = requests.post(
            url, json=payload, headers=HEADERS, timeout=10)
        response.raise_for_status()

        data = response.json()
        items = data.get("data", [])

        insegnamenti = []
        formatted_year = f"{year}/{year + 1}"

        for item in items:
            if item.get("activityCode") is None:
                continue

            insegnamento_data = parse_insegnamento_data(item)

            insegnamento = Insegnamento(
                codice_gomp=insegnamento_data["codice_gomp"],
                id_cds=course_code,
                anno_accademico=formatted_year,
                nome=insegnamento_data["nome"],
                docente=insegnamento_data["docente"],
                professor_tax=insegnamento_data["professor_tax"],
                canale=insegnamento_data["canale"],
                id_modulo=insegnamento_data["id_modulo"],
                ssd=insegnamento_data["ssd"]
            )
            insegnamenti.append(insegnamento)

        return insegnamenti
    except requests.exceptions.RequestException as e:
        print(
            f"Errore API Insegnamenti (Corso: {course_code}, Dip: {dept_code}, Anno: {year}): {e}")
        return []


def get_questions(year: int, dept_code: int, course_code: str, activity_code: int, professor_tax: str) ->List[SchedaOpis]:
    
    url = f"{BASE_URL}/getQuestions"
    
    payload = {
        "surveys": "",
        "academicYear": year,
        "departmentCode": str(dept_code),
        "courseCode": course_code,
        "activityCode": str(activity_code),
        "partCode": "null",
        "professor": professor_tax
    }
    
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Errore API Schede Opis (Activity: {activity_code}, Corso: {course_code}, Dip: {dept_code}, Anno: {year}): {e}")
        return []

    schede_opis_data = parse_scheda_opis_data(data)
    
    results = []
    formatted_year = f"{year}/{year + 1}"
    
    for item in schede_opis_data:
        item["anno_accademico"] = formatted_year
        item["id_insegnamento"] = activity_code
        results.append(SchedaOpis(**item))
    
    return results
    