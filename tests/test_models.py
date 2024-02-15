from __future__ import annotations

import typing

import annotated_types
import pytest

from pangloss_core_new.exceptions import PanglossConfigError
from pangloss_core_new.model_setup.base_node_definitions import (
    BaseNonHeritableMixin,
    RelationPropertiesModel,
)
from pangloss_core_new.model_setup.config_definitions import (
    EmbeddedConfig,
    RelationConfig,
)
from pangloss_core_new.model_setup.embedded import Embedded
from pangloss_core_new.model_setup.model_manager import ModelManager
from pangloss_core_new.model_setup.relation_to import RelationTo
from pangloss_core_new.models import BaseNode


@pytest.fixture(scope="function", autouse=True)
def reset_model_manager():
    ModelManager._reset()


def test_get_labels():
    class Thing(BaseNode):
        __abstract__ = True

    class Animal(Thing):
        pass

    class Pet(Animal):
        __abstract__ = True

    assert set(Pet._get_model_labels()) == set(["Thing", "Animal", "Pet", "BaseNode"])


def test_model_init_from_camel_dict():
    """Tests that models can be populated by the equivalent camelCase (standard for JSON API),
    which is automatically converted to snake_case"""

    class Thing(BaseNode):
        one_thing: int
        another_thing: str

    ModelManager.initialise_models(depth=3)

    thing = Thing(  # type: ignore
        **{
            "label": "something",
            "oneThing": 42,
            "anotherThing": "another thing",
        }
    )

    assert thing.one_thing == 42
    assert thing.another_thing == "another thing"


def test_abstract_declaration_not_inherited():
    class Thing(BaseNode):
        __abstract__ = True

    class Animal(Thing):
        pass

    class Pet(Animal):
        __abstract__ = True

    ModelManager.initialise_models(depth=3)

    assert Thing.__abstract__
    assert not Animal.__abstract__
    assert Pet.__abstract__


def test_non_heritable_mixins_are_inherited_directly():
    """Test NonHeritableMixins are inherited by direct child"""

    class Purchaseable(BaseNonHeritableMixin):
        price: int

    class Animal(BaseNode):
        name: str

    class Pet(Animal, Purchaseable):
        age: int

    ModelManager.initialise_models(depth=3)

    assert "name" in Pet.model_fields
    assert "age" in Pet.model_fields
    assert "price" in Pet.model_fields

    assert set(Pet._get_model_labels()) == set(
        ["BaseNode", "Purchaseable", "Animal", "Pet"]
    )


def test_non_heritable_mixins_are_not_inherited_indirectly():
    """Test NonHeritableMixins are not inherited by grandchild classes"""

    class Purchaseable(BaseNonHeritableMixin):
        price: int

    class Animal(BaseNode):
        name: str

    class Pet(Animal, Purchaseable):
        age: int

    class NonPurchaseablePet(Pet):
        something: int

    ModelManager.initialise_models(depth=3)

    assert "name" in Animal.model_fields
    assert "name" in Pet.model_fields
    assert "price" in Pet.model_fields

    # Check we have the expected inherited fields
    assert "name" in NonPurchaseablePet.model_fields
    assert "age" in NonPurchaseablePet.model_fields

    # But not the price, as we should not inherit from Purchaseable
    assert "price" not in NonPurchaseablePet.model_fields

    assert set(NonPurchaseablePet._get_model_labels()) == set(
        ["BaseNode", "NonPurchaseablePet", "Animal", "Pet"]
    )


def test_embedded_cannot_be_in_model_name():
    with pytest.raises(PanglossConfigError):

        class EmbeddedSomething(BaseNode):
            pass


def test_embedded_model_tracks_base_class():
    class Thing(BaseNode):
        pass

    ModelManager.initialise_models()

    assert Thing.Embedded.base_class is Thing


def test_model_embedded_type_with_basic_fields():
    class Thing(BaseNode):
        age: int
        something_else: str

    ModelManager.initialise_models()

    assert Thing.Embedded
    assert "label" not in Thing.Embedded.model_fields
    assert set(Thing.Embedded.model_fields.keys()) == set(
        ["real_type", "uid", "age", "something_else"]
    )


