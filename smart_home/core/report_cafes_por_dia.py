"""Script dedicado: Cafés preparados por dia.

Exemplo:
  python -m smart_home.core.report_cafes_por_dia \
      --trans data/logs/transitions.csv \
      --out data/reports/report_cafes_por_dia.csv
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import argparse
import json

from .relatorios import cafes_por_dia, salvar_csv

def parse_args():
    p = argparse.ArgumentParser("Cafés por dia")
    p.add_argument("--trans", type=Path, required=True, help="transitions.csv")
    p.add_argument("--inicio", type=str, default=None, help="Datetime ISO inicial (opcional)")
    p.add_argument("--fim", type=str, default=None, help="Datetime ISO final (opcional)")
    p.add_argument("--out", type=Path, default=None, help="Salvar CSV nesse caminho")
    p.add_argument("--json", action="store_true", help="Saída JSON em stdout")
    return p.parse_args()

def main():
    args = parse_args()
    inicio = datetime.fromisoformat(args.inicio) if args.inicio else None
    fim = datetime.fromisoformat(args.fim) if args.fim else None

    rows = cafes_por_dia(args.trans, inicio, fim)

    if args.out:
        salvar_csv(args.out, ["data","preparos_no_dia"], rows)
        print(f"[OK] CSV salvo em {args.out}")

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r['data']}: {r['preparos_no_dia']}")

if __name__ == "__main__":
    main()
