import inspect
import types
import typing

import typing_inspect

from pangloss_core.exceptions import PanglossConfigError
from pangloss_core.model_setup.relation_to import ReifiedRelation

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


def __setup_model_instantiates_trait__(
    cls: (
        type["AbstractBaseNode"]
        | type["BaseHeritableTrait"]
        | type["BaseNonHeritableTrait"]
    ),
) -> bool:
    from pangloss_core.model_setup.base_node_definitions import (
        BaseNonHeritableTrait,
        BaseHeritableTrait,
    )

    # print(cls)
    """Determines whether a Node model is a direct instantiation of a trait."""
    return (
        issubclass(cls, (BaseNonHeritableTrait, BaseHeritableTrait))
        and cls.__pg_is_subclass_of_trait__()
    )


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
    from pangloss_core.model_setup.base_node_definitions import (
        BaseNonHeritableTrait,
        BaseHeritableTrait,
    )

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
    elif (
        inspect.isclass(classes)
        and issubclass(
            classes,
            BaseNonHeritableTrait,  # type: ignore
        )
        and __setup_model_instantiates_trait__(classes)
    ):
        for cl in classes.__pg_real_types_with_trait__:
            concrete_node_classes += list(_get_concrete_node_classes(cl))
    elif (
        inspect.isclass(classes)
        and issubclass(classes, BaseHeritableTrait)
        and __setup_model_instantiates_trait__(classes)
    ):
        for cl in _get_all_subclasses(classes, include_abstract=include_abstract):
            concrete_node_classes += list(_get_concrete_node_classes(cl))

    else:  # Classes is a single class
        if include_subclasses:
            subclasses = _get_all_subclasses(classes, include_abstract=include_abstract)
            concrete_node_classes.extend(subclasses)
        if include_abstract or not classes.__abstract__:  # type: ignore
            concrete_node_classes.append(classes)
    return set(concrete_node_classes)


def is_relation_field(
    model: type["AbstractBaseNode"], field_name: str, annotation: typing.Any
) -> bool:
    from pangloss_core.model_setup.base_node_definitions import (
        AbstractBaseNode,
        BaseHeritableTrait,
        BaseNonHeritableTrait,
    )
    from pangloss_core.model_setup.relation_to import ReifiedRelation

    def is_relateable_type(t):
        return inspect.isclass(t) and issubclass(
            t,
            (
                AbstractBaseNode,
                ReifiedRelation,
                BaseHeritableTrait,
                BaseNonHeritableTrait,
            ),
        )

    # If there is a non-wrapped type (i.e. not Union or Optional), check if it's relatable
    if is_relateable_type(annotation):
        return True

    if typing_inspect.is_union_type(annotation):

        relatable_types = [
            is_relateable_type(t) for t in typing_inspect.get_args(annotation)
        ]

        # If it's a union type, every contained type must be a relatable type
        if all(relatable_types):
            return True

        # If a contained type is None, this is not allowed
        if any(relatable_types) and any(
            t is types.NoneType for t in typing_inspect.get_args(annotation)
        ):
            raise PanglossConfigError(
                f"Error with model {model.__name__}.{field_name}: typing.Union[<BaseBode>, None] is not allowed for relations. Use annotated_types.MinLen(0) as an annotation instead"
            )

        # If some contained type is relatable, and another a literal type (str, int, etc.), this is not allowed
        if any(relatable_types) and not all(relatable_types):
            raise PanglossConfigError(
                "Error with model field {model.__name__}.{field_name}: Cannot mix relations to BaseNode/ReifiedRelation types and literal types"
            )

    # Check that a relation-type is not surrounded by typing.Optional
    if typing_inspect.is_optional_type(annotation):
        for ta in typing_inspect.get_args(annotation):
            if ta is types.NoneType:
                continue
            for ann_t in typing_inspect.get_args(ta):
                if is_relateable_type(ann_t):
                    raise PanglossConfigError(
                        f"Error with model {model.__name__}.{field_name}: typing.Optional is not allowed for relations. Use annotated_types.MinLen(0) as an annotation instead"
                    )

    return False


def get_subclasses(r):
    subclasses = []
    for sc in r.__subclasses__():
        subclasses.append(sc)
        subclasses = [*subclasses, *get_subclasses(sc)]
    return subclasses


def get_subclasses_of_reified_relations(annotation):
    from pangloss_core.model_setup.base_node_definitions import AbstractBaseNode
    from pangloss_core.model_setup.relation_to import ReifiedRelation

    # If it is a generic type...
    if origin_type := annotation.__pydantic_generic_metadata__.get("origin", False):
        subclasses = set()
        # ... get all the subclasses of the generic type...
        for sc in get_subclasses(origin_type):
            origin = sc.__pydantic_generic_metadata__.get("origin", False)
            args = sc.__pydantic_generic_metadata__.get("args", False)
            # ... and, checking the wrapped type is something real...
            if (
                args
                and inspect.isclass(args[0])
                and issubclass(args[0], (AbstractBaseNode, ReifiedRelation))
            ):
                # ...get the subclasses of that type which are generic (i.e. have "parameters")
                subclasses.add(sc)
                # ... get all the subclasses of that, and construct types out of that
                # by applying the original arg
                for ssc in get_subclasses(origin):
                    if ssc.__pydantic_generic_metadata__.get("parameters"):
                        subclasses.add(ssc[args[0]])
        return subclasses
    else:
        # Otherwise, it's a non-generic type; just get the subclasses and itself
        return set([annotation, *get_subclasses(annotation)])
