# smart_home/core/cli.py: CLI interativo com Rich
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box
from rich.traceback import install as rich_traceback

from smart_home.core.hub import Hub
from smart_home.core.dispositivos import TipoDeDispositivo
from smart_home.core.relatorios import (
    consumo_por_tomada,
    tempo_total_luzes_ligadas,
    dispositivos_mais_usados,
    cafes_por_dia,
    distribuicao_comandos_por_tipo,
    resumo as resumo_relatorios,
)

# enums úteis p/ coerção de parâmetros
from smart_home.dispositivos.luz import CorLuz
from smart_home.dispositivos.radio import EstacaoRadio
from smart_home.dispositivos.persiana import Persiana

from pathlib import Path
from smart_home.core.observers import ConsoleObserver, CsvObserverTransitions, CsvObserverEventos, CsvObserverComandos


console = Console()
rich_traceback(show_locals=True)
#--------------------------------------------------------------------------------------------------
# HELPERS CLI
#--------------------------------------------------------------------------------------------------
def listar_rotinas(hub: Hub):
    from rich.markdown import Markdown
    if not hub.rotinas:
        console.print(Panel.fit("[yellow]Nenhuma rotina configurada no JSON.[/]", border_style="yellow"))
        return
    t = Table(title="Rotinas disponíveis", box=box.SIMPLE)
    t.add_column("Nome", style="cyan")
    t.add_column("Passos", justify="right")
    for nome, passos in hub.rotinas.items():
        t.add_row(nome, str(len(passos)))
    console.print(t)

def executar_rotina_cli(hub: Hub):
    listar_rotinas(hub)
    if not hub.rotinas:
        return
    nome = Prompt.ask("[bold]Nome da rotina[/]").strip()
    if nome not in hub.rotinas:
        console.print(Panel.fit(f"[red]Rotina '{nome}' não encontrada.[/]", border_style="red"))
        return
    from rich.progress import track
    passos = hub.rotinas[nome]
    # feedback visual
    for _ in track(range(len(passos)), description=f"Executando '{nome}'..."):
        pass  # só barra de progresso estética; execução real abaixo

    try:
        resumo = hub.executar_rotina(nome)
        # imprime um resumo bonito
        t = Table(title=f"Resultado — {nome}", box=box.SIMPLE_HEAVY)
        t.add_column("#", justify="right", style="dim")
        t.add_column("ID", style="cyan")
        t.add_column("Comando", style="magenta")
        t.add_column("OK?", justify="center")
        t.add_column("Antes", style="white")
        t.add_column("Depois", style="white")
        t.add_column("Erro", style="red")
        for r in resumo["resultados"]:
            t.add_row(
                str(r["passo"]), r["id"], r["cmd"],
                "✅" if r["ok"] else "❌",
                r.get("antes",""), r.get("depois",""),
                r.get("erro",""),
            )
        console.print(t)
        console.print(Panel.fit(
            f"[bold]Total:[/] {resumo['total']}  "
            f"[green]Sucesso:[/] {resumo['sucesso']}  "
            f"[red]Falha:[/] {resumo['falha']}",
            border_style="cyan"
        ))
    except Exception as e:
        console.print(Panel.fit(f"[red]Erro executando rotina:[/] {e}", border_style="red"))
#--------------------------------------------------------------------------------------------------
# HELPERS VISUAIS (RICH)
#--------------------------------------------------------------------------------------------------
def header():
    console.rule("[italic bright_white]Smart Home Hub[/]")

def _estado_str(estado) -> str:
    return getattr(estado, "name", str(estado))

def listar_dispositivos(hub: Hub):
    t = Table(title="Dispositivos Registrados", box=box.SIMPLE_HEAVY)
    t.add_column("ID", style="cyan", no_wrap=True)
    t.add_column("Nome", style="bold")
    t.add_column("Tipo", style="magenta")
    t.add_column("Estado", style="green")
    for d in hub.listar():
        t.add_row(d.id, d.nome, d.tipo.value, _estado_str(d.estado))
    console.print(t)

