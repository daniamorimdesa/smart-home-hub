# smart_home/hubtest.py
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box
from rich.traceback import install as rich_traceback

from smart_home.dispositivos.porta import Porta
from smart_home.dispositivos.luz import Luz, CorLuz
from smart_home.dispositivos.tomada import Tomada
from smart_home.dispositivos.cafeteira import CafeteiraCapsulas
from smart_home.dispositivos.radio import Radio, EstacaoRadio
from smart_home.dispositivos.persiana import Persiana

console = Console() # Objeto global do console
rich_traceback(show_locals=True) # tracebacks mais amigáveis

# --------------------------------------------------------------------------------------
# CRIAÇÃO INICIAL DE DISPOSITIVOS (HARDCODED)
# --------------------------------------------------------------------------------------
def criar_dispositivos():
    return {
        "porta": Porta(id="porta_entrada", nome="Porta da Entrada"),
        "luz": Luz(id="luz_sala", nome="Luz da Sala"),
        "tomada": Tomada(id="tomada_bancada", nome="Tomada da Bancada", potencia_w=1000),
        "cafeteira": CafeteiraCapsulas(id="cafeteira", nome="Cafeteira da Cozinha"),
        "radio": Radio(id="radio_sala", nome="Rádio da Sala"),
        "persiana": Persiana(id="persiana_sala", nome="Persiana da Sala", abertura_inicial=0),
    }

# --------------------------------------------------------------------------------------
# UI HELPERS (RICH) - LISTAGEM, ESCOLHA, EXIBIÇÃO DE ATRIBUTOS/COMANDOS
# --------------------------------------------------------------------------------------
def header():
    # Header estilizado
    console.rule("[italic bright_white]Smart Home Hub[/]")

def listar_dispositivos(dispositivos):
    """Lista os dispositivos registrados.

    Args:
        dispositivos (dict): Dicionário de dispositivos.
    """
    table = Table(title="Dispositivos Registrados", box=box.SIMPLE_HEAVY) # borda simples
    table.add_column("Chave", style="cyan", no_wrap=True)                 # sem quebra de linha
    table.add_column("Nome", style="bold")                                # negrito no nome
    table.add_column("Tipo", style="magenta")                             # cor magenta
    table.add_column("Estado", style="green")                             # cor verde no estado

    # Popula a tabela e imprime no console
    for chave, d in dispositivos.items():
        table.add_row(chave, d.nome, d.tipo.value, getattr(d.estado, "name", str(d.estado)))
    console.print(table)

def escolher_dispositivo(dispositivos):
    """Escolhe um dispositivo da lista.

    Args:
        dispositivos (dict): Dicionário de dispositivos.

    Returns:
        DispositivoBase: O dispositivo escolhido ou None.
    """
    listar_dispositivos(dispositivos)                                                     # listar os dispositivos registrados
    chave = Prompt.ask("\n[bold]Escolha a [cyan]chave[/] do dispositivo[/]", default="")  # prompt para escolher a chave
    disp = dispositivos.get(chave.strip().lower())                                        # buscar o dispositivo pela chave
    
    # verificar se o dispositivo foi encontrado
    if not disp:
        console.print(":warning: [yellow]Dispositivo não encontrado.[/]")
    return disp  # retorna o dispositivo ou None


def mostrar_atributos(disp):
    """Mostra os atributos de um dispositivo.

    Args:
        disp (DispositivoBase): O dispositivo a ser exibido.
    """
    attrs = disp.atributos()                                           # obter os atributos do dispositivo
    table = Table(title=f"Atributos — {disp.nome}", box=box.SIMPLE)    # borda simples
    table.add_column("Atributo", style="cyan")                         # adicionar coluna de atributo
    table.add_column("Valor", style="green")                           # adicionar coluna de valor
    
    # popular a tabela e imprimir no console
    for k, v in attrs.items():
        table.add_row(str(k), str(v))
    console.print(table)

def mostrar_comandos(disp):
    """Mostra os comandos disponíveis de um dispositivo.

    Args:
        disp (DispositivoBase): O dispositivo a ser exibido.
    """
    cmds = disp.comandos_disponiveis()                                              # obter os comandos disponíveis
    table = Table(title=f"Comandos — {disp.nome}", box=box.MINIMAL_DOUBLE_HEAD)     # borda dupla minimalista
    table.add_column("Comando", style="cyan", no_wrap=True)                         # coluna de comando sem quebra de linha
    table.add_column("Descrição", style="white")                                    # coluna de descrição
    
    # popular a tabela e imprimir no console
    for k, v in cmds.items():
        table.add_row(k, v)
    console.print(table)

