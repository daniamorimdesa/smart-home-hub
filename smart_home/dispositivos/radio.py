# smart_home/dispositivos/radio.py : implementação da classe Radio com FSM.
from enum import Enum, auto
from typing import Any, Dict
from transitions import Machine, MachineError

from smart_home.core.dispositivos import DispositivoBase, TipoDeDispositivo

#--------------------------------------------------------------------------------------------------------------
# ESTADOS DO RÁDIO E ESTAÇÕES SUPORTADAS
#--------------------------------------------------------------------------------------------------------------
class EstadoRadio(Enum):
    DESLIGADO = auto()
    LIGADO = auto()

class EstacaoRadio(Enum):
    NOTICIAS    = auto()
    MPB         = auto()
    ROCK        = auto()
    JAZZ        = auto()
    CLASSICA    = auto()
    POP         = auto()
    REGGAE      = auto()
    LOFI        = auto()
    ESPORTES    = auto()
    ENTREVISTAS = auto()

#--------------------------------------------------------------------------------------------------------------
# MÉTODO AUXILIAR PARA NOMES DE ESTADO
#--------------------------------------------------------------------------------------------------------------
def _nome_estado(x):
    """Converte estado (Enum ou str) para str."""
    return x.name if hasattr(x, "name") else str(x)
