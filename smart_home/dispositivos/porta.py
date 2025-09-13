# smart_home/dispositivos/porta.py : implementação da classe Porta com FSM.
from enum import Enum, auto
from typing import Any, Dict
from transitions import Machine, MachineError
from smart_home.core.dispositivos import DispositivoBase, TipoDeDispositivo
#--------------------------------------------------------------------------------------------------------------
# ESTADOS DA PORTA
#--------------------------------------------------------------------------------------------------------------
class EstadoPorta(Enum):
    TRANCADA = auto()
    DESTRANCADA = auto()
    ABERTA = auto()
#--------------------------------------------------------------------------------------------------------------
# MÉTODO AUXILIAR PARA NOMES DE ESTADO
#--------------------------------------------------------------------------------------------------------------
def _nome_estado(x):
    """Converte estado (Enum ou str) para str."""
    return x.name if hasattr(x, "name") else str(x)
#--------------------------------------------------------------------------------------------------------------
# CLASSE PORTA
#--------------------------------------------------------------------------------------------------------------
class Porta(DispositivoBase):
    """
    Porta eletrônica com FSM gerenciada pela biblioteca `transitions`
    Estados: TRANCADA, DESTRANCADA, ABERTA
    Eventos/transições:
    - destrancar: TRANCADA -> DESTRANCADA
    - trancar:    DESTRANCADA -> TRANCADA
    - abrir:      DESTRANCADA -> ABERTA
    - fechar:     ABERTA -> DESTRANCADA
    Regras: 
    - tentar 'trancar' quando ABERTA não muda estado
    -  incrementar tentativas_invalidas
    """

    def __init__(self, id: str, nome: str):
        super().__init__(id=id, nome=nome, tipo=TipoDeDispositivo.PORTA, estado=EstadoPorta.TRANCADA)
        self.tentativas_invalidas: int = 0  # contador de tentativas inválidas de trancar a porta quando aberta
        
        # estados possíveis e transições
        estados = [EstadoPorta.TRANCADA, EstadoPorta.DESTRANCADA, EstadoPorta.ABERTA]
        transicoes = [
            # transições válidas
            {
                "trigger": "destrancar",
                "source" : EstadoPorta.TRANCADA,
                "dest"   : EstadoPorta.DESTRANCADA,
                "after": "_apos_comando",                    # log após o comando
            },
            {
                "trigger": "trancar",
                "source": EstadoPorta.DESTRANCADA,
                "dest": EstadoPorta.TRANCADA,
                "after": "_apos_comando",                   # log após o comando
            },
            {
                "trigger": "abrir",
                "source": EstadoPorta.DESTRANCADA,
                "dest": EstadoPorta.ABERTA,
                "after": "_apos_comando",                   # log após o comando
            },
            {
                "trigger": "fechar",                       
                "source": EstadoPorta.ABERTA,
                "dest": EstadoPorta.DESTRANCADA,
                "after": "_apos_comando",                  # log após o comando
            },
            # tentativa inválida: trancar quando ABERTA -> permanece ABERTA, conta tentativa
            {
                "trigger": "trancar",
                "source": EstadoPorta.ABERTA,
                "dest": EstadoPorta.ABERTA,                # permanece no mesmo estado 
                "before": "_contar_tentativa_invalida",
                "after": "_apos_comando_invalido",         # log após o comando inválido
            },
        ]
    
        # criar a máquina 
        self.maquina = Machine(
            model=self,                               # o próprio objeto Porta é o modelo
            states=estados,                           # estados possíveis
            transitions=transicoes,                   # transições definidas
            initial=EstadoPorta.TRANCADA,             # estado inicial
            model_attribute="estado",                 # atributo que guarda o estado atual
            send_event=True,                          # envia o evento para os callbacks
            after_state_change=self._apos_transicao,  # callback após qualquer transição
        )

    #--------------------------------------------------------------------------------------------------------------
    # MÉTODOS ABSTRATOS IMPLEMENTADOS
    #--------------------------------------------------------------------------------------------------------------  
    def executar_comando(self, comando: str, /, **kwargs: Any) -> None:
        """Executa um comando na porta.

        Args:
            comando (str): O comando a ser executado.

        Raises:
            ValueError: Se o comando não for suportado.
        """
        mapa = {
            "destrancar": self.destrancar,
            "trancar": self.trancar,
            "abrir": self.abrir,
            "fechar": self.fechar,
        }

        if comando not in mapa:
            raise ValueError(f"Comando '{comando}' não suportado para porta '{self.id}'.")
        
        try:
            mapa[comando](**kwargs) # chamar o método da FSM
            
        except MachineError as e:
            # comando inválido para o estado atual
            payload = self.evento_comando(
                comando=comando, antes=_nome_estado(self.estado), depois=_nome_estado(self.estado),
                extra={"bloqueado": True, "motivo": str(e)}
            )
            print("[COMANDO-BLOQUEADO]", payload)

    def atributos(self) -> Dict[str, Any]:
        """Retorna os atributos da porta.

        Returns:
            Dict[str, Any]: Atributos da porta.
        """
        return {"tentativas_invalidas": self.tentativas_invalidas, "estado_nome": _nome_estado(self.estado)}
  
    
    def comandos_disponiveis(self) -> Dict[str, str]:
        """Retorna os comandos disponíveis para a porta.

        Returns:
            Dict[str, str]: Mapeamento de comandos para suas descrições.
        """
        return {
            "destrancar": "TRANCADA → DESTRANCADA",
            "trancar": "DESTRANCADA → TRANCADA (bloqueado se ABERTA)",
            "abrir": "DESTRANCADA → ABERTA",
            "fechar": "ABERTA → DESTRANCADA",
        }
    
    #--------------------------------------------------------------------------------------------------------------
    # CALLBACKS/ LOGGING HELPERS
    #--------------------------------------------------------------------------------------------------------------
    def _contar_tentativa_invalida(self, event):
        """Callback chamado antes de uma tentativa inválida de trancar a porta quando aberta.

        Args:
            event (Event): O evento que disparou a tentativa inválida.
        """
        self.tentativas_invalidas += 1 


    def _apos_transicao(self, event): 
        """Callback chamado após qualquer transição de estado.

        Args:
            event (Event): O evento que disparou a transição.
        """
        src = _nome_estado(event.transition.source) # estado antes
        dst = _nome_estado(event.transition.dest)   # estado depois
        
        if src == dst:  # se não houve mudança de estado
            return  # oculta self-loops ('trancar' quando ABERTA)

        payload = self.evento_transicao(
            evento=event.event.name,                        # nome do evento
            origem=src,                                     # estado antes
            destino=dst,                                    # estado depois
        )
        print("[TRANSIÇÃO]", payload)  # por enquanto, só console (depois mandamos ao logger)


    def _apos_comando(self, event):
        """Callback chamado após a execução de um comando.

        Args:
            event (Event): O evento que disparou o comando.
        """
        payload = self.evento_comando(              
            comando=event.event.name,                    # nome do comando
            antes=_nome_estado(event.transition.source), # estado antes
            depois=_nome_estado(event.transition.dest),  # estado depois
        )
        print("[COMANDO]", payload)                      # por enquanto, só console (depois mandamos ao logger)


    def _apos_comando_invalido(self, event):
        """Callback chamado após a execução de um comando inválido.

        Args:
            event (Event): O evento que disparou o comando.
        """
        payload = self.evento_comando(
            comando=event.event.name,                         # nome do comando
            antes=_nome_estado(event.transition.source),      # estado antes
            depois=_nome_estado(event.transition.dest),       # permanece no mesmo estado
            extra={"invalido": True, "tentativas_invalidas": self.tentativas_invalidas}, # extra info 
        )
        print("[COMANDO-INVÁLIDO]", payload)         # por enquanto, só console (depois mandamos ao logger)


    # def _log_comando(self, comando: str, antes: EstadoPorta, depois: EstadoPorta):
    #     """Registra a execução de um comando.

    #     Args:
    #         comando (str): O nome do comando executado.
    #         antes (EstadoPorta): O estado da porta antes da execução do comando.
    #         depois (EstadoPorta): O estado da porta após a execução do comando.
    #     """
    #     payload = self.evento_comando(comando, _nome_estado(antes), _nome_estado(depois))   # log básico
    #     print("[COMANDO]", payload)  # por enquanto, só console (depois mandamos ao logger)


