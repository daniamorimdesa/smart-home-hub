"""Utilitário de logging em CSV.

Este módulo expõe apenas `CsvLogger`, usado pelos observers em
`smart_home.core.observers` para registrar:
 - transições de estado (arquivo transitions.csv)
 - comandos e demais eventos (arquivo events.csv)

Removido código legado/facade não utilizado (`LoggerCSV`) para simplificar.
Se no futuro for necessário um wrapper de alto nível para relatórios ou
agregações, crie um módulo separado (ex.: `relatorios_export.py`) em vez de
reacoplar aqui.
"""

from __future__ import annotations

import csv
from pathlib import Path
from threading import Lock
from typing import Iterable, Mapping, Any


class CsvLogger:
    """Singleton minimalista para escrever linhas em CSV (com cabeçalho automático)."""
    _instance: "CsvLogger | None" = None
    _lock = Lock()

    def __new__(cls) -> "CsvLogger":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # armazena quais arquivos já tiveram cabeçalho escrito nesta execução
                cls._instance._file_headers_written = set()  # type: ignore[attr-defined]
            return cls._instance

    def write_row(self, path: Path | str, headers: Iterable[str], row: Mapping[str, Any]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        headers = list(headers)
        write_header = p not in self._file_headers_written and not p.exists()

        with p.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            if write_header:
                writer.writeheader()
                self._file_headers_written.add(p)
            writer.writerow(row)

    def write_rows(self, path: Path | str, headers: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
        for r in rows:
            self.write_row(path, headers, r)
    