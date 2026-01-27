from dataclasses import dataclass
from typing import Optional


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
    
    anno: str = ""
    semestre: str = ""
    cfu: str = ""
    
    canale: str = "no" 
    id_modulo: int = 0
    
    ssd: Optional[str] = None