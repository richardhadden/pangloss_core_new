import asyncio
import typing

from rich import print


from pangloss_core.database import Database
from pangloss_core.model_setup.model_manager import ModelManager
from pydantic import BaseModel

if typing.TYPE_CHECKING:
    from pangloss_core.models import BaseNode

class IndexAnnotation():
    def __hash__(self):
        return 0

class Index(IndexAnnotation):
    pass


class Unique(IndexAnnotation):
    pass


class TextIndex(IndexAnnotation):
    pass


class FullTextIndex(IndexAnnotation):
    pass


class OmitFromNodeFullTextIndex(IndexAnnotation):
    pass


def get_string_fields(model: type["BaseNode"]) -> list[str]:
    string_fields = []
    for field_name, field in model.model_fields.items():

        try:
            annotated_type, *annotations = typing.get_args(field.annotation)
            annotated_string = annotated_type == str and not any(
                isinstance(ann, OmitFromNodeFullTextIndex)
                or ann is OmitFromNodeFullTextIndex
                for ann in annotations
            )
        except ValueError:
            pass

        if field.annotation == str or annotated_string:
            string_fields.append(field_name)

    return string_fields


def install_indexes_and_constraints():
    queries = [
        "CREATE CONSTRAINT BaseNodeUidUnique IF NOT EXISTS FOR (n:BaseNode) REQUIRE n.uid IS UNIQUE",
    ]
    print("Creating Constraint: [green bold]BaseNode[/green bold].[blue bold]uid[/blue bold] must be unique")
    
    for model in ModelManager._registered_models:
        string_fields = get_string_fields(model)
        string_fields_query = ", ".join(
            f"n.{field_name}" for field_name in string_fields
        )
        queries.extend(
            [   
                f"""CREATE FULLTEXT INDEX {model.__name__}FullTextIndex 
                IF NOT EXISTS FOR (n:{model.__name__}) ON EACH [{string_fields_query}]
                OPTIONS {{
                    indexConfig: {{
                        `fulltext.analyzer`: 'standard-no-stop-words',
                        `fulltext.eventually_consistent`: true
                    }}
                }}
                """,
            ]
        )
        print(f"Creating Full Text Index for [green bold]{model.__name__}[/green bold] on fields {", ".join(f"[blue bold]{f}[/blue bold]" for f in string_fields)}")

    async def _run(queries):

        async def _run_query(query):
            await Database.cypher_write(query, {})

        await asyncio.gather(*[_run_query(query) for query in queries])

    asyncio.run(_run(queries))
