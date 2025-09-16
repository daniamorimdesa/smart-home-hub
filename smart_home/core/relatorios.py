# smart_home/core/relatorios.py: funções para gerar relatórios a partir dos logs
from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Dict, List, Iterable, Optional, Tuple, Any
from datetime import datetime
from collections import Counter, defaultdict
from functools import reduce
# -------------------------------------------------------------------------------------------------
# Util: leitura de arquivos
# -------------------------------------------------------------------------------------------------
_DT_FMT = "%Y-%m-%dT%H:%M:%S"  # formato primário de timestamps dos CSVs

def _parse_dt(s: str) -> datetime:
    """Converte string em datetime.

    Tenta primeiro o formato conhecido; se falhar, delega para fromisoformat
    (aceitando também microssegundos).
    """
    try:
        return datetime.strptime(s, _DT_FMT)
    except ValueError:
        return datetime.fromisoformat(s)

def ler_csv_transitions(path: Path) -> List[dict]:
    """Lê `transitions.csv`.

    Estrutura esperada: timestamp,id_dispositivo,evento,estado_origem,estado_destino
    Linhas sem timestamp são ignoradas.
    """
    if not path.exists():
        return []
    rows: List[dict] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ts = row.get("timestamp")
            if not ts:
                continue
            try:
                row["timestamp"] = _parse_dt(ts)
            except Exception:
                continue  # descarta linha corrompida
            rows.append(row)
    return rows

def ler_csv_events(path: Path) -> List[dict]:
    """Lê `events.csv`.

    Tenta desserializar a coluna 'extra' se for JSON plausível.
    Linhas sem timestamp são ignoradas.
    """
    if not path.exists():
        return []
    rows: List[dict] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ts = row.get("timestamp")
            if not ts:
                continue
            try:
                row["timestamp"] = _parse_dt(ts)
            except Exception:
                continue
            extra = row.get("extra")
            if isinstance(extra, str) and extra:
                # tenta um parse direto; se falhar, mantém string original
                try:
                    row["extra"] = json.loads(extra)
                except Exception:
                    try:
                        # fallback leve: substituir aspas simples
                        row["extra"] = json.loads(extra.replace("'", '"'))
                    except Exception:
                        pass
            rows.append(row)
    return rows

