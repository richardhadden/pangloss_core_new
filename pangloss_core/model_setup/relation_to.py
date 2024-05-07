from __future__ import annotations

import typing
import uuid

import pydantic
import pydantic_core

from pangloss_core.model_setup.models_base import CamelModel


class RelationTo[T](typing.Sequence[T]):
    wrapper_type = "RelationTo"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: typing.Any, handler: pydantic.GetCoreSchemaHandler
    ) -> pydantic_core.core_schema.CoreSchema:
        instance_schema = pydantic_core.core_schema.is_instance_schema(cls)

        args = typing.get_args(source)
        # cls.relation_to_type = args[0]
        if args:
            # replace the type and rely on Pydantic to generate the right schema
            # for `Sequence`
            sequence_t_schema = handler.generate_schema(
                typing.Sequence[args[0]]  # type: ignore
            )
        else:
            sequence_t_schema = handler.generate_schema(typing.Sequence)

        non_instance_schema = (
            pydantic_core.core_schema.no_info_after_validator_function(
                list, sequence_t_schema
            )
        )
        return pydantic_core.core_schema.union_schema(
            [instance_schema, non_instance_schema]
        )


class ReifiedRelation[T](CamelModel):
    __abstract__ = True
    target: T
    uid: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)

    @classmethod
    def _get_model_labels(cls):
        return [cls.__name__.split("[")[0], "ReifiedRelation"]

    # def __str__(self):
    #    return f"<ReifiedRelation::{self.__class__.__name__} target={self.target.__str__()}"
