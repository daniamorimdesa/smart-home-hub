# dispositivos.py: class Dispositivo

from __future__ import annotations       # para hints de tipo auto-referenciados 
from abc import ABC, abstractmethod      # para classe base abstrata
from enum import Enum                    # para enumerações
from dataclasses import dataclass        # para dataclass
from typing import Any, Dict, Optional   # para hints de tipo

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
    PROJETOR = "PROJETOR"         

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
    """
    id: str
    nome: str
    tipo: TipoDeDispositivo
    estado: Any
    maquina: Any = None

    #----------------------------------------------------------------------------------------------
    # MÉTODOS ABSTRATOS - FORÇAM IMPLEMENTAÇÃO NAS SUBCLASSES
    #----------------------------------------------------------------------------------------------
    @abstractmethod
    def executar_comando(self, comando: str, /, **kwargs: Any) -> None:
        """
        Executa um comando específico do dispositivo.
        Cada subclasse deve mapear comandos para triggers/métodos da FSM.
        """
        raise NotImplementedError  

    @abstractmethod
    def atributos(self) -> Dict[str, Any]:
        """
        Retorna os atributos relevantes do dispositivo
        (ex.: brilho, cor, nível de água, volume).
        """
        raise NotImplementedError 
    
    
    #----------------------------------------------------------------------------------------------
    # Hooks opcionais (o Hub pode chamá-los ao ligar/desligar o sistema)
    # NÃO são abstratos — dispositivos podem ignorá-los.
    #----------------------------------------------------------------------------------------------
    def ao_ligar_sistema(self) -> None:
        """Chamado pelo Hub quando o sistema é ligado. Subclasses podem sobrescrever."""
        return
    #------------------------------------------------------------------
    def ao_desligar_sistema(self) -> None:
        """Chamado pelo Hub quando o sistema é desligado. Subclasses podem sobrescrever."""
        return

    #----------------------------------------------------------------------------------------------
    # MÉTODOS COMPORTAMENTAIS - PODEM SER SOBRESCRITOS NAS SUBCLASSES
    #----------------------------------------------------------------------------------------------

    def comandos_disponiveis(self) -> Dict[str, str]:
        """
        Opcional: lista de comandos suportados (nome -> descrição).
        Útil para a CLI mostrar ajuda.
        """
        return {}

    def para_dict(self) -> Dict[str, Any]:
        """
        Serializa o dispositivo em dicionário (compatível com JSON de config).
        """
        return {
            "id": self.id,
            "tipo": self.tipo.value,
            "nome": self.nome,
            "estado": self.estado,
            "atributos": self.atributos(),
        }

    def alterar_atributo(self, chave: str, valor: Any) -> None:
        """
        Atualiza dinamicamente um atributo.
        Subclasses podem sobrescrever para validações mais específicas.
        """
        if hasattr(self, chave):
            setattr(self, chave, valor)
        else:
            raise AttributeError(f"Atributo '{chave}' não existe em {self.id}")

    def detalhes_str(self) -> str:
        """
        Retorna uma string formatada para exibir na CLI (listar dispositivos).
        """
        return f"{self.id} | {self.tipo.name} | {self.estado}"

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
        """Converte `estado` (string ou Enum) para string para exibição/JSON."""
        try:
            # Enum -> usa o nome 
            return self.estado.name  # type: ignore[attr-defined]
        except AttributeError:
            # já é string
            return str(self.estado)