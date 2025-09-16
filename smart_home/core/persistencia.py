"""Persistência de configuração em JSON.

Este módulo agora centraliza a lógica de salvar/carregar a configuração do Hub
em JSON. Mantém compatibilidade com o formato legado (dicionário simples onde
cada chave era um dispositivo) por meio de funções *_legacy.

Formatos suportados:
1. Formato atual (hub):
{
    "hub": {"nome": "Casa Inteligente", "versao": "1.0"},
    "dispositivos": [
         {"id": "luz_sala", "tipo": "LUZ", "nome": "Luz da Sala", "estado": "DESLIGADA", "atributos": {...}},
         ...
    ],
    "rotinas": { "rotina_manha": [ {"id": "luz_sala", "comando": "ligar"}, ... ] }
}

2. Formato legado:
{
    "luz": {"id": "luz_sala", "tipo": "LUZ", "estado": "DESLIGADA", "atributos": {...}},
    "porta": { ... }
}

Ao carregar, detectamos automaticamente o formato. Ao salvar, usamos sempre o
formato novo.

Funções principais expostas:
 - salvar_config_hub(path, hub)
 - carregar_config_hub(path) -> dict {"dispositivos": {id: disp}, "rotinas": {...}}

As antigas salvar_config/carregar_config foram renomeadas para preservar
compatibilidade: salvar_config_legacy / carregar_config_legacy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Tuple

from smart_home.dispositivos.porta import Porta
from smart_home.dispositivos.luz import Luz, CorLuz
from smart_home.dispositivos.tomada import Tomada
from smart_home.dispositivos.cafeteira import CafeteiraCapsulas
from smart_home.dispositivos.radio import Radio, EstacaoRadio
from smart_home.dispositivos.persiana import Persiana
from smart_home.core.dispositivos import TipoDeDispositivo, DispositivoBase


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
def salvar_config_legacy(path: Path, dispositivos: Dict[str, Any]) -> None:
    """(LEGADO) Salva configuração no formato antigo.

    Formato: {"chave": {id, nome, tipo, estado, atributos}, ...}
    Preferir `salvar_config_hub` para novas implementações.
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
def carregar_config_legacy(path: Path) -> Dict[str, Any]:
    """(LEGADO) Carrega formato antigo e retorna dict de dispositivos.

    Usado como fallback quando formato novo não é detectado. Em caso de erro
    retorna defaults.
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

# ---------------------------------------------------------------------------
# Novo formato (Hub) - dispositivos (lista) + rotinas + metadados hub
# ---------------------------------------------------------------------------

def _dispositivo_para_dict(d: DispositivoBase) -> dict:
    return {
        "id": d.id,
        "tipo": d.tipo.value,
        "nome": d.nome,
        "estado": getattr(d.estado, "name", str(d.estado)),
        "atributos": d.atributos(),
    }

def salvar_config_hub(path: Path, hub) -> None:
    """Salva configuração completa do hub no formato atual.

    Args:
        path: Caminho destino.
        hub: Instância de Hub (duck-typed: precisa de listar() e rotinas).
    """
    data = {
        "hub": {"nome": "Casa Inteligente", "versao": "1.0"},
        "dispositivos": [_dispositivo_para_dict(d) for d in hub.listar()],
        "rotinas": hub.rotinas,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _instanciar_dispositivo(tipo: str, cfg: dict) -> DispositivoBase | None:
    tipo_up = (tipo or "").upper()
    id_ = cfg.get("id")
    nome = cfg.get("nome", id_)
    attrs = cfg.get("atributos", {}) or {}
    try:
        if tipo_up == "PORTA":
            return Porta(id=id_, nome=nome)
        if tipo_up == "LUZ":
            brilho = int(attrs.get("brilho", attrs.get("brilho_inicial", 0)))
            cor = attrs.get("cor", attrs.get("cor_inicial", CorLuz.NEUTRA))
            if isinstance(cor, str):
                try:
                    cor = CorLuz[cor.strip().upper()]
                except Exception:
                    cor = CorLuz.NEUTRA
            return Luz(id=id_, nome=nome, brilho_inicial=brilho, cor_inicial=cor)
        if tipo_up == "TOMADA":
            pot = int(attrs.get("potencia_w", 0))
            return Tomada(id=id_, nome=nome, potencia_w=pot)
        if tipo_up == "CAFETEIRA":
            return CafeteiraCapsulas(id=id_, nome=nome)
        if tipo_up == "RADIO":
            vol = int(attrs.get("volume", attrs.get("volume_inicial", 0)))
            est = attrs.get("estacao", attrs.get("estacao_inicial", EstacaoRadio.MPB))
            if isinstance(est, str):
                try:
                    est = EstacaoRadio[est.strip().upper()]
                except Exception:
                    est = EstacaoRadio.MPB
            return Radio(id=id_, nome=nome, volume_inicial=vol, estacao_inicial=est)
        if tipo_up == "PERSIANA":
            ab = int(attrs.get("abertura", attrs.get("abertura_inicial", 0)))
            return Persiana(id=id_, nome=nome, abertura_inicial=ab)
    except Exception:
        return None
    return None


def carregar_config_hub(path: Path) -> Dict[str, Any]:
    """Carrega configuração no formato atual ou legado.

    Retorna dict:
      {
        "dispositivos": {id: instancia},
        "rotinas": {nome: list[passos]}
      }
    """
    if not path.exists():
        return {"dispositivos": carregar_config_legacy(path), "rotinas": {}}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"dispositivos": criar_dispositivos_default(), "rotinas": {}}

    # Detectar formato: se tiver chave "dispositivos" lista -> novo formato
    if isinstance(data, dict) and isinstance(data.get("dispositivos"), list):
        dispositivos: Dict[str, DispositivoBase] = {}
        entries = data.get("dispositivos", [])
        for cfg in entries:
            if not isinstance(cfg, dict):
                continue
            tipo = cfg.get("tipo")
            disp = _instanciar_dispositivo(tipo, cfg)
            if not disp:
                continue
            # aplicar atributos crus
            attrs = cfg.get("atributos", {}) or {}
            for k, v in attrs.items():
                try:
                    if k == "historico":
                        continue
                    disp.alterar_atributo(k, v)
                except Exception:
                    pass
            dispositivos[disp.id] = disp
        rotinas = data.get("rotinas", {})
        if not isinstance(rotinas, dict):
            rotinas = {}
        # filtrar rotinas para listas
        rotinas = {k: list(v) for k, v in rotinas.items() if isinstance(v, list)}
        return {"dispositivos": dispositivos, "rotinas": rotinas}

    # Caso contrário, tratar como legado
    return {"dispositivos": carregar_config_legacy(path), "rotinas": {}}