def test_embedding_a_model():
    class Thing(BaseNode):
        pass

    class Parent(BaseNode):
        things_plain: Embedded[Thing]
        things_annotated: typing.Annotated[
            Embedded[Thing], EmbeddedConfig(validators=[annotated_types.MaxLen(3)])
        ]
        otherthings_plain: Embedded[OtherThing]
        otherthings_annotated: typing.Annotated[
            Embedded[OtherThing], EmbeddedConfig(validators=[annotated_types.MaxLen(1)])
        ]

        mixed_thing: Embedded[Thing | OtherThing]

    class OtherThing(BaseNode):
        pass

    ModelManager.initialise_models(depth=3)

    # Test annotations are returned with the correct types
    assert Parent.model_fields["things_plain"].annotation == list[Thing.Embedded]
    assert Parent.model_fields["things_annotated"].annotation == list[Thing.Embedded]
    assert (
        Parent.model_fields["otherthings_plain"].annotation == list[OtherThing.Embedded]
    )
    assert (
        Parent.model_fields["otherthings_annotated"].annotation
        == list[OtherThing.Embedded]
    )
    assert (
        Parent.model_fields["mixed_thing"].annotation
        == list[typing.Union[Thing.Embedded, OtherThing.Embedded]]
    )

    # Check default length (1) for non-specified annotation
    assert annotated_types.MinLen(1) in Parent.model_fields["things_plain"].metadata
    assert annotated_types.MaxLen(1) in Parent.model_fields["things_plain"].metadata

    # Assert defaults are not used when validators provided
    assert (
        annotated_types.MinLen(1)
        not in Parent.model_fields["things_annotated"].metadata
    )
    assert annotated_types.MaxLen(3) in Parent.model_fields["things_annotated"].metadata

    assert Parent.embedded_nodes["things_plain"].embedded_class == Thing


def test_double_model_embedding():
    class Inner(BaseNode):
        pass

    class Outer(BaseNode):
        has_inner: Embedded[Inner]

    class Parent(BaseNode):
        has_outer: Embedded[Outer]

    ModelManager.initialise_models(depth=3)

    assert Parent.model_fields["has_outer"].annotation == list[Outer.Embedded]
    assert Outer.model_fields["has_inner"].annotation == list[Inner.Embedded]
    assert Outer.Embedded.model_fields["has_inner"].annotation == list[Inner.Embedded]

    assert Parent.embedded_nodes["has_outer"].embedded_class == Outer
    assert Outer.embedded_nodes["has_inner"].embedded_class == Inner


def test_instantiating_double_embedded():
    class Inner(BaseNode):
        pass

    class Outer(BaseNode):
        has_inner: Embedded[Inner]

    class Parent(BaseNode):
        has_outer: Embedded[Outer]

    ModelManager.initialise_models(depth=3)

    p = Parent(
        label="A Parent",
        has_outer=[{"real_type": "outer", "has_inner": [{"real_type": "inner"}]}],
    )

    # Check things are instantiated with the right type
    assert isinstance(p.has_outer[0], Outer.Embedded)
    assert isinstance(p.has_outer[0].has_inner[0], Inner.Embedded)

    # Check we can also access embedded_nodes via proxy to main object
    assert p.has_outer[0].embedded_nodes == Outer.embedded_nodes
    assert p.has_outer[0].embedded_nodes["has_inner"].embedded_class == Inner


def test_model_relation_construction():
    class Person(BaseNode):
        pets: typing.Annotated[
            RelationTo[Pet],
            RelationConfig(
                reverse_name="is_owned_by", validators=[annotated_types.MaxLen(2)]
            ),
        ]

    class Pet(BaseNode):
        pass

    class Reptile(Pet):
        __abstract__ = True

    class Crocodile(Pet):
        pass

    ModelManager.initialise_models(depth=3)

    assert set(
        cl.__name__
        for cl in typing.get_args(
            typing.get_args(Person.model_fields["pets"].annotation)[0]
        )
    ) == {"Person__pets__Pet_Reference", "Person__pets__Crocodile_Reference"}

    schema = Person.model_json_schema()

    assert {"$ref": "#/$defs/Person__pets__Pet_Reference"} in schema["properties"][
        "pets"
    ]["items"]["anyOf"]
    assert {"$ref": "#/$defs/Person__pets__Crocodile_Reference"} in schema[
        "properties"
    ]["pets"]["items"]["anyOf"]


