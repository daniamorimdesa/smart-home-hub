
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from functools import reduce
import json
import argparse

from .relatorios import (
    consumo_por_tomada,
    tempo_total_luzes_ligadas,
    dispositivos_mais_usados,
    cafes_preparados,
    cafes_por_dia,
    distribuicao_comandos_por_tipo,
    salvar_csv,
    ler_csv_transitions,
    ler_config,
)
#--------------------------------------------------------------------------------------------------
# Script demonstrativo para gerar relatórios a partir dos logs.
#--------------------------------------------------------------------------------------------------

def _paths_base(explicit_root: Path | None = None) -> dict:
    root = explicit_root or Path(__file__).resolve().parents[2]
    data_dir = root / "data"
    logs_dir = data_dir / "logs"
    return {
        "root": root,
        "data": data_dir,
        "logs": logs_dir,
        "transitions_csv": logs_dir / "transitions.csv",
        "events_csv": logs_dir / "events.csv",
        "config_json": data_dir / "config.json",
        "reports_dir": data_dir / "reports",
    }


def gerar_csv_consumo(transitions: Path, config: Path, saida: Path, inicio: datetime | None, fim: datetime | None):
    rows = consumo_por_tomada(transitions, config, inicio, fim)
    minimal = [
        {
            "id_dispositivo": r["id_dispositivo"],
            "total_wh": r["total_wh"],
            "inicio_periodo": r["inicio_periodo"],
            "fim_periodo": r["fim_periodo"],
        }
        for r in rows
    ]
    total_geral = reduce(lambda acc, r: acc + r["total_wh"], minimal, 0.0)
    saida.parent.mkdir(parents=True, exist_ok=True)
    salvar_csv(saida, ["id_dispositivo", "total_wh", "inicio_periodo", "fim_periodo"], minimal)
    return minimal, total_geral


