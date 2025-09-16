# smart_home/core/hub.py: gerenciamento dos dispositivos e observadores
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
#--------------------------------------------------------------------------------------------------
# HUB (CAMADA DE SERVIÇO) - GERENCIA DISPOSITIVOS, COMANDOS, ATRIBUTOS, ROTINAS E OBSERVERS
#--------------------------------------------------------------------------------------------------
class Hub:
    def __init__(self) -> None:
        self.dispositivos: Dict[str, DispositivoBase] = {}
        self._observers: list[Observer] = []
        self.rotinas: dict[str, list[dict]] = {}

    # injeta emissor em dispositivo recém criado/recuperado
    def _wire(self, disp: DispositivoBase) -> DispositivoBase:
        disp.set_emissor(lambda evt: self._emitir(evt))
        return disp

    def registrar_observer(self, obs: Observer) -> None:
        self._observers.append(obs)

    def _emitir(self, evt: Evento) -> None:
        for obs in self._observers:
            try: obs.on_event(evt)
            except Exception: pass  # não derruba o hub
    # defaults
    # (definição de carregar_defaults antiga removida - duplicada mais abaixo)
        
        
    # CRUD
    def adicionar(self, tipo: str, id: str, nome: str, **attrs: Any) -> DispositivoBase:
        if id in self.dispositivos:
            from smart_home.core.erros import DispositivoJaExiste
            raise DispositivoJaExiste(f"Ja existe dispositivo com id '{id}'.")
        disp = self._criar_dispositivo(tipo, id, nome, attrs)
        self._wire(disp)
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
        
        
        
    # ----------- executar rotina -----------
    def executar_rotina(self, nome: str) -> dict:
        passos = self.rotinas.get(nome)
        if not passos:
            from smart_home.core.erros import ErroDeValidacao
            raise ErroDeValidacao(f"Rotina '{nome}' nao encontrada.", detalhes={"nome": nome})

        resultados = []
        ok = 0
        for i, passo in enumerate(passos, 1):
            pid = passo.get("id")
            cmd = passo.get("comando")
            # aceita tanto 'argumentos' quanto legado 'args'
            args = passo.get("argumentos")
            if args is None:
                args = passo.get("args", {})
            args = args or {}
            try:
                disp = self._exigir(pid)
                antes = getattr(disp.estado, "name", str(disp.estado))
                disp.executar_comando(cmd, **args)
                depois = getattr(disp.estado, "name", str(disp.estado))
                resultados.append({"passo": i, "id": pid, "cmd": cmd, "ok": True, "antes": antes, "depois": depois})
                ok += 1
            except Exception as e:
                resultados.append({"passo": i, "id": pid, "cmd": cmd, "ok": False, "erro": str(e)})

        resumo = {"rotina": nome, "total": len(passos), "sucesso": ok, "falha": len(passos)-ok, "resultados": resultados}
        # emite um evento “macro” (útil p/ CSV geral)
        from smart_home.core.eventos import Evento, TipoEvento
        self._emitir(Evento(TipoEvento.ROTINA_EXECUTADA, resumo))
        return resumo

        
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

    # (_attrs_persistentes removido - não utilizado)

    def salvar_config(self, caminho: str | Path) -> None:
        p = Path(caminho)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "hub": {"nome": "Casa Inteligente", "versao": "1.0"},
            "dispositivos": [
                {
                    "id": d.id,
                    "tipo": d.tipo.value,
                    "nome": d.nome,
                    "estado": getattr(d.estado, "name", str(d.estado)),
                    "atributos": d.atributos(),
                } for d in self.listar()
            ],
            "rotinas": self.rotinas,
        }
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            

    def carregar_config(self, caminho: str | Path) -> None:
        p = Path(caminho)
        if not p.exists():
            raise FileNotFoundError(f"Arquivo de config nao encontrado: {caminho}")
        data = json.loads(p.read_text(encoding="utf-8"))

        # rotinas (normaliza "argumentos"/"args" permanecem como estão, sem validação extra)
        rots = data.get("rotinas", {})
        self.rotinas = {nome: list(lista) for nome, lista in rots.items() if isinstance(lista, list)} if isinstance(rots, dict) else {}

        entries: list[dict] = []
        if isinstance(data, dict) and isinstance(data.get("dispositivos"), list):
            entries = data["dispositivos"]
        elif isinstance(data, dict):
            for _, cfg in data.items():
                if isinstance(cfg, dict) and {"id", "tipo"}.issubset(cfg.keys()):
                    entries.append(cfg)

        self.dispositivos.clear()

        for cfg in entries:
            try:
                tipo = str(cfg.get("tipo", "")).upper()
                id_ = cfg["id"]
                nome = cfg.get("nome", id_)
                estado_str = str(cfg.get("estado", "")).upper()
                attrs = cfg.get("atributos", {}) or {}

                disp = self._criar_dispositivo(tipo, id_, nome, attrs)

                # aplicar atributos crus (validação em cada dispositivo)
                for k, v in attrs.items():
                    try:
                        # ignora chave legada 'historico' (antes era quantidade; na classe é lista)
                        if k == "historico":
                            continue
                        disp.alterar_atributo(k, v)
                    except Exception:
                        pass

                # restaurar estado enum
                try:
                    if tipo == "PORTA" and estado_str:
                        disp.estado = EstadoPorta.get(estado_str, disp.estado) if hasattr(EstadoPorta, 'get') else EstadoPorta[estado_str]
                    elif tipo == "LUZ" and estado_str:
                        disp.estado = EstadoLuz[estado_str]
                    elif tipo == "TOMADA" and estado_str:
                        disp.estado = EstadoTomada[estado_str]
                    elif tipo == "CAFETEIRA" and estado_str:
                        disp.estado = EstadoCafeteira[estado_str]
                    elif tipo == "RADIO" and estado_str:
                        disp.estado = EstadoRadio[estado_str]
                    elif tipo == "PERSIANA" and estado_str:
                        # abertura já aplicada via atributos; ainda assim tenta sincronizar enum
                        disp.estado = EstadoPersiana[estado_str]
                except Exception:
                    pass

                self._wire(disp)
                self.dispositivos[id_] = disp
            except Exception:
                continue

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

