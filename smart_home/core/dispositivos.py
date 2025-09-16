# smart_home/core/dispositivos.py: class Dispositivo: base, tipos de dispositivo (Enum)
from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable

from smart_home.core.eventos import Evento, TipoEvento
#--------------------------------------------------------------------------------------------------
# TIPOS DE DISPOSITIVOS
#--------------------------------------------------------------------------------------------------
class TipoDeDispositivo(Enum):
    
    """Tipos de dispositivos suportados (valores usados no JSON)."""
    
    # básicos
    PORTA = "PORTA"
    LUZ = "LUZ"
    TOMADA = "TOMADA"
    
    # extras
    CAFETEIRA = "CAFETEIRA"
    RADIO = "RADIO"
    PERSIANA = "PERSIANA"

#--------------------------------------------------------------------------------------------------
# CLASSE BASE DE DISPOSITIVO
#--------------------------------------------------------------------------------------------------
@dataclass
class DispositivoBase(ABC):
    
    """Classe base abstrata para dispositivos do Smart Home.
    Cada dispositivo terá sua própria FSM (via `transitions`) e 
    atributos próprios.

    Atributos:
    - id: identificador único do dispositivo, ex.: luz_sala
    - nome: nome exibido na CLI
    - tipo: tipo do dispositivo (TipoDeDispositivo)
    - estado: estado atual (controlado pela FSM vinculada)
    - maquina: instância da máquina de estados (transitions.Machine)
    - _emissor: função callback para emitir eventos (injetado pelo Hub)
    """
    id: str
    nome: str
    tipo: TipoDeDispositivo
    estado: Any
    maquina: Any = field(default=None, repr=False, compare=False) # não aparece no repr/eq 
    # emissor de eventos (injetado pelo Hub)
    _emissor: Optional[Callable[[Evento], None]] = field(default=None, repr=False, compare=False)

    #----------------------------------------------------------------------------------------------
    # MÉTODOS ABSTRATOS - FORÇAM IMPLEMENTAÇÃO NAS SUBCLASSES
    #----------------------------------------------------------------------------------------------
    @abstractmethod
    def executar_comando(self, comando: str, /, **kwargs: Any) -> None:
        """Executa um comando (string) com argumentos opcionais."""
        pass

    @abstractmethod
    def atributos(self) -> Dict[str, Any]:
        """Retorna os atributos do dispositivo."""
        pass
    
    # ----------------------------------------------------------------------------------------------
    # EMISSÃO DE EVENTOS (Observer/Logger)
    #----------------------------------------------------------------------------------------------
    def set_emissor(self, emissor: Callable[[Evento], None]) -> None:
        """Define a função callback para emitir eventos (injetado pelo Hub)."""     
        self._emissor = emissor

    def _emitir(self, tipo: TipoEvento, payload: dict) -> None:
        """Emite um evento (se o emissor foi definido)."""
        if self._emissor:
            self._emissor(Evento(tipo, payload))

    #----------------------------------------------------------------------------------------------
    # MÉTODOS COMPORTAMENTAIS - PODEM SER SOBRESCRITOS NAS SUBCLASSES
    #----------------------------------------------------------------------------------------------

    def comandos_disponiveis(self) -> Dict[str, str]:
        """
        Opcional: lista de comandos suportados (nome -> descrição).
        """
        return {}

    def para_dict(self) -> Dict[str, Any]:
        """Serializa o dispositivo para JSON de configuração."""
        return {
            "id": self.id,
            "tipo": self.tipo.value,
            "nome": self.nome,
            "estado": self._estado_str(),
            "atributos": self.atributos(),
        }

    
    def alterar_atributo(self, chave: str, valor: Any) -> None:
        reservados = {"id", "nome", "tipo", "estado", "maquina", "atributos"}
        if chave in reservados:
            raise AttributeError(f"'{chave}' é reservado e não pode ser alterado.")

        atual = getattr(self, chave, None)
        if callable(atual):
            raise AttributeError(f"'{chave}' é um método/propriedade e não pode ser sobrescrito.")

        if hasattr(self, chave):
            setattr(self, chave, valor)
        else:
            raise AttributeError(f"Atributo '{chave}' não existe em {self.id}")


    def detalhes_str(self) -> str:
        """Retorna uma string formatada para exibir na CLI (listar dispositivos).

        Returns:
            str: String formatada com id, tipo e estado.
        """
        return f"{self.id} | {self.tipo.name} | {self._estado_str()}"

    # ------------------------------------------------------------------
    # HELPERs PARA OBSERVER/LOGGER (PAYLOADS PADRÕES)
    # ------------------------------------------------------------------
    def evento_transicao(self, evento: str, origem: str, destino: str,
                         extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Monta payload padrão de transição de estado.
        """
        dados = {
            "id": self.id,
            "tipo": self.tipo.value,
            "evento": evento,
            "antes": origem,
            "depois": destino,
        }
        if extra:
            dados.update(extra)
        return dados

    def evento_comando(self, comando: str, antes: str, depois: str,
                       extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Monta payload padrão para comando executado.
        """
        dados = {
            "id": self.id,
            "comando": comando,
            "antes": antes,
            "depois": depois,
        }
        if extra:
            dados.update(extra)
        return dados
    
    # -------------------------------------------------------------------------
    # HELPERS INTERNOS
    # -------------------------------------------------------------------------
    def _estado_str(self) -> str:
        """Converte `estado` (Enum ou str) para str."""
        try:
            return self.estado.name  # se for Enum
        except AttributeError:
            return str(self.estado)