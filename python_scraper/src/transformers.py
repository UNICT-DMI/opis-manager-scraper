import re
from typing import Tuple, Dict, Any, List


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
        "ssd": item.get("SSDsigla"),
        "professor_tax": item.get("professorTaxCode", "")
    }
    
    
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
            "tipo_scheda": cluster_name,
            "totale_schede": totale_schede,
            "domande": domande_flat,
            "eta": eta_data if eta_data else None
        })
        
    return result_list
            
        
        
        