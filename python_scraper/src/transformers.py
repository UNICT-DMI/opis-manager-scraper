import re
from typing import Tuple, Dict, Any


def parse_course_name(full_name: str) -> Tuple[str, str]:

    if not full_name:
        return "", ""

    pattern = r"\s+(L(?:M|MCU)?-[0-9]+)$"

    match = re.search(pattern, full_name)

    if match:

        classe = match.group(1)
        nome = full_name[:match.start()].strip()
        return nome, classe

    return full_name.strip(), ""


def parse_insegnamento_data(item: Dict[str, Any]) -> Dict[str, Any]:
    cognome = item.get("professorLastName")
    nome = item.get("professorName")
    docente_full = f"{cognome} {nome}".strip()
    
    canale = item.get("channel")
    if not canale:
        canale = "no"
        
    id_modulo = item.get("partCode")
    if not id_modulo:
        id_modulo = 0
    else:
        try:
            id_modulo = int(id_modulo)
        except ValueError:
            id_modulo = 0

    return {
        "codice_gomp": int(item["activityCode"]) if item.get("activityCode") else 0,
        "nome": item.get("activityName", ""),
        "docente": docente_full,
        "canale": canale,
        "id_modulo": id_modulo,
        "ssd": item.get("SSDsigla")
    }
    
    