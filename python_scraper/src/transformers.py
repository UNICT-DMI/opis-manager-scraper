import re
from typing import Any, Dict, List, Optional, Tuple


def parse_course_name(full_name: Optional[str]) -> Tuple[str, str]:

    if not full_name:
        return "", ""

    full_name = full_name.strip()

    # Regex universale e sicura:
    # \s+              -> Spazio che separa il nome dalla classe
    # \(?              -> Ignora eventuale parentesi tonda aperta
    # (                -> INIZIO GRUPPO 1 (Quello che salveremo come 'classe')
    #   L[a-z]* -> "L" seguita da lettere opzionali (L, LM, LMCU, LMG...)
    #   [-/]           -> Separatore obbligatorio (trattino o slash)
    #   (?:\d|snt)     -> Dopo il separatore DEVE esserci un numero (\d) o "snt"
    #   .*?            -> Cattura TUTTO il resto in modo pigro (altre classi, virgole, R, cu...)
    # )                -> FINE GRUPPO 1
    # \)?              -> Ignora eventuale parentesi tonda chiusa
    # \s*$             -> Fine stringa (ignorando eventuali spazi vuoti finali)
    pattern = r"\s+\(?(L[a-z]*[-/](?:\d|snt).*?)\)?\s*$"

    match = re.search(pattern, full_name, re.IGNORECASE)

    if match:

        classe = match.group(1).upper()
        nome = full_name[: match.start()].strip()

        if nome.endswith("-"):
            nome = nome[:-1].strip()

        # The post-2021 API appends " R" ("Riformato") to every class code
        # (e.g. "LM-7 R", "L-39 R, LM-40 R"). Pre-2021 data stored plain
        # "LM-7" / "L-39, LM-40", so strip the suffix from every comma-
        # separated class code to keep both eras comparable.
        classe = re.sub(r"\s+R(?=,|$)", "", classe)

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


# OPIS uses a 4-level Likert scale (R1..R4). R5 "Non so" and R6 "Non previste"
# are collected by the survey but are explicitly excluded from evaluation
# (see API HTML: "le risposte 'non so' e 'non previste' non sono computate
# ai fini del calcolo"), so we drop them here to stay aligned with the
# pre-2021 data shape consumed by opis-manager-core / OPIS-Manager frontend.
NUM_QUESTIONS = 12
NUM_ANSWERS = 4
DOMANDE_LEN = NUM_QUESTIONS * NUM_ANSWERS


def _process_cluster_data(cluster: Dict[str, Any], record: Dict[str, Any]) -> None:
    cluster_info = cluster.get("cluster", {})
    cluster_name = cluster_info.get("Text", "").lower()
    is_nf = "non frequentanti" in cluster_name

    domande_flat = [0] * DOMANDE_LEN
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

        if q_idx < 0 or q_idx >= NUM_QUESTIONS:
            continue

        subs = q.get("submissions", 0)
        totale_schede = max(totale_schede, subs)

        base_offset = q_idx * NUM_ANSWERS
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

            if offset >= 0:
                domande_flat[base_offset + offset] = count

    if is_nf:
        record["totale_schede_nf"] = totale_schede
        record["domande_nf"] = domande_flat
    else:
        record["totale_schede"] = totale_schede
        record["domande"] = domande_flat


def _process_graph_pie(
    pie: Dict[str, Any], is_nf_graph: bool, record: Dict[str, Any]
) -> None:
    datasets = pie.get("datasets", [])
    if not datasets:
        return

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
                if lbl_sesso.lower() in ["f", "femmina", "femmine"] and i < len(values):
                    femmine_count += int(values[i])

            if is_nf_graph:
                record["femmine_nf"] = (record.get("femmine_nf") or 0) + femmine_count
            else:
                record["femmine"] = (record.get("femmine") or 0) + femmine_count

        case lbl if any(k in lbl for k in ["fuori corso", "iscrizione", "anno di iscr"]):
            fc_count = 0
            for i, lbl_fc in enumerate(labels):
                if "fuori corso" in lbl_fc.lower() and i < len(values):
                    fc_count += int(values[i])
            record["fc"] += fc_count
            _aggiorna_statistica_json(record, "anno_iscr", labels, values)

        case _:
            pass


def parse_scheda_opis_data(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    clusters = json_data.get("clusterData", [])
    graphs = json_data.get("graphPieList", [])

    record = {
        "totale_schede": 0,
        "totale_schede_nf": 0,
        "fc": 0,
        "inatt_nf": 0,
        "domande": [0] * DOMANDE_LEN,
        "domande_nf": [0] * DOMANDE_LEN,
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
        _process_cluster_data(cluster, record)

    for graph in graphs:
        is_nf_graph = "non frequentanti" in graph.get("name", "").lower()

        for pie in graph.get("dataPie", []):
            _process_graph_pie(pie, is_nf_graph, record)

    for campo in ["eta", "num_studenti", "studio_gg", "studio_tot", "ragg_uni", "anno_iscr"]:
        if not record[campo]:
            record[campo] = None

    # Skip activities for which neither cluster produced usable Likert data.
    # The API returns the two cluster headers (Frequentanti / Non Frequentanti)
    # even when response counts are too low to publish per-question detail
    # (a privacy threshold), so we'd otherwise insert a row of all zeros and
    # pollute the /insegnamenti API output with apparent "empty" teachings.
    if record["totale_schede"] == 0 and record["totale_schede_nf"] == 0:
        return []

    return [record]
