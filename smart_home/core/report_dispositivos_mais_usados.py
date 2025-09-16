"""Script dedicado para gerar CSV de dispositivos mais usados.

Uso:
  python -m smart_home.core.report_dispositivos_mais_usados \
      --trans data/logs/transitions.csv \
      --events data/logs/events.csv \
      --out data/reports/report_top_dispositivos.csv \
      --inicio 2025-09-15T00:00:00 --fim 2025-09-15T23:59:59

Args:
  --trans   Caminho para transitions.csv
  --events  Caminho para events.csv
  --n       Quantidade de itens (default=10)
  --inicio  Datetime ISO inicial (opcional)
  --fim     Datetime ISO final (opcional)
  --out     Caminho do CSV de saída (opcional). Se omitido apenas imprime.
  --json    Imprime JSON em stdout em vez de formato simples.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json
import argparse

from .relatorios import dispositivos_mais_usados, salvar_csv

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("Top dispositivos mais usados")
    p.add_argument("--trans", type=Path, required=True, help="transitions.csv")
    p.add_argument("--events", type=Path, required=True, help="events.csv")
    p.add_argument("--n", type=int, default=10, help="Quantidade de itens (default=10)")
    p.add_argument("--inicio", type=str, default=None, help="Datetime ISO inicial (opcional)")
    p.add_argument("--fim", type=str, default=None, help="Datetime ISO final (opcional)")
    p.add_argument("--out", type=Path, default=None, help="Salvar CSV nesse caminho")
    p.add_argument("--json", action="store_true", help="Saída JSON")
    return p.parse_args()


def main():
    args = parse_args()
    inicio = datetime.fromisoformat(args.inicio) if args.inicio else None
    fim = datetime.fromisoformat(args.fim) if args.fim else None
    rows = dispositivos_mais_usados(args.trans, args.events, args.n, inicio, fim)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        salvar_csv(
            args.out,
            ["id_dispositivo", "qtd", "inicio_periodo", "fim_periodo"],
            [
                {
                    "id_dispositivo": dev_id,
                    "qtd": qtd,
                    "inicio_periodo": inicio.isoformat() if inicio else None,
                    "fim_periodo": fim.isoformat() if fim else None,
                }
                for dev_id, qtd in rows
            ],
        )
        print(f"[OK] CSV salvo em {args.out}")

    if args.json:
        print(json.dumps({"top": rows}, ensure_ascii=False, indent=2))
    else:
        for i, (dev_id, qtd) in enumerate(rows, start=1):
            print(f"{i:02d}. {dev_id} -> {qtd}")

if __name__ == "__main__":
    main()
