# smart_home/core/persistencia.py: carregar/salvar config JSON
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from smart_home.dispositivos.porta import Porta
from smart_home.dispositivos.luz import Luz, CorLuz
from smart_home.dispositivos.tomada import Tomada
from smart_home.dispositivos.cafeteira import CafeteiraCapsulas
from smart_home.dispositivos.radio import Radio, EstacaoRadio
from smart_home.dispositivos.persiana import Persiana
from smart_home.core.dispositivos import TipoDeDispositivo


# -------------------------
# Defaults (para primeiro uso)
# -------------------------
def criar_dispositivos_default() -> Dict[str, Any]:
    return {
        "porta": Porta(id="porta_entrada", nome="Porta da Entrada"),
        "luz": Luz(id="luz_sala", nome="Luz da Sala"),
        "tomada": Tomada(id="tomada_bancada", nome="Tomada da Bancada", potencia_w=1000),
        "cafeteira": CafeteiraCapsulas(id="cafeteira", nome="Cafeteira da Cozinha"),
        "radio": Radio(id="radio_sala", nome="Rádio da Sala"),
        "persiana": Persiana(id="persiana_sala", nome="Persiana da Sala", abertura_inicial=0),
    }

def _estado_str(estado) -> str:
    return getattr(estado, "name", str(estado))

# -------------------------
# Salvar
# -------------------------
def salvar_config(path: Path, dispositivos: Dict[str, Any]) -> None:
    """
    Serializa os dispositivos (usando as 'chaves' do dicionário) num JSON simples.
    """
    data = {}
    for chave, d in dispositivos.items():
        data[chave] = {
            "id": d.id,
            "nome": d.nome,
            "tipo": d.tipo.value,
            "estado": _estado_str(d.estado),   # hoje só informativo; não reaplicamos no load
            "atributos": d.atributos(),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# -------------------------
# Carregar
# -------------------------
def carregar_config(path: Path) -> Dict[str, Any]:
    """
    Reconstrói o dicionário {chave: dispositivo} a partir do JSON.
    Se o arquivo não existir ou der erro, retorna os defaults.
    """
    if not path.exists():
        return criar_dispositivos_default()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return criar_dispositivos_default()

    dispositivos: Dict[str, Any] = {}

    for chave, cfg in data.items():
        tipo = (cfg.get("tipo") or "").upper()
        id_ = cfg.get("id", chave)
        nome = cfg.get("nome", chave)
        attrs = cfg.get("atributos", {}) or {}
        

        try:
            if tipo == TipoDeDispositivo.PORTA.value:
                disp = Porta(id=id_, nome=nome)

            elif tipo == TipoDeDispositivo.LUZ.value:
                brilho = int(attrs.get("brilho", 0))
                cor = attrs.get("cor", "NEUTRA")
                if isinstance(cor, str):
                    try:
                        cor = CorLuz[cor]
                    except Exception:
                        cor = CorLuz.NEUTRA
                disp = Luz(id=id_, nome=nome, brilho_inicial=brilho, cor_inicial=cor)

            elif tipo == TipoDeDispositivo.TOMADA.value:
                pot = int(attrs.get("potencia_w", 0))
                disp = Tomada(id=id_, nome=nome, potencia_w=pot)

            elif tipo == TipoDeDispositivo.CAFETEIRA.value:
                disp = CafeteiraCapsulas(id=id_, nome=nome)

            elif tipo == TipoDeDispositivo.RADIO.value:
                est = attrs.get("estacao", "MPB")
                if isinstance(est, str):
                    try:
                        est = EstacaoRadio[est]
                    except Exception:
                        est = EstacaoRadio.MPB
                vol = int(attrs.get("ultimo_volume", attrs.get("volume", 0)))
                disp = Radio(id=id_, nome=nome, volume_inicial=vol, estacao_inicial=est)

            elif tipo == TipoDeDispositivo.PERSIANA.value:
                ab = int(attrs.get("abertura", attrs.get("abertura_inicial", 0)))
                disp = Persiana(id=id_, nome=nome, abertura_inicial=ab)

            else:
                # tipo desconhecido: ignora entrada
                continue

            dispositivos[chave] = disp

        except Exception:
            # qualquer erro ao reconstruir esse item → pula e segue
            continue

    # se nada deu certo, volta pros defaults
    if not dispositivos:
        dispositivos = criar_dispositivos_default()

    return dispositivos
