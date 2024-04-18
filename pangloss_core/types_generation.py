import os
from pathlib import Path
import typing
import sys
import importlib.util

import typer

type_generation_cli = typer.Typer(name="types")


def import_project_file_of_name(folder_name: str, file_name: str):
    sys.path.append(os.getcwd())

    MODULE_PATH = os.path.join(folder_name, file_name)
    MODULE_NAME = folder_name
    spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)

    if spec and spec.loader:
        try:
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            p = importlib.import_module(folder_name, package=folder_name)
        except FileNotFoundError:
            return None
        return p


def get_project_settings(project_name: str):
    p = import_project_file_of_name(folder_name=project_name, file_name="settings.py")
    if not p:
        raise Exception(f'Project "{project_name}" not found"')
    return getattr(p, "settings")


@type_generation_cli.command(name="generate")
def generate(application_path: Path):
    # print(application_path.absolute())
    sys.path.append("tests")
    __import__("testing_application")