def ler_config(path: Path) -> Dict[str, dict]:
    """Lê `config.json` e devolve índice por id.

    Retorna dict vazio se arquivo não existir ou estiver corrompido.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    idx: Dict[str, dict] = {}
    for d in data.get("dispositivos", []) or []:
        dev_id = d.get("id")
        if not dev_id:
            continue
        idx[dev_id] = {
            "tipo": d.get("tipo"),
            "nome": d.get("nome"),
            "estado": d.get("estado"),
            "atributos": d.get("atributos", {}),
        }
    return idx

# -------------------------------------------------------------------------------------------------
# Filtros de janela temporal
# -------------------------------------------------------------------------------------------------
def _filtro_periodo(rows: Iterable[dict], inicio: Optional[datetime], fim: Optional[datetime]) -> List[dict]:
    """Filtra registros entre [inicio, fim]."""
    return [r for r in rows if (inicio is None or r["timestamp"] >= inicio) and (fim is None or r["timestamp"] <= fim)]


def _intervalos_ligado(evts: List[dict], on_label: str, off_label: str, fim_periodo: Optional[datetime]) -> float:
    """Calcula total em horas (ou segundos, depois convertido) entre sequências ON/OFF.

    Considera que cada linha já está ordenada por timestamp; se não, ordena localmente.
    Se o último intervalo não fechar, usa `fim_periodo` ou o último timestamp.
    """
    if not evts:
        return 0.0
    evts = sorted(evts, key=lambda x: x["timestamp"])
    ligado_desde: Optional[datetime] = None
    acumulado_horas = 0.0
    for e in evts:
        dst = str(e.get("estado_destino", "")).upper()
        if dst == on_label and ligado_desde is None:
            ligado_desde = e["timestamp"]
        elif dst == off_label and ligado_desde is not None:
            acumulado_horas += max((e["timestamp"] - ligado_desde).total_seconds() / 3600.0, 0.0)
            ligado_desde = None
    if ligado_desde is not None:
        limite = fim_periodo or evts[-1]["timestamp"]
        acumulado_horas += max((limite - ligado_desde).total_seconds() / 3600.0, 0.0)
    return acumulado_horas

# -------------------------------------------------------------------------------------------------
# 1) Consumo por TOMADA (Wh no período)  — reduce
# Lemos transitions.csv; para cada tomada, calculamos somando (potencia_w * horas_ligadas)
# -------------------------------------------------------------------------------------------------
def consumo_por_tomada(
    transitions_csv: Path,
    config_json: Path,
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
    incluir_total: bool = False,
) -> List[dict]:
    """Calcula consumo (Wh) por tomada no período.

    Se `incluir_total` for True, adiciona um registro agregado com id_dispositivo='__TOTAL__'.
    """
    trans = _filtro_periodo(ler_csv_transitions(transitions_csv), inicio, fim)
    cfg = ler_config(config_json)
    pot_por_id: Dict[str, float] = {
        i: float(info.get("atributos", {}).get("potencia_w", 0))
        for i, info in cfg.items() if info.get("tipo") == "TOMADA"
    }
    eventos_por_id: Dict[str, List[dict]] = defaultdict(list)
    for r in trans:
        did = r.get("id_dispositivo")
        if did in pot_por_id:
            eventos_por_id[did].append(r)
    resultados: List[dict] = []
    for id_, evts in eventos_por_id.items():
        horas = _intervalos_ligado(evts, on_label="LIGADA", off_label="DESLIGADA", fim_periodo=fim)
        wh = pot_por_id.get(id_, 0.0) * horas
        evts_sorted = sorted(evts, key=lambda x: x["timestamp"])  # para datas
        resultados.append(
            {
                "id_dispositivo": id_,
                "potencia_w": pot_por_id.get(id_, 0.0),
                "horas_ligada": round(horas, 6),
                "total_wh": round(wh, 4),
                "inicio_periodo": (inicio or evts_sorted[0]["timestamp"]).isoformat(timespec="seconds"),
                "fim_periodo": (fim or evts_sorted[-1]["timestamp"]).isoformat(timespec="seconds"),
            }
        )
    if incluir_total and resultados:
        total_wh = round(reduce(lambda acc, r: acc + r["total_wh"], resultados, 0.0), 4)
        resultados.append({
            "id_dispositivo": "__TOTAL__",
            "potencia_w": 0.0,
            "horas_ligada": round(reduce(lambda acc, r: acc + r["horas_ligada"], resultados, 0.0), 6),
            "total_wh": total_wh,
            "inicio_periodo": resultados[0]["inicio_periodo"],
            "fim_periodo": resultados[0]["fim_periodo"],
        })
    return resultados

# -------------------------------------------------------------------------------------------------
# 2) Tempo total com cada LUZ ligada (hh:mm:ss) — map/filter + comprehensions
# -------------------------------------------------------------------------------------------------
def tempo_total_luzes_ligadas(
    transitions_csv: Path,
    config_json: Path,
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
) -> List[dict]:
    """Calcula o tempo total (segundos) que cada luz permaneceu ligada."""
    trans = _filtro_periodo(ler_csv_transitions(transitions_csv), inicio, fim)
    # Mantemos somente eventos onde houve efetiva mudança de estado para reduzir ruído
    trans = [r for r in trans if r.get("estado_origem") != r.get("estado_destino")]
    cfg = ler_config(config_json)
    ids_luz = {i for i, info in cfg.items() if info.get("tipo") == "LUZ"}
    por_id: Dict[str, List[dict]] = defaultdict(list)
    for r in trans:
        did = r.get("id_dispositivo")
        if did in ids_luz:
            por_id[did].append(r)
    resultados: List[dict] = []
    for id_, evts in por_id.items():
        horas = _intervalos_ligado(evts, on_label="LIGADA", off_label="DESLIGADA", fim_periodo=fim)
        segundos = int(horas * 3600)
        resultados.append({
            "id_dispositivo": id_,
            "segundos_ligada": segundos,
            "hhmmss": _fmt_hhmmss(segundos),
        })
    return sorted(resultados, key=lambda r: r["segundos_ligada"], reverse=True)

def _fmt_hhmmss(seg: int) -> str:
    h = seg // 3600
    m = (seg % 3600) // 60
    s = seg % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

# -------------------------------------------------------------------------------------------------
# 3) Dispositivos mais usados — ordenar por número de eventos no log (sorted)
#    (soma transitions.csv + events.csv para uma visão mais ampla)
# -------------------------------------------------------------------------------------------------
def dispositivos_mais_usados(
    transitions_csv: Path,
    events_csv: Path,
    top_n: int = 10,
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
) -> List[Tuple[str, int]]:
    """Retorna tuplas (id, quantidade_eventos) ordenadas por uso decrescente."""
    trans = _filtro_periodo(ler_csv_transitions(transitions_csv), inicio, fim)
    evs = _filtro_periodo(ler_csv_events(events_csv), inicio, fim)
    c = Counter()
    c.update([r.get("id_dispositivo") for r in trans if r.get("id_dispositivo")])
    c.update([r.get("id") for r in evs if r.get("id")])
    return c.most_common(top_n)

# -------------------------------------------------------------------------------------------------
# 4) Bônus: Quantidade de cafés preparados no período
#    (usa transitions.csv: evento == 'finalizar_preparo' OU destino == 'PRONTA' vindo de PREPARANDO)
# -------------------------------------------------------------------------------------------------
def cafes_preparados(
    transitions_csv: Path,
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
) -> int:
    """Conta quantos preparos de café foram concluídos no período."""
    trans = _filtro_periodo(ler_csv_transitions(transitions_csv), inicio, fim)
    def _ok(r: dict) -> bool:
        ev = (r.get("evento") or "").lower()
        so = (r.get("estado_origem") or "").upper()
        sd = (r.get("estado_destino") or "").upper()
        return ev == "finalizar_preparo" or (so == "PREPARANDO" and sd == "PRONTA")
    return sum(1 for r in trans if _ok(r))

def cafes_por_dia(
    transitions_csv: Path,
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
) -> List[dict]:
    """Retorna contagem de cafés por dia (data ISO yyyy-mm-dd, preparos_no_dia).

    Usa mesma lógica de detecção de preparo concluído de `cafes_preparados`.
    """
    trans = _filtro_periodo(ler_csv_transitions(transitions_csv), inicio, fim)
    def _ok(r: dict) -> bool:
        ev = (r.get("evento") or "").lower()
        so = (r.get("estado_origem") or "").upper()
        sd = (r.get("estado_destino") or "").upper()
        return ev == "finalizar_preparo" or (so == "PREPARANDO" and sd == "PRONTA")
    por_dia: Dict[str, int] = defaultdict(int)
    for r in trans:
        if _ok(r):
            dia = r["timestamp"].date().isoformat()
            por_dia[dia] += 1
    return [
        {"data": dia, "preparos_no_dia": qtd}
        for dia, qtd in sorted(por_dia.items())
    ]

# -------------------------------------------------------------------------------------------------
# 5) Bônus: Distribuição de comandos por tipo de dispositivo (events.csv + config.json)
#    Conta COMANDO_EXECUTADO por tipo
# -------------------------------------------------------------------------------------------------
def distribuicao_comandos_por_tipo(
    events_csv: Path,
    config_json: Path,
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
) -> List[Tuple[str, int]]:
    """Distribuição de COMANDO_EXECUTADO por tipo de dispositivo."""
    evs = _filtro_periodo(ler_csv_events(events_csv), inicio, fim)
    cfg = ler_config(config_json)
    id_tipo = {i: info.get("tipo", "DESCONHECIDO") for i, info in cfg.items()}
    c = Counter()
    for e in evs:
        if e.get("tipo") == "COMANDO_EXECUTADO":
            c[id_tipo.get(e.get("id"), "DESCONHECIDO")] += 1
    return sorted(c.items(), key=lambda kv: kv[1], reverse=True)


def resumo(
    transitions_csv: Path,
    events_csv: Path,
    config_json: Path,
    inicio: Optional[datetime] = None,
    fim: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Gera um resumo consolidado com métricas principais.

    Inclui: consumo por tomada, top dispositivos, cafés preparados, distribuição por tipo e tempo de luzes.
    """
    return {
        "consumo_tomadas": consumo_por_tomada(transitions_csv, config_json, inicio, fim, incluir_total=True),
        "top_uso": dispositivos_mais_usados(transitions_csv, events_csv, 10, inicio, fim),
        "cafes_preparados": cafes_preparados(transitions_csv, inicio, fim),
        "dist_comandos_tipo": distribuicao_comandos_por_tipo(events_csv, config_json, inicio, fim),
        "luzes_tempo": tempo_total_luzes_ligadas(transitions_csv, config_json, inicio, fim),
    }

