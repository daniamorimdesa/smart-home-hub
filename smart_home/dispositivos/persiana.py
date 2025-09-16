# smart_home/dispositivos/persiana.py
from enum import Enum, auto
from typing import Any, Dict
from transitions import Machine, MachineError
from smart_home.core.dispositivos import DispositivoBase, TipoDeDispositivo
from smart_home.core.eventos import TipoEvento
from smart_home.core.erros import ComandoInvalido, AtributoInvalido
# --------------------------------------------------------------------------------------------------
# ESTADOS DA PERSIANA
# --------------------------------------------------------------------------------------------------
class EstadoPersiana(Enum):
    FECHADA = auto()
    PARCIAL = auto()
    ABERTA  = auto()
#--------------------------------------------------------------------------------------------------------------
# MÉTODOS AUXILIARES PARA NOMES DE ESTADO E LEITURA DE ARGUMENTOS
#--------------------------------------------------------------------------------------------------------------
def _nome_estado(x):
    """Converte estado (Enum ou str) para str."""
    return x.name if hasattr(x, "name") else str(x)

def _parse_percentual(v: Any) -> int:
    """
    Converte valores como 50, "50", "50%", 50.0 -> int 0..100.
    Lança ValueError se não der.
    """
    if isinstance(v, (int, float)):
        p = int(v)
    else:
        s = str(v).strip().replace("%", "")
        p = int(float(s))
    if not (0 <= p <= 100):
        raise AtributoInvalido("Percentual deve estar entre 0 e 100.", detalhes={"atributo": "percentual", "valor": p})
    return p


def _extrair_percentual(kwargs: Dict[str, Any]) -> int:
    """
    Procura o percentual em múltiplas chaves: 'percentual', 'abertura', 'valor', 'percent'.
    """
    for k in ("percentual", "abertura", "valor", "percent"):
        if k in kwargs and kwargs[k] is not None:
            return _parse_percentual(kwargs[k])
    raise AtributoInvalido("Faltou 'percentual' (ou 'abertura/valor/percent') para ajustar(percentual=...).", detalhes={"atributo": "percentual"})

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

        self._abertura: int = 0
        self.abertura = abertura_inicial  # valida via setter

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
                "conditions": "_guard_ajuste_aberta",                             # só vai para ABERTA se percentual==100
                "before": "_aplicar_percentual",                                  # aplica o percentual
                "after": "_apos_comando"                                          # log do comando
            },
            {
                "trigger": "ajustar", 
                "source": estados, 
                "dest": EstadoPersiana.FECHADA,
                "conditions": "_guard_ajuste_fechada",                            # só vai para FECHADA se percentual==0
                "before": "_aplicar_percentual",                                  # aplica o percentual
                "after": "_apos_comando"                                          # log do comando
            },
            {
                "trigger": "ajustar", 
                "source": estados, 
                "dest": EstadoPersiana.PARCIAL,
                "conditions": "_guard_ajuste_parcial",                            # só vai para PARCIAL se 1<=percentual<=99
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
        return self._abertura

    @abertura.setter
    def abertura(self, valor: int) -> None:
        """Define o percentual de abertura da persiana (0-100).

        Args:
            valor (int): Percentual de abertura.
        """
        self._abertura = _parse_percentual(valor)

    # ----------------------------------------------------------------------------------------------
    # GUARDS E AÇÕES (para ajustar)
    # ----------------------------------------------------------------------------------------------

    def _aplicar_percentual(self, event) -> None:
        """Aplica o percentual de abertura da persiana.

        Args:
            event (Event): O evento que contém o percentual.
        """
        self.abertura = _extrair_percentual(event.kwargs)

    def _abrir_total(self, event) -> None:
        """Abre a persiana totalmente.

        Args:
            event (Event): O evento que contém o percentual.
        """
        self.abertura = 100

    def _fechar_total(self, event) -> None:
        """Fecha a persiana totalmente.

        Args:
            event (Event): O evento que contém o percentual.
        """
        self.abertura = 0

    def _guard_ajuste_aberta(self, event) -> bool:
        """Verifica se o ajuste é para a posição aberta.

        Args:
            event (Event): O evento que contém o percentual.

        Returns:
            bool: True se o percentual for 100, False caso contrário.
        """
        return _extrair_percentual(event.kwargs) == 100

    def _guard_ajuste_fechada(self, event) -> bool:
        """Verifica se o ajuste é para a posição fechada.

        Args:
            event (Event): O evento que contém o percentual.

        Returns:
            bool: True se o percentual for 0, False caso contrário.
        """
        return _extrair_percentual(event.kwargs) == 0

    def _guard_ajuste_parcial(self, event) -> bool:
        """Verifica se o ajuste é para a posição parcial.

        Args:
            event (Event): O evento que contém o percentual.

        Returns:
            bool: True se o percentual estiver entre 1 e 99, False caso contrário.
        """
        p = _extrair_percentual(event.kwargs)
        return 1 <= p <= 99
    
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
            "abrir_parcial": self.abrir_parcial,  # atalho
        }
        
        if comando not in mapa:
            raise ComandoInvalido(f"Comando '{comando}' não suportado para persiana '{self.id}'.", detalhes={"id": self.id, "comando": comando})

        try:
            mapa[comando](**kwargs)  # executa o comando
            
        except MachineError as e:
            payload = self.evento_comando(
                comando=comando,
                antes=_nome_estado(self.estado),
                depois=_nome_estado(self.estado),
                extra={"bloqueado": True, "motivo": str(e)},
            )
            print("[COMANDO-BLOQUEADO]", payload)
            self._emitir(TipoEvento.COMANDO_EXECUTADO, payload) # emitir evento ao hub


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
            "abrir_parcial": "Atalho: ajustar(percentual=1..99)",
        }

    # ----------------------------------------------------------------------------------------------
    # CALLBACKS / LOGGING HELPERS
    # ----------------------------------------------------------------------------------------------
    def abrir_parcial(self, percentual: int):
        """helper explícito para rotina/CLI: abrir_parcial(percentual)"""
        self.ajustar(percentual=_parse_percentual(percentual))

    def _comando_redundante(self, event) -> None:
        payload = self.evento_comando(
            comando=event.event.name,
            antes=_nome_estado(event.transition.source),
            depois=_nome_estado(event.transition.dest),
            extra={"redundante": True},
        )
        print("[COMANDO-REDUNDANTE]", payload)
        self._emitir(TipoEvento.COMANDO_EXECUTADO, payload)  # emitir evento ao hub

    def _apos_transicao(self, event):
        src = _nome_estado(event.transition.source)
        dst = _nome_estado(event.transition.dest)
        if src == dst:
            return
        payload = self.evento_transicao(evento=event.event.name, origem=src, destino=dst)
        print("[TRANSIÇÃO]", payload)
        self._emitir(TipoEvento.TRANSICAO_ESTADO, payload) # emitir evento ao hub

    def _apos_comando(self, event):
        payload = self.evento_comando(
            comando=event.event.name,
            antes=_nome_estado(event.transition.source),
            depois=_nome_estado(event.transition.dest),
        )
        print("[COMANDO]", payload)
        self._emitir(TipoEvento.COMANDO_EXECUTADO, payload)  # emitir evento ao hub

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