def executar_relatorios(inicio: str | None, fim: str | None, json_out: bool):
    paths = _paths_base()
    if not paths["transitions_csv"].exists():
        raise SystemExit(f"Arquivo não encontrado: {paths['transitions_csv']}")
    if not paths["config_json"].exists():
        raise SystemExit(f"Arquivo não encontrado: {paths['config_json']}")

    dt_inicio = datetime.fromisoformat(inicio) if inicio else None
    dt_fim = datetime.fromisoformat(fim) if fim else None

    consumo_min, total_geral = gerar_csv_consumo(
        paths["transitions_csv"], paths["config_json"], paths["reports_dir"] / "report_consumo_wh.csv", dt_inicio, dt_fim
    )

    luzes = tempo_total_luzes_ligadas(paths["transitions_csv"], paths["config_json"], dt_inicio, dt_fim)

    events_ok = paths["events_csv"].exists()
    top = dispositivos_mais_usados(
        paths["transitions_csv"], paths["events_csv"], 10, dt_inicio, dt_fim
    ) if events_ok else []

    cafes = cafes_preparados(paths["transitions_csv"], dt_inicio, dt_fim)
    dist = distribuicao_comandos_por_tipo(
        paths["events_csv"], paths["config_json"], dt_inicio, dt_fim
    ) if events_ok else []
    cafes_dia = cafes_por_dia(paths["transitions_csv"], dt_inicio, dt_fim)

    period_start = dt_inicio.isoformat() if dt_inicio else None
    period_end = dt_fim.isoformat() if dt_fim else None

    # (Removido CSV de cafés agregados; mantemos apenas relatório diário)

    dist_csv = paths["reports_dir"] / "report_dist_comandos_tipo.csv"
    dist_rows_csv = [{"tipo": t, "qtd": q} for t, q in dist]
    salvar_csv(dist_csv, ["tipo", "qtd"], dist_rows_csv)

    cafes_por_dia_csv = paths["reports_dir"] / "report_cafes_por_dia.csv"
    if cafes_dia:
        salvar_csv(cafes_por_dia_csv, ["data", "preparos_no_dia"], cafes_dia)
    else:
        cafes_por_dia_csv = None

    # Export adicional: tempo de luzes ligadas
    if luzes:
        # Deriva período automaticamente se não fornecido: usa menor/maior timestamp de eventos de luz
        if not period_start or not period_end:
            trans_all = ler_csv_transitions(paths["transitions_csv"])
            cfg = ler_config(paths["config_json"])
            ids_luz = {i for i, info in cfg.items() if info.get("tipo") == "LUZ"}
            luz_events = [r for r in trans_all if r.get("id_dispositivo") in ids_luz]
            if luz_events:
                luz_events.sort(key=lambda r: r["timestamp"])
                period_start = period_start or luz_events[0]["timestamp"].isoformat(timespec="seconds")
                period_end = period_end or luz_events[-1]["timestamp"].isoformat(timespec="seconds")
        luzes_csv = paths["reports_dir"] / "report_tempo_luzes.csv"
        luzes_rows_csv = [
            {
                "id_dispositivo": r["id_dispositivo"],
                "segundos_ligada": r["segundos_ligada"],
                "hhmmss": r["hhmmss"],
                "inicio_periodo": period_start or "",
                "fim_periodo": period_end or "",
            }
            for r in luzes
        ]
        salvar_csv(
            luzes_csv,
            ["id_dispositivo", "segundos_ligada", "hhmmss", "inicio_periodo", "fim_periodo"],
            luzes_rows_csv,
        )
    else:
        luzes_csv = None

    # Export adicional: top dispositivos (id, qtd, periodo)
    if top:
        top_csv = paths["reports_dir"] / "report_top_dispositivos.csv"
        top_rows_csv = [
            {"id_dispositivo": did, "qtd_eventos": qtd, "inicio_periodo": period_start, "fim_periodo": period_end}
            for did, qtd in top
        ]
        salvar_csv(top_csv, ["id_dispositivo", "qtd_eventos", "inicio_periodo", "fim_periodo"], top_rows_csv)
    else:
        top_csv = None

    resumo_funcional = {
        "consumo_min": consumo_min,
        "total_wh_geral": total_geral,
        "luzes_tempo": luzes,
        "top_usados": top,
        "cafes_preparados": cafes,
        "dist_comandos_tipo": dist,
        "periodo": {
            "inicio": dt_inicio.isoformat() if dt_inicio else None,
            "fim": dt_fim.isoformat() if dt_fim else None,
        },
    }

    if json_out:
        print(json.dumps(resumo_funcional, ensure_ascii=False, indent=2))
        return resumo_funcional

    print("== Consumo (CSV salvo em data/reports/report_consumo_wh.csv) ==")
    for r in consumo_min:
        print(r)
    print(f"TOTAL GERAL (Wh): {total_geral}")
    print("\n== Luzes (tempo ligada) ==")
    for r in luzes:
        print(r)
    print("\n== Top Dispositivos ==")
    for t in top:
        print(t)
    print("\n== Cafés Preparados (total no período) ==")
    print({"cafes_preparados": cafes})
    print("\n== Distribuição de Comandos por Tipo ==")
    for d in dist:
        print(d)
    print("\n== Cafés por Dia ==")
    for cd in cafes_dia:
        print(cd)
    print("\nArquivos gerados:")
    print(f" - Consumo: {paths['reports_dir'] / 'report_consumo_wh.csv'}")
    if cafes_por_dia_csv:
        print(f" - Cafés por dia: {cafes_por_dia_csv}")
    print(f" - Distribuição comandos: {dist_csv}")
    if top_csv:
        print(f" - Top dispositivos: {top_csv}")
    if luzes_csv:
        print(f" - Tempo luzes: {luzes_csv}")
    return resumo_funcional


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        "Relatórios demonstrativos (relatorios_demo.py)",
        description="Gera arquivos de exemplo e imprime métricas derivadas dos logs.",
    )
    p.add_argument("--inicio", type=str, default=None, help="Data/hora inicial ISO (opcional)")
    p.add_argument("--fim", type=str, default=None, help="Data/hora final ISO (opcional)")
    p.add_argument("--json", action="store_true", help="Imprime resultado agregado em JSON")
    return p


def main():
    args = build_arg_parser().parse_args()
    executar_relatorios(args.inicio, args.fim, args.json)

#--------------------------------------------------------------------------------------------------
# Testes manuais
#--------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
