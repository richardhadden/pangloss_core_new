import dataclasses
import inspect
import types
import typing

import annotated_types

from pangloss_core.model_setup.setup_utils import _get_concrete_node_classes
from pangloss_core.exceptions import PanglossConfigError


if typing.TYPE_CHECKING:
    from pangloss_core.model_setup.base_node_definitions import (
        AbstractBaseNode,
        BaseHeritableTrait,
        BaseNonHeritableTrait,
    )
    from pangloss_core.model_setup.reference_node_base import BaseNodeReference
    from relation_to import ReifiedRelation
    from relation_properties_model import RelationPropertiesModel


@dataclasses.dataclass
class RelationConfig:
    """Provides configuration for a `RelationTo` type, e.g.:

    ```
    class Person:
        pets: RelationTo[Pet, RelationConfig(reverse_name="owned_by")]
    ```
    """

    reverse_name: str
    relation_model: typing.Optional[type["RelationPropertiesModel"]] = None
    validators: typing.Optional[typing.Sequence[annotated_types.BaseMetadata]] = None
    subclasses_relation: typing.Optional[str] = None
    create_inline: bool = False
    edit_inline: bool = False
    delete_related_on_detach: bool = False

    def __hash__(self):

        return hash(
            repr(self.reverse_name)
            + repr(self.relation_model)
            + repr(self.validators)
            + repr(self.subclasses_relation)
            + repr(self.create_inline)
            + repr(self.edit_inline)
            + repr(self.delete_related_on_detach)
        )


@dataclasses.dataclass
class _RelationConfigInstantiated:
    """Internal version of RelationConfig for storing the config on
    relationship declaration. Avoids exposing the `relation_to_base` variable
    as something settable by user. Redeclares variables
    instead of inheriting from RelationConfig to avoid issue with ordering variables
    with default-less variables first, which is impossible when inheriting!"""

    reverse_name: str
    relation_to_base: type["AbstractBaseNode"]
    relation_model: typing.Optional[type["RelationPropertiesModel"]] = None
    validators: typing.Optional[typing.Sequence[annotated_types.BaseMetadata]] = None
    subclasses_relation: typing.Optional[str] = None
    relation_labels: set[str] = dataclasses.field(default_factory=set)
    create_inline: bool = False
    edit_inline: bool = False
    delete_related_on_detach: bool = False


@dataclasses.dataclass
class _OutgoingRelationDefinition:
    """Class containing the definition of an outgoing node:

    - `target_base_class: type[BaseNode]`: the target ("to") class of the relationship
    - `target_reference_class: type[BaseNodeReference]`: the reference class of the target class
    - `relation_config: _PG_RelationshipConfigInstantiated`: the configuration model for the relationship
    - `origin_base_class: type[BaseNode]`: the origin ("from") class of the relationship
    """

    target_base_class: type["AbstractBaseNode"]
    target_reference_class: type["BaseNodeReference"]
    relation_config: _RelationConfigInstantiated
    origin_base_class: type["AbstractBaseNode"]

    def __hash__(self):
        return hash(
            repr(self.origin_base_class)
            + repr(self.target_base_class)
            + repr(self.relation_config)
        )


@dataclasses.dataclass
class _OutgoingReifiedRelationDefinition:
    """Class containing the definition of an outgoing node:

    - `target_base_class: type[BaseNode]`: the target ("to") class of the relationship
    - `target_reference_class: type[BaseNodeReference]`: the reference class of the target class
    - `relation_config: _PG_RelationshipConfigInstantiated`: the configuration model for the relationship
    - `origin_base_class: type[BaseNode]`: the origin ("from") class of the relationship
    """

    target_base_class: type["AbstractBaseNode"]
    relation_config: _RelationConfigInstantiated
    origin_base_class: type["AbstractBaseNode"]

    def __hash__(self):
        return hash(
            repr(self.origin_base_class)
            + repr(self.target_base_class)
            + repr(self.relation_config)
        )


@dataclasses.dataclass
class EmbeddedConfig:
    validators: typing.Optional[typing.Sequence[annotated_types.BaseMetadata]] = None


@dataclasses.dataclass
class _EmbeddedConfigInstantiated:
    embedded_node_base: (
        type["AbstractBaseNode"]
        | type["BaseNonHeritableTrait"]
        | type["BaseHeritableTrait"]
        | type[types.UnionType]
    )
    validators: typing.Optional[typing.Sequence[annotated_types.BaseMetadata]] = None


@dataclasses.dataclass
class _EmbeddedNodeDefinition:
    embedded_class: (
        type["AbstractBaseNode"]
        | type["BaseNonHeritableTrait"]
        | type["BaseHeritableTrait"]
        | type[types.UnionType]
    )
    embedded_config: _EmbeddedConfigInstantiated


@dataclasses.dataclass(frozen=True)
class _IncomingRelationDefinition:
    origin_base_class: type["AbstractBaseNode"]
    origin_reference_class: type["BaseNodeReference"]
    relation_config: _RelationConfigInstantiated
    target_base_class: type["AbstractBaseNode"]

    def __hash__(self):
        return hash(
            "incoming_relation_definition"
            + repr(self.origin_base_class)
            + repr(self.origin_reference_class)
            + repr(self.relation_config)
        )


