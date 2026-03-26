from dataclasses import dataclass
from typing import Any, Optional, List


@dataclass
class Dipartimento:
    unict_id: int
    nome: str
    anno_accademico: str


@dataclass
class CorsoDiStudi:
    unict_id: str
    nome: str
    classe: str
    anno_accademico: str
    dipartimento_id: int


@dataclass
class Insegnamento:
    codice_gomp: int
    id_cds: str
    anno_accademico: str
    nome: str
    docente: str
    # Campo Transitorio
    professor_tax: str

    anno: str = ""
    semestre: str = ""
    cfu: str = ""

    canale: str = "no"
    id_modulo: int = 0

    ssd: Optional[str] = None
    nome_modulo: Optional[str] = None


@dataclass
class SchedaOpis:
    anno_accademico: str
    id_insegnamento: int
    totale_schede: int
    totale_schede_nf: int
    fc: int
    inatt_nf: int

    domande: List[int]
    domande_nf: List[int]
    motivo_nf: List[str]  # ?
    sugg: List[str]  # ?
    sugg_nf: List[str]  # ?

    eta: Optional[dict[str, int]] = None
    inatt: Optional[int] = None
    femmine: Optional[int] = None
    femmine_nf: Optional[int] = None
    anno_iscr: Optional[Any] = None
    num_studenti: Optional[Any] = None
    ragg_uni: Optional[Any] = None
    studio_gg: Optional[Any] = None
    studio_tot: Optional[Any] = None