# -------------------------------------------------------------------------------------------------
# Persistência opcional dos relatórios em CSV
# -------------------------------------------------------------------------------------------------
def salvar_csv(path: Path, headers: List[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in headers})

# -------------------------------------------------------------------------------------------------
# Mini-CLI para facilitar testes
# Exemplos:
#   python -m smart_home.core.relatorio consumo --trans data/logs/transitions.csv --config data/config.json --out data/reports/consumo.csv
#   python -m smart_home.core.relatorio luzes --trans data/logs/transitions.csv --config data/config.json
#   python -m smart_home.core.relatorio top --trans data/logs/transitions.csv --events data/logs/events.csv --n 5
#   python -m smart_home.core.relatorio cafes --trans data/logs/transitions.csv
#   python -m smart_home.core.relatorio dist --events data/logs/events.csv --config data/config.json
# -------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser("Relatórios Smart Home")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_periodo(a: argparse.ArgumentParser, incluir_out: bool = False, incluir_config: bool = False, incluir_events: bool = False):
        a.add_argument("--trans", type=Path, required=True, help="Caminho para transitions.csv")
        if incluir_config:
            a.add_argument("--config", type=Path, required=True, help="Caminho para config.json")
        if incluir_events:
            a.add_argument("--events", type=Path, required=True, help="Caminho para events.csv")
        a.add_argument("--inicio", type=str, default=None, help="Datetime ISO inicial (opcional)")
        a.add_argument("--fim", type=str, default=None, help="Datetime ISO final (opcional)")
        if incluir_out:
            a.add_argument("--out", type=Path, default=None, help="Salvar CSV nesse caminho")
        a.add_argument("--json", action="store_true", help="Força saída em JSON (stdout)")

    # consumo
    add_periodo(sub.add_parser("consumo", help="Consumo por tomada (Wh)"), incluir_out=True, incluir_config=True)

    # luzes
    add_periodo(sub.add_parser("luzes", help="Tempo total com cada luz ligada"), incluir_out=True, incluir_config=True)

    # top usados
    sp_top = sub.add_parser("top", help="Dispositivos mais usados")
    add_periodo(sp_top, incluir_config=False, incluir_events=True)
    sp_top.add_argument("--n", type=int, default=10)

    # cafés
    add_periodo(sub.add_parser("cafes", help="Quantidade de cafés preparados"))

    # distribuição por tipo
    add_periodo(sub.add_parser("dist", help="Distribuição de comandos por tipo"), incluir_out=True, incluir_config=True, incluir_events=True)

    # resumo agregado
    add_periodo(sub.add_parser("resumo", help="Resumo consolidado (várias métricas)"), incluir_config=True, incluir_events=True)

    args = p.parse_args()
    inicio = datetime.fromisoformat(args.inicio) if getattr(args, "inicio", None) else None
    fim = datetime.fromisoformat(args.fim) if getattr(args, "fim", None) else None

    def _emit(obj: Any):
        if args.json:
            print(json.dumps(obj, ensure_ascii=False, indent=2))
        else:
            if isinstance(obj, list):
                for item in obj:
                    print(item)
            else:
                print(obj)

    if args.cmd == "consumo":
        rows = consumo_por_tomada(args.trans, args.config, inicio, fim)
        if args.out:
            salvar_csv(args.out, ["id_dispositivo", "potencia_w", "horas_ligada", "total_wh", "inicio_periodo", "fim_periodo"], rows)
            print(f"[OK] Salvo em {args.out}")
        _emit(rows)
    elif args.cmd == "luzes":
        rows = tempo_total_luzes_ligadas(args.trans, args.config, inicio, fim)
        if args.out:
            salvar_csv(args.out, ["id_dispositivo", "segundos_ligada", "hhmmss"], rows)
            print(f"[OK] Salvo em {args.out}")
        _emit(rows)
    elif args.cmd == "top":
        top_rows = dispositivos_mais_usados(args.trans, args.events, args.n, inicio, fim)
        _emit(top_rows)
    elif args.cmd == "cafes":
        qtd = cafes_preparados(args.trans, inicio, fim)
        _emit({"cafes_preparados": qtd})
    elif args.cmd == "dist":
        rows = distribuicao_comandos_por_tipo(args.events, args.config, inicio, fim)
        if args.out:
            salvar_csv(args.out, ["tipo", "qtd"], [{"tipo": t, "qtd": n} for t, n in rows])
            print(f"[OK] Salvo em {args.out}")
        _emit(rows)
    elif args.cmd == "resumo":
        data = resumo(args.trans, args.events, args.config, inicio, fim)
        _emit(data)
