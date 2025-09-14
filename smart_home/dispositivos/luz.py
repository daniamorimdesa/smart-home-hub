# smart_home/dispositivos/luz.py: implementação da classe Luz com FSM.
from enum import Enum, auto
from typing import Any, Dict
from transitions import Machine, MachineError
from smart_home.core.dispositivos import DispositivoBase, TipoDeDispositivo
from smart_home.core.eventos import TipoEvento
#--------------------------------------------------------------------------------------------------------------
# ESTADOS DA LUZ E CORES SUPORTADAS
#--------------------------------------------------------------------------------------------------------------
class EstadoLuz(Enum):
    DESLIGADA = auto()   # off
    LIGADA = auto()      # on
    
class CorLuz(Enum):
    QUENTE = auto()
    FRIA = auto()
    NEUTRA = auto()
#--------------------------------------------------------------------------------------------------------------
# MÉTODO AUXILIAR PARA NOMES DE ESTADO
#--------------------------------------------------------------------------------------------------------------
def _nome_estado(x):
    """Converte estado (Enum ou str) para str."""
    return x.name if hasattr(x, "name") else str(x)
#--------------------------------------------------------------------------------------------------------------
# CLASSE LUZ
#--------------------------------------------------------------------------------------------------------------
class Luz(DispositivoBase):
    """
    Luz com FSM gerenciada pela biblioteca `transitions`
    Estados: DESLIGADA (off), LIGADA (on)
    Eventos/transições:
    - ligar: DESLIGADA -> LIGADA
    - desligar: LIGADA -> DESLIGADA
    - definir_brilho[x]: LIGADA -> LIGADA (validar 0-100)
    - definir_cor[COLOR]: LIGADA -> LIGADA (validar Enum CorLuz)
    Atributos com validação (propriedades):
    - brilho: int (0-100)
    - cor: CorLuz (QUENTE, FRIA, NEUTRA)
    """
    
    def __init__(self, id: str, nome: str, *, brilho_inicial: int = 0, cor_inicial: CorLuz = CorLuz.NEUTRA):
        super().__init__(id=id, nome=nome, tipo=TipoDeDispositivo.LUZ, estado=EstadoLuz.DESLIGADA)
        
        # atributos validados por propriedades
        self._brilho: int = 0 
        self._cor: CorLuz = CorLuz.NEUTRA 
        
        self.ultimo_brilho: int = 100    # lembrar último brilho > 0 para restaurar ao ligar
        self.brilho = brilho_inicial     # validar via propriedade, inicializa _brilho
        self.cor = cor_inicial           # validar via propriedade, inicializa _cor 

        
        # estados possíveis e transições
        estados = [EstadoLuz.DESLIGADA, EstadoLuz.LIGADA]
        transicoes = [
            # ligar / desligar com restauração/persistência de brilho
            {
                "trigger": "ligar",
                "source": EstadoLuz.DESLIGADA,
                "dest": EstadoLuz.LIGADA,
                "before": "_restaurar_brilho_ao_ligar",       # restaurar último brilho > 0
                "after": "_apos_comando"                      # log do comando
            },
            {
                "trigger": "desligar",
                "source": EstadoLuz.LIGADA,                    
                "dest": EstadoLuz.DESLIGADA,
                "before": "_salvar_brilho_ao_desligar",       # salvar último brilho > 0
                "after": "_apos_comando"                      # log do comando
            },
            
            # definir_brilho: permitido somente quando a luz está LIGADA (on -> on)
            {
                "trigger": "definir_brilho",
                "source": EstadoLuz.LIGADA,
                "dest": EstadoLuz.LIGADA,
                "before": "_escolher_brilho",                 # validar e definir brilho
                "after": "_apos_comando"                      # log do comando
            },
            # tentativa com luz desligada → bloqueada (self-loop em DESLIGADA, apenas log)
            {
                "trigger": "definir_brilho",
                "source": EstadoLuz.DESLIGADA,
                "dest": EstadoLuz.DESLIGADA,
                "after": "_comando_bloqueado"                 # log do comando bloqueado
            },

            # definir_cor: permitido somente quando a luz está LIGADA (on -> on)
            {
                "trigger": "definir_cor",
                "source": EstadoLuz.LIGADA,
                "dest": EstadoLuz.LIGADA,
                "before": "_escolher_cor",                    # validar e definir cor
                "after": "_apos_comando"                      # log do comando
            },
            # tentativa com luz desligada → bloqueada
            {
                "trigger": "definir_cor",
                "source": EstadoLuz.DESLIGADA,
                "dest": EstadoLuz.DESLIGADA,
                "after": "_comando_bloqueado"                 # log do comando bloqueado
            },
        ]
        
        # criar a máquina
        self.maquina = Machine(
            model=self,                                                            # o próprio objeto Luz é o modelo
            states=estados,                                                        # estados possíveis
            transitions=transicoes,                                                # transições definidas
            initial=EstadoLuz.DESLIGADA if self.brilho == 0 else EstadoLuz.LIGADA, # estado inicial
            model_attribute="estado",                                              # atributo que guarda o estado atual
            send_event=True,                                                       # envia o evento para os callbacks
            after_state_change=self._apos_transicao,                               # callback após qualquer transição
        )
    #--------------------------------------------------------------------------------------------------------------
    # PROPRIEDADES COM VALIDAÇÃO
    #--------------------------------------------------------------------------------------------------------------

    # brilho - getter e setter
    @property                  
    def brilho(self) -> int:
        """Brilho da luz (0-100)."""
        return self._brilho
    
    @brilho.setter
    def brilho(self, valor: int) -> None:
        """Define o brilho da luz.

        Args:
            valor (int): Valor do brilho (0-100).

        Raises:
            ValueError: Se o valor não for um inteiro.
            ValueError: Se o valor estiver fora do intervalo (0-100).
        """
        try:
            intensidade = int(valor)
        except Exception:
            raise ValueError("Brilho deve ser inteiro (0-100).")
        if not (0 <= intensidade <= 100):
            raise ValueError("Brilho deve estar entre 0 e 100.")
        self._brilho = intensidade  # atualizar brilho atual
        if intensidade > 0:
            self.ultimo_brilho = intensidade  # guardar último brilho > 0


    # cor - getter e setter
    @property
    def cor(self) -> CorLuz:
        """Cor da luz (NEUTRA, QUENTE, FRIA)."""
        return self._cor

    @cor.setter
    def cor(self, valor: CorLuz) -> None:
        """Define a cor da luz.

        Args:
            valor (CorLuz): A nova cor da luz.

        Raises:
            ValueError: Se o valor não for uma instância de CorLuz ou string válida.
            ValueError: Se a string não corresponder a uma cor válida.
        """
        if isinstance(valor, CorLuz):
            self._cor = valor
        elif isinstance(valor, str):  # aceitar strings como "quente"/"fria"/"neutra" também
            cor = valor.strip().upper()
            try:
                self._cor = CorLuz[cor]    # tentar converter string para Enum
            except Exception:              
                raise ValueError("Cor inválida. Use: QUENTE, FRIA ou NEUTRA.")
        else:
            raise ValueError("Cor deve ser uma instância de CorLuz ou string ('QUENTE', 'FRIA', 'NEUTRA').")

    #--------------------------------------------------------------------------------------------------------------
    # MÉTODOS ABSTRATOS IMPLEMENTADOS
    #--------------------------------------------------------------------------------------------------------------
    def executar_comando(self, comando: str, /, **kwargs: Any) -> None:
        """
        Comandos suportados:
          - ligar()
          - desligar()
          - definir_brilho(valor: int)
          - definir_cor(cor: CorLuz|str)
        """
        mapa = {
            "ligar": self.ligar,
            "desligar": self.desligar,
            "definir_brilho": self.definir_brilho,
            "definir_cor": self.definir_cor,
        }
        
        if comando not in mapa: 
            raise ValueError(f"Comando '{comando}' não suportado para luz '{self.id}'.")
        
        try:
            mapa[comando](**kwargs)  # chamar o método da FSM
            
        except MachineError as e:
            # comando inválido para o estado atual
            payload = self.evento_comando(
                comando=comando, antes=_nome_estado(self.estado), depois=_nome_estado(self.estado),
                extra={"bloqueado": True, "motivo": str(e)}
            )
            print("[COMANDO-BLOQUEADO]", payload)
            self._emitir(TipoEvento.COMANDO_EXECUTADO, payload)  # emitir evento ao hub
            
    def atributos(self) -> Dict[str, Any]:
        """Retorna os atributos da luz.

        Returns:
            Dict[str, Any]: Atributos da luz.
        """
        return {
            "brilho": self.brilho,
            #"ultimo_brilho": self.ultimo_brilho,
            "cor": self.cor.name,
            "estado_nome": _nome_estado(self.estado)
        }

    def comandos_disponiveis(self) -> Dict[str, str]:
        """Retorna os comandos disponíveis para a luz.

        Returns:
            Dict[str, str]: Mapeamento de comandos para suas descrições.
        """
        return {
            "ligar": "DESLIGADA → LIGADA (restaura último brilho ou 100)",
            "desligar": "LIGADA → DESLIGADA (salva último brilho e zera)",
            "definir_brilho": "Ajusta brilho (0..100) — requer LIGADA",
            "definir_cor": "Ajusta cor (QUENTE/FRIA/NEUTRA) — requer LIGADA",
        }
        
    #--------------------------------------------------------------------------------------------------------------
    # CALLBACKS/ LOGGING HELPERS
    #--------------------------------------------------------------------------------------------------------------
    def _escolher_brilho(self, event) -> None:
        """Escolher o brilho da luz.

        Args:
            event (Event): O evento que disparou a escolha do brilho.

        Raises:
            ValueError: Se o valor do brilho não for válido.
        """
        if "valor" not in event.kwargs:
            raise ValueError("Faltou 'valor' para definir_brilho(valor=...).")
        self.brilho = event.kwargs["valor"]  # valida via propriedade

    def _escolher_cor(self, event) -> None:
        """Escolher a cor da luz.

        Args:
            event (Event): O evento que disparou a escolha da cor.

        Raises:
            ValueError: _description_
        """
        if "cor" not in event.kwargs:
            raise ValueError("Faltou 'cor' para definir_cor(cor=...).")
        self.cor = event.kwargs["cor"]  # valida via propriedade
        
          
    def _restaurar_brilho_ao_ligar(self, event) -> None:
        """Restaura o brilho da luz ao ligar.
        Caso o brilho atual seja 0, restaurar memória; se nunca setado, usar 100

        Args:
            event (Event): O evento que disparou a restauração do brilho.
        """
        if self.brilho == 0:
            self.brilho = self.ultimo_brilho or 100

    def _salvar_brilho_ao_desligar(self, event) -> None:
        """Salva o brilho atual da luz ao desligar.
        Guarda brilho atual (>0) em ultimo_brilho e zera brilho.

        Args:
            event (Event): O evento que disparou a ação de desligar.
        """
        if self.brilho > 0:
            self.ultimo_brilho = self.brilho
        self._brilho = 0  # seta direto para não sobrescrever ultimo_brilho

    def _comando_bloqueado(self, event) -> None:
        """Callback chamado quando um comando é bloqueado.

        Args:
            event (Event): O evento que disparou o bloqueio do comando.
        """
        payload = self.evento_comando(
            comando=event.event.name,
            antes=_nome_estado(event.transition.source),
            depois=_nome_estado(event.transition.dest),
            extra={"bloqueado": True, "motivo": "luz_desligada"},
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
# Teste de uso da classe Luz
#--------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    luz = Luz(id="luz_sala", nome="Luz da Sala", brilho_inicial=0, cor_inicial=CorLuz.NEUTRA)

    print("Inicial:", luz.estado.name, "| brilho:", luz.brilho, "| cor:", luz.cor.name)

    # ligar/desligar
    luz.executar_comando("ligar")
    luz.executar_comando("desligar")

    # tentar definir_brilho/cor com luz DESLIGADA (bloqueado)
    luz.executar_comando("definir_brilho", valor=50)
    luz.executar_comando("definir_cor", cor="quente")

    # ligar e ajustar
    luz.executar_comando("ligar")
    luz.executar_comando("definir_brilho", valor=75)
    luz.executar_comando("definir_cor", cor=CorLuz.FRIA)
    print(f"\nAtual: {luz.estado.name} | brilho: {luz.brilho} | cor: {luz.cor.name}\n")
    luz.executar_comando("definir_cor", cor="quente")  # também aceita string
    luz.executar_comando("definir_brilho", valor=25)  # ajustar brilho para 25
    print(f"\nAtual: {luz.estado.name} | brilho: {luz.brilho} | cor: {luz.cor.name}\n")

    # comandos_disponiveis
    print("\n------------------------------------------------------------------")
    print("Comandos disponíveis:")
    for comando, descricao in luz.comandos_disponiveis().items():
        print(f"{comando}: {descricao}")
    print("------------------------------------------------------------------")
