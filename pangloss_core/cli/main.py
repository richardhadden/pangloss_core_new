
import subprocess
import typing
import os
from pathlib import Path


from cookiecutter.exceptions import OutputDirExistsException
from cookiecutter.main import cookiecutter
from rich import print
from rich.panel import Panel


import typer


from pangloss_core.model_setup.model_manager import ModelManager
from pangloss_core.users import user_cli
from pangloss_core.types_generation import type_generation_cli
from pangloss_core.translation import translation_cli
from pangloss_core.indexes import install_indexes_and_constraints
from pangloss_core.database import initialise_database_driver
from pangloss_core.initialisation import get_project_settings

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates")

cli_app = typer.Typer(
    add_completion=False,
    help="Pangloss CLI",
    name="Pangloss CLI",
)

cli_app.add_typer(user_cli, name="users")
cli_app.add_typer(type_generation_cli, name="types")
cli_app.add_typer(translation_cli, name="translation")

@cli_app.command()
def registercli(project: typing.Annotated[Path, typer.Option(exists=True, help="The path of the project to run")]):
    print(project)
    
    
@cli_app.command(help="Create new project")
def createapp(app_name: typing.Annotated[str, typer.Argument()]):
    context = {"folder_name": app_name}
    try:
        cookiecutter(
            os.path.join(TEMPLATES_DIR, "app"),
            extra_context=context,
            no_input=True,
        )
    except OutputDirExistsException:
        print(
            "\n",
            Panel(
                f"[bold red]App creation failed:[/bold red] Folder [bold blue]{context["folder_name"]}[/bold blue] already exists.",
                title="Creating Pangloss app",
                subtitle="😡",
                subtitle_align="right",
            ),
            "\n",
        )
    else:

        print(
            "\n",
            Panel(
                (
                    f"[bold green]App successfully created:[/bold green] Pangloss app [bold blue]{context["folder_name"]}[/bold blue] created successfully!"
                    f'\n\nGo to your project [blue]settings.py[/blue] and add [blue]"{context["folder_name"]}"[/blue] to [blue]Settings.INSTALLED_APPS[/blue]:'
                    f"\n\nThen go to [blue]{context["folder_name"]}/models.py[/blue] to add some models"
                ),
                title="Creating Pangloss project",
                subtitle="🍹",
                subtitle_align="right",
            ),
            "\n",
        )


@cli_app.command(help="Create new project")
def createproject(project_name: typing.Annotated[str, typer.Argument()]):
    context = {"folder_name": project_name}
    try:
        cookiecutter(
            os.path.join(TEMPLATES_DIR, "project"),
            extra_context=context,
            no_input=True,
        )
    except OutputDirExistsException:
        print(
            "\n",
            Panel(
                f"[bold red]Project creation failed:[/bold red] Folder [bold blue]{context["folder_name"]}[/bold blue] already exists.",
                title="Creating Pangloss project",
                subtitle="😡",
                subtitle_align="right",
            ),
            "\n",
        )
    else:
        print(
            "\n",
            Panel(
                (
                    f"[bold green]Project successfully created:[/bold green] Pangloss project [bold blue]{context["folder_name"]}[/bold blue] created successfully!"
                    f"\n\nGo to [blue]{context["folder_name"]}/settings.py[/blue] to configure the database"
                    f"\n\nThen run [deep_pink4]pangloss run {context["folder_name"]}[/deep_pink4] to run the development server"
                ),
                title="Creating Pangloss project",
                subtitle="🍹",
                subtitle_align="right",
            ),
            "\n",
        )


@cli_app.command(help="Does Nothing")
def start_app(name: str):
    print("[green]Hello world![/green]")



Project = typing.Annotated[Path, typer.Option(exists=True, help="The path of the project to run")]

@cli_app.command(help="Starts development server")
def run(project: Project):
    settings = get_project_settings(str(project))        
    reload_watch_list = ["--reload-dir", project]
    for installed_app in settings.INSTALLED_APPS:
        m = __import__(installed_app)

        reload_watch_list.append("--reload-dir")
        reload_watch_list.append(m.__path__[0])

    panel = Panel(
        (
            f"Autoreloading on!\n\n   Watching project: [bold green]{str(project)}[/bold green]\n   "
            f"Watching installed apps: {", ".join(f"[bold blue]{a}[/bold blue]" for a in settings.INSTALLED_APPS)}"
        ),
        title="📜 Starting Pangloss development server!",
        subtitle="(tally ho!)",
        subtitle_align="right",
    )
    print("\n\n", panel, "\n\n")
    sc_command = ["uvicorn", f"{str(project)}.main:app", "--lifespan", "on", "--reload", *reload_watch_list]
    subprocess.call(sc_command)

@cli_app.command()
def setup_database(project: Project):
    install_indexes_and_constraints()
    

    

def cli():
    """Initialises the Typer-based CLI by checking installed app folders
    for a cli.py file and finding Typer apps inside."""
    import sys  
   
    if "--project" in sys.argv:
        project_path = sys.argv[sys.argv.index("--project") + 1]
        if project_path:
            settings = get_project_settings(project_path)
            initialise_database_driver(settings)
            for app in settings.INSTALLED_APPS:
                __import__(f"{app}.models")
                try:
                    m = __import__(f"{app}.cli")
                    c = m.cli.__dict__.get("cli")
                    if c:
                        cli_app.add_typer(c, name=c.info.name)
                except ModuleNotFoundError:
                    pass
            
            ModelManager.initialise_models(depth=3)
    return cli_app()
