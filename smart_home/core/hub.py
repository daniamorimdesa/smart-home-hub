# smart_home/core/hub.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import json
from pathlib import Path

from smart_home.core.eventos import Evento, TipoEvento
from smart_home.core.observers import Observer
from smart_home.core.persistencia import carregar_config as _load_cfg, salvar_config as _save_cfg


from smart_home.dispositivos.porta import Porta
from smart_home.dispositivos.luz import Luz, CorLuz
from smart_home.dispositivos.tomada import Tomada
from smart_home.dispositivos.cafeteira import CafeteiraCapsulas
from smart_home.dispositivos.radio import Radio, EstacaoRadio
from smart_home.dispositivos.persiana import Persiana
from smart_home.core.dispositivos import DispositivoBase, TipoDeDispositivo

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
        antes = getattr(disp.estado, "name", str(disp.estado))
        disp.executar_comando(comando, **kwargs)
        depois = getattr(disp.estado, "name", str(disp.estado))
        self._emitir(Evento(TipoEvento.COMANDO_EXECUTADO, {
            "id": id, "comando": comando, "antes": antes, "depois": depois, **({"args": kwargs} if kwargs else {})
        }))

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
    def salvar_config(self, caminho: str) -> None:
        # espera um dict {id: dispositivo}
        _save_cfg(caminho, self.dispositivos)

    def carregar_config(self, caminho: str) -> None:
        # retorna um dict {id: dispositivo}
        self.dispositivos = _load_cfg(caminho, factory=self._criar_dispositivo)

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

