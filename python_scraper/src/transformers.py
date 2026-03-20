import re
from typing import Tuple, Dict, Any, List, Optional


def parse_course_name(full_name: Optional[str]) -> Tuple[str, str]:

    if not full_name:
        return "", ""

    full_name = full_name.strip()

    # Regex potenziata:
    # \s+                  -> Spazio iniziale
    # \(?                  -> Parentesi aperta opzionale
    # (                    -> INIZIO GRUPPO 1 (quello che estraiamo come classe)
    #   L(?:M|MCU)?        -> Base: L, LM, o LMCU
    #   (?:-|\/)           -> Separatore: accetta sia il trattino "-" che la slash "/"
    #   (?:[0-9]+|SNT[0-9]+) -> Valore: accetta numeri puri (es. 4, 31) o sigla SNT + numeri (es. SNT1)
    #   (?:\s*c\.?u\.?)?   -> Ciclo Unico opzionale: accetta "cu" o "c.u." (con o senza spazi e punti)
    #   (?:\s*R)?          -> Riformato opzionale: la lettera "R" (con o senza spazi prima)
    # )                    -> FINE GRUPPO 1
    # \)?                  -> Parentesi chiusa opzionale
    # \s*$                 -> Spazi finali opzionali e fine stringa
    pattern = r"\s+\(?(L(?:M|MCU)?(?:-|\/)(?:[0-9]+|SNT[0-9]+)(?:\s*c\.?u\.?)?(?:\s*R)?)\)?\s*$"

    match = re.search(pattern, full_name, re.IGNORECASE)

    if match:

        classe = match.group(1).upper()
        nome = full_name[: match.start()].strip()

        if nome.endswith("-"):
            nome = nome[:-1].strip()

        return nome, classe

    return full_name, ""


def parse_insegnamento_data(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_code = item.get("activityCode")
    if not raw_code:
        return None

    try:
        codice_gomp = int(raw_code)
    except ValueError:
        return None

    cognome = item.get("professorLastName") or ""
    nome = item.get("professorName") or ""
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
        "codice_gomp": codice_gomp,
        "nome": item.get("activityName", ""),
        "docente": docente_full,
        "canale": canale,
        "id_modulo": id_modulo,
        "nome_modulo": item.get("partName"),
        "ssd": item.get("SSDsigla"),
        "professor_tax": item.get("professorTaxCode", ""),
    }


def _aggiorna_statistica_json(
    record: Dict[str, Any], campo: str, labels: List[str], values: List[Any]
) -> None:
    if record[campo] is None:
        record[campo] = {}
    for i, lbl in enumerate(labels):
        if i < len(values):
            record[campo][lbl] = record[campo].get(lbl, 0) + int(values[i])


def parse_scheda_opis_data(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    clusters = json_data.get("clusterData", [])
    graphs = json_data.get("graphPieList", [])

    record = {
        "totale_schede": 0,
        "totale_schede_nf": 0,
        "fc": 0,
        "inatt_nf": 0,
        "domande": [0] * 60,
        "domande_nf": [0] * 60,
        "motivo_nf": [],
        "sugg": [],
        "sugg_nf": [],
        "femmine": None,
        "femmine_nf": None,
        "inatt": None,
        "eta": None,
        "anno_iscr": None,
        "num_studenti": None,
        "ragg_uni": None,
        "studio_gg": None,
        "studio_tot": None,
    }

    for cluster in clusters:
        cluster_info = cluster.get("cluster", {})
        cluster_name = cluster_info.get("Text", "").lower()
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
                    case "R1":
                        offset = 0
                    case "R2":
                        offset = 1
                    case "R3":
                        offset = 2
                    case "R4":
                        offset = 3
                    case "R5":
                        offset = 4

                if offset >= 0:
                    domande_flat[base_offset + offset] = count

        if is_nf:
            record["totale_schede_nf"] = totale_schede
            record["domande_nf"] = domande_flat
        else:
            record["totale_schede"] = totale_schede
            record["domande"] = domande_flat

    for graph in graphs:
        is_nf_graph = "non frequentanti" in graph.get("name", "").lower()

        for pie in graph.get("dataPie", []):
            datasets = pie.get("datasets", [])
            if not datasets:
                continue

            graph_label = datasets[0].get("label", "").lower()
            labels = pie.get("labels", [])
            values = datasets[0].get("data", [])

            match graph_label:
                case lbl if any(k in lbl for k in ["età", "eta'", "age"]):
                    _aggiorna_statistica_json(record, "eta", labels, values)

                case lbl if "numero medio di studenti" in lbl:
                    _aggiorna_statistica_json(record, "num_studenti", labels, values)

                case lbl if any(k in lbl for k in ["studio autonomo", "giornalmente"]):
                    _aggiorna_statistica_json(record, "studio_gg", labels, values)

                case lbl if "ore di studio, in totale" in lbl:
                    _aggiorna_statistica_json(record, "studio_tot", labels, values)

                case lbl if any(k in lbl for k in ["domicilio", "tempo impiega"]):
                    _aggiorna_statistica_json(record, "ragg_uni", labels, values)

                case lbl if any(k in lbl for k in ["sesso", "genere", "gender"]):
                    femmine_count = 0
                    for i, lbl_sesso in enumerate(labels):
                        if lbl_sesso.lower() in ["f", "femmina", "femmine"] and i < len(
                            values
                        ):
                            femmine_count += int(values[i])

                    if is_nf_graph:
                        record["femmine_nf"] = (
                            record.get("femmine_nf") or 0
                        ) + femmine_count
                    else:
                        record["femmine"] = (record.get("femmine") or 0) + femmine_count

                case lbl if any(k in lbl for k in ["fuori corso", "iscrizione"]):
                    fc_count = 0
                    for i, lbl_fc in enumerate(labels):
                        if "fuori corso" in lbl_fc.lower() and i < len(values):
                            fc_count += int(values[i])
                    record["fc"] += fc_count

                case _:
                    pass

    for campo in ["eta", "num_studenti", "studio_gg", "studio_tot", "ragg_uni"]:
        if record[campo] == {}:
            record[campo] = None

    return [record]