@dataclasses.dataclass
class _IncomingReifiedRelationDefinition:
    origin_base_class: type["AbstractBaseNode"]
    origin_reference_class: type["BaseNodeReference"]
    relation_to_reification_config: _RelationConfigInstantiated
    relation_to_target_config: _RelationConfigInstantiated
    reification_class: type["ReifiedRelation"]
    target_base_class: type["AbstractBaseNode"]

    def __hash__(self):
        return hash(
            "incoming_reified_relation_definition"
            + repr(self.origin_base_class)
            + repr(self.relation_to_reification_config)
            + repr(self.relation_to_target_config)
            + repr(self.reification_class)
            + repr(self.target_base_class)
        )


""""NEW!!"""


@dataclasses.dataclass
class FieldDefinition:
    pass


@dataclasses.dataclass
class RelationDefinition(FieldDefinition):
    reverse_name: str
    annotation_class: tuple[
        type["AbstractBaseNode"]
        | type["BaseHeritableTrait"]
        | type["BaseNonHeritableTrait"]
        | typing.Union[
            type["AbstractBaseNode"],
            type["BaseHeritableTrait"],
            type["BaseNonHeritableTrait"],
        ]
    ]
    target_base_classes: set[type["AbstractBaseNode"]]
    target_real_classes: set[type["AbstractBaseNode"] | type["ReifiedRelation"]]
    origin_base_class: type["AbstractBaseNode"]
    relation_properties_model: typing.Optional[type["RelationPropertiesModel"]] = None
    validators: typing.Optional[typing.Sequence[annotated_types.BaseMetadata]] = None
    subclasses_relation: typing.Optional[str] = None
    create_inline: bool = False
    edit_inline: bool = False
    delete_related_on_detach: bool = False

    pangloss_field_type: typing.Literal["Relation"] = dataclasses.field(
        default="Relation"
    )

    @staticmethod
    def get_target_base_classes(annotation):
        return _get_concrete_node_classes(annotation, include_subclasses=True)

    def __init__(
        self, annotation, metadata, model: type["AbstractBaseNode"], field_name: str
    ):

        self.annotation_class = annotation
        self.target_base_classes = self.get_target_base_classes(annotation=annotation)
        self.origin_base_class = model

        if not metadata:
            raise PanglossConfigError(
                f"Field '{field_name}' on model {model.__name__} is missing a RelationConfig object"
            )
        relation_config = [
            item for item in metadata if isinstance(item, RelationConfig)
        ][0]
        self.validators = [
            item for item in metadata if isinstance(item, annotated_types.BaseMetadata)
        ]
        if extra_validators := relation_config.validators:
            self.validators += extra_validators

        self.subclasses_relation = relation_config.subclasses_relation

        self.create_inline = relation_config.create_inline
        self.edit_inline = relation_config.edit_inline
        self.delete_related_on_detach = relation_config.delete_related_on_detach
        self.reverse_name = relation_config.reverse_name


@dataclasses.dataclass
class EmbeddedNodeDefinition(FieldDefinition):
    annotation_class: tuple[
        type["AbstractBaseNode"]
        | type["BaseHeritableTrait"]
        | type["BaseNonHeritableTrait"]
        | typing.Union[
            type["AbstractBaseNode"],
            type["BaseHeritableTrait"],
            type["BaseNonHeritableTrait"],
        ]
    ]
    concrete_embedded_classes: set[type["AbstractBaseNode"]] = dataclasses.field(
        default_factory=set,
    )
    embedded_config: EmbeddedConfig | None = None
    pangloss_field_type: typing.Literal["EmbeddedNode"] = dataclasses.field(
        default="EmbeddedNode"
    )

    def __post_init__(self):
        from pangloss_core.model_setup.base_node_definitions import (
            AbstractBaseNode,
            BaseHeritableTrait,
            BaseNonHeritableTrait,
        )

        for ac in self.annotation_class:
            if not inspect.isclass(ac) or not issubclass(
                ac,
                (AbstractBaseNode, BaseHeritableTrait, BaseNonHeritableTrait),
            ):
                raise PanglossConfigError(
                    f"The type of an Embedded Node must be a node or trait type, not {self.annotation_class}"
                )

        self.concrete_embedded_classes = _get_concrete_node_classes(
            self.annotation_class, include_subclasses=True
        )


@dataclasses.dataclass
class LiteralFieldDefinition(FieldDefinition):
    pangloss_field_type: typing.Literal["Literal"]


@dataclasses.dataclass
class PropertyFieldDefinition(FieldDefinition):
    pangloss_field_type: typing.Literal["Value"]


class OutgoingRelationDefinition(FieldDefinition):
    """Class containing the definition of an outgoing node:

    - `target_base_class: type[BaseNode]`: the target ("to") class of the relationship
    - `target_reference_class: type[BaseNodeReference]`: the reference class of the target class
    - `relation_config: _PG_RelationshipConfigInstantiated`: the configuration model for the relationship
    - `origin_base_class: type[BaseNode]`: the origin ("from") class of the relationship
    """

    target_base_class: type["AbstractBaseNode"]
    target_reference_class: type["BaseNodeReference"]
    relation_config: _RelationConfigInstantiated
    origin_base_class: type["AbstractBaseNode"]

    def __hash__(self):
        return hash(
            repr(self.origin_base_class)
            + repr(self.target_base_class)
            + repr(self.relation_config)
        )


@dataclasses.dataclass
class ModelFieldsDefinitions:
    fields: dict[str, FieldDefinition | None] = dataclasses.field(default_factory=dict)

    def __getitem__(self, key):
        return self.fields[key]
