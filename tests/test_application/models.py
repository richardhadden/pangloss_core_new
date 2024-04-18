from __future__ import annotations

import datetime
from typing import Annotated, Optional

from pangloss_core.models import (
    BaseNode,
    RelationTo,
    RelationConfig,
    Embedded,
    EmbeddedConfig,
    ReifiedRelation,
    ReifiedTargetConfig,
    RelationPropertiesModel,
)

from annotated_types import MinLen, MaxLen


class ZoteroEntry(BaseNode):
    __create__ = False
    __edit__ = False
    __delete__ = False


class Entity(BaseNode):
    __abstract__ = True


class Person(Entity):
    pass


class Organisation(Entity):
    pass


class Source(BaseNode):
    """A source of something"""

    title: str


class Citation(BaseNode):
    __create__ = False
    __edit__ = False
    __delete__ = False
    __search__ = False

    reference: Annotated[
        RelationTo[ZoteroEntry],
        RelationConfig(
            reverse_name="is_reference_for", validators=[MinLen(1), MaxLen(1)]
        ),
    ]
    scope: Optional[str]


class Factoid(BaseNode):

    citation: Embedded[Citation]

    statements: Annotated[
        RelationTo[Statement],
        RelationConfig(
            reverse_name="comprises_factoid_part", create_inline=True, edit_inline=True
        ),
        MinLen(1),
    ]


class Identification[T](ReifiedRelation[T]):
    pass


class Statement(BaseNode):
    __abstract__ = True

    subject_of_statement: Annotated[
        RelationTo[Person],
        RelationConfig(reverse_name="is_subject_of_statement"),
    ]


class TemporalStatement(Statement):
    __abstract__ = True
    when: Optional[datetime.date]


class Naming(Statement):
    first_name: str
    last_name: str


class Birth(TemporalStatement):
    person_born: Annotated[
        RelationTo[Person],
        RelationConfig(
            reverse_name="has_birth_event",
            subclasses_relation="subject_of_statement",
            validators=[MinLen(1), MaxLen(1)],
        ),
    ]


class NatureOfDeath(RelationPropertiesModel):
    type: str


class Death(TemporalStatement):
    person_born: Annotated[
        RelationTo[Person],
        RelationConfig(
            reverse_name="has_death_event",
            subclasses_relation="subject_of_statement",
            validators=[MinLen(1), MaxLen(1)],
            relation_model=NatureOfDeath,
        ),
    ]


class Activity(TemporalStatement):
    __abstract__ = True

    carried_out_by: Annotated[
        RelationTo[Person | Organisation],
        RelationConfig(reverse_name="carried_out_activity", validators=[MaxLen(1)]),
    ]


class MakeJam(Activity):
    pass


class Order(TemporalStatement):
    thing_ordered: Annotated[
        RelationTo[Order | MakeJam],
        RelationConfig("was_ordered_in", create_inline=True),
    ]
