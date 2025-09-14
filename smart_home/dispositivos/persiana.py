# smart_home/dispositivos/persiana.py
from enum import Enum, auto
from typing import Any, Dict
from transitions import Machine, MachineError
from smart_home.core.dispositivos import DispositivoBase, TipoDeDispositivo
# --------------------------------------------------------------------------------------------------
# ESTADOS DA PERSIANA
# --------------------------------------------------------------------------------------------------
class EstadoPersiana(Enum):
    FECHADA = auto()
    PARCIAL = auto()
    ABERTA  = auto()
#--------------------------------------------------------------------------------------------------------------
# MÉTODO AUXILIAR PARA NOMES DE ESTADO
#--------------------------------------------------------------------------------------------------------------
def _nome_estado(x):
    """Converte estado (Enum ou str) para str."""
    return x.name if hasattr(x, "name") else str(x)
#--------------------------------------------------------------------------------------------------------------
# CLASSE PERSIANA
#--------------------------------------------------------------------------------------------------------------
class Persiana(DispositivoBase):
    """
    Persiana com FSM gerenciada pela biblioteca `transitions`
    Estados: FECHADA, PARCIAL, ABERTA
    Atributo validado:
    - abertura: int (0-100)  [0=fechada, 100=aberta, 1-99=parcial]
    Eventos/transições:
    - abrir:   FECHADA|PARCIAL -> ABERTA    (abertura=100)
    - fechar:  ABERTA|PARCIAL  -> FECHADA   (abertura=0)
    - ajustar[percentual]:
    * -> ABERTA   se percentual==100
    * -> FECHADA  se percentual==0
    * -> PARCIAL  se 1<=percentual<=99
    """
    def __init__(self, id: str, nome: str, *, abertura_inicial: int = 0):
        estado_inicial = (
            EstadoPersiana.ABERTA if abertura_inicial == 100
            else EstadoPersiana.FECHADA if abertura_inicial == 0
            else EstadoPersiana.PARCIAL
        )
        super().__init__(id=id, nome=nome, tipo=TipoDeDispositivo.PERSIANA, estado=estado_inicial)

        # atributo validado
        self._abertura: int = 0
        self.abertura = abertura_inicial  # passa pelo setter (validação)

        # estados e transições
        estados = [EstadoPersiana.FECHADA, EstadoPersiana.PARCIAL, EstadoPersiana.ABERTA]
        transicoes = [
            # abrir persiana
            {
                "trigger": "abrir",  
                "source": [EstadoPersiana.FECHADA, EstadoPersiana.PARCIAL],
                "dest": EstadoPersiana.ABERTA, 
                "before": "_abrir_total",                                         # abre totalmente
                "after": "_apos_comando"                                          # log do comando
            },
            {
                "trigger": "abrir",
                "source": EstadoPersiana.ABERTA,
                "dest": EstadoPersiana.ABERTA,
                "after": "_comando_redundante"                                    # log de comando redundante
            },

            # fechar persiana
            {
                "trigger": "fechar", 
                "source": [EstadoPersiana.ABERTA, EstadoPersiana.PARCIAL],
                "dest": EstadoPersiana.FECHADA, 
                "before": "_fechar_total",                                        # fecha totalmente
                "after": "_apos_comando"                                          # log do comando
            },
            {
                "trigger": "fechar", 
                "source": EstadoPersiana.FECHADA,
                "dest": EstadoPersiana.FECHADA, 
                "after": "_comando_redundante"                                    # log de comando redundante
            },

            # ajustar(percentual)
            {
                "trigger": "ajustar", 
                "source": estados, 
                "dest": EstadoPersiana.ABERTA,
                "conditions": "_valor_ajuste_aberta",                             # só vai para ABERTA se percentual==100
                "before": "_aplicar_percentual",                                  # aplica o percentual
                "after": "_apos_comando"                                          # log do comando
            },
            {
                "trigger": "ajustar", 
                "source": estados, 
                "dest": EstadoPersiana.FECHADA,
                "conditions": "_valor_ajuste_fechada",                            # só vai para FECHADA se percentual==0
                "before": "_aplicar_percentual",                                  # aplica o percentual
                "after": "_apos_comando"                                          # log do comando
            },
            {
                "trigger": "ajustar", 
                "source": estados, 
                "dest": EstadoPersiana.PARCIAL,
                "conditions": "_valor_ajuste_parcial",                            # só vai para PARCIAL se 1<=percentual<=99
                "before": "_aplicar_percentual",                                  # aplica o percentual
                "after": "_apos_comando"                                          # log do comando
            },
        ]

        # criar a máquina
        self.maquina = Machine(
            model=self,                                                   # o próprio objeto Persiana é o modelo
            states=estados,                                               # estados possíveis
            transitions=transicoes,                                       # transições definidas
            initial=estado_inicial,                                       # estado inicial
            model_attribute="estado",                                     # atributo que guarda o estado atual
            send_event=True,                                              # envia o evento para os callbacks
            after_state_change=self._apos_transicao,                      # callback após qualquer transição
        )

    #--------------------------------------------------------------------------------------------------------------
    # PROPRIEDADE COM VALIDAÇÃO
    #--------------------------------------------------------------------------------------------------------------
    
    # abertura - getter e setter
    @property
    def abertura(self) -> int:
        """Percentual de abertura da persiana (0-100)."""
        return self._abertura

    @abertura.setter
    def abertura(self, valor: int) -> None:
        """Define o percentual de abertura da persiana (0-100).

        Args:
            valor (int): Percentual de abertura.

        Raises:
            ValueError: Se o valor não for um inteiro.
            ValueError: Se o valor estiver fora do intervalo (0-100).
        """
        try:
            percentual = int(valor)
        except Exception:
            raise ValueError("Abertura deve ser inteiro (0-100).")
        if not (0 <= percentual <= 100):
            raise ValueError("Abertura deve estar entre 0 e 100.")
        self._abertura = percentual # atribui o valor validado

    # ----------------------------------------------------------------------------------------------
    # GUARDS E AÇÕES (para ajustar)
    # ----------------------------------------------------------------------------------------------
    def _pegar_percentual_do_evento(self, event) -> int:
        """Extrai o percentual do evento.

        Args:
            event (Event): O evento que contém o percentual.

        Raises:
            ValueError: Se o percentual não estiver presente no evento.
            ValueError: Se o percentual não for um inteiro.
            ValueError: Se o percentual estiver fora do intervalo (0-100).

        Returns:
            int: O percentual extraído do evento.
        """
        if "percentual" not in event.kwargs:
            raise ValueError("Faltou 'percentual' para ajustar(percentual=...).")
        # valida aqui também para garantir erro cedo
        valor = event.kwargs["percentual"]
        try:
            percentual = int(valor)
        except Exception:
            raise ValueError("Percentual deve ser inteiro (0-100).")
        if not (0 <= percentual <= 100):
            raise ValueError("Percentual deve estar entre 0 e 100.")
        return percentual

    # condições (guards)
    def _valor_ajuste_aberta(self, event) -> bool:
        """Verifica se o ajuste é para 100% (aberta).

        Args:
            event (Event): O evento que contém o percentual.

        Returns:
            bool: True se o ajuste for para 100%, False caso contrário.
        """
        return self._pegar_percentual_do_evento(event) == 100

    def _valor_ajuste_fechada(self, event) -> bool:
        """Verifica se o ajuste é para 0% (fechada).

        Args:
            event (Event): O evento que contém o percentual.

        Returns:
            bool: True se o ajuste for para 0%, False caso contrário.
        """
        return self._pegar_percentual_do_evento(event) == 0

    def _valor_ajuste_parcial(self, event) -> bool:
        """Verifica se o ajuste é para um valor parcial (1-99%).

        Args:
            event (Event): O evento que contém o percentual.

        Returns:
            bool: True se o ajuste for para um valor parcial, False caso contrário.
        """
        percentual = self._pegar_percentual_do_evento(event)
        return 1 <= percentual <= 99

    # ações (before)
    def _aplicar_percentual(self, event) -> None:
        """Aplica o percentual extraído do evento."""
        self.abertura = self._pegar_percentual_do_evento(event)

    def _abrir_total(self, event) -> None:
        """Abre a persiana totalmente."""
        self.abertura = 100

    def _fechar_total(self, event) -> None:
        """Fecha a persiana totalmente."""
        self.abertura = 0

    # ----------------------------------------------------------------------------------------------
    # MÉTODOS ABSTRATOS IMPLEMENTADOS
    # ----------------------------------------------------------------------------------------------
    def executar_comando(self, comando: str, /, **kwargs: Any) -> None:
        """
        Comandos suportados:
          - abrir()
          - fechar()
          - ajustar(percentual: int)
        """
        mapa = {
            "abrir": self.abrir,
            "fechar": self.fechar,
            "ajustar": self.ajustar,
        }
        
        if comando not in mapa:
            raise ValueError(f"Comando '{comando}' não suportado para persiana '{self.id}'.")
        
        try:
            mapa[comando](**kwargs)  # chamar o método da FSM
            
        except MachineError as e:
            payload = self.evento_comando(
                comando=comando, antes=_nome_estado(self.estado), depois=_nome_estado(self.estado),
                extra={"bloqueado": True, "motivo": str(e)},
            )
            print("[COMANDO-BLOQUEADO]", payload)  # log do comando bloqueado

    def atributos(self) -> Dict[str, Any]:
        """Retorna os atributos da persiana.

        Returns:
            Dict[str, Any]: Os atributos da persiana.
        """
        return {
            "estado_nome": _nome_estado(self.estado),
            "abertura": self.abertura,
        }

    def comandos_disponiveis(self) -> Dict[str, str]:
        """Retorna os comandos disponíveis para a persiana.

        Returns:
            Dict[str, str]: Mapeamento de comandos para suas descrições.
        """
        return {
            "abrir": "FECHADA|PARCIAL → ABERTA (abertura=100)",
            "fechar": "ABERTA|PARCIAL → FECHADA (abertura=0)",
            "ajustar": "Ajusta abertura (0-100): 0 → FECHADA, 100 → ABERTA, 1-99 → PARCIAL",
            "abrir_parcial": "Abre parcialmente (1-99%) — atalho para ajustar",
        }

    # ----------------------------------------------------------------------------------------------
    # CALLBACKS / LOGGING HELPERS
    # ----------------------------------------------------------------------------------------------
    def abrir_parcial(self, percentual: int):
        """Abre a persiana parcialmente para o percentual especificado (1-99)."""
        if not (1 <= percentual <= 99):
            raise ValueError("Percentual deve estar entre 1 e 99 para abrir parcialmente.")
        self.ajustar(percentual=percentual)

    def _comando_redundante(self, event) -> None:
        payload = self.evento_comando(
            comando=event.event.name,
            antes=_nome_estado(event.transition.source),
            depois=_nome_estado(event.transition.dest),
            extra={"redundante": True},
        )
        print("[COMANDO-REDUNDANTE]", payload)

    def _apos_transicao(self, event):
        src = _nome_estado(event.transition.source)
        dst = _nome_estado(event.transition.dest)
        if src == dst:
            return
        payload = self.evento_transicao(evento=event.event.name, origem=src, destino=dst)
        print("[TRANSIÇÃO]", payload)

    def _apos_comando(self, event):
        payload = self.evento_comando(
            comando=event.event.name,
            antes=_nome_estado(event.transition.source),
            depois=_nome_estado(event.transition.dest),
        )
        print("[COMANDO]", payload)

# --------------------------------------------------------------------------------------------------
# Teste de uso da classe Persiana
# --------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    persiana = Persiana(id="persiana_sala", nome="Persiana da Sala", abertura_inicial=0)
    print("Inicial:", persiana.estado.name, "| abertura:", persiana.abertura)

    persiana.executar_comando("abrir")
    print(f"\nAtual: {persiana.estado.name} | abertura: {persiana.abertura}")
    persiana.executar_comando("ajustar", percentual=40)
    print(f"\nAtual: {persiana.estado.name} | abertura: {persiana.abertura}")
    persiana.executar_comando("abrir")
    print(f"\nAtual: {persiana.estado.name} | abertura: {persiana.abertura}")
    persiana.executar_comando("fechar")
    persiana.executar_comando("ajustar", percentual=0)  # permanece FECHADA

    print(f"\nFinal: {persiana.estado.name} | abertura: {persiana.abertura}")
    
        # comandos_disponiveis
    print("\n---------------------------------------------------------------------------------------")
    print("Comandos disponíveis:")
    for comando, descricao in persiana.comandos_disponiveis().items():
        print(f"{comando}: {descricao}")
    print("---------------------------------------------------------------------------------------")
