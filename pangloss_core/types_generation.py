import os
from pathlib import Path
import typing
import typing_inspect
import inspect

import annotated_types
import typer
from pangloss_core.indexes import IndexAnnotation
from pangloss_core.exceptions import PanglossCLIError

type_generation_cli = typer.Typer(name="types")


class Union(list):
    def __repr__(self):
        return f"Union({super().__repr__()[1:][:-1]})"


class Literal(str):
    def __repr__(self):
        return f"Literal({super().__repr__()})"


def parse(ann):
    """Parses a type annotation to a nested object"""
    if typing_inspect.is_literal_type(ann):
        return Literal(typing_inspect.get_args(ann)[0])
    if typing.get_origin(ann) is typing.Annotated:
        return {
            **parse(typing_inspect.get_args(ann)[0]),
            "type": typing.get_origin(typing_inspect.get_origin(ann))
            or typing_inspect.get_origin(ann),
            "annotations": list(typing.get_args(ann)[1:]),
        }
    if typing_inspect.is_union_type(ann):
        return Union(parse(a) for a in typing_inspect.get_args(ann))

    if typing_inspect.is_generic_type(ann):
        return {
            "type": typing_inspect.get_origin(ann)
            or typing_inspect.get_origin(typing.get_args(ann)[0])
            or typing_inspect.get_origin(ann),
            "inner": parse(typing.get_args(ann)[0]),
        }
    return {"type": ann}


def primitive_types(t) -> str:
    """Converts Pydantic primitive types to Valibot validators"""
    match t:
        case {"type": pydantic.HttpUrl}:
            return "v.string([v.url()])"
        case {"type": types.NoneType}:
            return "v.null_()"
        case {"type": uuid.UUID}:
            return "v.string([v.uuid()])"
        case {"type": field_types.str}:
            if vs := t.get("annotations", None):
                return f"v.string([{",".join(parse_validators(v) for v in vs)}])"
            return "v.string()"
        case {"type": datetime.date}:
            return "v.string([v.isoDate()])"
        case {"type": datetime.datetime}:
            return "v.string([v.isoDateTime()])"
        case {"type": field_types.int}:
            if vs := t.get("annotations", None):
                return f"v.number([v.integer(), {",".join(parse_validators(v) for v in vs)}])"
            return "v.number([v.integer()])"
        case {"type": field_types.float}:
            if vs := t.get("annotations", None):
                return f"v.number([v.decimal(), {",".join(parse_validators(v) for v in vs)}])"
            return "v.number([v.decimal()])"
        case {"type": c} if issubclass(c, BaseNode):
            return f"v.lazy(() => {c.__name__}Validator)"
        case {"type": c } if issubclass(c, BaseNodeReference):
            if c not in already_built_reference_types:
                already_built_reference_types.add(c)
                extra_reference_types_to_write[c] = build_valibot_item_for_model(c)
            return f"{c.__name__}Validator"
        case {"type": c} if issubclass(c, RelationPropertiesModel):
           
            return f"""v.object({{{
                ",".join(f"\n\t{name}: {decl}" for name, decl in build_valibot_item_for_model(c).items()) 
            }}})"""
        case _:
            return "v.any()"
            return "Missing!"

def parse_validators(ann):
    """Converts typing.Annotated validators to additional Valibot validators"""
    match ann:
        case annotated_types.MaxLen(n):
            return f"v.maxLength({n})"
        case annotated_types.MinLen(n):
            return f"v.minLength({n})"
        case annotated_types.Gt(n):
            return f"v.minValue({n}), v.notValue({n})"
        case annotated_types.Lt(n):
            return f"v.maxValue({n}), v.notValue({n})"
        case annotated_types.Ge(n):
            return f"v.minValue({n})"
        case annotated_types.Le(n):
            return f"v.maxValue({n})"
        case annotated_types.Len(l, u):
            return f"v.minLength({l}), v.maxLength({u})"
        case a if (inspect.isclass(a) and issubclass(a, IndexAnnotation)) or isinstance(a, IndexAnnotation):
            return ""
        case _:
            raise PanglossInterfaceConfigError(f"Cannot build interface validator for annotation {ann}")

def to_python_stub(td):
    """Converts parsed nested model to Valibot validator objects"""
    match td:
        case Union(items):
            union_items = " | ".join(to_python_stub(i) for i in items)
            return f"typing.Union[{union_items})"
        case Literal(value):
            return f'typing.Literal["{value}"]'
        case {"type": field_types.list}:
            return f"v.array({to_valibot(td.get("inner", ""))}{f", [{",".join(parse_validators(t) for t in td.get("annotations", []))}]" if td.get("annotations", None) else ""})"
        case t:
            return primitive_types(t)


@type_generation_cli.command(name="generate")
def generate(application_path: Path):
    # print(application_path.absolute())

    import importlib.util
    import sys

    app_name = str(application_path).split("/")[-1]

    spec = importlib.util.spec_from_file_location(
        f"{app_name}.models",
        os.path.join(application_path.absolute(), "models.py"),
    )
    if spec and spec.loader:
        try:
            models = importlib.util.module_from_spec(spec)
            sys.modules[f"{app_name}.models"] = models
            spec.loader.exec_module(models)
        except Exception:
            raise PanglossCLIError(
                f"Something went wrong identifying the models.py file in {app_name}"
            )

    from pangloss_core.model_setup.model_manager import ModelManager

    # stub_generator()

    with open(os.path.join(application_path.absolute(), "models.pyi"), "w") as f:
        f.write("from pangloss_core.models import BaseNode\n\n")
        ModelManager.initialise_models()
        for model in ModelManager._registered_models:
            f.write(f"class {model.__name__}(BaseNode):\n")
            for field_name, field in model.model_fields.items():
                print(parse(field.annotation))
                # f.write(f"\t{field_name}: {field.annotation.__name__}\n")

            f.write("\n")
