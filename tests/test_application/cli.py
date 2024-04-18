from typer import Typer

from pangloss_core.cli.main import Project

cli = Typer(name="test_application")

# All commands should specify a "project" argument, so that the correct settings
# can be loaded

@cli.command()
def test(project: Project):
    print("Greetings from Pangloss app: test_application")