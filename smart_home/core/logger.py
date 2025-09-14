# smart_home/core/logger.py
from __future__ import annotations

import csv
import json
from pathlib import Path
from threading import Lock
from typing import Iterable, Mapping, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # Importa só para type-check (não roda em tempo de execução)
    from smart_home.core.eventos import Evento


class CsvLogger:
    """
    Singleton minimalista para escrever linhas em CSV, com criação de pasta
    e cabeçalho automático.
    """
    _instance: "CsvLogger | None" = None
    _lock = Lock()

    def __new__(cls) -> "CsvLogger":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._file_headers_written: set[Path] = set()
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


class LoggerCSV:
    """
    Facade (também Singleton) por cima do CsvLogger, com caminhos padrão e
    utilitários para eventos e relatórios.
    """
    _instance: "LoggerCSV | None" = None
    _lock = Lock()

    def __new__(cls, base_dir: Path | str = "data"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # atributos de instância inicializados aqui para garantir singleton
                cls._instance._base_dir = Path(base_dir)
                cls._instance._csv = CsvLogger()
            return cls._instance

    # opcional: permitir mudar diretório base em runtime
    def set_base_dir(self, base_dir: Path | str) -> None:
        self._base_dir = Path(base_dir)

    # ---------- utilitários de alto nível ----------
    def log_transicao(self, *, id_dispositivo: str, evento: str, estado_origem: str, estado_destino: str,
                      timestamp: Optional[str] = None) -> None:
        path = self._base_dir / "logs" / "transicoes.csv"
        headers = ["timestamp", "id_dispositivo", "evento", "estado_origem", "estado_destino"]
        row = {
            "timestamp": timestamp or "",  # observers podem preencher com datetime.now().isoformat()
            "id_dispositivo": id_dispositivo,
            "evento": evento,
            "estado_origem": estado_origem,
            "estado_destino": estado_destino,
        }
        self._csv.write_row(path, headers, row)

    def log_evento_generico(self, evt: "Evento") -> None:
        """
        Fallback universal: salva tipo + payload JSON bruto.
        Útil para COMANDO_EXECUTADO, DISPOSITIVO_ADICIONADO etc.
        """
        path = self._base_dir / "logs" / "eventos.csv"
        headers = ["timestamp", "tipo", "payload_json"]
        row = {
            "timestamp": evt.timestamp,
            "tipo": getattr(evt.tipo, "name", str(evt.tipo)),
            "payload_json": json.dumps(evt.payload, ensure_ascii=False),
        }
        self._csv.write_row(path, headers, row)

    def log_relatorio(self, nome: str, headers: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
        """
        Escreve relatórios em CSV (ex.: consumo, uso por hora etc.).
        """
        path = self._base_dir / "relatorios" / f"{nome}.csv"
        self._csv.write_rows(path, headers, rows)
    
    # # --- Helper opcional para registrar observers padrão (evita circular import) ---
    # from pathlib import Path

    # def registrar_loggers_padrao(hub, base_dir: Path | str = "data/logs") -> None:
    #     """
    #     Registra um ConsoleObserver e dois CSV observers padrão (transitions.csv, events.csv).
    #     Import interno para evitar import circular.
    #     """
    #     from smart_home.core.observers import ConsoleObserver, CsvObserverTransitions, CsvObserverEventos  # import tardio

    #     base = Path(base_dir)
    #     base.mkdir(parents=True, exist_ok=True)

    #     hub.registrar_observer(ConsoleObserver())
    #     hub.registrar_observer(CsvObserverTransitions(base / "transitions.csv"))
    #     hub.registrar_observer(CsvObserverEventos(base / "events.csv"))


































# # smart_home/core/logger.py: logger singleton para CSV e observers para eventos do Hub
# from __future__ import annotations
# import csv
# import json
# from pathlib import Path
# from threading import Lock
# from typing import Iterable, Mapping, Any

# from smart_home.core.eventos import Evento, TipoEvento
# from smart_home.core.observers import Observer

# # -------------------------------------------------------------------------------------------------
# # CsvLogger (Singleton utilitário) — escreve linhas/arquivos CSV com cabeçalho automático
# # -------------------------------------------------------------------------------------------------
# class CsvLogger:
#     _instance: "CsvLogger | None" = None
#     _lock = Lock()

#     def __new__(cls) -> "CsvLogger":
#         with cls._lock:
#             if cls._instance is None:
#                 cls._instance = super().__new__(cls)
#                 # guarda quais arquivos já tiveram header escrito nesta execução
#                 cls._instance._file_headers_written: set[Path] = set()
#             return cls._instance

#     def write_row(self, path: str | Path, headers: Iterable[str], row: Mapping[str, Any]) -> None:
#         p = Path(path)
#         p.parent.mkdir(parents=True, exist_ok=True)

#         headers = list(headers)
#         write_header = p not in self._file_headers_written and not p.exists()

#         # Normaliza valores para CSV (ex.: dict vira JSON)
#         def _norm(v: Any) -> Any:
#             if isinstance(v, (dict, list)):
#                 return json.dumps(v, ensure_ascii=False)
#             return v

#         with p.open("a", newline="", encoding="utf-8") as f:
#             writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
#             if write_header:
#                 writer.writeheader()
#                 self._file_headers_written.add(p)
#             writer.writerow({k: _norm(row.get(k)) for k in headers})

#     def write_rows(self, path: str | Path, headers: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
#         for r in rows:
#             self.write_row(path, headers, r)


# # -------------------------------------------------------------------------------------------------
# # LoggerEventosCSV (Observer) — escuta eventos do Hub e escreve em CSV padrão do enunciado
# # -------------------------------------------------------------------------------------------------
# class LoggerEventosCSV(Observer):
#     """
#     Observador que registra eventos do Hub em CSV.
#     Formato principal (compatível com o enunciado):
#       timestamp,id_dispositivo,evento,estado_origem,estado_destino

#     Também registra DISPOSITIVO_ADICIONADO, DISPOSITIVO_REMOVIDO e ATRIBUTO_ALTERADO
#     usando as mesmas colunas (as que não se aplicarem ficam vazias) e um campo 'extra'
#     opcional com informações úteis em JSON.
#     """

#     HEADERS = ["timestamp", "id_dispositivo", "evento", "estado_origem", "estado_destino", "extra"]

#     def __init__(self, path: str | Path = "data/eventos.csv") -> None:
#         self.path = Path(path)

#     def on_event(self, evt: Evento) -> None:
#         # Mapeamento básico (fallbacks vazios mantêm CSV consistente)
#         payload = evt.payload or {}
#         id_disp   = payload.get("id", "")
#         antes     = payload.get("antes", "")
#         depois    = payload.get("depois", "")
#         # evento: usa nome do comando quando houver; senão o tipo do evento
#         evento    = payload.get("comando") or evt.tipo.name

#         # extra: guardamos o payload completo, removendo campos já mapeados
#         extra_dict = {k: v for k, v in payload.items() if k not in {"id", "antes", "depois", "comando"}}
#         extra_str  = extra_dict if extra_dict else ""

#         # Escreve a linha
#         CsvLogger().write_row(
#             self.path,
#             self.HEADERS,
#             {
#                 "timestamp": evt.timestamp,
#                 "id_dispositivo": id_disp,
#                 "evento": evento,
#                 "estado_origem": antes,
#                 "estado_destino": depois,
#                 "extra": extra_str,
#             },
#         )


# # -------------------------------------------------------------------------------------------------
# # (Opcional) LoggerErrosCSV — caso você dispare TipoEvento.ERRO pelo Hub
# # -------------------------------------------------------------------------------------------------
# class LoggerErrosCSV(Observer):
#     """Observador simples para erros do Hub."""
#     HEADERS = ["timestamp", "origem", "mensagem", "detalhes"]

#     def __init__(self, path: str | Path = "data/erros.csv") -> None:
#         self.path = Path(path)

#     def on_event(self, evt: Evento) -> None:
#         if evt.tipo.name != "ERRO":
#             return
#         payload = evt.payload or {}
#         CsvLogger().write_row(
#             self.path,
#             self.HEADERS,
#             {
#                 "timestamp": evt.timestamp,
#                 "origem": payload.get("origem", ""),
#                 "mensagem": payload.get("mensagem", ""),
#                 "detalhes": {k: v for k, v in payload.items() if k not in {"origem", "mensagem"}},
#             },
#         )


# # -------------------------------------------------------------------------------------------------
# # Helper opcional para registrar rapidamente no Hub
# # -------------------------------------------------------------------------------------------------
# def registrar_loggers_padrao(hub, *, eventos_csv: str | Path = "data/eventos.csv", erros_csv: str | Path = "data/erros.csv") -> None:
#     """Registra LoggerEventosCSV e LoggerErrosCSV no hub."""
#     hub.registrar_observer(LoggerEventosCSV(eventos_csv))
#     hub.registrar_observer(LoggerErrosCSV(erros_csv))
























































# # # smart_home/core/logger.py: logger singleton para CSV
# # from __future__ import annotations
# # import csv
# # from pathlib import Path
# # from threading import Lock
# # from typing import Iterable, Mapping, Any

# # class CsvLogger:
# #     """Singleton minimalista para escrever linhas em CSV, com criação de pasta e cabeçalho automático."""
# #     _instance: "CsvLogger | None" = None
# #     _lock = Lock()

# #     def __new__(cls) -> "CsvLogger":
# #         with cls._lock:
# #             if cls._instance is None:
# #                 cls._instance = super().__new__(cls)
# #                 cls._instance._file_headers_written: set[Path] = set()
# #             return cls._instance

# #     # API: chame sempre via CsvLogger().write_row(...)
# #     def write_row(self, path: Path | str, headers: Iterable[str], row: Mapping[str, Any]) -> None:
# #         p = Path(path)
# #         p.parent.mkdir(parents=True, exist_ok=True)

# #         headers = list(headers)
# #         write_header = p not in self._file_headers_written and not p.exists()

# #         with p.open("a", newline="", encoding="utf-8") as f:
# #             writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
# #             if write_header:
# #                 writer.writeheader()
# #                 self._file_headers_written.add(p)
# #             writer.writerow(row)

# #     def write_rows(self, path: Path | str, headers: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
# #         for r in rows:
# #             self.write_row(path, headers, r)


# # # smart_home/core/logger.py
# # from __future__ import annotations
# # import csv
# # from pathlib import Path
# # from threading import Lock
# # from smart_home.core.eventos import Evento, TipoEvento
# # from smart_home.core.observers import Observer

# # class LoggerCSV(Observer):
# #     _instance = None
# #     _lock = Lock()

# #     def __new__(cls, arquivo: str = "data/eventos.csv"):
# #         with cls._lock:
# #             if cls._instance is None:
# #                 cls._instance = super().__new__(cls)
# #                 cls._instance._init(arquivo)
# #             return cls._instance

# #     def _init(self, arquivo: str):
# #         self.path = Path(arquivo)
# #         self.path.parent.mkdir(parents=True, exist_ok=True)
# #         # se não existe, cria com cabeçalho
# #         if not self.path.exists():
# #             with self.path.open("w", newline="", encoding="utf-8") as f:
# #                 writer = csv.writer(f)
# #                 writer.writerow(["timestamp","id_dispositivo","evento",
# #                                  "estado_origem","estado_destino"])

# #     def on_event(self, evt: Evento) -> None:
# #         if evt.tipo in (TipoEvento.TRANSICAO_ESTADO, TipoEvento.COMANDO_EXECUTADO):
# #             with self.path.open("a", newline="", encoding="utf-8") as f:
# #                 writer = csv.writer(f)
# #                 writer.writerow([
# #                     evt.timestamp,
# #                     evt.payload.get("id"),
# #                     evt.payload.get("comando") or evt.tipo.name,
# #                     evt.payload.get("antes"),
# #                     evt.payload.get("depois"),
# #                 ])
