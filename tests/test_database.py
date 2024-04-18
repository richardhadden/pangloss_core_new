from __future__ import annotations

import uuid
from typing import Annotated, Optional
import typing

import pytest
import pytest_asyncio


from neo4j import Record


from pangloss_core.database import (
    Database,
    Transaction,
    read_transaction,
    write_transaction,
)
from pangloss_core.model_setup.model_manager import ModelManager
from pangloss_core.model_setup.relation_properties_model import (
    RelationPropertiesModel,
)
from pangloss_core.model_setup.embedded import Embedded
from pangloss_core.models import BaseNode
from pangloss_core.model_setup.base_node_definitions import BaseNonHeritableMixin
from pangloss_core.model_setup.relation_to import (
    RelationTo,
    RelationConfig,
    ReifiedRelation,
    ReifiedTargetConfig,
)
from pangloss_core.exceptions import PanglossNotFoundError, PanglossCreateError

FAKE_UID = uuid.UUID("a19c71f4-a844-458d-82eb-527307f89aab")


@pytest.fixture(scope="function", autouse=True)
def reset_model_manager():
    ModelManager._reset()


@pytest_asyncio.fixture(scope="function")
async def clear_database():
    # await Database.dangerously_clear_database()
    try:
        yield
    except Exception:
        pass

    await Database.dangerously_clear_database()


class ArbitraryDatabaseClass:
    @classmethod
    @write_transaction
    async def write_fake_data(cls, tx: Transaction):
        result = await tx.run(
            "CREATE (new_person:Person {uid: $uid}) RETURN new_person",
            uid=str(FAKE_UID),
        )
        item = await result.single()
        return item

    @classmethod
    @read_transaction
    async def get(
        cls,
        tx: Transaction,
        uid: uuid.UUID,
    ) -> Record | None:
        result = await tx.run(
            "MATCH (new_person {uid: $uid}) RETURN new_person", uid=str(uid)
        )
        item = await result.single()
        return item


@pytest.mark.asyncio
async def test_database_delete():
    await Database.dangerously_clear_database()
    result = await ArbitraryDatabaseClass.write_fake_data()
    assert result
    assert result.data()["new_person"]["uid"] == str(FAKE_UID)

    result = await ArbitraryDatabaseClass.get(FAKE_UID)
    assert result
    assert result.data()["new_person"]["uid"] == str(FAKE_UID)

    await Database.dangerously_clear_database()

    result = await ArbitraryDatabaseClass.get(FAKE_UID)
    assert result is None


@pytest.mark.asyncio
async def test_clear_database_fixture(clear_database):
    result = await ArbitraryDatabaseClass.write_fake_data()
    assert result
    assert result.data()["new_person"]["uid"] == str(FAKE_UID)


@typing.no_type_check
@pytest.mark.asyncio
async def test_model_save(clear_database):
    class Thing(BaseNode):
        name: str
        age: int

    ModelManager.initialise_models(depth=3)

    thing = Thing(label="JohnLabel", name="John", age=100)
    result = await thing.create()
    assert result
    assert result.uid == thing.uid


