# smart_home/core/persistencia.py: salvar e carregar configuração do hub em JSON
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
from smart_home.core.erros import ConfigInvalida
#--------------------------------------------------------------------------------------------------
# DEFAULTS DE DISPOSITIVOS (USADOS SE NÃO HOUVER ARQUIVO DE CONFIGURAÇÃO CONFIG.JSON)
#--------------------------------------------------------------------------------------------------
def criar_dispositivos_default() -> Dict[str, Any]:
    return {
        "porta_entrada": Porta(id="porta_entrada", nome="Porta da Entrada"),
        "luz_sala": Luz(id="luz_sala", nome="Luz da Sala", brilho_inicial=40, cor_inicial=CorLuz.QUENTE),
        "tomada_tv": Tomada(id="tomada_tv", nome="Tomada da TV", potencia_w=150),
        "cafeteira_cozinha": CafeteiraCapsulas(id="cafeteira_cozinha", nome="Cafeteira da Cozinha"),
        "radio_cozinha": Radio(id="radio_cozinha", nome="Rádio da Cozinha", volume_inicial=50, estacao_inicial="LOFI"),
        "persiana_quarto": Persiana(id="persiana_quarto", nome="Persiana do Quarto", abertura_inicial=0),
        "luz_cozinha": Luz(id="luz_cozinha", nome="Luz da Cozinha", brilho_inicial=100, cor_inicial=CorLuz.NEUTRA),
        "tomada_cozinha": Tomada(id="tomada_cozinha", nome="Tomada da Cozinha", potencia_w=500),
    }

def _estado_str(estado) -> str:
    """ Retorna representação string do estado (enum ou outro).
    Usado para salvar estado em formato legível. """
    return getattr(estado, "name", str(estado))


#--------------------------------------------------------------------------------------------------
# FUNÇÕES PARA SALVAR E CARREGAR CONFIGURAÇÃO DO HUB EM JSON 
#--------------------------------------------------------------------------------------------------

def _dispositivo_para_dict(d: DispositivoBase) -> dict:
    """ Converte um dispositivo em dict serializável para JSON.
    Inclui somente atributos "essenciais" (id, tipo, nome, estado, atributos).
    """
    return {
        "id": d.id,
        "tipo": d.tipo.value,
        "nome": d.nome,
        "estado": getattr(d.estado, "name", str(d.estado)),
        "atributos": d.atributos(),
    }

def salvar_config_hub(path: Path, hub) -> None:
    """Salva configuração completa do hub.

    Args:
        path: Caminho destino.
        hub: Instância de Hub (duck-typed: precisa de listar() e rotinas).
    """
    # criar dict de configuração
    data = {
        "hub": {"nome": "Casa Inteligente", "versao": "1.0"},
        "dispositivos": [_dispositivo_para_dict(d) for d in hub.listar()], # lista de dicts de dispositivos 
        "rotinas": hub.rotinas, # dict de rotinas
    }
    # garantir que o diretório existe
    path.parent.mkdir(parents=True, exist_ok=True) 
    # salvar em JSON a configuração
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8") 


def _instanciar_dispositivo(tipo: str, cfg: dict) -> DispositivoBase | None:
    """Instancia um dispositivo a partir de configuração em dict lida do arquivo.
    Retorna None se não conseguir instanciar (tipo inválido ou erro).
    """
    tipo_up = (tipo or "").upper()              # normaliza tipo
    id_ = cfg.get("id")                         # id é obrigatório
    nome = cfg.get("nome", id_)                 # nome opcional, default = id
    attrs = cfg.get("atributos", {}) or {}      # atributos opcionais
    
    # validação mínima
    if not id_:
        raise ConfigInvalida("Dispositivo sem 'id' na configuração.", detalhes={"id": id_, "tipo": tipo_up})
    
    # tentar instanciar conforme tipo
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
    except Exception as e:
        # Propaga como ConfigInvalida para tratamento no loader
        raise ConfigInvalida(
            f"Erro instanciando dispositivo '{id_}' do tipo '{tipo_up}': {e}",
            detalhes={"id": id_, "tipo": tipo_up, "erro": str(e)}
        )
    return None


def carregar_config_hub(path: Path) -> Dict[str, Any]:
    """Carrega configuração no formato atual ou legado.

    Retorna dict:
      {
        "dispositivos": {id: instancia},
        "rotinas": {nome: list[passos]}
      }
    """
    if not path.exists(): # se o arquivo não existe: usar defaults
        return {"dispositivos": criar_dispositivos_default(), "rotinas": {}}

    try: # tentar ler JSON
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"dispositivos": criar_dispositivos_default(), "rotinas": {}}

    if isinstance(data, dict) and isinstance(data.get("dispositivos"), list): 
        dispositivos: Dict[str, DispositivoBase] = {}
        entries = data.get("dispositivos", [])
        for cfg in entries:
            if not isinstance(cfg, dict):
                continue
            tipo = cfg.get("tipo")
            try:
                disp = _instanciar_dispositivo(tipo, cfg)
            except ConfigInvalida as e:
                # ignorar entrada inválida mantendo comportamento tolerante
                try:
                    ident = cfg.get("id")
                    info = f"id={ident}, tipo={tipo}"
                    det = getattr(e, "detalhes", None)
                    if det:
                        info += f", detalhes={det}"
                    print(f"[persistencia] Config inválida ignorada: {info} — {e}")
                except Exception:
                    pass
                continue
            if not disp:
                continue
            # aplicar atributos extras (se houver)
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

    # caso contrário, formato inválido/desconhecido: usar defaults
    return {"dispositivos": criar_dispositivos_default(), "rotinas": {}}
