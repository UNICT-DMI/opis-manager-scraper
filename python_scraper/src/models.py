from dataclasses import dataclass


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
