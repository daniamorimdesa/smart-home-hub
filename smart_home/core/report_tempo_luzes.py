"""Script dedicado: Tempo total que cada luz permaneceu ligada.

Exemplo:
  python -m smart_home.core.report_tempo_luzes \
      --trans data/logs/transitions.csv \
      --config data/config.json \
      --out data/reports/report_tempo_luzes.csv
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import argparse
import json

from .relatorios import tempo_total_luzes_ligadas, salvar_csv

def parse_args():
    p = argparse.ArgumentParser("Tempo total luzes ligadas")
    p.add_argument("--trans", type=Path, required=True, help="transitions.csv")
    p.add_argument("--config", type=Path, required=True, help="config.json")
    p.add_argument("--inicio", type=str, default=None, help="Datetime ISO inicial (opcional)")
    p.add_argument("--fim", type=str, default=None, help="Datetime ISO final (opcional)")
    p.add_argument("--out", type=Path, default=None, help="Salvar CSV nesse caminho")
    p.add_argument("--json", action="store_true", help="Saída JSON em stdout")
    return p.parse_args()

def main():
    args = parse_args()
    inicio = datetime.fromisoformat(args.inicio) if args.inicio else None
    fim = datetime.fromisoformat(args.fim) if args.fim else None

    rows = tempo_total_luzes_ligadas(args.trans, args.config, inicio, fim)

    if args.out:
        salvar_csv(
            args.out,
            ["id_dispositivo","segundos_ligada","hhmmss"],
            rows,
        )
        print(f"[OK] CSV salvo em {args.out}")

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r['id_dispositivo']}: {r['hhmmss']} ({r['segundos_ligada']}s)")

if __name__ == "__main__":
    main()