def test_relation_to():
    class Pet(BaseNode):
        pass

    class Reptile(Pet):
        __abstract__ = True

    class Crocodile(Pet):
        pass

    class Person(BaseNode):
        pets: typing.Annotated[
            RelationTo[Pet],
            RelationConfig(
                reverse_name="is_owned_by", validators=[annotated_types.MaxLen(2)]
            ),
        ]

    ModelManager.initialise_models(depth=3)
    assert "pets" in Person.model_fields
    assert {
        arg.__name__
        for arg in Person.model_fields["pets"].annotation.__args__[0].__args__
    } == {"Person__pets__Pet_Reference", "Person__pets__Crocodile_Reference"}

    # Test that that abstract Reptile is not included by
    # making sure that the length is only 2 (i.e. the above two)
    assert len(Person.model_fields["pets"].annotation.__args__[0].__args__) == 2  # type: ignore

    maxlen_validator, relation_config = Person.model_fields["pets"].metadata

    assert maxlen_validator == annotated_types.MaxLen(2)
    assert relation_config.reverse_name == "is_owned_by"
    assert relation_config.relation_to_base == Pet

    schema = Person.model_json_schema()

    assert {"$ref": "#/$defs/Person__pets__Pet_Reference"} in schema["properties"][
        "pets"
    ]["items"]["anyOf"]
    assert {"$ref": "#/$defs/Person__pets__Crocodile_Reference"} in schema[
        "properties"
    ]["pets"]["items"]["anyOf"]

    # Test that that abstract Reptile is not included by
    # making sure that the length is only 2 (i.e. the above two)
    assert len(schema["properties"]["pets"]["items"]["anyOf"]) == 2


def test_relation_to_with_union_type():
    class Person(BaseNode):
        pass

    class Cat(BaseNode):
        pass

    class Event(BaseNode):
        subject: typing.Annotated[
            RelationTo[Person | Cat], RelationConfig(reverse_name="is_subject_of")
        ]

    ModelManager.initialise_models(depth=3)


def test_reference_model_on_relation():
    class PersonPetRelation(RelationPropertiesModel):
        cost_of_purchase: int

    class Pet(BaseNode):
        name: str

        # class Reference:
        #    name: str
        #    weight: int

    class Crocodile(Pet):
        pass

    class Person(BaseNode):
        pets: typing.Annotated[
            RelationTo[Pet],
            RelationConfig(
                reverse_name="is_owned_by",
                validators=[annotated_types.MaxLen(2)],
                relation_model=PersonPetRelation,
            ),
        ]

    ModelManager.initialise_models(depth=3)

    p = Person(
        **{
            "label": "Tom Jones",
            "pets": [
                {
                    "name": "Mister Frisky",
                    "label": "Mr Frisky",
                    "real_type": "pet",
                    "relation_properties": {"cost_of_purchase": 200},
                },
                {
                    "name": "Mr Snappy",
                    "label": "Mr Snappy",
                    "real_type": "crocodile",
                    "relation_properties": {"cost_of_purchase": 300},
                },
            ],
        }
    )

    assert Person.model_fields["pets"].annotation
    assert typing.get_args(Person.model_fields["pets"].annotation)

    assert len(p.pets) == 2
    mf, ms = sorted(list(p.pets), key=lambda p: p.label)

    assert type(mf).__name__ == "Person__pets__Pet_Reference"

    assert mf.label == "Mr Frisky"

    assert mf.relation_properties.cost_of_purchase == 200

    assert type(ms).__name__ == "Person__pets__Crocodile_Reference"
    assert ms.label == "Mr Snappy"
    assert ms.relation_properties.cost_of_purchase == 300
