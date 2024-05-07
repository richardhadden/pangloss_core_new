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

from annotated_types import MinLen, MaxLen, Gt, Le


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


class Certainty(RelationPropertiesModel):
    certainty: Annotated[int, Gt(0), Le(0)]


class Identification[T](ReifiedRelation[T]):
    target: Annotated[
        RelationTo[T],
        RelationConfig(reverse_name="is_identified_in", relation_model=Certainty),
    ]


class RepresentationIdentification(Identification[Person]):
    represented_by: Annotated[
        Identification[Person],
        RelationConfig("acts_as_representative_in"),
    ]


class Statement(BaseNode):
    __abstract__ = True
    __create__ = False
    __edit__ = False
    __delete__ = False

    subject_of_statement: Annotated[
        Identification[Person] | RepresentationIdentification,
        RelationConfig(reverse_name="is_subject_of_statement"),
    ]


class TemporalStatement(Statement):
    __abstract__ = True
    when: Optional[datetime.date]


class Naming(Statement):
    person_named: Annotated[
        Identification[Person],
        RelationConfig(
            reverse_name="is_named_in",
            subclasses_relation="subject_of_statement",
            validators=[MinLen(1), MaxLen(1)],
        ),
    ]
    first_name: str
    last_name: str


class Birth(TemporalStatement):
    person_born: Annotated[
        Identification[Person],
        RelationConfig(
            reverse_name="has_birth_event",
            subclasses_relation="subject_of_statement",
            validators=[MinLen(1), MaxLen(1)],
        ),
    ]


class Death(TemporalStatement):
    person_died: Annotated[
        Identification[Person],
        RelationConfig(
            reverse_name="has_death_event",
            subclasses_relation="subject_of_statement",
            validators=[MinLen(1), MaxLen(1)],
        ),
    ]


class Activity(TemporalStatement):
    __abstract__ = True

    carried_out_by: Annotated[
        Identification[Person | Organisation] | RepresentationIdentification,
        RelationConfig(reverse_name="carried_out_activity", validators=[MaxLen(1)]),
    ]


class MakeJam(Activity):
    pass


class Order(TemporalStatement):
    order_given_by: Annotated[
        Identification[Person | Organisation],
        RelationConfig(
            reverse_name="gave_order",
            subclasses_relation="subject_of_statement",
        ),
    ]
    thing_ordered: Annotated[
        RelationTo[Order | MakeJam],
        RelationConfig("was_ordered_in", create_inline=True),
    ]
