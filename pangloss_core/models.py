import re
import typing
import uuid

import neo4j.exceptions
import pydantic

from pangloss_core.model_setup.base_node_definitions import EditNodeBase

from pangloss_core.model_setup.base_node_definitions import (
    AbstractBaseNode,
    ViewNodeBase,
)
from pangloss_core.model_setup.model_manager import ModelManager
from pangloss_core.database import Transaction, write_transaction, read_transaction
from pangloss_core.model_setup.reference_node_base import BaseNodeReference
from pangloss_core.cypher_utils import cypher
from pangloss_core.exceptions import PanglossNotFoundError, PanglossCreateError

from pangloss_core.model_setup.relation_to import (
    RelationTo,
    ReifiedRelation,
    ReifiedTargetConfig,
)
from pangloss_core.model_setup.embedded import Embedded
from pangloss_core.model_setup.config_definitions import EmbeddedConfig, RelationConfig
from pangloss_core.model_setup.relation_properties_model import RelationPropertiesModel


class BaseNode(AbstractBaseNode):
    __abstract__ = True

    def __init_subclass__(cls):
        ModelManager.register_model(cls)
        super().__init_subclass__()

    def __str__(self):
        return f"{self.__class__.__name__}({super().__str__()})"

    @classmethod
    @read_transaction
    async def get_view(cls, tx: Transaction, uid: uuid.UUID) -> ViewNodeBase | None:
        query = cypher.read_query(cls)

        with open("read_query.cypher", "w") as f:
            f.write(query)

        result = await tx.run(query, {"uid": str(uid)})  # type: ignore
        record = await result.value()
        # print(record)
        if len(record) == 0:
            raise PanglossNotFoundError(f'<{cls.__name__} uid="{uid}"> not found')
        # print(record[0])
        return cls.View(**record[0])

    @write_transaction
    async def create(
        self, tx: Transaction, username: str = "Auto"
    ) -> BaseNodeReference:
        # print(user.username)
        (
            node_identifier,
            MATCH_CLAUSES,
            CREATE_CLAUSES,
            params_dict,
        ) = cypher.build_write_query_and_params_dict(self, username=username)

        query = f"""
        {"""

        """.join(MATCH_CLAUSES)}
        {"""

        """.join(CREATE_CLAUSES)}
        
        
        return {node_identifier}{{.uid, .label, .real_type}}
        """

        with open("write_query.cypher", "w") as f:
            f.write(query)

            f.write(str(params_dict))

        # try:
        # Annoyingly, need override this type hint as Transaction.run takes type LiteralString
        # (not str), which means we cannot dynamically construct the query string
        try:
            result = await tx.run(query, params_dict)  # type:ignore

            record = await result.value()
        except neo4j.exceptions.ConstraintError as e:
            raise PanglossCreateError(e.message)

        # print(record)
        return self.Reference(**record[0])
        # except Exception as e:
        #    print(e)
        #    raise PanglossCreateError(message=e)

    @classmethod
    @read_transaction
    async def get_edit(cls, tx: Transaction, uid: uuid.UUID) -> EditNodeBase:
        # Added some query optimisation: if cls has no outgoing relations or embedded nodes defined,
        # there should be no need to look up these paths.
        # TODO: Further optimisation: if no paths need to be followed at all, there is no need to do this
        # path unpacking business at all!
        query = cypher.read_query(cls)

        with open("read_query.cypher", "w") as f:
            f.write(query)

        result = await tx.run(query, {"uid": str(uid)})  # type: ignore
        record = await result.value()

        if len(record) == 0:
            raise PanglossNotFoundError(f'<{cls.__name__} uid="{uid}"> not found')

        return cls.Edit(**record[0])

    @staticmethod
    @write_transaction
    async def _write_edit(
        item: EditNodeBase, tx: Transaction, username: str = "Auto"
    ) -> None:
        query, params = cypher.update_query(item, username=username)
        with open("update_query.cypher", "w") as f:
            f.write(query)
            f.write("\n\n\n\n")
            f.write(str(params))
        result = await tx.run(query, params)  # type: ignore
        record = await result.value()
        if len(record) == 0:
            raise PanglossNotFoundError(
                f'<{item.base_class.__name__} uid="{item.uid}"> not found'
            )

    @classmethod
    @read_transaction
    async def get_list(
        cls,
        tx: Transaction,
        q: typing.Optional[str],
        page: int = 0,
        page_size: int = 10,
    ) -> list[BaseNodeReference]:
        if q:
            terms = q.split(" ")

            search_string = " AND ".join(f"/{re.escape(term)}.*/" for term in terms)

            query = f"""            
                CALL {{
                    CALL db.index.fulltext.queryNodes("{cls.__name__}FullTextIndex", $q) YIELD node, score

                    WITH collect(node) AS ns, COUNT(DISTINCT node) as total, score
                    UNWIND ns AS m

                    RETURN m as matches, total as total_items ORDER BY score SKIP $skip LIMIT $pageSize
                }}
                WITH COLLECT(matches{{.uid, .label, .citation, .real_type}}) AS matches_list, total_items
                RETURN {{results: matches_list, count: total_items, page: $page, totalPages: toInteger(round((total_items*1.0)/$pageSize, 0, "UP"))}}
            """

            params = {
                "skip": (page - 1) * page_size,
                "pageSize": page_size,
                "page": page,
                "q": search_string,
            }

        else:
            query = f"""CALL {{
                        MATCH (node:{cls.__name__})
                        WITH collect(node) AS ns, COUNT (DISTINCT node) as total
                        UNWIND ns AS m
                        RETURN m as matches, total as total_items ORDER BY m.label SKIP $skip LIMIT $pageSize
                    }}
                    WITH COLLECT(matches{{.uid, .label, .citation, .real_type}}) AS matches_list, total_items
                    RETURN {{results: matches_list, count: total_items, page: $page, totalPages: toInteger(round((total_items*1.0)/$pageSize, 0, "UP"))}}
                """
            params = {
                "skip": (page - 1) * page_size,
                "pageSize": page_size,
                "page": page,
            }

        result = await tx.run(query, params)  # type: ignore
        records = await result.value()

        try:

            return records[0]
        except IndexError:
            return {"results": [], "count": 0, "page": page, "totalPages": 0}