# --------------------------------------------------------------------------------------
# PARSING DE PARÂMETROS (INT AUTOMÁTICO + ENUMS CONHECIDOS)
# --------------------------------------------------------------------------------------
def _try_int(s: str):
    """Tenta converter uma string para um inteiro."""
    try:
        return int(s)
    except Exception:
        return s

def _coerce_enum(value: str):
    """
    Converte strings para enums conhecidos (case-insensitive):
      - CorLuz: QUENTE/FRIA/NEUTRA
      - EstacaoRadio: nomes das estações
    Mantém ints/strings que não batem.
    """
    if not isinstance(value, str):
        return value
    v = value.strip().upper()

    # CorLuz
    try:
        return CorLuz[v]
    except Exception:
        pass

    # EstacaoRadio
    try:
        return EstacaoRadio[v]
    except Exception:
        pass

    return value

def ler_parametros_interativos():
    """Lê parâmetros interativos do usuário.

    Returns:
        dict: Um dicionário com os parâmetros lidos.
    """
    console.print(Panel.fit("[bold]Digite parâmetros no formato[/] [cyan]chave=valor[/].\n"
                            "Ex.: [green]valor=70[/], [green]cor=quente[/], [green]estacao=JAZZ[/]\n"
                            "Pressione [bold]<Enter>[/] sem nada para concluir.",
                            title="Parâmetros", border_style="cyan"))
    args = {} # dicionário para armazenar os parâmetros
    # loop para ler linhas até o usuário pressionar Enter vazio
    while True:
        linha = Prompt.ask("[dim]param[/]", default="")
        if not linha.strip():
            break
        if "=" not in linha:
            console.print("[yellow]Use o formato chave=valor.[/]")
            continue
        # separa chave e valor
        k, v = [p.strip() for p in linha.split("=", 1)]
        
        # tenta int -> tenta enum conhecido
        v = _try_int(v)
        v = _coerce_enum(v)
        
        # adiciona ao dicionário
        args[k] = v 
        
    return args

# --------------------------------------------------------------------------------------
# MAIN LOOP DO HUB (CLI SIMPLES)
# --------------------------------------------------------------------------------------
def mostrar_menu():
    """Mostra o menu principal."""
    table = Table.grid(padding=1) # grid com padding
    # coluna direita, ciano, sem quebra de linha
    table.add_column(justify="right", style="cyan", no_wrap=True) 
    table.add_column(style="white") # coluna branca
    
    # adicionar linhas do menu
    table.add_row("1", "Listar dispositivos") 
    table.add_row("2", "Atributos de um dispositivo")
    table.add_row("3", "Comandos disponíveis de um dispositivo")
    table.add_row("4", "Executar comando em um dispositivo")
    table.add_row("0", "Sair")
    console.print(Panel(table, title="[bold]MENU[/]", border_style="cyan")) # imprimir o menu

def main():
    dispositivos = criar_dispositivos() # criar dispositivos iniciais
    header()                            # mostrar header
   
    # loop principal do menu
    while True:
        mostrar_menu()
        opcao = Prompt.ask("[bold]Selecione[/]", choices=["0", "1", "2", "3", "4"], default="1")

        if opcao == "0":
            if Confirm.ask("Deseja realmente sair?", default=True):
                console.print("\n[bold green]💾 Encerrando Hub...\n🌟 Até mais!🌟[/]")
                break

        elif opcao == "1":
            listar_dispositivos(dispositivos)

        elif opcao == "2":
            disp = escolher_dispositivo(dispositivos)
            if disp:
                mostrar_atributos(disp)

        elif opcao == "3":
            disp = escolher_dispositivo(dispositivos)
            if disp:
                mostrar_comandos(disp)

        elif opcao == "4":
            disp = escolher_dispositivo(dispositivos)
            if not disp:
                continue
            mostrar_comandos(disp)
            cmd = Prompt.ask("\n[bold]Comando[/]").strip()
            if cmd not in disp.comandos_disponiveis():
                console.print(":no_entry: [red]Comando inválido para esse dispositivo.[/]")
                continue

            args = ler_parametros_interativos()
            try:
                disp.executar_comando(cmd, **args)
                console.print(Panel.fit("[bold green]OK[/] comando executado!", border_style="green"))
            except Exception as e:
                console.print(Panel.fit(f"[red]Erro:[/] {e}", border_style="red"))

if __name__ == "__main__":
    main()
