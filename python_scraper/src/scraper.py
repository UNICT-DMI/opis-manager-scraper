import logging
import time
from src.api_client import get_departments, get_courses, get_activities, get_questions

logger = logging.getLogger(__name__)

ACCADEMIC_YEARS = [2021, 2022, 2023, 2024]
DELAY = 1.0  

def process_activity(year: int, dept_code: str, course_code: str, activity) : 
    if not activity.professor_tax:
        logger.warning(f"      [SKIP] {activity.nome}: codice docente mancante.")
        return
    
    logger.info(f"      [FETCH] Chiamata in corso per: {activity.nome}...")
    
    schede_opis = get_questions(year, dept_code, course_code, activity.codice_gomp, activity.professor_tax)
    time.sleep(DELAY)
    
    if schede_opis:
        logger.info(f"      [OK] Scaricate {len(schede_opis)} schede per {activity.nome}.")
    else:
        logger.info(f"      [VUOTO] Nessuna scheda per {activity.nome}.")
        
    
def process_course(year: int, dept_code: str, course):
    logger.info(f"  > Analisi Corso: {course.nome} ({course.unict_id})")
    
    activities = get_activities(year, dept_code, course.unict_id)
    time.sleep(DELAY)
    
    if not activities:
        logger.info(f"      [SKIP CORSO] Nessuna materia trovata per {course.unict_id} nell'anno {year}.")
        return
    
    for activity in activities:
        process_activity(year, dept_code, course.unict_id, activity)
        

def process_department(year: int, department):
    logger.info(f"--- Analisi Dipartimento: {department.nome} ({department.unict_id}) ---")
    
    courses = get_courses(year, department.unict_id)
    time.sleep(DELAY)
    
    for course in courses:
        process_course(year, department.unict_id, course)
        

def run_scraper():
    logger.info("Avvio estrazione dati OPIS (Anni 2021-2024)...")
    
    for year in ACCADEMIC_YEARS:
        logger.info(f"==========================================")
        logger.info(f" INIZIO ELABORAZIONE ANNO ACCADEMICO {year}/{year+1}")
        logger.info(f"==========================================")
        
        departments = get_departments(year)
        time.sleep(DELAY)
        logger.info(f"Trovati {len(departments)} dipartimenti per l'anno {year}.")
        
        for department in departments:
            process_department(year, department)