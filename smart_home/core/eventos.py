# smart_home/core/eventos.py: tipos de evento do hub (para Observer)
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict
from datetime import datetime
#--------------------------------------------------------------------------------------------------
# TIPOS DE EVENTOS REGISTRADOS PELO HUB E ENVIADOS AOS OBSERVERS REGISTRADOS
#--------------------------------------------------------------------------------------------------
class TipoEvento(Enum):
    DISPOSITIVO_ADICIONADO = auto()
    DISPOSITIVO_REMOVIDO   = auto()
    COMANDO_EXECUTADO      = auto()
    ATRIBUTO_ALTERADO      = auto()
    TRANSICAO_ESTADO       = auto()
    ROTINA_EXECUTADA       = auto()
    ERRO                   = auto()
#--------------------------------------------------------------------------------------------------
# CLASSE DE EVENTO 
#--------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Evento:
    tipo: TipoEvento
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