#--------------------------------------------------------------------------------------------------------------
# CLASSE RADIO
#--------------------------------------------------------------------------------------------------------------
class Radio(DispositivoBase):
    """
    Rádio simples com FSM (transitions)
    Estados: DESLIGADO, LIGADO
    Atributos com validação:
    - volume: int (0-100), restaura último volume ao ligar
    - estacao: EstacaoRadio (10 opções)
    Eventos/transições:
    - ligar: DESLIGADO -> LIGADO (restaura último volume > 0 ou usa 50)
    - desligar: LIGADO -> DESLIGADO (salva volume > 0 e zera volume atual)
    - definir_volume[x]: LIGADO -> LIGADO (valida 0-100)
    - definir_estacao[ESTACAO]: LIGADO -> LIGADO (valida enum/str)
    """
    def __init__(self, id: str, nome: str,*, volume_inicial: int = 0, estacao_inicial: EstacaoRadio = EstacaoRadio.MPB):
        super().__init__(id=id, nome=nome, tipo=TipoDeDispositivo.RADIO, estado=EstadoRadio.DESLIGADO)

        # atributos com validação
        self._volume: int = 0
        self._estacao: EstacaoRadio = EstacaoRadio.MPB

        # memória de volume para restaurar ao ligar
        self.ultimo_volume: int = 50
        
        # inicializações (validam via setters)
        self.volume = volume_inicial
        self.estacao = estacao_inicial
        
        # estados possíveis e transições
        estados = [EstadoRadio.DESLIGADO, EstadoRadio.LIGADO]
        transicoes = [
            # energia
            {
                "trigger": "ligar",
                "source": EstadoRadio.DESLIGADO,
                "dest": EstadoRadio.LIGADO,
                "before": "_restaurar_volume_ao_ligar",  # restaura último volume > 0 ou usa 50
                "after": "_apos_comando",                # log do comando
            },
            {
                "trigger": "desligar",
                "source": EstadoRadio.LIGADO,
                "dest": EstadoRadio.DESLIGADO,
                "before": "_salvar_volume_ao_desligar",  # salva volume > 0 e zera volume atual
                "after": "_apos_comando",                # log do comando
            },
            # definir_volume
            {
                "trigger": "definir_volume",
                "source": EstadoRadio.LIGADO,
                "dest": EstadoRadio.LIGADO,
                "before": "_escolher_volume",            # valida e define volume
                "after": "_apos_comando",                # log do comando
            },
            {
                "trigger": "definir_volume",
                "source": EstadoRadio.DESLIGADO,
                "dest": EstadoRadio.DESLIGADO,
                "after": "_comando_bloqueado",           # log de comando bloqueado
            },
            # definir_estacao
            {
                "trigger": "definir_estacao",
                "source": EstadoRadio.LIGADO,
                "dest": EstadoRadio.LIGADO,
                "before": "_escolher_estacao",           # valida e define estação
                "after": "_apos_comando",                # log do comando
            },
            {
                "trigger": "definir_estacao",
                "source": EstadoRadio.DESLIGADO,
                "dest": EstadoRadio.DESLIGADO,
                "after": "_comando_bloqueado",           # log de comando bloqueado
            },
        ]
        
        # criar a máquina
        self.maquina = Machine(
            model=self,                                                                # o próprio objeto Radio é o modelo
            states=estados,                                                            # estados possíveis
            transitions=transicoes,                                                    # transições definidas
            initial=EstadoRadio.DESLIGADO if self.volume == 0 else EstadoRadio.LIGADO, # estado inicial
            model_attribute="estado",                                                  # atributo que guarda o estado atual
            send_event=True,                                                           # envia o evento para os callbacks
            after_state_change=self._apos_transicao,                                   # callback após qualquer transição
        )
    # ----------------------------------------------------------------------------------------------------------
    # PROPRIEDADES COM VALIDAÇÃO
    # ----------------------------------------------------------------------------------------------------------
    
    # volume - getter e setter
    @property
    def volume(self) -> int:
        """Volume (0-100)."""
        return self._volume

    @volume.setter
    def volume(self, valor: int) -> None:
        """Define o volume (0-100).

        Args:
            valor (int): Novo valor do volume.

        Raises:
            ValueError: Se o valor não for um inteiro.
            ValueError: Se o valor estiver fora do intervalo (0-100).
        """
        try:
            volume = int(valor)
        except Exception:
            raise ValueError("Volume deve ser inteiro (0-100).")
        if not (0 <= volume <= 100):
            raise ValueError("Volume deve estar entre 0 e 100.")
        self._volume = volume
        if volume > 0:
            self.ultimo_volume = volume

    # estação - getter e setter
    @property
    def estacao(self) -> EstacaoRadio:
        """Estação do rádio."""
        return self._estacao

    @estacao.setter
    def estacao(self, valor: EstacaoRadio | str) -> None:
        """Define a estação do rádio.

        Args:
            valor (EstacaoRadio | str): Nova estação do rádio.

        Raises:
            ValueError: Se o valor não for uma estação válida.
        """
        if isinstance(valor, EstacaoRadio):
            self._estacao = valor
        elif isinstance(valor, str):
            nome_estacao = valor.strip().upper() # aceitar string com nome da estação também
            try:
                self._estacao = EstacaoRadio[nome_estacao]
            except Exception:
                validas = ", ".join([estacao.name for estacao in EstacaoRadio])
                raise ValueError(f"Estação inválida. Use: {validas}.")
        else:
            raise ValueError("Estação deve ser do tipo EstacaoRadio ou uma string com o nome da estação.")
        
    #--------------------------------------------------------------------------------------------------------------
    # MÉTODOS ABSTRATOS IMPLEMENTADOS
    #--------------------------------------------------------------------------------------------------------------
    def executar_comando(self, comando: str, /, **kwargs: Any) -> None:
        """
        Comandos suportados:
          - ligar()
          - desligar()
          - definir_volume(valor: int)
          - definir_estacao(estacao: EstacaoRadio | str)
        """
        mapa = {
            "ligar": self.ligar,
            "desligar": self.desligar,
            "definir_volume": self.definir_volume,
            "definir_estacao": self.definir_estacao,
        }
        
        if comando not in mapa:
            raise ValueError(f"Comando '{comando}' não suportado para rádio '{self.id}'.")
        
        try:
            mapa[comando](**kwargs) # chamar o método da FSM com argumentos
            
        except MachineError as e:
            # comando inválido para o estado atual
            payload = self.evento_comando(
                comando=comando, antes=_nome_estado(self.estado), depois=_nome_estado(self.estado),
                extra={"bloqueado": True, "motivo": str(e)}
            )
            print("[COMANDO-BLOQUEADO]", payload)
        
    def atributos(self) -> Dict[str, Any]:
        """Retorna os atributos do rádio.

        Returns:
            Dict[str, Any]: Atributos do rádio.
        """
        return {
            "estado_nome": _nome_estado(self.estado),
            "volume": self.volume,
            "ultimo_volume": self.ultimo_volume,
            "estacao": self.estacao.name,
        }
    
    def comandos_disponiveis(self) -> Dict[str, str]:
        """Retorna os comandos disponíveis para o rádio.

        Returns:
            Dict[str, str]: Mapeamento de comandos para suas descrições.
        """
        estacoes = ", ".join([estacao.name for estacao in EstacaoRadio]) # listar estações
        return {
            "ligar": "DESLIGADO → LIGADO (restaura último volume ou 50)",
            "desligar": "LIGADO → DESLIGADO (salva volume e zera)",
            "definir_volume": "Ajusta volume (0..100) — requer LIGADO",
            "definir_estacao": f"Ajusta estação ({estacoes}) — requer LIGADO",
        }
        
    #--------------------------------------------------------------------------------------------------------------
    # CALLBACKS/ LOGGING HELPERS
    #--------------------------------------------------------------------------------------------------------------
    def _escolher_volume(self, event) -> None:
        """Define o volume do rádio.

        Args:
            event (Event): Evento contendo o novo valor de volume.

        Raises:
            ValueError: Se o valor não for fornecido no evento.
        """
        if "valor" not in event.kwargs:
            raise ValueError("Faltou 'valor' para definir_volume(valor=...).")
        self.volume = event.kwargs["valor"] 

    def _escolher_estacao(self, event) -> None:
        """Define a estação do rádio.

        Args:
            event (Event): Evento contendo a nova estação.

        Raises:
            ValueError: Se a estação não for fornecida no evento.
        """
        if "estacao" not in event.kwargs:
            raise ValueError("Faltou 'estacao' para definir_estacao(estacao=...).")
        self.estacao = event.kwargs["estacao"] # aceita EstacaoRadio ou str

    def _restaurar_volume_ao_ligar(self, event) -> None:
        """Restaura o volume do rádio ao ligar.

        Args:
            event (Event): Evento de ligar o rádio.
        """
        if self.volume == 0: # se volume atual é 0, restaurar último ou usar 50
            self.volume = self.ultimo_volume or 50 
    
    def _salvar_volume_ao_desligar(self, event) -> None:
        """Salva o volume atual ao desligar.

        Args:
            event (Event): Evento de desligar o rádio.
        """
        if self.volume > 0:  # salvar último volume se for > 0
            self.ultimo_volume = self.volume
        self._volume = 0  # zera sem atualizar ultimo_volume
        
    def _comando_bloqueado(self, event) -> None:
        """Callback chamado quando um comando é bloqueado.

        Args:
            event (Event): O evento que disparou o bloqueio do comando.
        """
        payload = self.evento_comando(
            comando=event.event.name,
            antes=_nome_estado(event.transition.source),
            depois=_nome_estado(event.transition.dest),
            extra={"bloqueado": True, "motivo": "radio_desligado"},
        )
        print("[COMANDO-BLOQUEADO]", payload) # por enquanto, só console (depois mandamos ao logger)
        
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
        print("[TRANSIÇÃO]", payload) # por enquanto, só console (depois mandamos ao logger)
        
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
        print("[COMANDO]", payload) # por enquanto, só console (depois mandamos ao logger)
        