def escolher_dispositivo(hub: Hub):
    listar_dispositivos(hub)
    id_ = Prompt.ask("\n[bold]ID do dispositivo[/]", default="").strip()
    disp = hub.obter(id_)
    if not disp:
        console.print(":warning: [yellow]Dispositivo não encontrado.[/]")
    return disp

def mostrar_atributos(disp):
    attrs = disp.atributos()
    t = Table(title=f"Atributos — {disp.nome}", box=box.SIMPLE)
    t.add_column("Atributo", style="cyan")
    t.add_column("Valor", style="green")
    for k, v in attrs.items():
        t.add_row(str(k), str(v))
    console.print(t)

def mostrar_comandos(disp):
    cmds = disp.comandos_disponiveis()
    t = Table(title=f"Comandos — {disp.nome}", box=box.MINIMAL_DOUBLE_HEAD)
    t.add_column("Comando", style="cyan", no_wrap=True)
    t.add_column("Descrição", style="white")
    for k, v in cmds.items():
        t.add_row(k, v)
    console.print(t)

def mostrar_menu():
    grid = Table.grid(padding=1)
    grid.add_column(justify="right", style="cyan", no_wrap=True)
    grid.add_column(style="white")
    itens = [
        ("1", "Listar dispositivos"),
        ("2", "Mostrar dispositivo"),
        ("3", "Executar comando em dispositivo"),
        ("4", "Alterar atributo de dispositivo"),
        ("5", "Executar rotina"),
        ("6", "Gerar relatorio"),
        ("7", "Salvar configuracao"),
        ("8", "Adicionar dispositivo"),
        ("9", "Remover dispositivo"),
        ("10", "Sair"),
    ]
    for k, v in itens:
        grid.add_row(k, v)
    console.print(Panel(grid, title="[bold]MENU[/]", border_style="cyan"))

#--------------------------------------------------------------------------------------------------
# PARSING UTILITÁRIO (INT + ENUMS CONHECIDOS)
#--------------------------------------------------------------------------------------------------
def _try_int(s: str):
    try:
        return int(s)
    except Exception:
        return s

def _coerce_enum(value: Any):
    if not isinstance(value, str):
        return value
    v = value.strip().upper()
    # Luz
    try:
        return CorLuz[v]
    except Exception:
        pass
    # Rádio
    try:
        return EstacaoRadio[v]
    except Exception:
        pass
    return value

def ler_parametros_interativos():
    console.print(Panel.fit(
        "[bold]Digite parâmetros no formato[/] [cyan]chave=valor[/].\n"
        "Ex.: [green]valor=70[/], [green]cor=quente[/], [green]estacao=JAZZ[/]\n"
        "Pressione [bold]<Enter>[/] sem nada para concluir.",
        title="Parâmetros", border_style="cyan"
    ))
    args: Dict[str, Any] = {}
    while True:
        linha = Prompt.ask("[dim]param[/]", default="")
        if not linha.strip():
            break
        if "=" not in linha:
            console.print("[yellow]Use o formato chave=valor.[/]")
            continue
        k, v = [p.strip() for p in linha.split("=", 1)]
        v = _coerce_enum(_try_int(v))
        args[k] = v
    return args

