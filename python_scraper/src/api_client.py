import requests
from typing import List
from .models import Dipartimento, CorsoDiStudi
from src.transformers import parse_course_name


BASE_URL = "https://public.smartedu.unict.it/EnqaDataViewer"


def get_departments(year: int) -> List[Dipartimento]:
    url = f"{BASE_URL}/getDepartments"

    payload = {
        "surveys": "",
        "academicYear": year
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.post(
            url, json=payload, headers=headers, timeout=10)
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

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.post(
            url, json=payload, headers=headers, timeout=10)
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
