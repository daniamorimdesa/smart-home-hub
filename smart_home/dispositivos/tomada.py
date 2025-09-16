# smart_home/dispositivos/tomada.py : implementação da classe Tomada com FSM.
from enum import Enum, auto
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from transitions import Machine, MachineError
from smart_home.core.dispositivos import DispositivoBase, TipoDeDispositivo
from smart_home.core.eventos import TipoEvento
from smart_home.core.erros import ComandoInvalido, AtributoInvalido
#--------------------------------------------------------------------------------------------------------------
# ESTADOS DA TOMADA
#--------------------------------------------------------------------------------------------------------------
class EstadoTomada(Enum):
    DESLIGADA = auto()  # off
    LIGADA = auto()     # on
#--------------------------------------------------------------------------------------------------------------
# MÉTODO AUXILIAR PARA NOMES DE ESTADO
#--------------------------------------------------------------------------------------------------------------
def _nome_estado(x):
    """Converte estado (Enum ou str) para str."""
    return x.name if hasattr(x, "name") else str(x)
#--------------------------------------------------------------------------------------------------------------
# CLASSE TOMADA
#--------------------------------------------------------------------------------------------------------------
class Tomada(DispositivoBase):
    """
    Tomada com FSM gerenciada pela biblioteca `transitions`
    Estados: DESLIGADA (off), LIGADA (on)
    Eventos/transições:
    - ligar: DESLIGADA -> LIGADA
    - desligar: LIGADA -> DESLIGADA
    Atributos / métricas:
    - potencia_w: int >= 0 (validado).
    - consumo_wh: acumulado com base nos intervalos ligados:
      consumo_wh (float acumulado)
      
      
    """
    def __init__(self, id: str, nome: str, *, potencia_w: int):
        super().__init__(id=id, nome=nome, tipo=TipoDeDispositivo.TOMADA, estado=EstadoTomada.DESLIGADA)
        
       # validar potência inicial
        try:
            potencia = int(potencia_w)
        except Exception:
            raise AtributoInvalido("potencia_w deve ser inteiro (≥ 0).", detalhes={"atributo": "potencia_w", "valor": potencia_w})
        if potencia < 0:
            raise AtributoInvalido("potencia_w deve ser ≥ 0.", detalhes={"atributo": "potencia_w", "valor": potencia})
        self._potencia_w: int = potencia
        
        # atributos de consumo
        self.consumo_wh: float = 0.0
        self._ligada_desde: Optional[datetime] = None
 
 
        # estados possíveis e transições
        estados = [EstadoTomada.DESLIGADA, EstadoTomada.LIGADA]
        transicoes = [
            # transições válidas
            {
                "trigger": "ligar", 
                "source": EstadoTomada.DESLIGADA, 
                "dest": EstadoTomada.LIGADA,
                "before": "_marcar_inicio",               # marca o início do período ligado
                "after": "_apos_comando"},                # log após o comando
            {
                "trigger": "desligar",
                "source": EstadoTomada.LIGADA,
                "dest": EstadoTomada.DESLIGADA,
                "before": "_agregar_consumo_e_limpar",    # agrega consumo e limpa início
                "after": "_apos_comando"                  # log após o comando
            }, 
            # transições inválidas
            {
                "trigger": "ligar", 
                "source": EstadoTomada.LIGADA, 
                "dest": EstadoTomada.LIGADA,
                "after": "_comando_bloqueado"             # log após o comando inválido
            },
            {
                "trigger": "desligar",
                "source": EstadoTomada.DESLIGADA,
                "dest": EstadoTomada.DESLIGADA,
                "after": "_comando_bloqueado"             # log após o comando inválido
            },
        ]

        # criar a máquina
        self.maquina = Machine(
            model=self,
            states=estados,
            transitions=transicoes,
            initial=EstadoTomada.DESLIGADA,
            model_attribute="estado",
            send_event=True,
            after_state_change=self._apos_transicao,
        )
    #--------------------------------------------------------------------------------------------------------------
    # MÉTODO DE LEITURA DO ATRIBUTO potencia_w
    #--------------------------------------------------------------------------------------------------------------    
    @property
    def potencia_w(self) -> int:
        return self._potencia_w
    #--------------------------------------------------------------------------------------------------------------
    # MÉTODOS ABSTRATOS IMPLEMENTADOS
    #--------------------------------------------------------------------------------------------------------------   
    def executar_comando(self, comando: str, /, **kwargs: Any) -> None:
        """
        Comandos suportados:
        - "ligar": liga a tomada (se já ligada, comando é bloqueado)
        - "desligar": desliga a tomada (se já desligada, comando é bloqueado)
        """
        mapa = {
            "ligar": self.ligar,
            "desligar": self.desligar
        }
        
        if comando not in mapa:
            raise ComandoInvalido(f"Comando '{comando}' não suportado para tomada '{self.id}'.", detalhes={"id": self.id, "comando": comando})
        
        try:
            mapa[comando](**kwargs) # chamar o método da FSM
            
        except MachineError as e:
            # comando inválido para o estado atual
            payload = self.evento_comando(
                comando=comando, antes=_nome_estado(self.estado), depois=_nome_estado(self.estado),
                extra={"bloqueado": True, "motivo": str(e)}
            )
            print("[COMANDO-BLOQUEADO]", payload)
            self._emitir(TipoEvento.COMANDO_EXECUTADO, payload)  # emitir evento ao hub
    
    def atributos(self) -> Dict[str, Any]:
        """Retorna os atributos da tomada.

        Returns:
            Dict[str, Any]: Atributos da tomada.
        """
        return {
            "potencia_w": self.potencia_w,
            "consumo_wh": round(self.consumo_wh, 4),                # consumo acumulado até o último desligamento 
            "consumo_wh_total": round(self.consumo_wh_total(), 4),  # consumo total até o momento (inclui período atual se ligada)
            "estado_nome": _nome_estado(self.estado),             
            # converte para str no padrão ISO(facilitar JSON e leitura)
            "ligada_desde":self._ligada_desde.strftime("%d/%m/%Y %H:%M:%S") if self._ligada_desde else None,
        }
        
    def comandos_disponiveis(self) -> Dict[str, str]:
        """Retorna os comandos disponíveis para a tomada.

        Returns:
            Dict[str, str]: Mapeamento de comandos para suas descrições.
        """
        return {
            "ligar": "DESLIGADA → LIGADA (inicia medição de consumo)",
            "desligar": "LIGADA → DESLIGADA (agrega consumo do intervalo)",
        }
        
    #--------------------------------------------------------------------------------------------------------------
    # MÉTODOS PARA CÁLCULO DE CONSUMO E MARCAÇÃO DE PERÍODOS DE TEMPO
    #--------------------------------------------------------------------------------------------------------------
    def _marcar_inicio(self, event) -> None:
        """Marca o início do período em que a tomada foi ligada."""
        self._ligada_desde = datetime.now()

    """ Métodos auxiliares
    _agregar_consumo_e_limpar: atualiza o consumo acumulado e limpa o tempo
    quando a tomada é desligada.
    
    consumo_wh_total: retorna o consumo total até o momento, incluindo o período 
    atual se a tomada estiver ligada, mas não altera o estado interno."""
    
    def _agregar_consumo_e_limpar(self, event) -> None:
        if self._ligada_desde is not None:  # se estava ligada
            agora = datetime.now()          # momento atual
            # calcular o tempo decorrido em horas
            delta_h = (agora - self._ligada_desde).total_seconds() / 3600.0
            
            # agregar consumo (potência * tempo)
            if delta_h > 0:
                self.consumo_wh += self.potencia_w * delta_h # consumo em Wh(watt-hora)
        self._ligada_desde = None                            # limpar a marcação
    
    def consumo_wh_total(self) -> float:
        total = self.consumo_wh
        # se estiver ligada, agrega o consumo desde que foi ligada
        if self.estado == EstadoTomada.LIGADA and self._ligada_desde is not None:
            # calcular o tempo decorrido em horas
            delta_h = (datetime.now() - self._ligada_desde).total_seconds() / 3600.0
            # agregar consumo (potência * tempo)
            if delta_h > 0:
                total += self.potencia_w * delta_h # consumo em Wh(watt-hora)
        return total 
    #--------------------------------------------------------------------------------------------------------------
    # CALLBACKS/ LOGGING HELPERS
    #--------------------------------------------------------------------------------------------------------------
    def _comando_bloqueado(self, event) -> None:
        """Callback chamado quando um comando é bloqueado.

        Args:
            event (Event): O evento que disparou o bloqueio do comando.
        """
        payload = self.evento_comando(
            comando=event.event.name,
            antes=_nome_estado(event.transition.source),
            depois=_nome_estado(event.transition.dest),
            extra={"bloqueado": True, "motivo": "transicao_redundante"},
        )
        print("[COMANDO-BLOQUEADO]", payload)
        self._emitir(TipoEvento.COMANDO_EXECUTADO, payload)  # emitir evento ao hub

    def _apos_transicao(self, event):
        """Callback chamado após uma transição de estado.

        Args:
            event (Event): O evento que disparou a transição.

        Returns:
            None
        """
        src = _nome_estado(event.transition.source)
        dst = _nome_estado(event.transition.dest)
        
        if src == dst:
            return  # oculta self-loops
        
        payload = self.evento_transicao(evento=event.event.name, origem=src, destino=dst)
        print("[TRANSIÇÃO]", payload) 
        self._emitir(TipoEvento.TRANSICAO_ESTADO, payload) # emitir evento ao hub
        
    def _apos_comando(self, event):
        """Callback chamado após a execução de um comando.

        Args:
            event (Event): O evento que disparou a execução do comando.
        """
        payload = self.evento_comando(
            comando=event.event.name,
            antes=_nome_estado(event.transition.source),
            depois=_nome_estado(event.transition.dest),
        )
        print("[COMANDO]", payload)
        self._emitir(TipoEvento.COMANDO_EXECUTADO, payload)  # emitir evento ao hub
        
#--------------------------------------------------------------------------------------------------------------
# Teste de uso da classe Tomada
#--------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    tomada = Tomada(id="tomada_bancada", nome="Tomada da Bancada", potencia_w=1000)
    print("Inicial:", tomada.estado.name, "| potencia_w:", tomada.potencia_w, "| consumo_wh:", tomada.consumo_wh)

    # ligar “2h atrás” (simulação)
    tomada.executar_comando("ligar")
    tomada._ligada_desde = datetime.now() - timedelta(hours=2)

    # desligar agrega consumo de 2h * 1000W = 2000 Wh
    tomada.executar_comando("desligar")
    
    # comandos_disponiveis
    print("\n------------------------------------------------------------------")
    print("Comandos disponíveis:")
    for comando, descricao in tomada.comandos_disponiveis().items():
        print(f"{comando}: {descricao}")
    print("------------------------------------------------------------------")

    print(f"Final: {tomada.estado.name} | potencia_w: {tomada.potencia_w} | consumo_wh: {round(tomada.consumo_wh, 2)} Wh")
    print(f"Consumo total (inclui período atual se ligada): {round(tomada.consumo_wh_total(), 2)} Wh")