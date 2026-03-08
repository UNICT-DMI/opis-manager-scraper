import re
from typing import Tuple, Dict, Any, List


def parse_course_name(full_name: str) -> Tuple[str, str]:

    if not full_name:
        return "", ""

    full_name = full_name.strip()

    pattern = r"\s+\(?(L(?:M|MCU)?-[0-9]+(?:\s*R)?)\)?\s*$"

    match = re.search(pattern, full_name)

    if match:

        classe = match.group(1)
        nome = full_name[:match.start()].strip()

        if nome.endswith('-'):
            nome = nome[:-1].strip()

        return nome, classe

    return full_name, ""


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
        "ssd": item.get("SSDsigla"),
        "professor_tax": item.get("professorTaxCode", "")
    }


"""
def parse_scheda_opis_data(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:

    clusters = json_data.get("clusterData", [])
    graphs = json_data.get("graphPieList", [])
    result_list = []

    for cluster in clusters:
        cluster_info = cluster.get("cluster", {})
        cluster_name = cluster_info.get("Text", "Sconosciuto")

        domande_flat = [0] * 60
        questions = cluster.get("questions", [])

        totale_schede = 0

        for q in questions:

            q_code_str = q.get("questionCode")

            if not q_code_str:
                continue

            try:
                q_idx = int(q_code_str) - 1
            except ValueError:
                continue

            if q_idx < 0 or q_idx >= 12:
                continue

            subs = q.get("submissions", 0)
            if subs > totale_schede:
                totale_schede = subs

            base_offset = q_idx * 5
            for ans in q.get("answers", []):
                a_code = ans.get("answerCode")
                count = ans.get("count", 0)

                offset = -1

                match a_code:
                    case "R1": offset = 0
                    case "R2": offset = 1
                    case "R3": offset = 2
                    case "R4": offset = 3
                    case "R5": offset = 4
                    case _: offset = -1

                if offset >= 0:
                    domande_flat[base_offset + offset] = count

        eta_data = {}
        for graph in graphs:
            if graph.get("name") == cluster_name:
                for pie in graph.get("dataPie", []):
                    datasets = pie.get("datasets", [])
                    if datasets and "Età" in datasets[0].get("label", ""):
                        labels = pie.get("labels", [])
                        values = datasets[0].get("data", [])

                        for i, label in enumerate(labels):
                            if i < len(values):
                                eta_data[label] = int(values[i])

        result_list.append({
            "totale_schede": totale_schede,
            "domande": domande_flat,
            "eta": eta_data if eta_data else None
        })

    return result_list
"""


def parse_scheda_opis_data(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    clusters = json_data.get("clusterData", [])
    graphs = json_data.get("graphPieList", [])

    # 1. Creiamo un UNICO record di base per questa materia.
    # Inizializziamo i campi Not Null con valori vuoti validi (0 o liste vuote)
    # per non far arrabbiare MySQL.
    record = {
        "totale_schede": 0,
        "totale_schede_nf": 0,
        "fc": 0,          # Fuori corso (Not Null)
        "inatt_nf": 0,    # Inattivi (Not Null)
        "domande": [0] * 60,
        "domande_nf": [0] * 60,
        "motivo_nf": [],  # JSON Not Null
        "sugg": [],       # JSON Not Null
        "sugg_nf": [],    # JSON Not Null

        # Campi nullable (possono restare None se non li troviamo)
        "femmine": None,
        "femmine_nf": None,
        "inatt": None,
        "eta": None,
        "anno_iscr": None,
        "num_studenti": None,
        "ragg_uni": None,
        "studio_gg": None,
        "studio_tot": None
    }

    # 2. Estraiamo i dati dalle domande e li smistiamo
    for cluster in clusters:
        cluster_info = cluster.get("cluster", {})
        cluster_name = cluster_info.get("Text", "").lower()

        # Capiamo se stiamo guardando il cluster dei Non Frequentanti
        is_nf = "non frequentanti" in cluster_name

        domande_flat = [0] * 60
        totale_schede = 0
        questions = cluster.get("questions", [])

        for q in questions:
            q_code_str = q.get("questionCode")
            if not q_code_str:
                continue

            try:
                q_idx = int(q_code_str) - 1
            except ValueError:
                continue

            if q_idx < 0 or q_idx >= 12:
                continue

            subs = q.get("submissions", 0)
            if subs > totale_schede:
                totale_schede = subs

            base_offset = q_idx * 5
            for ans in q.get("answers", []):
                a_code = ans.get("answerCode")
                count = ans.get("count", 0)

                offset = -1
                match a_code:
                    case "R1": offset = 0
                    case "R2": offset = 1
                    case "R3": offset = 2
                    case "R4": offset = 3
                    case "R5": offset = 4
                    case _: offset = -1

                if offset >= 0:
                    domande_flat[base_offset + offset] = count

        # Salviamo i dati nel posto giusto del nostro record unico
        if is_nf:
            record["totale_schede_nf"] = totale_schede
            record["domande_nf"] = domande_flat
        else:
            record["totale_schede"] = totale_schede
            record["domande"] = domande_flat

    # 3. Estraiamo l'età dai grafici (Aggregando Frequentanti e Non Frequentanti)
    eta_data = {}
    for graph in graphs:
        for pie in graph.get("dataPie", []):
            datasets = pie.get("datasets", [])
            if datasets and "Età" in datasets[0].get("label", ""):
                labels = pie.get("labels", [])
                values = datasets[0].get("data", [])

                for i, label in enumerate(labels):
                    if i < len(values):
                        # Sommiamo l'età se c'è sia nei frequentanti che nei non frequentanti
                        eta_data[label] = eta_data.get(
                            label, 0) + int(values[i])

    if eta_data:
        record["eta"] = eta_data

    # Restituiamo una lista contenente il nostro unico e perfetto record
    return [record]
