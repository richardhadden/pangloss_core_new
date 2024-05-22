import datetime
import typing
import uuid

import annotated_types
import humps
import pydantic


class CamelModel(pydantic.BaseModel):
    """Converts fields by default from Python snake_case to Javascript Schema CamelCase and back.

    Modified from Ahmed Nafies's code for Pydantic 2.0, which renames 'allow_population_by_name' to 'populate_by_name'
    """

    __author__ = "Ahmed Nafies <ahmed.nafies@gmail.com>"
    __copyright__ = "Copyright 2020, Ahmed Nafies"
    __license__ = "MIT"
    __version__ = "1.0.5"

    model_config = {"alias_generator": humps.camelize, "populate_by_name": True}


class BaseNodeStandardFields(CamelModel):
    """Class defining the standard fields for all Node models, Node reference models, etc."""

    __abstract__ = True
    __create__ = True
    __edit__ = True
    __delete__ = True

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    # Standard fields for all Reference types

    # TODO: uid needs to be added to appropriate models...
    # uid: typing.Optional[uuid.UUID] = pydantic.Field(default_factory=uuid.uuid4)
    label: typing.Annotated[str, annotated_types.MaxLen(500)]

    def __hash__(self):
        return hash(self.uid)

    def __init__(self, *args, **kwargs):
        """
        When initialising, any dot-separated property of a neo4j representation of
        a relation property, ie. relation_name.relation_field_name; these need to be
        splint and added as "relation_properties" before initialising the instance
        """
        if "relation_properties" not in kwargs:
            kwargs["relation_properties"] = {}

        for key, value in kwargs.items():
            if "." in key:
                kwargs["relation_properties"][key.split(".")[1]] = value
        super().__init__(*args, **kwargs)
