from collections import defaultdict
import typing

import pydantic

from pangloss_core.exceptions import PanglossConfigError
from pangloss_core.model_setup.setup_procedures import (
    __pg_create_embedded_class__,
    __setup_delete_indirect_non_heritable_mixin_fields__,
    __setup_update_embedded_definitions__,
    __setup_update_relation_annotations__,
    __setup_update_reified_relation_annotations__,
    __setup_add_incoming_relations_to_related_models__,
    __setup_delete_subclassed_relations__,
    __setup_add_all_property_fields__,
    __setup_construct_view_type__,
    __setup_construct_edit_type__,
    __setup_create_reference_class__,
    setup_build_model_definition,
)

if typing.TYPE_CHECKING:
    from pangloss_core.model_setup.base_node_definitions import AbstractBaseNode
    from pangloss_core.models import BaseNode


class ModelManager:
    _registered_models: list[type["BaseNode"]] = []
    # _edit_models_cache = {}

    def __init__(self, *args, **kwargs):
        raise PanglossConfigError("Model Manager cannot be initialised")

    @classmethod
    def register_model(cls, model):
        cls._registered_models.append(model)

    @classmethod
    def _reset(cls):
        cls._registered_models = []
        # cls._edit_models_cache = {}

    @classmethod
    def initialise_models(cls, depth=2):
        for subclass in cls._registered_models:
            # Adding real_type literal to the subclass; does not work on
            # subclassing (this way we bypass weird inheritance issues)
            subclass.model_fields["real_type"] = pydantic.fields.FieldInfo(
                annotation=typing.Literal[subclass.__name__],
                default=subclass.__name__,
            )

            subclass.model_rebuild(force=True, _parent_namespace_depth=depth)
            subclass.field_definitions = setup_build_model_definition(subclass)

            """ __setup_delete_indirect_non_heritable_mixin_fields__(subclass)
            subclass.model_rebuild(force=True, _parent_namespace_depth=depth)

            subclass.outgoing_relations = {}
            __setup_update_relation_annotations__(subclass)
            __setup_update_reified_relation_annotations__(subclass)
            subclass.model_rebuild(force=True, _parent_namespace_depth=depth)
            __setup_delete_subclassed_relations__(subclass)
            subclass.embedded_nodes = {}
            __setup_update_embedded_definitions__(subclass)
            subclass.Embedded = __pg_create_embedded_class__(subclass)

            subclass.incoming_relations = defaultdict(set)
            subclass.model_rebuild(force=True, _parent_namespace_depth=depth) """

        """ for subclass in cls._registered_models:
            __setup_add_incoming_relations_to_related_models__(subclass)
            __setup_add_all_property_fields__(subclass)

        for subclass in cls._registered_models:
            __setup_construct_view_type__(subclass)
            subclass.model_rebuild(force=True, _parent_namespace_depth=depth)
            __setup_construct_edit_type__(subclass)

            __setup_create_reference_class__(subclass)
            subclass.model_rebuild(force=True, _parent_namespace_depth=depth)

        for subclass in cls._registered_models:
            for k, v in subclass.Edit.model_fields.items():
                v = v.rebuild_annotation()

            subclass.Edit.model_rebuild(force=True, _parent_namespace_depth=depth) """
