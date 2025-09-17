# smart_home/core/observers.py: observers para o hub 
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict
from smart_home.core.eventos import Evento, TipoEvento
from smart_home.core.logger import CsvLogger
#--------------------------------------------------------------------------------------------------
# CLASSE BASE PARA OBSERVERS (PADRÃO OBSERVER)
#--------------------------------------------------------------------------------------------------
class Observer(ABC):
    @abstractmethod
    def on_event(self, evt: Evento) -> None:
        pass

#--------------------------------------------------------------------------------------------------
#  OBSERVER PARA GRAVAR TRANSIÇÕES DE ESTADO EM CSV
#--------------------------------------------------------------------------------------------------
class CsvObserverTransitions(Observer):
    """
    Escreve as transições de estado em CSV com as colunas do enunciado:
    timestamp,id_dispositivo,evento,estado_origem,estado_destino
    """
    HEADERS = ["timestamp", "id_dispositivo", "evento", "estado_origem", "estado_destino"]

    def __init__(self, path: Path) -> None:
        """Inicializa o observer com o caminho do arquivo CSV destino. """
        self.path = Path(path)

    def on_event(self, evt: Evento) -> None:
        """Registra somente eventos de transição de estado (TRANSICAO_ESTADO)."""
        if evt.tipo != TipoEvento.TRANSICAO_ESTADO:
            return
        p = evt.payload
        row = {
            "timestamp": evt.timestamp,
            "id_dispositivo": p.get("id", ""),
            "evento": str(p.get("evento", "")).lower(),
            "estado_origem": str(p.get("antes", "")).lower(),
            "estado_destino": str(p.get("depois", "")).lower(),
        }
        CsvLogger().write_row(self.path, self.HEADERS, row)

#--------------------------------------------------------------------------------------------------
# OBSERVER SIMPLES DE CONSOLE
#--------------------------------------------------------------------------------------------------
class ConsoleObserver(Observer):
    """Observer simples de console; útil para depuração."""
    def on_event(self, evt: Evento) -> None:
        # você pode trocar por "rich" aqui se quiser
        print(f"[EVENTO] {evt.tipo.name}: {evt.payload} @ {evt.timestamp}")

#--------------------------------------------------------------------------------------------------
# OBSERVER PARA GRAVAR COMANDOS EXECUTADOS EM CSV
#--------------------------------------------------------------------------------------------------
class CsvObserverComandos(Observer):
    """Grava somente comandos executados (COMANDO_EXECUTADO) em CSV.

    Formato: timestamp,id_dispositivo,comando,estado_origem,estado_destino
    Útil para análises adicionais separadas das transições reais.
    """
    def __init__(self, path_csv: str | Path) -> None:
        self.path = Path(path_csv)
        self.headers = ["timestamp", "id_dispositivo", "comando", "estado_origem", "estado_destino"]
        self.logger = CsvLogger()

    def on_event(self, evt: Evento) -> None:
        """Registra somente eventos de comando executado (COMANDO_EXECUTADO)."""
        if evt.tipo is not TipoEvento.COMANDO_EXECUTADO:
            return
        p = evt.payload
        row = {
            "timestamp": evt.timestamp,
            "id_dispositivo": p.get("id"),
            "comando": p.get("comando"),
            "estado_origem": p.get("antes"),
            "estado_destino": p.get("depois"),
        }
        self.logger.write_row(self.path, self.headers, row)

#--------------------------------------------------------------------------------------------------
# OBSERVER PARA GRAVAR TODOS OS EVENTOS EM CSV
#--------------------------------------------------------------------------------------------------
class CsvObserverEventos(Observer):
    """Grava os eventos num CSV geral."""
    def __init__(self, path_csv: str | Path) -> None:
        self.path = Path(path_csv)
        self.headers = ["timestamp", "tipo", "id", "extra"]
        self.logger = CsvLogger()

    def on_event(self, evt: Evento) -> None:
        """Registra todos os eventos."""
        p = evt.payload 
        row = {
            "timestamp": evt.timestamp,
            "tipo": evt.tipo.name,
            "id": p.get("id"),
            "extra": {k: v for k, v in p.items() if k != "id"},
        }
        self.logger.write_row(self.path, self.headers, row)