#--------------------------------------------------------------------------------------------------
# FLUXO DE COMANDOS CLI
#--------------------------------------------------------------------------------------------------
def executar_comando(hub: Hub, disp):
    mostrar_comandos(disp)
    # Hints contextuais para parâmetros aceitos
    try:
        from smart_home.dispositivos.luz import Luz
        from smart_home.dispositivos.radio import Radio
        from smart_home.dispositivos.persiana import Persiana
        from smart_home.dispositivos.cafeteira import CafeteiraCapsulas
    except Exception:
        Luz = Radio = Persiana = CafeteiraCapsulas = object  # fallbacks

    hints = []
    if isinstance(disp, Luz):
        cores = ", ".join(c.name for c in CorLuz)
        hints.append(f"cor={cores}")
        hints.append("valor(brilho)=0..100")
    if isinstance(disp, Radio):
        estacoes = ", ".join(e.name for e in EstacaoRadio)
        hints.append(f"estacao={estacoes}")
        hints.append("valor(volume)=0..100")
    if isinstance(disp, Persiana):
        hints.append("percentual/abertura/valor=0..100 (0 FECHADA, 100 ABERTA, 1-99 PARCIAL)")
    if isinstance(disp, CafeteiraCapsulas):
        hints.append("Sem parâmetros nos comandos atuais")
    if hints:
        t = Table(title="Parâmetros Aceitos", box=box.SIMPLE)
        t.add_column("Formato / Opções", style="cyan")
        for h in hints:
            t.add_row(h)
        console.print(t)
    cmd = Prompt.ask("\n[bold]Comando[/]").strip()
    if cmd not in disp.comandos_disponiveis():
        console.print(":no_entry: [red]Comando inválido para esse dispositivo.[/]")
        return
    args = ler_parametros_interativos()
    try:
        hub.executar_comando(disp.id, cmd, **args)
        console.print(Panel.fit("[bold green]OK[/] comando executado!", border_style="green"))
    except Exception as e:
        console.print(Panel.fit(f"[red]Erro:[/] {e}", border_style="red"))

def alterar_atributo(hub: Hub, disp):
    mostrar_atributos(disp)
    # Hints rápidos sobre atributos editáveis
    try:
        from smart_home.dispositivos.luz import Luz
        from smart_home.dispositivos.radio import Radio
        from smart_home.dispositivos.persiana import Persiana
    except Exception:
        Luz = Radio = Persiana = object
    dicas = []
    if isinstance(disp, Luz):
        dicas.append("brilho: 0..100")
        cores = ", ".join(c.name for c in CorLuz)
        dicas.append(f"cor: {cores}")
    if isinstance(disp, Radio):
        dicas.append("volume: 0..100")
        estacoes = ", ".join(e.name for e in EstacaoRadio)
        dicas.append(f"estacao: {estacoes}")
    if isinstance(disp, Persiana):
        dicas.append("abertura: 0..100 (0 FECHADA,100 ABERTA,1-99 PARCIAL)")
    if dicas:
        t = Table(title="Atributos Editáveis", box=box.SIMPLE)
        t.add_column("Atributo / Faixa", style="magenta")
        for d in dicas:
            t.add_row(d)
        console.print(t)
    k = Prompt.ask("\n[bold]Atributo[/]").strip()
    v = Prompt.ask("[bold]Novo valor[/]").strip()
    v = _coerce_enum(_try_int(v))
    try:
        hub.alterar_atributo(disp.id, k, v)
        console.print(Panel.fit("[bold green]OK[/] atributo alterado!", border_style="green"))
    except Exception as e:
        console.print(Panel.fit(f"[red]Erro:[/] {e}", border_style="red"))


