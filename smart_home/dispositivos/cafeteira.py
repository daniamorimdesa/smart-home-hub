# smart_home/dispositivos/cafeteira.py : implementação da classe Cafeteira com FSM.
from enum import Enum, auto
from typing import Any, Dict, List
from datetime import datetime
from transitions import Machine, MachineError
from smart_home.core.dispositivos import DispositivoBase, TipoDeDispositivo
from smart_home.core.eventos import TipoEvento
#--------------------------------------------------------------------------------------------------------------
# ESTADOS DA CAFETEIRA E CONSTANTES 
#--------------------------------------------------------------------------------------------------------------
class EstadoCafeteira(Enum):
    DESLIGADA = auto()      # off
    PRONTA = auto()         # disponível para o preparo de bebidas
    PREPARANDO = auto()     # extraindo bebida selecionada
    SEM_RECURSOS = auto() 

AGUA_MAX_ML = 1000   # 1 litro
CAPS_MAX = 10        # 10 cápsulas
VOLUME_POR_BEBIDA = 100  # cada preparo consome 100ml
#--------------------------------------------------------------------------------------------------------------
# MÉTODO AUXILIAR PARA NOMES DE ESTADO
#--------------------------------------------------------------------------------------------------------------
def _nome_estado(x):
    """Converte estado (Enum ou str) para str."""
    return x.name if hasattr(x, "name") else str(x)