#--------------------------------------------------------------------------------------------------------------
# Teste de uso da classe Radio
#--------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    radio = Radio(id="radio_sala", nome="Rádio da Sala", volume_inicial=0, estacao_inicial=EstacaoRadio.MPB)

    print("Inicial:", radio.estado.name, "| volume:", radio.volume, "| estacao:", radio.estacao.name)

    # tentar configurar desligado (bloqueado)
    radio.executar_comando("definir_volume", valor=30)
    radio.executar_comando("definir_estacao", estacao="rock")

    # ligar e ajustar
    radio.executar_comando("ligar")
    radio.executar_comando("definir_volume", valor=70)
    radio.executar_comando("definir_estacao", estacao=EstacaoRadio.JAZZ)
    print(f"\nAtual: {radio.estado.name} | volume: {radio.volume} | estacao: {radio.estacao.name}\n")

    # desligar salva volume e zera
    radio.executar_comando("desligar")
    print(f"Desligado: {radio.estado.name} | volume: {radio.volume} | ultimo_volume: {radio.ultimo_volume}\n")

    # religar restaura último volume
    radio.executar_comando("ligar")
    print(f"Religado: {radio.estado.name} | volume: {radio.volume} | estacao: {radio.estacao.name}\n")

    # comandos_disponiveis
    print("\n------------------------------------------------------------------")
    print("Comandos disponíveis:")
    for comando, descricao in radio.comandos_disponiveis().items():
        print(f"{comando}: {descricao}")
    print("------------------------------------------------------------------")