def gerar_relatorio(hub: Hub, cfg_path: Path):
    """Submenu de relatórios funcionais.

    Opções:
      1) Consumo por tomada (Wh)
      2) Tempo total luzes ligadas
      3) Dispositivos mais usados (top 10)
      4) Cafés por dia
      5) Distribuição comandos por tipo
      6) Resumo agregado
    """
    logs_dir = Path("data/logs")
    transitions_csv = logs_dir / "transitions.csv"
    events_csv = logs_dir / "events.csv"
    config_json = cfg_path

    if not transitions_csv.exists():
        console.print(Panel.fit(f"[red]Arquivo não encontrado:[/] {transitions_csv}", border_style="red"))
        return
    # events e config só são obrigatórios em alguns relatórios; config deve existir
    if not config_json.exists():
        console.print(Panel.fit(f"[red]Config não encontrada:[/] {config_json}", border_style="red"))
        return

    grid = Table.grid(padding=1)
    grid.add_column(style="cyan", justify="right")
    grid.add_column(style="white")
    opcoes = [
        ("1", "Consumo por tomada (Wh)"),
        ("2", "Tempo total luzes ligadas"),
        ("3", "Top dispositivos mais usados"),
        ("4", "Cafés por dia"),
        ("5", "Distribuição comandos por tipo"),
        ("6", "Resumo agregado"),
        ("0", "Voltar"),
    ]
    for k, v in opcoes:
        grid.add_row(k, v)
    console.print(Panel(grid, title="[bold]Relatórios[/]", border_style="cyan"))

    escolha = Prompt.ask("[bold]Relatório[/]", choices=[k for k, _ in opcoes], default="0")
    if escolha == "0":
        return

    inicio_str = Prompt.ask("Início (ISO) ou vazio", default="").strip()
    fim_str = Prompt.ask("Fim (ISO) ou vazio", default="").strip()
    from datetime import datetime
    inicio = None
    fim = None
    if inicio_str:
        try:
            inicio = datetime.fromisoformat(inicio_str)
        except Exception:
            console.print("[yellow]Formato de início inválido, ignorando.[/]")
    if fim_str:
        try:
            fim = datetime.fromisoformat(fim_str)
        except Exception:
            console.print("[yellow]Formato de fim inválido, ignorando.[/]")

    try:
        if escolha == "1":  # consumo
            dados = consumo_por_tomada(transitions_csv, config_json, inicio, fim)
            if not dados:
                console.print("[yellow]Sem dados de consumo no período.[/]")
                return
            t = Table(title="Consumo por Tomada (Wh)", box=box.SIMPLE_HEAVY)
            t.add_column("ID", style="cyan")
            t.add_column("Potência W", justify="right")
            t.add_column("Horas Ligada", justify="right")
            t.add_column("Total Wh", justify="right")
            for r in dados:
                t.add_row(r["id_dispositivo"], f"{r['potencia_w']:.0f}", f"{r['horas_ligada']:.3f}", f"{r['total_wh']:.2f}")
            console.print(t)

        elif escolha == "2":  # tempo luzes
            dados = tempo_total_luzes_ligadas(transitions_csv, config_json, inicio, fim)
            if not dados:
                console.print("[yellow]Sem eventos de luz no período.[/]")
                return
            t = Table(title="Tempo Luzes Ligadas", box=box.SIMPLE_HEAVY)
            t.add_column("Luz", style="cyan")
            t.add_column("Segundos", justify="right")
            t.add_column("HH:MM:SS", justify="right")
            for r in dados:
                t.add_row(r["id_dispositivo"], str(r["segundos_ligada"]), r["hhmmss"])
            console.print(t)

        elif escolha == "3":  # top usados
            if not events_csv.exists():
                console.print("[yellow]events.csv ausente; relatório pode ficar incompleto.[/]")
            dados = dispositivos_mais_usados(transitions_csv, events_csv, 10, inicio, fim)
            if not dados:
                console.print("[yellow]Sem eventos para ranking.[/]")
                return
            t = Table(title="Top Dispositivos", box=box.SIMPLE_HEAVY)
            t.add_column("#", justify="right")
            t.add_column("ID", style="cyan")
            t.add_column("Eventos", justify="right")
            for i, (did, qtd) in enumerate(dados, start=1):
                t.add_row(str(i), did, str(qtd))
            console.print(t)

        elif escolha == "4":  # cafés por dia
            dados = cafes_por_dia(transitions_csv, inicio, fim)
            if not dados:
                total = 0
            else:
                total = sum(r["preparos_no_dia"] for r in dados)
            t = Table(title=f"Cafés por Dia (Total={total})", box=box.SIMPLE_HEAVY)
            t.add_column("Data", style="cyan")
            t.add_column("Preparos", justify="right")
            for r in dados:
                t.add_row(r["data"], str(r["preparos_no_dia"]))
            if not dados:
                console.print("[yellow]Nenhum café no período.[/]")
            console.print(t)

        elif escolha == "5":  # dist comandos
            if not events_csv.exists():
                console.print("[red]events.csv não encontrado para este relatório.[/]")
                return
            dados = distribuicao_comandos_por_tipo(events_csv, config_json, inicio, fim)
            if not dados:
                console.print("[yellow]Sem comandos no período.[/]")
                return
            t = Table(title="Distribuição de Comandos por Tipo", box=box.SIMPLE_HEAVY)
            t.add_column("Tipo", style="cyan")
            t.add_column("Qtd", justify="right")
            for tipo, qtd in dados:
                t.add_row(tipo, str(qtd))
            console.print(t)

        elif escolha == "6":  # resumo agregado
            if not events_csv.exists():
                console.print("[yellow]events.csv ausente; algumas métricas podem faltar.[/]")
            data = resumo_relatorios(transitions_csv, events_csv, config_json, inicio, fim)
            # consumo
            t1 = Table(title="Consumo Tomadas", box=box.SIMPLE)
            t1.add_column("ID")
            t1.add_column("Wh", justify="right")
            for r in data["consumo_tomadas"]:
                if r["id_dispositivo"] == "__TOTAL__":
                    continue
                t1.add_row(r["id_dispositivo"], f"{r['total_wh']:.2f}")
            console.print(t1)
            # top uso
            t2 = Table(title="Top Uso", box=box.SIMPLE)
            t2.add_column("ID")
            t2.add_column("Eventos", justify="right")
            for did, qtd in data["top_uso"]:
                t2.add_row(did, str(qtd))
            console.print(t2)
            # cafés
            console.print(Panel.fit(f"Cafés preparados: [bold]{data['cafes_preparados']}[/]", border_style="green"))
            # dist comandos
            t3 = Table(title="Comandos por Tipo", box=box.SIMPLE)
            t3.add_column("Tipo")
            t3.add_column("Qtd", justify="right")
            for tipo, qtd in data["dist_comandos_tipo"]:
                t3.add_row(tipo, str(qtd))
            console.print(t3)
            # luzes tempo
            t4 = Table(title="Tempo Luzes", box=box.SIMPLE)
            t4.add_column("Luz")
            t4.add_column("Segundos", justify="right")
            for r in data["luzes_tempo"]:
                t4.add_row(r["id_dispositivo"], str(r["segundos_ligada"]))
            console.print(t4)
    except Exception as e:
        console.print(Panel.fit(f"[red]Erro gerando relatório:[/] {e}", border_style="red"))

