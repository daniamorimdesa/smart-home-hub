# smart_home/core/hub.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import json
from pathlib import Path

from smart_home.core.eventos import Evento, TipoEvento
from smart_home.core.observers import Observer
from smart_home.core.persistencia import carregar_config as _load_cfg, salvar_config as _save_cfg


from smart_home.dispositivos.porta import Porta, EstadoPorta
from smart_home.dispositivos.luz import Luz, CorLuz, EstadoLuz
from smart_home.dispositivos.tomada import Tomada, EstadoTomada
from smart_home.dispositivos.cafeteira import CafeteiraCapsulas, EstadoCafeteira
from smart_home.dispositivos.radio import Radio, EstacaoRadio, EstadoRadio
from smart_home.dispositivos.persiana import Persiana, EstadoPersiana
from smart_home.core.dispositivos import DispositivoBase, TipoDeDispositivo


def _json_default(o):
    # para Enums como EstadoX e TipoDeDispositivo
    try:
        return o.name
    except AttributeError:
        # fallback para qualquer outro objeto não serializável
        return str(o)

def _estado_str(estado) -> str:
    return getattr(estado, "name", str(estado))

# -------------------------
# Hub (camada de serviço)
# -------------------------
class Hub:
    def __init__(self) -> None:
        self.dispositivos: Dict[str, DispositivoBase] = {}
        self._observers: list[Observer] = []

    def registrar_observer(self, obs: Observer) -> None:
        self._observers.append(obs)

    def _emitir(self, evt: Evento) -> None:
        for obs in self._observers:
            try: obs.on_event(evt)
            except Exception: pass  # não derruba o hub
    # defaults
    def carregar_defaults(self) -> None:
        """Carrega uma configuração default, com alguns dispositivos."""
        self.dispositivos.clear()
        self.adicionar("porta", "porta_entrada", "Porta da Entrada")
        self.adicionar("luz", "luz_sala", "Luz da Sala", brilho=75, cor=CorLuz.QUENTE)
        self.adicionar("tomada", "tomada_tv", "Tomada da TV", potencia_w=150)
        self.adicionar("cafeteira", "cafeteira_cozinha", "Cafeteira da Cozinha")
        self.adicionar("radio", "radio_cozinha", "Rádio da Cozinha", volume=30, estacao=EstacaoRadio.MPB)
        self.adicionar("persiana", "persiana_quarto", "Persiana do Quarto", abertura=50)
        
        
    # CRUD
    def adicionar(self, tipo: str, id: str, nome: str, **attrs: Any) -> DispositivoBase:
        if id in self.dispositivos:
            from smart_home.core.erros import DispositivoJaExiste
            raise DispositivoJaExiste(f"Ja existe dispositivo com id '{id}'.")
        disp = self._criar_dispositivo(tipo, id, nome, attrs)
        disp.set_emissor(self._emitir)
        self.dispositivos[id] = disp
        self._emitir(Evento(TipoEvento.DISPOSITIVO_ADICIONADO, {"id": id, "tipo": tipo, "nome": nome}))
        return disp

    def remover(self, id: str) -> None:
        if id not in self.dispositivos:
            from smart_home.core.erros import DispositivoNaoEncontrado
            raise DispositivoNaoEncontrado(f"Dispositivo '{id}' nao encontrado.")
        tipo = self.dispositivos[id].tipo.value
        del self.dispositivos[id]
        self._emitir(Evento(TipoEvento.DISPOSITIVO_REMOVIDO, {"id": id, "tipo": tipo}))

    # Acoes
    def executar_comando(self, id: str, comando: str, **kwargs: Any) -> None:
        disp = self._exigir(id)
        disp.executar_comando(comando, **kwargs)


    def alterar_atributo(self, id: str, chave: str, valor: Any) -> None:
        disp = self._exigir(id)
        antigo = disp.atributos().get(chave)
        disp.alterar_atributo(chave, valor)
        self._emitir(Evento(TipoEvento.ATRIBUTO_ALTERADO, {
            "id": id, "atributo": chave, "antes": antigo, "depois": valor
        }))
        
    # ---------- Fabrica/Factory ----------
    def _criar_dispositivo(self, tipo: str, id: str, nome: str, attrs: Dict[str, Any]) -> DispositivoBase:
        t = tipo.strip().upper()
        if t == "PORTA":
            return Porta(id=id, nome=nome)
        if t == "LUZ":
            brilho_inicial = int(attrs.get("brilho", attrs.get("brilho_inicial", 0)))
            cor_val = attrs.get("cor", attrs.get("cor_inicial", CorLuz.NEUTRA))
            if isinstance(cor_val, str):
                cor_val = CorLuz[cor_val.strip().upper()]
            return Luz(id=id, nome=nome, brilho_inicial=brilho_inicial, cor_inicial=cor_val)
        if t == "TOMADA":
            pot = int(attrs.get("potencia_w", 0))
            return Tomada(id=id, nome=nome, potencia_w=pot)
        if t == "CAFETEIRA":
            return CafeteiraCapsulas(id=id, nome=nome)
        if t == "RADIO":
            vol = int(attrs.get("volume", attrs.get("volume_inicial", 0)))
            est = attrs.get("estacao", attrs.get("estacao_inicial", EstacaoRadio.MPB))
            if isinstance(est, str):
                est = EstacaoRadio[est.strip().upper()]
            return Radio(id=id, nome=nome, volume_inicial=vol, estacao_inicial=est)
        if t == "PERSIANA":
            ab = int(attrs.get("abertura", attrs.get("abertura_inicial", 0)))
            return Persiana(id=id, nome=nome, abertura_inicial=ab)
        raise ValueError(f"Tipo de dispositivo nao suportado: {tipo}")

    # ---------- Consultas ----------
    def listar(self) -> List[DispositivoBase]:
        return list(self.dispositivos.values())

    def obter(self, id: str) -> Optional[DispositivoBase]:
        return self.dispositivos.get(id)

    def _exigir(self, id: str) -> DispositivoBase:
        disp = self.obter(id)
        if not disp:
            from smart_home.core.erros import DispositivoNaoEncontrado
            raise DispositivoNaoEncontrado(f"Dispositivo '{id}' nao encontrado.")
        return disp

    # ---------- Persistência (wrappers para persistencia.py) ----------

    def _attrs_persistentes(self, disp) -> dict:
        tipo = disp.tipo.value
        base = disp.atributos()

        permitidos = {
            "PORTA": set(),
            "LUZ": {"brilho", "cor", "ultimo_brilho"},
            "TOMADA": {"potencia_w", "consumo_wh"},
            "CAFETEIRA": {"agua_ml", "capsulas", "ultimo_preparo"},
            "RADIO": {"volume", "estacao"},
            "PERSIANA": {"abertura"},
        }.get(tipo, set())

        # remove derivados comuns
        derivados = {"estado_nome", "consumo_wh_total", "ligada_desde"}
        return {k: v for k, v in base.items() if k in permitidos and k not in derivados}

    def salvar_config(self, caminho: str | Path) -> None:
        p = Path(caminho)
        p.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "dispositivos": [d.para_dict() for d in self.listar()]
        }

        # sempre escreve com UTF-8 e indentado
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            

    def carregar_config(self, caminho: str | Path) -> None:
        p = Path(caminho)
        if not p.exists():
            raise FileNotFoundError(f"Arquivo de config nao encontrado: {caminho}")

        data = json.loads(p.read_text(encoding="utf-8"))

        # suporta dois formatos:
        # A) {"dispositivos": [ {...}, {...} ]}
        # B) {"chave_ou_id": { "id": "...", "tipo": "...", ... }, ...}
        entries = []
        if isinstance(data, dict) and "dispositivos" in data and isinstance(data["dispositivos"], list):
            entries = data["dispositivos"]
        elif isinstance(data, dict):
            # dicionário mapeando chave->config
            for _, cfg in data.items():
                if isinstance(cfg, dict) and "id" in cfg and "tipo" in cfg:
                    entries.append(cfg)

        self.dispositivos.clear()

        for cfg in entries:
            tipo = str(cfg.get("tipo", "")).upper()
            id_  = cfg["id"]
            nome = cfg.get("nome", id_)
            estado_str = str(cfg.get("estado", "")).upper()
            attrs = cfg.get("atributos", {}) or {}

            # 1) criar
            disp = self._criar_dispositivo(tipo, id_, nome, attrs)

            # 2) aplicar atributos salvos (somente persistentes, com coerções)
            def _persistentes_por_tipo(tipo: str) -> set[str]:
                if tipo == "PORTA":
                    return set()
                if tipo == "LUZ":
                    return {"brilho", "cor", "ultimo_brilho"}
                if tipo == "TOMADA":
                    # _ligada_desde é interno; não persistir direto (ou parsear à parte)
                    return {"potencia_w", "consumo_wh"}
                if tipo == "CAFETEIRA":
                    # ajuste conforme seus campos reais
                    return {"agua_ml", "capsulas", "ultimo_preparo"}
                if tipo == "RADIO":
                    return {"volume", "estacao"}
                if tipo == "PERSIANA":
                    return {"abertura"}
                return set()

            # dentro do loop de cada cfg:
            permitidos = _persistentes_por_tipo(tipo)
            for k, v in attrs.items():
                if k not in permitidos:
                    continue
                try:
                    # coerções por tipo/campo
                    if tipo == "LUZ" and k == "cor" and isinstance(v, str):
                        from smart_home.dispositivos.luz import CorLuz
                        v = CorLuz[v.upper()]
                    if tipo == "RADIO" and k == "estacao" and isinstance(v, str):
                        from smart_home.dispositivos.radio import EstacaoRadio
                        v = EstacaoRadio[v.upper()]
                    if k in {"brilho", "potencia_w", "volume", "abertura", "agua_ml", "capsulas", "ultimo_brilho"} and isinstance(v, str):
                        v = int(v)
                    disp.alterar_atributo(k, v)
                except Exception:
                    pass  # ignora atributo inválido


            # 3) restaurar estado enum de forma segura
            try:
                if tipo == "PORTA":
                    disp.estado = EstadoPorta[estado_str] if estado_str else disp.estado
                elif tipo == "LUZ":
                    disp.estado = EstadoLuz[estado_str] if estado_str else disp.estado
                elif tipo == "TOMADA":
                    disp.estado = EstadoTomada[estado_str] if estado_str else disp.estado
                elif tipo == "CAFETEIRA":
                    disp.estado = EstadoCafeteira[estado_str] if estado_str else disp.estado
                elif tipo == "RADIO":
                    disp.estado = EstadoRadio[estado_str] if estado_str else disp.estado
                elif tipo == "PERSIANA":
                    disp.estado = EstadoPersiana[estado_str] if estado_str else disp.estado
            except Exception:
                # estado inválido no JSON: mantém o default da classe
                pass

            # 4) registrar no hub
            self.dispositivos[id_] = disp

    # ---------- Defaults ----------
    def carregar_defaults(self) -> None:
        """Carrega uma configuração default, com alguns dispositivos."""
        self.dispositivos.clear()
        # use tipo em MAIÚSCULAS, pois _criar_dispositivo faz t.upper()
        self.adicionar("PORTA", "porta_entrada", "Porta da Entrada")
        self.adicionar("LUZ", "luz_sala", "Luz da Sala", brilho=75, cor=CorLuz.QUENTE)
        self.adicionar("TOMADA", "tomada_tv", "Tomada da TV", potencia_w=150)
        self.adicionar("CAFETEIRA", "cafeteira_cozinha", "Cafeteira da Cozinha")
        self.adicionar("RADIO", "radio_cozinha", "Rádio da Cozinha", volume=30, estacao=EstacaoRadio.MPB)
        self.adicionar("PERSIANA", "persiana_quarto", "Persiana do Quarto", abertura=50)

