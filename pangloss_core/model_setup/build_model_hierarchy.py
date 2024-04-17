import typing

if typing.TYPE_CHECKING:
    from pangloss_core.models import BaseNode

from pangloss_core.model_setup.model_manager import ModelManager


def build_model_hierarchy(model: type["BaseNode"]):
    subclass_hierarchy = {}
    for subclass in model.__subclasses__():
        subclass_hierarchy[subclass.__name__] = build_model_hierarchy(subclass)
    return subclass_hierarchy


def recursive_get_subclasses(model: type["BaseNode"]):

    subclasses = []
    for subclass in model.__subclasses__():
        subclasses.append(subclass)
        subclasses += recursive_get_subclasses(subclass)

    return subclasses


def build_model_subclass_lists():
    subclass_lists = {}
    for model in ModelManager._registered_models:
        subclass_lists[model.__name__] = recursive_get_subclasses(model)
    return subclass_lists


def build_top_level_classes_list():
    from pangloss_core.models import BaseNode

    return [subclass.__name__ for subclass in BaseNode.__subclasses__()]