def adicionar_dispositivo(hub: Hub):
    tipos = ", ".join(t.value for t in TipoDeDispositivo)
    console.print(Panel.fit(f"Tipos suportados: [bold]{tipos}[/]", title="Adicionar", border_style="cyan"))

    tipo_str = Prompt.ask("tipo").strip().upper()
    try:
        tipo = TipoDeDispositivo[tipo_str]
    except Exception:
        console.print("[red]Tipo inválido.[/]")
        return

    id_ = Prompt.ask("id (sem espaços)").strip()
    if not id_ or hub.obter(id_):
        console.print("[red]ID inválido ou já usado.[/]")
        return
    nome = Prompt.ask("nome").strip()

    try:
        if tipo == TipoDeDispositivo.PORTA:
            hub.adicionar("PORTA", id_, nome)

        elif tipo == TipoDeDispositivo.LUZ:
            brilho = _try_int(Prompt.ask("brilho (0-100) [0]", default="0"))
            cor = _coerce_enum(Prompt.ask("cor [QUENTE/FRIA/NEUTRA] [NEUTRA]", default="NEUTRA"))
            hub.adicionar("LUZ", id_, nome, brilho=brilho, cor=cor.name if isinstance(cor, CorLuz) else str(cor))

        elif tipo == TipoDeDispositivo.TOMADA:
            pot = _try_int(Prompt.ask("potencia_w (>=0) [1000]", default="1000"))
            hub.adicionar("TOMADA", id_, nome, potencia_w=pot)

        elif tipo == TipoDeDispositivo.CAFETEIRA:
            hub.adicionar("CAFETEIRA", id_, nome)

        elif tipo == TipoDeDispositivo.RADIO:
            vol = _try_int(Prompt.ask("volume (0-100) [0]", default="0"))
            est = _coerce_enum(Prompt.ask("estacao (MPB/ROCK/JAZZ/...) [MPB]", default="MPB"))
            hub.adicionar("RADIO", id_, nome,
                          volume=vol, estacao=est.name if isinstance(est, EstacaoRadio) else str(est))

        elif tipo == TipoDeDispositivo.PERSIANA:
            ab = _try_int(Prompt.ask("abertura_inicial (0-100) [0]", default="0"))
            hub.adicionar("PERSIANA", id_, nome, abertura=ab)

        console.print(Panel.fit(f"[bold green]OK[/] dispositivo [cyan]{id_}[/] adicionado.", border_style="green"))
    except Exception as e:
        console.print(Panel.fit(f"[red]Erro criando dispositivo:[/] {e}", border_style="red"))

