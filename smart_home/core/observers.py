# smart_home/core/observers.py: observadores (Observer) do hub
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable
from rich.console import Console
from rich.table import Table
from rich import box
from smart_home.core.eventos import Evento

class Observer(ABC):
    @abstractmethod
    def on_event(self, evt: Evento) -> None: ...

class ConsoleObserver(Observer):
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
    def on_event(self, evt: Evento) -> None:
        t = Table(box=box.SIMPLE, show_header=False)
        t.add_row("tipo", str(evt.tipo.name))
        for k, v in evt.payload.items():
            t.add_row(str(k), str(v))
        t.add_row("quando", evt.timestamp)
        self.console.print(t)

# simples, escreve CSV com cabeçalho
import csv, os
class CsvObserver(Observer):
    def __init__(self, path: str = "data/eventos.csv"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._ensure_header()
    def _ensure_header(self):
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["timestamp","tipo","campo","valor"])
    def on_event(self, evt: Evento) -> None:
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if evt.payload:
                for k, v in evt.payload.items():
                    w.writerow([evt.timestamp, evt.tipo.name, k, v])
            else:
                w.writerow([evt.timestamp, evt.tipo.name, "", ""])