#--------------------------------------------------------------------------------------------------------------
# Teste de uso da classe Porta
#--------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    
    #  criar a porta
    p = Porta(id="porta_entrada", nome="Porta da Entrada")

    # estado inicial
    print("Estado inicial:", p.estado.name, "| tentativas_invalidas:", p.tentativas_invalidas)

    # fluxo feliz: destrancar -> abrir -> fechar -> trancar
    p.executar_comando("destrancar")
    p.executar_comando("abrir")
    p.executar_comando("fechar")
    p.executar_comando("trancar")

    # violar a regra: tentar trancar quando ABERTA
    p.executar_comando("destrancar")
    p.executar_comando("abrir")
    antes = p.tentativas_invalidas
    p.executar_comando("trancar")   # não muda estado; incrementa contador
    print("Após tentativa inválida, estado:", p.estado.name,
          "| tentativas_invalidas:", p.tentativas_invalidas, f"(+{p.tentativas_invalidas - antes})")
    
    antes = p.tentativas_invalidas
    p.executar_comando("trancar")   # não muda estado; incrementa contador
    print("Após tentativa inválida, estado:", p.estado.name,
          "| tentativas_invalidas:", p.tentativas_invalidas, f"(+{p.tentativas_invalidas - antes})")

    # voltar ao normal
    p.executar_comando("fechar")
    p.executar_comando("trancar")
    print("Estado atual:", p.estado.name, "| tentativas_invalidas:", p.tentativas_invalidas)

    # comandos_disponiveis
    print("\n-------------------------------------------------------")
    print("Comandos disponíveis:")
    for comando, descricao in p.comandos_disponiveis().items():
        print(f"{comando}: {descricao}")
    print("-------------------------------------------------------")