def remover_dispositivo(hub: Hub):
    listar_dispositivos(hub)
    id_ = Prompt.ask("\n[bold]ID do dispositivo a remover[/]").strip()
    try:
        hub.remover(id_)
        console.print(Panel.fit(f"[bold yellow]Removido[/] {id_}", border_style="yellow"))
    except Exception as e:
        console.print(Panel.fit(f"[red]Erro:[/] {e}", border_style="red"))

#--------------------------------------------------------------------------------------------------
# MAIN CLI
#--------------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Smart Home Hub (CLI)")
    parser.add_argument("--config", type=str, default="data/config.json", help="Arquivo de configuração JSON")
    args = parser.parse_args()
    cfg_path = Path(args.config)

    hub = Hub()
    
    # carrega config se existir; senão, defaults
    try:
        hub.carregar_config(cfg_path)
        console.print(Panel.fit(f"[bold green]Config carregada de[/] [cyan]{cfg_path}[/]", border_style="green"))
    except Exception:
        hub.carregar_defaults()
        console.print(Panel.fit("[yellow]Usando configuração padrão.[/]", border_style="yellow"))


    # Observers
    hub.registrar_observer(ConsoleObserver())
    hub.registrar_observer(CsvObserverTransitions(Path("data/logs/transitions.csv")))  # transições estado

    # CSV geral:
    hub.registrar_observer(CsvObserverEventos(Path("data/logs/events.csv")))
    # comandos (opcional para análises futuras)
    hub.registrar_observer(CsvObserverComandos(Path("data/logs/commands.csv")))
    
    header()

    while True:
        mostrar_menu()
        opcao = Prompt.ask("[bold]Selecione[/]", choices=[str(i) for i in range(1, 11)], default="1")

        if opcao == "1":
            listar_dispositivos(hub)

        elif opcao == "2":
            disp = escolher_dispositivo(hub)
            if disp:
                mostrar_atributos(disp)

        elif opcao == "3":
            disp = escolher_dispositivo(hub)
            if disp:
                executar_comando(hub, disp)

        elif opcao == "4":
            disp = escolher_dispositivo(hub)
            if disp:
                alterar_atributo(hub, disp)

        elif opcao == "5":
            executar_rotina_cli(hub)

        elif opcao == "6":
            gerar_relatorio(hub, cfg_path)

        elif opcao == "7":
            try:
                hub.salvar_config(cfg_path)
                console.print(Panel.fit(f"[bold green]Configuração salva em[/] [cyan]{cfg_path}[/]", border_style="green"))
            except Exception as e:
                console.print(Panel.fit(f"[red]Erro salvando config:[/] {e}", border_style="red"))

        elif opcao == "8":
            adicionar_dispositivo(hub)

        elif opcao == "9":
            remover_dispositivo(hub)

        elif opcao == "10":
            if Confirm.ask("Deseja salvar a configuração antes de sair?", default=True):
                try:
                    hub.salvar_config(cfg_path)
                    console.print(Panel.fit(f"[bold green]Configuração salva em[/] [cyan]{cfg_path}[/]", border_style="green"))
                except Exception as e:
                    console.print(Panel.fit(f"[red]Erro salvando config:[/] {e}", border_style="red"))
            console.print("\n[bold green]💾 Encerrando Hub...\n\n🌟 Até mais!🌟\n[/]")
            break

if __name__ == "__main__":
    main()
