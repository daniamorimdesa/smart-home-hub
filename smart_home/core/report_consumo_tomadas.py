"""Script dedicado: Consumo por tomada (Wh) a partir de transitions.csv + config.json.

Exemplo:
  python -m smart_home.core.report_consumo_tomadas \
      --trans data/logs/transitions.csv \
      --config data/config.json \
      --out data/reports/report_consumo_wh.csv \
      --inicio 2025-09-15T00:00:00 --fim 2025-09-15T23:59:59
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import argparse
import json

from .relatorios import consumo_por_tomada, salvar_csv

def parse_args():
    p = argparse.ArgumentParser("Consumo por tomada (Wh)")
    p.add_argument("--trans", type=Path, required=True, help="transitions.csv")
    p.add_argument("--config", type=Path, required=True, help="config.json")
    p.add_argument("--inicio", type=str, default=None, help="Datetime ISO inicial (opcional)")
    p.add_argument("--fim", type=str, default=None, help="Datetime ISO final (opcional)")
    p.add_argument("--out", type=Path, default=None, help="Salvar CSV nesse caminho")
    p.add_argument("--json", action="store_true", help="Saída JSON em stdout")
    p.add_argument("--total", action="store_true", help="Incluir linha agregada __TOTAL__")
    return p.parse_args()

def main():
    args = parse_args()
    inicio = datetime.fromisoformat(args.inicio) if args.inicio else None
    fim = datetime.fromisoformat(args.fim) if args.fim else None

    rows = consumo_por_tomada(args.trans, args.config, inicio, fim, incluir_total=args.total)

    if args.out:
        salvar_csv(
            args.out,
            ["id_dispositivo","potencia_w","horas_ligada","total_wh","inicio_periodo","fim_periodo"],
            rows,
        )
        print(f"[OK] CSV salvo em {args.out}")

    if args.json:
        import json
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r['id_dispositivo']}: {r['total_wh']} Wh (horas={r['horas_ligada']})")

if __name__ == "__main__":
    main()
