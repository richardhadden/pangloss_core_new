from collections import defaultdict
import json
import os
from pathlib import Path
import re
import typing

import patchdiff
from patchdiff.pointer import Pointer
from pluralizer import Pluralizer

from pangloss_core.settings import BaseSettings


if typing.TYPE_CHECKING:
    from pangloss_core.models import BaseNode


pluralizer = Pluralizer()


def infinite_defaultdict():
    return defaultdict(infinite_defaultdict)


def to_space_separated_string(string: str) -> str:
    return re.sub(r"((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))", r" \1", string)


def create_model_translation_dict(
    model: "type[BaseNode]", langs: list[str], default_lang: str = "en"
):

    translation = infinite_defaultdict()
    for lang_ in langs:
        lang = lang_.upper()
        if lang_ == "en":
            translation["__model"][lang]["verbose_name"] = to_space_separated_string(
                model.__name__
            )
            translation["__model"][lang]["verbose_name_plural"] = (
                to_space_separated_string(pluralizer.pluralize(model.__name__))
            )
            translation["__model"][lang]["description"] = model.__doc__ or ""
        else:
            translation["__model"][lang]["verbose_name"] = "VerboseNameInGerman"
            translation["__model"][lang][
                "verbose_name_plural"
            ] = "SomeVerbosePluralNameInGerman"
            translation["__model"][lang]["description"] = ""

    return translation


def decode_pointer(path):
    if path == "/":
        return []
    else:
        return [i for i in path.split("/") if i]


def build_or_patch_translation_file(project: Path, settings: type[BaseSettings]):
    from pangloss_core.model_setup.model_manager import ModelManager

    generated_translation_dict = {}

    for model in ModelManager._registered_models:

        generated_translation_dict[model.__name__] = create_model_translation_dict(
            model, settings.INTERFACE_LANGUAGES, settings.DEFAULT_INTERFACE_LANGUAGE
        )

    try:
        with open(os.path.join(project, ".translation-model-ops.json")) as f:
            model_ops: list[dict] = json.loads(f.read())
    except FileNotFoundError:
        model_ops = []

    try:
        with open(os.path.join(project, ".translation-manual-ops.json")) as f:
            manual_ops: list[dict] = json.loads(f.read())
    except FileNotFoundError:
        manual_ops = []

    try:
        with open(os.path.join(project, "translation.json")) as f:
            edited_version = json.loads(f.read())
    except FileNotFoundError:
        edited_version = None

    if model_ops and edited_version:

        manual_paths = {op["path"] for op in manual_ops if op["op"] == "replace"}
        manual_ops = [
            {**op, "path": Pointer(decode_pointer(op["path"]))} for op in manual_ops
        ]
        change_ops = [
            {**op, "path": Pointer(decode_pointer(op["path"]))}
            for op in model_ops
            if op["path"] not in manual_paths
        ]

        try:
            with open(os.path.join(project, ".translation-base.json")) as f:
                base = json.loads(f.read())
        except FileNotFoundError:
            base = None

        base_fast_forwarded_to_model = (
            patchdiff.apply(base, change_ops) if change_ops else base
        )

        base_fast_forward_to_manual = patchdiff.apply(
            base_fast_forwarded_to_model, manual_ops
        )
        model_update_ops, _ = patchdiff.diff(
            base_fast_forwarded_to_model, generated_translation_dict
        )

        model_update_deletions = [
            op["path"] for op in model_update_ops if op["op"] == "remove"
        ]

        manual_update_ops = [
            op
            for op in patchdiff.diff(base_fast_forward_to_manual, edited_version)[0]
            if op["path"] not in {o["path"] for o in model_update_ops}
        ]

        manual_update_ops = [
            op for op in manual_update_ops if op["path"] not in model_update_deletions
        ]

        model_ops.extend(model_update_ops)
        manual_ops.extend(manual_update_ops)

        remove_update_ops = [op for op in model_update_ops if op["op"] == "remove"]
        other_update_ops = [op for op in model_update_ops if op["op"] != "remove"]

        new_version = patchdiff.apply(base_fast_forward_to_manual, other_update_ops)
        new_version = patchdiff.apply(new_version, manual_update_ops)
        new_version = patchdiff.apply(new_version, remove_update_ops)

        with open(os.path.join(project, "translation.json"), "w") as f:
            f.write(json.dumps(new_version, indent=4))

        with open(os.path.join(project, ".translation-model-ops.json"), "w") as f:
            f.write(patchdiff.to_json(model_ops, indent=4))

        with open(os.path.join(project, ".translation-manual-ops.json"), "w") as f:
            f.write(patchdiff.to_json(manual_ops, indent=4))

    else:
        base_ops, _ = patchdiff.diff({}, generated_translation_dict)

        with open(os.path.join(project, "translation.json"), "w") as f:
            f.write(json.dumps(generated_translation_dict, indent=4))

        with open(os.path.join(project, ".translation-base.json"), "w") as f:
            f.write(json.dumps(generated_translation_dict, indent=4))

        with open(os.path.join(project, ".translation-model-ops.json"), "w") as f:
            f.write(patchdiff.to_json(base_ops))

        with open(os.path.join(project, ".translation-manual-ops.json"), "w") as f:
            f.write(patchdiff.to_json(base_ops))
