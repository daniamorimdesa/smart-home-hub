"""Script dedicado: Distribuição de comandos executados por tipo de dispositivo.

Exemplo:
  python -m smart_home.core.report_dist_comandos_tipo \
      --events data/logs/events.csv --config data/config.json \
      --out data/reports/report_dist_comandos_tipo.csv
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import argparse
import json

from .relatorios import distribuicao_comandos_por_tipo, salvar_csv

def parse_args():
    p = argparse.ArgumentParser("Distribuição de comandos por tipo")
    p.add_argument("--events", type=Path, required=True, help="events.csv")
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

    rows = distribuicao_comandos_por_tipo(args.events, args.config, inicio, fim)

    if args.out:
        salvar_csv(args.out, ["tipo","qtd"], [{"tipo": t, "qtd": n} for t, n in rows])
        print(f"[OK] CSV salvo em {args.out}")

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for tipo, qtd in rows:
            print(f"{tipo}: {qtd}")

if __name__ == "__main__":
    main()