#--------------------------------------------------------------------------------------------------------------
# CLASSE CAFETEIRA
#--------------------------------------------------------------------------------------------------------------
class CafeteiraCapsulas(DispositivoBase):
    """
    Cafeteira de cápsulas com FSM gerenciada pela biblioteca `transitions`
    - água máx: 1000 ml; cápsulas máx: 10;
    - cada bebida consome 100 ml + 1 cápsula
    Estados: DESLIGADA (off), PRONTA (on), PREPARANDO, SEM_RECURSOS
    Eventos/transições:
    - ligar: DESLIGADA -> PRONTA
    - desligar: PRONTA/SEM_RECURSOS → DESLIGADA (bloqueado se PREPARANDO)
    - preparar_bebida: PRONTA → PREPARANDO (só se tiver recursos, se não, PRONTA → SEM_RECURSOS)
    - finalizar_preparo: PREPARANDO → PRONTA (consome 1 cápsula + 100 ml)
    - reabastecer_maquina:
        SEM_RECURSOS → PRONTA (repõe ao máximo)
        PRONTA/DESLIGADA → self-loop (reposição preventiva)
        bloqueado em PREPARANDO
    - A cafeteira sempre nasce cheia: 1000 ml de água e 10 cápsulas.
    """
    def __init__(self, id: str, nome: str):
        super().__init__(id=id, nome=nome, tipo=TipoDeDispositivo.CAFETEIRA, estado=EstadoCafeteira.DESLIGADA)

        # níveis iniciais de recursos (água e cápsulas sempre começam cheios)
        self.agua_ml: int = AGUA_MAX_ML
        self.capsulas: int = CAPS_MAX

        # métricas de uso
        self.total_bebidas: int = 0
        self.historico: List[Dict[str, Any]] = []
        
        # estados possíveis e transições
        estados = [EstadoCafeteira.DESLIGADA, EstadoCafeteira.PRONTA, EstadoCafeteira.PREPARANDO, EstadoCafeteira.SEM_RECURSOS]
        transicoes = [
            # energia
            {
            "trigger": "ligar",
            "source": EstadoCafeteira.DESLIGADA,
            "dest": EstadoCafeteira.PRONTA,
            "after": "_apos_comando"
            },
            {
            "trigger": "desligar",
            "source": [EstadoCafeteira.PRONTA, EstadoCafeteira.SEM_RECURSOS],
            "dest": EstadoCafeteira.DESLIGADA,
            "after": "_apos_comando"                         # log do comando
            },
            {
            "trigger": "desligar",
            "source": EstadoCafeteira.PREPARANDO,
            "dest": EstadoCafeteira.PREPARANDO,
            "after": "_comando_bloqueado"                    # bloqueado se estiver preparando
            },
            # preparo
            {
            "trigger": "preparar_bebida",
            "source": EstadoCafeteira.PRONTA,
            "dest": EstadoCafeteira.PREPARANDO,
            "conditions": "_recursos_ok",                     # só prepara se houver recursos
            "after": "_apos_comando"                          # log do comando
            },
            {
            "trigger": "preparar_bebida",
            "source": EstadoCafeteira.PRONTA,
            "dest": EstadoCafeteira.SEM_RECURSOS,
            "unless": "_recursos_ok",                         # só prepara se houver recursos
            "after": "_faltou_recurso"                        # log de falta de recurso
            },
            {
            "trigger": "finalizar_preparo",
            "source": EstadoCafeteira.PREPARANDO,
            "dest": EstadoCafeteira.PRONTA,
            "before": "_consumir_e_registrar",                # consome recursos e registra no histórico
            "after": "_apos_comando"                          # log do comando
            },
            # reabastecer (preventivo e por falta)
            {
            "trigger": "reabastecer_maquina",
            "source": EstadoCafeteira.SEM_RECURSOS,
            "dest": EstadoCafeteira.PRONTA,
            "before": "_reabastecer_total",                   # reabastece todos os recursos
            "after": "_apos_comando"                          # log do comando
            },
            {
            "trigger": "reabastecer_maquina",
            "source": EstadoCafeteira.PRONTA,
            "dest": EstadoCafeteira.PRONTA,
            "before": "_reabastecer_total",                   # reabastece todos os recursos
            "after": "_apos_comando"                          # log do comando
            },
            {
            "trigger": "reabastecer_maquina",
            "source": EstadoCafeteira.DESLIGADA,
            "dest": EstadoCafeteira.DESLIGADA,
            "before": "_reabastecer_total",                   # reabastece todos os recursos
            "after": "_apos_comando"                          # log do comando
            },
            {
            "trigger": "reabastecer_maquina",
            "source": EstadoCafeteira.PREPARANDO,
            "dest": EstadoCafeteira.PREPARANDO,
            "after": "_comando_bloqueado"                     # bloqueado se estiver preparando
            },
            # bloqueios adicionais (self-loops com comando_bloqueado)
            {
                "trigger": "preparar_bebida", 
                "source": EstadoCafeteira.DESLIGADA, 
                "dest": EstadoCafeteira.DESLIGADA, "after": "_comando_bloqueado"
            },
            {
                "trigger": "finalizar_preparo", 
                "source": EstadoCafeteira.DESLIGADA, 
                "dest": EstadoCafeteira.DESLIGADA, "after": "_comando_bloqueado"
            },
            {
                "trigger": "finalizar_preparo", 
                "source": EstadoCafeteira.PRONTA,
                "dest": EstadoCafeteira.PRONTA,
                "after": "_comando_bloqueado"
            },
            # bloqueios de 'ligar' (já ligado/ativo)
            {
                "trigger": "ligar", 
                "source": EstadoCafeteira.PRONTA,       
                "dest": EstadoCafeteira.PRONTA,       
                "after": "_comando_bloqueado"
            },
            {
                "trigger": "ligar", 
                "source": EstadoCafeteira.PREPARANDO,   
                "dest": EstadoCafeteira.PREPARANDO,   
                "after": "_comando_bloqueado"
            },
            {
                "trigger": "ligar", 
                "source": EstadoCafeteira.SEM_RECURSOS, 
                "dest": EstadoCafeteira.SEM_RECURSOS, 
                "after": "_comando_bloqueado"
            },

        ]
  
        # criar a máquina
        self.maquina = Machine(
            model=self,                                                            # o próprio objeto Cafeteira é o modelo
            states=estados,                                                        # estados possíveis
            transitions=transicoes,                                                # transições definidas
            initial=EstadoCafeteira.DESLIGADA,                                     # estado inicial
            model_attribute="estado",                                              # atributo que guarda o estado atual
            send_event=True,                                                       # envia o evento para os callbacks
            after_state_change=self._apos_transicao,                               # callback após qualquer transição
        )
        
    #--------------------------------------------------------------------------------------------------------------
    # GUARDS(VERIFICADORES DE CONDIÇÃO) E AÇÕES
    #--------------------------------------------------------------------------------------------------------------
    def _recursos_ok(self, event) -> bool:
        # Verifica se há recursos suficientes para preparar uma bebida
        return self.agua_ml >= VOLUME_POR_BEBIDA and self.capsulas >= 1 # precisa de 100ml e 1 cápsula

    def _consumir_e_registrar(self, event) -> None:
        # Consome recursos no término do preparo
        self.agua_ml -= VOLUME_POR_BEBIDA
        self.capsulas -= 1
        self.total_bebidas += 1
        self.historico.append({ 
            "timestamp": datetime.now().isoformat(timespec="seconds"),    # data/hora do preparo
            "volume_ml": VOLUME_POR_BEBIDA,                               # volume consumido
            "capsulas_restantes": self.capsulas,                          # cápsulas restantes
            "agua_restante_ml": self.agua_ml,                             # água restante
        })

    def _reabastecer_total(self, event) -> None:
        # Reabastece água e cápsulas ao máximo
        self.agua_ml = AGUA_MAX_ML
        self.capsulas = CAPS_MAX

    #--------------------------------------------------------------------------------------------------------------
    # MÉTODOS ABSTRATOS IMPLEMENTADOS
    #--------------------------------------------------------------------------------------------------------------
    def executar_comando(self, comando: str, /, **kwargs: Any) -> None:
        """
        Comandos suportados:
        - ligar()
        - desligar()
        - preparar_bebida()
        - finalizar_preparo()
        - reabastecer_maquina()
        """
        mapa = {
            "ligar": self.ligar,
            "desligar": self.desligar,
            "preparar_bebida": self.preparar_bebida,
            "finalizar_preparo": self.finalizar_preparo,
            "reabastecer_maquina": self.reabastecer_maquina,
        }
        
        if comando not in mapa:
            raise ValueError(f"Comando '{comando}' não suportado para cafeteira '{self.id}'.")
        
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
        """
        Retorna os atributos da cafeteira.

        Returns:
            Dict[str, Any]: Atributos da cafeteira.
        """
        return {
            "estado_nome": _nome_estado(self.estado),    # nome do estado atual
            "agua_ml": self.agua_ml,                     # nível atual de água
            "capsulas": self.capsulas,                   # número atual de cápsulas
            "total_bebidas": self.total_bebidas,         # total de bebidas preparadas
            "historico": len(self.historico),            # histórico de preparos (quantidade)
        }

    def comandos_disponiveis(self) -> Dict[str, str]:
        """
        Retorna os comandos disponíveis para a cafeteira.

        Returns:
            Dict[str, str]: Mapeamento de comandos para suas descrições.
        """
        return {
            "ligar": "DESLIGADA → PRONTA",
            "desligar": "PRONTA/SEM_RECURSOS → DESLIGADA (bloqueado em PREPARANDO)",
            "preparar_bebida": "PRONTA → PREPARANDO (se houver recursos)",
            "finalizar_preparo": "PREPARANDO → PRONTA (consome 100ml e 1 cápsula)",
            "reabastecer_maquina": "Repõe água e cápsulas ao máximo",
        }
    #--------------------------------------------------------------------------------------------------------------
    # CALLBACKS/ LOGGING HELPERS
    #--------------------------------------------------------------------------------------------------------------
    def _faltou_recurso(self, event) -> None:
        """Callback para quando falta recurso para preparar bebida.

        Args:
            event (Event): O evento que disparou a falta de recurso.
        """
        payload = self.evento_comando(
            comando="preparar_bebida",
            antes=_nome_estado(event.transition.source),
            depois=_nome_estado(event.transition.dest),
            extra={"agua_ml": self.agua_ml, "capsulas": self.capsulas, "motivo": "sem_recurso"},
        )
        print("[COMANDO-BLOQUEADO]", payload)
        self._emitir(TipoEvento.COMANDO_EXECUTADO, payload)  # emitir evento ao hub

    def _comando_bloqueado(self, event) -> None:
        """Callback chamado quando um comando é bloqueado.

        Args:
            event (Event): O evento que disparou o bloqueio do comando.
        """
        payload = self.evento_comando(
            comando=event.event.name,
            antes=_nome_estado(event.transition.source),
            depois=_nome_estado(event.transition.dest),
            extra={"bloqueado": True, "motivo": "comando_invalido"},
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
# Teste de uso da classe Cafeteira
#--------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    nespresso = CafeteiraCapsulas(id="cafeteira", nome="Cafeteira da Cozinha")
    print(f"Inicial: {nespresso.estado.name} | água: {nespresso.agua_ml} | caps: {nespresso.capsulas}\n")
    print("--------------------------------------------------------------------------------------------------")

    nespresso.executar_comando("ligar")
    # prepara 3 bebidas
    for _ in range(3):
        nespresso.executar_comando("preparar_bebida")
        nespresso.executar_comando("finalizar_preparo")
        print(f"Atual: {nespresso.estado.name} | água: {nespresso.agua_ml} | caps: {nespresso.capsulas}\n")
        print("--------------------------------------------------------------------------------------------------")

    # forçar falta de recurso
    nespresso.agua_ml = 50
    nespresso.capsulas = 0
    nespresso.executar_comando("preparar_bebida")  # PRONTA -> SEM_RECURSOS
    print(f"Atual: {nespresso.estado.name} | água: {nespresso.agua_ml} | caps: {nespresso.capsulas}\n")
    print("--------------------------------------------------------------------------------------------------")

    # reabastece e volta a usar
    nespresso.executar_comando("reabastecer_maquina")  # SEM_RECURSOS -> PRONTA
    print(f"Atual: {nespresso.estado.name} | água: {nespresso.agua_ml} | caps: {nespresso.capsulas}\n")
    nespresso.executar_comando("preparar_bebida")
    print(f"Atual: {nespresso.estado.name} | água: {nespresso.agua_ml} | caps: {nespresso.capsulas}\n")
    nespresso.executar_comando("finalizar_preparo")
    print(f"Atual: {nespresso.estado.name} | água: {nespresso.agua_ml} | caps: {nespresso.capsulas}\n")
    print("--------------------------------------------------------------------------------------------------")
    

    # desliga
    nespresso.executar_comando("desligar")
    print("Atributos finais:", nespresso.atributos())
    
    # comandos_disponiveis
    print("\n------------------------------------------------------------------")
    print("Comandos disponíveis:")
    for comando, descricao in nespresso.comandos_disponiveis().items():
        print(f"{comando}: {descricao}")
    print("------------------------------------------------------------------")