@typing.no_type_check
@pytest.mark.asyncio
async def test_model_with_relations(clear_database):
    class Pet(BaseNode):
        name: str

    class Cat(Pet):
        pass

    class Thing(BaseNode):
        name: str
        pets: Annotated[RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")]

    ModelManager.initialise_models(depth=3)

    # Create a Pet in the database
    mister_fluffy = Cat(label="Mister Fluffy", name="Mister Fluffy")
    result = await mister_fluffy.create()
    assert result.uid == mister_fluffy.uid

    thing = Thing(
        label="The Thing",
        name="The Thing",
        pets=[
            {"uid": mister_fluffy.uid, "label": mister_fluffy.label, "real_type": "Cat"}
        ],
    )

    await thing.create()

    result = await Thing.get_view(uid=thing.uid)

    assert result
    assert result.label == "The Thing"
    assert result.name == "The Thing"
    assert result.uid == thing.uid
    assert result.pets[0].uid == mister_fluffy.uid
    assert result.pets[0].label == mister_fluffy.label
    assert result.pets[0].real_type == "Cat"


@typing.no_type_check
@pytest.mark.asyncio
async def test_model_with_relation_data():
    class PersonPetRelation(RelationPropertiesModel):
        purchased_when: str

    class Pet(BaseNode):
        name: str

    class Cat(Pet):
        pass

    class Person(BaseNode):
        name: str
        pets: Annotated[
            RelationTo[Pet],
            RelationConfig(
                reverse_name="is_pet_of",
                relation_model=PersonPetRelation,
            ),
        ]

    ModelManager.initialise_models(depth=3)

    # Create a Pet in the database
    mister_fluffy = Cat(label="Mister Fluffy", name="Mister Fluffy")

    # Create and check it's there!
    result = await mister_fluffy.create()

    person = Person(
        label="The Person",
        name="The Person",
        pets=[
            {
                "uid": mister_fluffy.uid,
                "label": mister_fluffy.label,
                "real_type": "Cat",
                "relation_properties": {"purchased_when": "February"},
            }
        ],
    )

    await person.create()

    result = await Person.get_view(uid=person.uid)

    assert result
    assert result.uid == person.uid

    pet = result.pets[0]
    assert pet.label == "Mister Fluffy"
    assert pet.relation_properties.purchased_when == "February"


@typing.no_type_check
@pytest.mark.asyncio
async def test_create_with_multiple_relations():
    class Pet(BaseNode):
        name: str

    class Cat(Pet):
        pass

    class Place(BaseNode):
        pass

    class Person(BaseNode):
        name: str
        pets: Annotated[RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")]
        location: Annotated[
            RelationTo[Place], RelationConfig(reverse_name="is_location_of")
        ]

    ModelManager.initialise_models(depth=3)

    place = Place(label="France")
    await place.create()

    cat = Cat(label="Mister Fluffy", name="Mister Fluffy")
    await cat.create()

    cat2 = Cat(label="Mrs Fluffy", name="Mrs Fluffy")
    await cat2.create()

    person = Person(
        label="John Smith",
        name="John Smith",
        pets=[
            {"uid": cat.uid, "label": "Mister Fluffy", "real_type": "Cat"},
            {"uid": cat2.uid, "label": "Mrs Fluffy", "real_type": "Cat"},
        ],
        location=[{"uid": place.uid, "label": "France", "real_type": "Place"}],
    )

    await person.create()

    result = await Person.get_view(uid=person.uid)

    assert result
    assert result.label == "John Smith"

    assert len(result.pets) == 2
    assert len(result.location) == 1
    pet1 = result.pets.pop()
    assert pet1.real_type == "Cat"


@typing.no_type_check
@pytest.mark.asyncio
async def test_create_with_embedded_node():
    class DateBase(BaseNode):
        __abstract__ = True

    class DatePrecise(DateBase):
        date_precise: str

    class DateImprecise(DateBase):
        date_not_before: str
        date_not_after: str

    class Person(BaseNode):
        date_of_birth: Embedded[DateBase]

    ModelManager.initialise_models(depth=3)

    person = Person(
        label="A Person",
        date_of_birth=[{"real_type": "DatePrecise", "date_precise": "Last February"}],
    )
    print(Person.model_fields)

    await person.create()

    result = await Person.get_view(uid=person.uid)
    assert result.uid == person.uid
    date_of_birth = result.date_of_birth.pop()
    assert date_of_birth.date_precise == "Last February"


@typing.no_type_check
@pytest.mark.asyncio
async def test_create_with_double_embedded_node(clear_database):
    class DoubleInner(BaseNode):
        name: str

    class Inner(BaseNode):
        double_inner: Embedded[DoubleInner]
        name: str

    class Outer(BaseNode):
        inner: Embedded[Inner]
        name: str

    class Person(BaseNode):
        outer: Embedded[Outer]

    ModelManager.initialise_models(depth=3)

    person = Person(
        label="PersonLabel",
        outer=[
            {
                "name": "OuterName",
                "inner": [
                    {
                        "name": "InnerName",
                        "double_inner": [
                            {
                                "name": "DoubleInnerName",
                            }
                        ],
                    }
                ],
            }
        ],
    )

    await person.create()

    result = await Person.get_view(uid=person.uid)
    assert result
    outer = result.outer.pop()
    assert outer.name == "OuterName"

    inner = outer.inner.pop()
    assert inner.name == "InnerName"

    double_inner = inner.double_inner.pop()
    assert double_inner.name == "DoubleInnerName"


@typing.no_type_check
@pytest.mark.asyncio
async def test_create_with_double_embedded_node_with_relation(clear_database):
    # await Database.dangerously_clear_database()

    class Pet(BaseNode):
        name: str

    class DoubleInner(BaseNode):
        name: str
        double_inner_has_pet: Annotated[
            RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")
        ]

    class Inner(BaseNode):
        double_inner: Embedded[DoubleInner]
        name: str
        # inner_has_pet: RelationTo[Pet, RelationConfig(reverse_name="is_pet_of")]

    class Outer(BaseNode):
        inner: Embedded[Inner]
        name: str
        outer_has_pet: Annotated[
            RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")
        ]

    class Person(BaseNode):
        outer: Embedded[Outer]
        person_has_pet: Annotated[
            RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")
        ]

    ModelManager.initialise_models(depth=3)

    person_pet = Pet(label="PersonPet", name="Mr Fluffy")
    await person_pet.create()

    outer_pet = Pet(label="OuterPet", name="Mr Fluffy")
    await outer_pet.create()

    double_inner_pet = Pet(label="DoubleInnerPet", name="Mr Fluffy")
    await double_inner_pet.create()

    person = Person(
        label="PersonLabel",
        person_has_pet=[
            {
                "label": person_pet.label,
                "uid": person_pet.uid,
                "real_type": "Pet",
            }
        ],
        outer=[
            {
                "outer_has_pet": [
                    {
                        "label": outer_pet.label,
                        "uid": outer_pet.uid,
                        "real_type": "Pet",
                    }
                ],
                "name": "OuterName",
                "inner": [
                    {
                        "name": "InnerName",
                        "double_inner": [
                            {
                                "name": "DoubleInnerName",
                                "double_inner_has_pet": [
                                    {
                                        "label": double_inner_pet.label,
                                        "uid": double_inner_pet.uid,
                                        "real_type": "Pet",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    )

    await person.create()

    result = await Person.get_view(uid=person.uid)
    assert person
    person_has_pet = person.person_has_pet.pop()
    assert person_has_pet.label == "PersonPet"

    assert result
    outer = result.outer.pop()
    assert outer.name == "OuterName"

    assert outer.outer_has_pet
    outer_has_pet = outer.outer_has_pet.pop()
    assert outer_has_pet.label == "OuterPet"

    inner = outer.inner.pop()
    assert inner.name == "InnerName"

    double_inner = inner.double_inner.pop()
    assert double_inner.name == "DoubleInnerName"

    assert double_inner.double_inner_has_pet
    double_inner_has_pet = double_inner.double_inner_has_pet.pop()
    assert double_inner_has_pet.label == "DoubleInnerPet"


@typing.no_type_check
@pytest.mark.asyncio
async def test_write_abstract_reification():
    class IdentificationIdentifiedEntityRelation(RelationPropertiesModel):
        certainty: int

    class Identification[T](ReifiedRelation[T]):
        identification_type: str

    class Person(BaseNode):
        name: str

    class Day(BaseNode):
        pass

    class Event(BaseNode):
        when: Annotated[RelationTo[Day], RelationConfig(reverse_name="is_day_of_event")]
        person_identified: Annotated[
            Identification[Person],
            RelationConfig(
                reverse_name="is_identification_of_person_in_event",
            ),
            ReifiedTargetConfig(
                reverse_name="is_identified_in",
                relation_model=IdentificationIdentifiedEntityRelation,
            ),
        ]

    ModelManager.initialise_models(depth=3)

    person = Person(label="John Smith", name="John Smith")
    await person.create()

    tuesday = Day(label="Tuesday")
    await tuesday.create()

    event = Event(
        label="Big Bash",
        person_identified=[
            {
                "target": [
                    {
                        "uid": person.uid,
                        "label": person.label,
                        "real_type": "Person",
                        "relation_properties": {"certainty": 1},
                    }
                ],
                "identification_type": "visual",
            }
        ],
        when=[
            {
                "uid": tuesday.uid,
                "label": tuesday.label,
                "real_type": "Day",
            },
        ],
    )

    event_from_create = await event.create()
    event_from_db = await Event.get_view(uid=event.uid)


@typing.no_type_check
@pytest.mark.asyncio
async def test_write_trait(clear_database):
    class Purchaseable(BaseNonHeritableMixin):
        price: int

    class Pet(BaseNode, Purchaseable):
        pass

    class Person(BaseNode):
        purchased_items: Annotated[
            RelationTo[Purchaseable], RelationConfig(reverse_name="purchased_by")
        ]

    ModelManager.initialise_models(depth=3)

    pet = Pet(label="Mister Cat", price=100)
    assert pet.price == 100

    await pet.create()

    person = Person(
        label="John Smith",
        purchased_items=[
            {"uid": pet.uid, "label": pet.label, "real_type": "Pet"},
        ],
    )

    person_created = await person.create()
    assert person_created

    person_read = await Person.get_view(uid=person.uid)
    assert person_read
    purchased_item = person_read.purchased_items.pop()
    assert purchased_item.uid == pet.uid
    assert purchased_item.real_type == "Pet"


@typing.no_type_check
@pytest.mark.asyncio
async def test_read_view():
    # Create some data... (TODO: make this into a function somewhere maybe?)

    class Pet(BaseNode):
        name: str

    class Cat(Pet):
        pass

    class Place(BaseNode):
        pass

    class Person(BaseNode):
        name: str
        pets: Annotated[RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")]
        location: Annotated[
            RelationTo[Place], RelationConfig(reverse_name="is_location_of")
        ]

    ModelManager.initialise_models(depth=3)

    place = Place(label="France")
    await place.create()

    cat = Cat(label="Mister Fluffy", name="Mister Fluffy")
    await cat.create()

    cat2 = Cat(label="Mrs Fluffy", name="Mrs Fluffy")
    await cat2.create()

    person = Person(
        label="John Smith",
        name="John Smith",
        pets=[
            {"uid": cat.uid, "label": "Mister Fluffy", "real_type": "Cat"},
            {"uid": cat2.uid, "label": "Mrs Fluffy", "real_type": "Cat"},
        ],
        location=[{"uid": place.uid, "label": "France", "real_type": "Place"}],
    )

    person_create_result = await person.create()

    person_read_result = await Person.get_view(uid=person.uid)
    assert person_read_result
    assert person_read_result.__class__ is Person.View

    assert person_read_result.label == person.label
    location = person_read_result.location.pop()
    assert location.uid == place.uid

    place_read_result = await Place.get_view(uid=place.uid)
    assert place_read_result
    print(dict(place_read_result))
    assert place_read_result.is_location_of
    is_location_of = place_read_result.is_location_of.pop()
    assert is_location_of.uid == person.uid


@typing.no_type_check
@pytest.mark.asyncio
async def test_reverse_relations_through_embedded(clear_database):
    await Database.dangerously_clear_database()

    class Dog(BaseNode):
        pass

    class Cat(BaseNode):
        pass

    class Tortoise(BaseNode):
        pass

    class DoubleInnerThing(BaseNode):
        tortoises: Annotated[
            RelationTo[Tortoise], RelationConfig(reverse_name="tortoise_has_owner")
        ]

    class InnerThing(BaseNode):
        dogs: Annotated[RelationTo[Dog], RelationConfig(reverse_name="dog_has_owner")]
        double_inner_thing: Embedded[DoubleInnerThing]

    class OuterThing(BaseNode):
        inner_thing: Embedded[InnerThing]
        cats: Annotated[RelationTo[Cat], RelationConfig(reverse_name="cat_has_owner")]

    class Person(BaseNode):
        thing: Embedded[OuterThing]

    ModelManager.initialise_models(depth=3)

    cat = Cat(label="A Cat")
    await cat.create()
    dog = Dog(label="A Dog")
    await dog.create()
    tortoise = Tortoise(label="A Tortoise")
    await tortoise.create()

    person = Person(
        label="John smith",
        thing=[
            {
                "cats": [
                    {
                        "uid": cat.uid,
                        "label": cat.label,
                        "real_type": "Cat",
                    },
                ],
                "inner_thing": [
                    {
                        "dogs": [
                            {
                                "uid": dog.uid,
                                "label": dog.label,
                                "real_type": "Dog",
                            },
                        ],
                        "double_inner_thing": [
                            {
                                "tortoises": [
                                    {
                                        "uid": tortoise.uid,
                                        "label": tortoise.label,
                                        "real_type": "Tortoise",
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }
        ],
    )

    await person.create()

    cat_result = await Cat.get_view(cat.uid)

    assert cat_result
    assert cat_result.cat_has_owner[0].uid == person.uid

    dog_result = await Dog.get_view(dog.uid)

    assert dog_result
    assert dog_result.dog_has_owner[0].uid == person.uid

    tortoise_result = await Tortoise.get_view(tortoise.uid)

    assert tortoise_result
    assert tortoise_result.tortoise_has_owner[0].uid == person.uid


@typing.no_type_check
@pytest.mark.asyncio
async def test_get_reverse_relation_through_reified(clear_database):
    class Pet(BaseNode):
        pass

    class Identification[T](ReifiedRelation[T]):
        certainty: int

    class Person(BaseNode):
        pets: Annotated[
            Identification[Pet],
            RelationConfig(reverse_name="is_pet_of"),
        ]

    ModelManager.initialise_models(depth=3)

    pet = Pet(label="Mr Fluffy")
    await pet.create()

    person = Person(
        label="John Smith",
        pets=[
            {
                "certainty": 1,
                "target": [{"label": "Mr Fluffy", "real_type": "Pet", "uid": pet.uid}],
            }
        ],
    )

    await person.create()

    person_read = await Person.get_view(uid=person.uid)
    assert person_read

    assert person_read.pets[0].target[0].uid == pet.uid

    pet_read = await Pet.get_view(uid=pet.uid)
    assert pet_read
    assert pet_read.is_pet_of[0].uid == person.uid


@typing.no_type_check
@pytest.mark.asyncio
async def test_reverse_relations_do_not_propagate_indefinitely(clear_database):
    class Toy(BaseNode):
        pass

    class Pet(BaseNode):
        toys: Annotated[RelationTo[Toy], RelationConfig(reverse_name="toy_belongs_to")]

    class Person(BaseNode):
        pets: Annotated[RelationTo[Pet], RelationConfig(reverse_name="pet_owned_by")]

    ModelManager.initialise_models(depth=3)

    toy = Toy(label="Squeaky Toy")
    await toy.create()

    pet = Pet(
        label="Mr Fluffy",
        toys=[{"uid": toy.uid, "label": toy.label, "real_type": "Toy"}],
    )
    await pet.create()

    person = Person(
        label="John Smith",
        pets=[{"uid": pet.uid, "label": pet.label, "real_type": "Pet"}],
    )
    await person.create()

    toy_read = await Toy.get_view(uid=toy.uid)
    print(dict(toy_read))
    assert len(toy_read.toy_belongs_to) == 1
    assert toy_read.toy_belongs_to[0].uid == pet.uid


@typing.no_type_check
@pytest.mark.asyncio
async def test_create_relation_inline(clear_database):
    class Person(BaseNode):
        pass

    class Activity(BaseNode):
        activity_type: str
        date: str
        cost: int
        person_carrying_out_activity: Annotated[
            RelationTo[Person], RelationConfig(reverse_name="carried_out_activity")
        ]

    class Order(BaseNode):
        thing_ordered: Annotated[
            RelationTo[Activity],
            RelationConfig(reverse_name="was_ordered_by", create_inline=True),
        ]

    ModelManager.initialise_models(depth=3)

    person = Person(label="John Smith")
    await person.create()

    order = Order(
        label="Gives an order",
        thing_ordered=[
            {
                "label": "Making Soup",
                "activity_type": "cookery",
                "date": "February",
                "cost": 1,
                "person_carrying_out_activity": [
                    {"label": person.label, "uid": person.uid, "real_type": "Person"}
                ],
                "real_type": "Activity",
            }
        ],
    )

    order_created = await order.create()

    order_read = await Order.get_view(uid=order_created.uid)

    assert order_read.thing_ordered[0].label == "Making Soup"


@typing.no_type_check
@pytest.mark.asyncio
async def test_non_match_returns_error(clear_database):
    class Person(BaseNode):
        age: int

    ModelManager.initialise_models(depth=3)

    with pytest.raises(PanglossNotFoundError):
        await Person.get_view(uid=uuid.uuid4())


@typing.no_type_check
@pytest.mark.asyncio
async def test_uid_uniqueness_constraint_violation_raises_error(clear_database):
    class Person(BaseNode):
        age: int

    ModelManager.initialise_models(depth=3)

    person = Person(label="John Smith", age=1)
    await person.create()

    person2 = Person(uid=person.uid, label="Another Person", age=1)

    with pytest.raises(PanglossCreateError):
        await person2.create()


@typing.no_type_check
@pytest.mark.asyncio
async def test_view_get_method(clear_database):
    class Person(BaseNode):
        age: int

    ModelManager.initialise_models(depth=3)

    person = Person(label="John Smith", age=1)
    await person.create()

    person_view = await Person.View.get(uid=person.uid)


@typing.no_type_check
@pytest.mark.asyncio
async def test_edit_relation_inline(clear_database):
    class Person(BaseNode):
        pass

    class Activity(BaseNode):
        activity_type: str
        date: str
        cost: int
        person_carrying_out_activity: Annotated[
            RelationTo[Person], RelationConfig(reverse_name="carried_out_activity")
        ]

    class Order(BaseNode):
        thing_ordered: Annotated[
            RelationTo[Activity],
            RelationConfig(
                reverse_name="was_ordered_by", create_inline=True, edit_inline=True
            ),
        ]

    ModelManager.initialise_models(depth=3)

    person = Person(label="John Smith")
    await person.create()

    order = Order(
        label="Gives an order",
        thing_ordered=[
            {
                "label": "Making Soup",
                "activity_type": "cookery",
                "date": "February",
                "cost": 1,
                "person_carrying_out_activity": [
                    {"label": person.label, "uid": person.uid, "real_type": "Person"}
                ],
                "real_type": "Activity",
            }
        ],
    )

    await order.create()

    order_update_view = await Order.get_edit(uid=order.uid)

    assert order_update_view.thing_ordered[0].date == "February"
    assert (
        order_update_view.thing_ordered[0].person_carrying_out_activity[0].uid
        == person.uid
    )

    order_update_view = await Order.Edit.get(uid=order.uid)


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_properties(clear_database):
    class Person(BaseNode):
        age: int
        name: str

    ModelManager.initialise_models(depth=3)

    person = Person(label="John Smith", name="John Smith", age=100)
    await person.create()

    person_to_update = await Person.get_edit(uid=person.uid)

    await person_to_update.write_edit()

    person_to_update.name = "John Smith II"

    await person_to_update.write_edit()

    person_updated = await Person.Edit.get(uid=person.uid)
    assert person_updated.name == "John Smith II"

    person_to_update = Person.Edit(
        label="John Smith", uid=person.uid, name="John Smith III", age=101
    )
    await person_to_update.write_edit()

    person_updated = await Person.Edit.get(uid=person.uid)

    assert person_updated.label == "John Smith"
    assert person_updated.name == "John Smith III"
    assert person_updated.age == 101


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_basic_relations():
    class Pet(BaseNode):
        pass

    class Person(BaseNode):
        pets: Annotated[RelationTo[Pet], RelationConfig(reverse_name="belongs_to")]

    ModelManager.initialise_models(depth=3)

    fluffle = Pet(label="Fluffle")
    await fluffle.create()

    wuffle = Pet(label="Wuffle")
    await wuffle.create()

    snuffle = Pet(label="Snuffle")
    await snuffle.create()

    truffle = Pet(label="Truffle")
    await truffle.create()

    person = Person(
        label="John Smith",
        pets=[
            {"uid": fluffle.uid, "label": fluffle.label, "real_type": "Pet"},
            {"uid": wuffle.uid, "label": wuffle.label, "real_type": "Pet"},
        ],
    )

    await person.create()

    # Do an update with no changes
    person_to_update = Person.Edit(
        uid=person.uid,
        label="John Smith",
        pets=[
            {"uid": fluffle.uid, "label": fluffle.label, "real_type": "Pet"},
            {"uid": wuffle.uid, "label": wuffle.label, "real_type": "Pet"},
        ],
    )

    await person_to_update.write_edit()

    person_written = await Person.get_view(uid=person.uid)
    assert {pet.label for pet in person_written.pets} == {fluffle.label, wuffle.label}
    assert {pet.uid for pet in person_written.pets} == {fluffle.uid, wuffle.uid}

    # Do an update changing snuffle to wuffle
    person_to_update = Person.Edit(
        uid=person.uid,
        label="John Smith",
        pets=[
            {"uid": fluffle.uid, "label": fluffle.label, "real_type": "Pet"},
            {"uid": snuffle.uid, "label": snuffle.label, "real_type": "Pet"},
        ],
    )

    await person_to_update.write_edit()

    person_written = await Person.get_view(uid=person.uid)
    assert {pet.label for pet in person_written.pets} == {fluffle.label, snuffle.label}
    assert {pet.uid for pet in person_written.pets} == {fluffle.uid, snuffle.uid}

    # Do an update adding wuffle and truffle
    person_to_update = Person.Edit(
        uid=person.uid,
        label="John Smith",
        pets=[
            {"uid": fluffle.uid, "label": fluffle.label, "real_type": "Pet"},
            {"uid": snuffle.uid, "label": snuffle.label, "real_type": "Pet"},
            {"uid": wuffle.uid, "label": wuffle.label, "real_type": "Pet"},
            {"uid": truffle.uid, "label": truffle.label, "real_type": "Pet"},
        ],
    )

    await person_to_update.write_edit()

    person_written = await Person.get_view(uid=person.uid)
    assert {pet.label for pet in person_written.pets} == {
        fluffle.label,
        snuffle.label,
        wuffle.label,
        truffle.label,
    }
    assert {pet.uid for pet in person_written.pets} == {
        fluffle.uid,
        snuffle.uid,
        wuffle.uid,
        truffle.uid,
    }


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_inline_editable_relation(clear_database):
    class Pet(BaseNode):
        pass

    class Person(BaseNode):
        pets: Annotated[
            RelationTo[Pet],
            RelationConfig(
                reverse_name="belongs_to",
                create_inline=True,
                edit_inline=True,
                delete_related_on_detach=True,
            ),
        ]

    ModelManager.initialise_models(depth=3)

    # Initiate these things as nice containers
    fluffle = Pet(label="Fluffle")
    wuffle = Pet(label="Wuffle")
    snuffle = Pet(label="Snuffle")
    truffle = Pet(label="Truffle")

    # Create person
    person = Person(
        label="John Smith",
        pets=[
            {"uid": fluffle.uid, "label": fluffle.label, "real_type": "Pet"},
            {"uid": wuffle.uid, "label": wuffle.label, "real_type": "Pet"},
        ],
    )

    await person.create()

    # Build Edit View of Person
    person_to_edit = Person.Edit(
        uid=person.uid,
        label="John Smith",
        pets=[
            {"uid": fluffle.uid, "label": "Fluffle New Label", "real_type": "Pet"},
            {"uid": wuffle.uid, "label": wuffle.label, "real_type": "Pet"},
        ],
    )
    await person_to_edit.write_edit()

    # Get it back from the database and check update of Fluffle
    person_read = await Person.View.get(uid=person.uid)

    assert {pet.label for pet in person_read.pets} == {"Fluffle New Label", "Wuffle"}

    person_to_edit = Person.Edit(
        uid=person.uid,
        label="John Smith",
        pets=[
            {
                "uid": fluffle.uid,
                "label": "Fluffle Even Newer Label",
                "real_type": "Pet",
            },
        ],
    )
    await person_to_edit.write_edit()

    person_read = await Person.View.get(uid=person.uid)
    assert len(person_read.pets) == 1
    assert person_read.pets[0].label == "Fluffle Even Newer Label"

    # Now changed the Pets list to create Truffle
    person_to_edit = Person.Edit(
        uid=person.uid,
        label="John Smith",
        pets=[
            {"uid": truffle.uid, "label": truffle.label, "real_type": "Pet"},
        ],
    )

    await person_to_edit.write_edit()

    person_read = await Person.View.get(uid=person.uid)

    assert len(person_read.pets) == 1
    assert person_read.pets[0].label == "Truffle"

    pet_in_db = await Pet.View.get(uid=person_read.pets[0].uid)
    assert pet_in_db.created_when
    assert pet_in_db.modified_when

    # By replacing Fluffle and Wuffle with Truffle, these two should
    # now be deleted
    with pytest.raises(PanglossNotFoundError):
        await Pet.View.get(uid=fluffle.uid)

    with pytest.raises(PanglossNotFoundError):
        await Pet.View.get(uid=wuffle.uid)

    # TODO: delete dependents!


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_double_embedded_objects():
    await Database.dangerously_clear_database()
    from typing import Union

    class Person(BaseNode):
        pass

    class Payment(BaseNode):
        how_much: int
        payment_made_by: Annotated[
            RelationTo[Person], RelationConfig(reverse_name="made_payment")
        ]

    class WritingBook(BaseNode):
        written_by: Annotated[
            RelationTo[Person], RelationConfig(reverse_name="made_payment")
        ]
        something: Optional[str] = ""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            print(args, kwargs)

    class Order(BaseNode):
        thing_ordered: Annotated[
            RelationTo[Union[Order, Payment, WritingBook]],
            RelationConfig(
                reverse_name="was_ordered_in",
                create_inline=True,
                edit_inline=True,
                delete_related_on_detach=True,
            ),
        ]
        carried_out_by: Annotated[
            RelationTo[Person], RelationConfig(reverse_name="carried_out_order")
        ]

    ModelManager.initialise_models(depth=3)

    john_smith = Person(label="John Smith")
    await john_smith.create()

    toby_jones = Person(label="Toby Jones")
    await toby_jones.create()

    olive_branch = Person(label="Olive Branch")
    await olive_branch.create()

    order = Order(
        label="John Smith orders Toby Jones to order Olive Branch to make a payment",
        carried_out_by=[
            {"uid": john_smith.uid, "label": john_smith.label, "real_type": "Person"}
        ],
        thing_ordered=[
            {
                "label": "Toby Jones orders Olive Branch to make a payment",
                "real_type": "Order",
                "carried_out_by": [
                    {
                        "uid": toby_jones.uid,
                        "label": toby_jones.label,
                        "real_type": "Person",
                    }
                ],
                "thing_ordered": [
                    {
                        "label": "Olive Branch makes payment",
                        "real_type": "Payment",
                        "how_much": 1,
                        "payment_made_by": [
                            {
                                "uid": olive_branch.uid,
                                "label": olive_branch.label,
                                "real_type": "Person",
                            }
                        ],
                    }
                ],
            }
        ],
    )
    import time

    start = time.perf_counter()
    await order.create()
    print("Created in :", time.perf_counter() - start)

    bertie_wooster = Person(label="Bertie Wooster")
    await bertie_wooster.create()

    lucky_jim = Person(label="Lucky Jim")
    await lucky_jim.create()

    miss_marple = Person(label="Miss Marple")
    await miss_marple.create()

    order_to_edit = Order.Edit(
        uid=order.uid,
        label="Bertie Wooster orders Toby Jones to order Olive Branch to make a payment",  # Update top level prop
        carried_out_by=[  # Update top level direct relation
            {
                "real_type": "Person",
                "uid": bertie_wooster.uid,
                "label": bertie_wooster.label,
            }
        ],
        thing_ordered=[
            {
                "real_type": "Order",
                "uid": order.thing_ordered[0].uid,
                "label": "Lucky Jim orders Olive Branch to make a payment UPDATED",  # Update second level prop
                "carried_out_by": [
                    {
                        "uid": lucky_jim.uid,
                        "label": lucky_jim.label,
                        "real_type": "Person",
                    }
                ],
                "thing_ordered": [
                    {
                        "uid": order.thing_ordered[0].thing_ordered[0].uid,
                        "label": "Olive Branch makes payment",
                        "real_type": "Payment",
                        "how_much": 1,
                        "payment_made_by": [
                            {
                                "uid": olive_branch.uid,
                                "label": olive_branch.label,
                                "real_type": "Person",
                            }
                        ],
                    }
                ],
            }
        ],
    )

    assert type(order_to_edit.thing_ordered[0].thing_ordered[0]) is Payment.Edit
    assert order_to_edit.thing_ordered[0].thing_ordered[0].real_type == "Payment"

    start = time.perf_counter()
    await order_to_edit.write_edit()
    print("First edit in :", time.perf_counter() - start)

    updated_order = await Order.View.get(uid=order.uid)

    assert updated_order.carried_out_by[0].uid == bertie_wooster.uid
    assert (
        updated_order.label
        == "Bertie Wooster orders Toby Jones to order Olive Branch to make a payment"
    )

    assert len(updated_order.thing_ordered) == 1

    assert updated_order.thing_ordered[0].thing_ordered[0].real_type == "Payment"

    assert (
        updated_order.thing_ordered[0].label
        == "Lucky Jim orders Olive Branch to make a payment UPDATED"
    )

    assert updated_order.thing_ordered[0].carried_out_by[0].uid == lucky_jim.uid

    order_to_edit2 = Order.Edit(
        uid=order.uid,
        label="Bertie Wooster orders Lucky Jim to order Miss Marple to write a book",  # Update top level prop
        carried_out_by=[  # Update top level direct relation
            {
                "real_type": "Person",
                "uid": bertie_wooster.uid,
                "label": bertie_wooster.label,
            }
        ],
        thing_ordered=[
            {
                "real_type": "Order",
                "uid": order.thing_ordered[0].uid,
                "label": "Lucky Jim orders Miss Marple to write a book",  # Update second level prop
                "carried_out_by": [
                    {
                        "uid": lucky_jim.uid,
                        "label": lucky_jim.label,
                        "real_type": "Person",
                    }
                ],
                "thing_ordered": [
                    {
                        "label": "Miss Marple writes book",
                        "real_type": "WritingBook",
                        "written_by": [
                            {
                                "uid": miss_marple.uid,
                                "label": miss_marple.label,
                                "real_type": "Person",
                            }
                        ],
                    }
                ],
            }
        ],
    )

    start = time.perf_counter()
    await order_to_edit2.write_edit()
    print("Second edit in:", time.perf_counter() - start)

    updated_order = await Order.View.get(uid=order.uid)

    assert (
        updated_order.label
        == "Bertie Wooster orders Lucky Jim to order Miss Marple to write a book"
    )
    assert len(updated_order.thing_ordered) == 1

    assert (
        updated_order.thing_ordered[0].label
        == "Lucky Jim orders Miss Marple to write a book"
    )
    assert updated_order.thing_ordered[0].carried_out_by[0].uid == lucky_jim.uid

    assert len(updated_order.thing_ordered[0].thing_ordered) == 1

    assert updated_order.thing_ordered[0].thing_ordered[0].real_type
    assert type(updated_order.thing_ordered[0].thing_ordered[0]) is WritingBook

    assert (
        updated_order.thing_ordered[0].thing_ordered[0].written_by[0].uid
        == miss_marple.uid
    )
    # print(dict(updated_order.thing_ordered[0].thing_ordered[0]))

    # assert (
    #    "TODO:: Here check proper cleanup of stray items; delete dependent nodes that can be..."
    #    == False
    # )

    order_to_edit3 = Order.Edit(
        uid=order.uid,
        label="Bertie Wooster orders Olive Branch to make a payment",  # Update top level prop
        carried_out_by=[  # Update top level direct relation
            {
                "real_type": "Person",
                "uid": bertie_wooster.uid,
                "label": bertie_wooster.label,
            }
        ],
        thing_ordered=[
            {
                "label": "Olive Branch makes payment",
                "real_type": "Payment",
                "how_much": 1,
                "payment_made_by": [
                    {
                        "uid": olive_branch.uid,
                        "label": olive_branch.label,
                        "real_type": "Person",
                    }
                ],
            }
        ],
    )
    start = time.perf_counter()
    await order_to_edit3.write_edit()
    print("Third edit in :", time.perf_counter() - start)

    start = time.perf_counter()
    updated_order = await Order.View.get(uid=order.uid)
    print("Getting view in :", time.perf_counter() - start)

    assert len(updated_order.thing_ordered) == 1
    assert updated_order.label == "Bertie Wooster orders Olive Branch to make a payment"
    assert updated_order.thing_ordered[0].real_type == "Payment"
    assert updated_order.thing_ordered[0].uid == order_to_edit3.thing_ordered[0].uid
    assert updated_order.thing_ordered[0].label == "Olive Branch makes payment"
    assert updated_order.thing_ordered[0].payment_made_by[0].uid == olive_branch.uid

    ordered_olive_branch = await Payment.View.get(
        uid=updated_order.thing_ordered[0].uid
    )
    assert ordered_olive_branch.label == "Olive Branch makes payment"

    with pytest.raises(PanglossNotFoundError):
        await Order.View.get(uid=order_to_edit2.thing_ordered[0].uid)


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_nested_embedded():
    class Pet(BaseNode):
        name: str

    class Inner(BaseNode):
        name: str
        inner_has_pet: Annotated[
            RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")
        ]

    class OuterTypeOne(BaseNode):
        inner: Embedded[Inner]
        some_value: str
        outer_one_has_pet: Annotated[
            RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")
        ]

    class OuterTypeTwo(BaseNode):
        inner: Embedded[Inner]
        some_other_value: str
        outer_two_has_pet: Annotated[
            RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")
        ]

    class Person(BaseNode):
        outer: Embedded[OuterTypeOne | OuterTypeTwo]
        person_has_pet: Annotated[
            RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")
        ]

    ModelManager.initialise_models(depth=3)

    john_smith_pet = Pet(label="John Smith's Pet", name="Truffles")
    await john_smith_pet.create()

    outer_one_pet = Pet(label="Outer One Pet", name="Wuffles")
    await outer_one_pet.create()

    outer_two_pet = Pet(label="Outer Two Pet", name="Fluffles")
    await outer_two_pet.create()

    inner_pet = Pet(label="Inner Pet", name="Snuffles")
    await inner_pet.create()

    john_smith = Person(
        label="John Smith",
        person_has_pet=[john_smith_pet.as_reference_dict()],
        outer=[
            {
                "real_type": "OuterTypeOne",
                "some_value": "SomeValue",
                "outer_one_has_pet": [outer_one_pet.as_reference_dict()],
                "inner": [
                    {
                        "real_type": "Inner",
                        "name": "InnerEmbedded",
                        "inner_has_pet": [inner_pet.as_reference_dict()],
                    }
                ],
            }
        ],
    )

    await john_smith.create()

    john_smith_edit = Person.Edit(
        uid=john_smith.uid,
        label="John Smith",
        person_has_pet=[john_smith_pet.as_reference_dict()],
        outer=[
            {
                "real_type": "OuterTypeTwo",
                "some_other_value": "SomeValue",
                "outer_two_has_pet": [outer_two_pet.as_reference_dict()],
                "inner": [
                    {
                        "real_type": "Inner",
                        "name": "InnerEmbedded",
                        "inner_has_pet": [inner_pet.as_reference_dict()],
                    }
                ],
            }
        ],
    )

    await john_smith_edit.write_edit()

    john_smith_updated = await Person.View.get(uid=john_smith.uid)
    assert john_smith_updated
    assert len(john_smith_updated.outer) == 1

    assert john_smith_updated.outer[0].real_type == "OuterTypeTwo"


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_raises_error_and_does_nothing_if_uid_not_found():
    class Pet(BaseNode):
        name: str

    class Inner(BaseNode):
        name: str
        inner_has_pet: Annotated[
            RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")
        ]

    class OuterTypeOne(BaseNode):
        inner: Embedded[Inner]
        some_value: str
        outer_one_has_pet: Annotated[
            RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")
        ]

    class OuterTypeTwo(BaseNode):
        inner: Embedded[Inner]
        some_other_value: str
        outer_two_has_pet: Annotated[
            RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")
        ]

    class Person(BaseNode):
        outer: Embedded[OuterTypeOne | OuterTypeTwo]
        person_has_pet: Annotated[
            RelationTo[Pet], RelationConfig(reverse_name="is_pet_of")
        ]

    ModelManager.initialise_models(depth=3)

    john_smith_pet = Pet(label="John Smith's Pet", name="Truffles")
    await john_smith_pet.create()

    outer_one_pet = Pet(label="Outer One Pet", name="Wuffles")
    await outer_one_pet.create()

    outer_two_pet = Pet(label="Outer Two Pet", name="Fluffles")
    await outer_two_pet.create()

    inner_pet = Pet(label="Inner Pet", name="Snuffles")
    await inner_pet.create()

    john_smith = Person(
        label="John Smith",
        person_has_pet=[john_smith_pet.as_reference_dict()],
        outer=[
            {
                "real_type": "OuterTypeOne",
                "some_value": "SomeValue",
                "outer_one_has_pet": [outer_one_pet.as_reference_dict()],
                "inner": [
                    {
                        "real_type": "Inner",
                        "name": "InnerEmbedded",
                        "inner_has_pet": [inner_pet.as_reference_dict()],
                    }
                ],
            }
        ],
    )

    await john_smith.create()

    john_smith_edit = Person.Edit(
        label="John Smith",
        person_has_pet=[john_smith_pet.as_reference_dict()],
        outer=[
            {
                "real_type": "OuterTypeTwo",
                "some_other_value": "SomeValue",
                "outer_two_has_pet": [outer_two_pet.as_reference_dict()],
                "inner": [
                    {
                        "real_type": "Inner",
                        "name": "InnerEmbedded",
                        "inner_has_pet": [inner_pet.as_reference_dict()],
                    }
                ],
            }
        ],
    )
    with pytest.raises(PanglossNotFoundError):
        await john_smith_edit.write_edit()

    john_smith_unchanged_edit = await Person.Edit.get(uid=john_smith.uid)
    assert john_smith_unchanged_edit
    assert dict(john_smith_unchanged_edit) == dict(john_smith)


"""
Database types:

- Create (post) -- Use Base Model (DONE)
- Reference (referenced) (DONE)
- View -- 
    View class should return all CreateInline/ReadInline related nodes fully expanded (DONE)
- Update View -- use same for GET and POST

"""
