import inspect
import types
import typing

if typing.TYPE_CHECKING:
    from pangloss_core.model_setup.base_node_definitions import (
        AbstractBaseNode,
        BaseHeritableTrait,
        BaseNonHeritableTrait,
    )


def _get_all_subclasses(
    cls, include_abstract: bool = False
) -> set[type["AbstractBaseNode"]]:
    subclasses = []
    for subclass in cls.__subclasses__():
        if not subclass.__abstract__ or include_abstract:
            subclasses += [subclass, *_get_all_subclasses(subclass)]
        else:
            subclasses += _get_all_subclasses(subclass)
    return set(subclasses)


def __setup_model_instantiates_abstract_trait__(
    cls: type["AbstractBaseNode"] | type["BaseHeritableTrait"],
) -> bool:
    from pangloss_core.model_setup.base_node_definitions import BaseNonHeritableTrait

    # print(cls)
    """Determines whether a Node model is a direct instantiation of a trait."""
    return issubclass(cls, BaseNonHeritableTrait) and cls.__pg_is_subclass_of_trait__()


def _get_concrete_node_classes(
    classes: (
        type["AbstractBaseNode"]
        | type["BaseNonHeritableTrait"]
        | type["BaseHeritableTrait"]
        | types.UnionType
        | typing.Iterable[
            type["AbstractBaseNode"]
            | type["BaseNonHeritableTrait"]
            | type["BaseHeritableTrait"]
            | type[types.UnionType]
        ]
    ),
    include_subclasses: bool = False,
    include_abstract: bool = False,
) -> set[type["AbstractBaseNode"]]:
    """Given a BaseNode, AbstractTrait or Union type, returns set of concrete BaseNode types.

    By default, does not include subclasses of types or abstract classes.
    """
    from pangloss_core.model_setup.base_node_definitions import BaseNonHeritableTrait

    concrete_node_classes = []
    if unpacked_classes := typing.get_args(classes):
        for cl in unpacked_classes:
            concrete_node_classes += list(
                _get_concrete_node_classes(
                    cl,
                    include_subclasses=include_subclasses,
                    include_abstract=include_abstract,
                )
            )
    elif isinstance(classes, typing.Iterable):
        for cl in classes:
            concrete_node_classes += list(
                _get_concrete_node_classes(
                    cl,
                    include_subclasses=include_subclasses,
                    include_abstract=include_abstract,
                )
            )
    elif issubclass(
        classes,  # type: ignore
        BaseNonHeritableTrait,  # type: ignore
    ) and __setup_model_instantiates_abstract_trait__(
        classes  # type: ignore
    ):
        for cl in classes.__pg_real_types_with_trait__:
            concrete_node_classes += list(_get_concrete_node_classes(cl))

    else:  # Classes is a single class
        if include_subclasses:
            subclasses = _get_all_subclasses(classes, include_abstract=include_abstract)
            concrete_node_classes.extend(subclasses)
        if include_abstract or not classes.__abstract__:  # type: ignore
            concrete_node_classes.append(classes)
    return set(concrete_node_classes)


def is_relation_field(annotation: typing.Any) -> bool:
    from pangloss_core.model_setup.base_node_definitions import AbstractBaseNode
    from pangloss_core.model_setup.relation_to import ReifiedRelation

    print(annotation)

    if inspect.isclass(annotation) and issubclass(annotation, AbstractBaseNode):
        return True

    if inspect.isclass(annotation) and issubclass(annotation, ReifiedRelation):
        return True

    return False
