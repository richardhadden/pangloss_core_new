from __future__ import annotations

import inspect
import typing
import uuid
from typing import Any
from pangloss_core.model_setup.base_node_definitions import (
    EditNodeBase,
    EmbeddedNodeBase,
)

import pydantic



if typing.TYPE_CHECKING:
    from pangloss_core.model_setup.base_node_definitions import (
        AbstractBaseNode,
    )

from pangloss_core.model_setup.relation_to import ReifiedRelation


def get_unique_string():
    return "x" + uuid.uuid4().hex[:6].lower()


def labels_to_query_labels(
    node: AbstractBaseNode | type[AbstractBaseNode] | type[EditNodeBase],
    extra_labels: list[str] | None = None,
) -> str:
    try:
        labels = node._get_model_labels()
    except:
        labels = node.base_class._get_model_labels()

    if extra_labels:
        labels.extend(extra_labels)
    return ":" + ":".join(labels)


def convert_type_for_writing(value):
    match value:
        case uuid.UUID():
            return str(value)
        case pydantic.AnyUrl():
            return str(value)
        case set():
            return list(value)
        case _:
            return value


def unpack_properties_to_create_props_and_param_dict(
    node: AbstractBaseNode,
    username: str,
    skip_fields: list[str] = [],
    omit_braces: bool=False
) -> tuple[str, dict[str, Any]]:
    q_pairs = []
    params = {}

    for prop_name, field in node.property_fields.items():
        if prop_name not in skip_fields:
            try:
                param_id = get_unique_string()
                params[param_id] = convert_type_for_writing(getattr(node, prop_name))
                q_pairs.append(f"""{prop_name}: ${param_id}""")
            except AttributeError as e:
                if isinstance(node, EmbeddedNodeBase) and prop_name == "label":
                    pass
                else:
                    print(prop_name)
                    raise AttributeError(e)

    real_type_id = get_unique_string()
    
   
    if hasattr(node, "real_type"):
        params[real_type_id] = (
            node.real_type
        )
    else:
        params[real_type_id] = node.__class__.__name__
  
    params["username"] = username
        
    q_pairs.append(f"""real_type: ${real_type_id}""")
    q_pairs.append("""created_when: datetime()""")
    q_pairs.append("""modified_when: datetime()""")
    q_pairs.append("""created_by: $username""")
    q_pairs.append("""modified_by: $username""")
    if omit_braces:
        return ", ".join(q_pairs), params
    return "{" + ", ".join(q_pairs) + "}", params


def unpack_dict_to_cypher_map_and_params(d):
    q_pairs = []
    params = {}
    for key, value in d.items():
        param_id = get_unique_string()
        params[param_id] = convert_type_for_writing(value)
        q_pairs.append(f"""{key}: ${param_id}""")
    return "{" + ", ".join(q_pairs) + "}", params


def build_write_query_and_params_dict_for_single_node(
    node: AbstractBaseNode, username: str
) -> tuple[str, str, dict[str, Any]]:
    labels = labels_to_query_labels(node)
    (
        node_props,
        params_dict,
    ) = unpack_properties_to_create_props_and_param_dict(node, username=username)

    node_identifier = get_unique_string()

    query = f"""
    
    CREATE ({node_identifier}{labels_to_query_labels(node)} {node_props})
    
    """
    return node_identifier, query, params_dict


def build_write_query_for_related_node(
    current_node_identifier: str,
    related_node: AbstractBaseNode,
    relation_label: str,
    relation_properties: dict,
) -> tuple[list[str], list[str], dict[str, Any]]:
    related_node_identifier = get_unique_string()
    uid_param = get_unique_string()

    (
        relation_properties_cypher,
        relation_properties_params,
    ) = unpack_dict_to_cypher_map_and_params(relation_properties)

    MATCH_CLAUSES = [f"MATCH ({related_node_identifier} {{uid: ${uid_param}}})"]
    CREATE_CLAUSES = [
        f"CREATE ({current_node_identifier})-[:{relation_label.upper()} {relation_properties_cypher}]->({related_node_identifier})"
    ]

    return (
        MATCH_CLAUSES,
        CREATE_CLAUSES,
        {
            **relation_properties_params,
            uid_param: convert_type_for_writing(related_node.uid),
        },
    )


def build_write_query_and_params_dict(
    node: AbstractBaseNode, username: str, extra_labels: list[str] | None = None, 
) -> tuple[str, list[str], list[str], dict[str, Any]]:
    
    (
        node_props,
        params_dict,
    ) = unpack_properties_to_create_props_and_param_dict(node, username=username)

    node_identifier = get_unique_string()

    CREATE_CLAUSES = [
        f"CREATE ({node_identifier}{labels_to_query_labels(node, extra_labels=extra_labels)} {node_props})"
    ]
    MATCH_CLAUSES = []

    for embedded_name, embedded_definition in node.embedded_nodes.items():
        for embedded_node in getattr(node, embedded_name):
            (
                embedded_node_identifier,
                embedded_query_match_clauses,
                embedded_query_create_clauses,
                embedded_params_dict,
            ) = build_write_query_and_params_dict(
                embedded_node, extra_labels=["Embedded", "DeleteDetach"], username=username
            )
            CREATE_CLAUSES += [
                *embedded_query_create_clauses,
                f"CREATE ({node_identifier})-[:{embedded_name.upper()}]->({embedded_node_identifier})",
            ]
            MATCH_CLAUSES += embedded_query_match_clauses

            params_dict = {**params_dict, **embedded_params_dict}

    for relation_name, relation in node.outgoing_relations.items():
        # print(">>>>", relation.target_base_class)
        if inspect.isclass(relation.target_base_class) and issubclass(
            relation.target_base_class, ReifiedRelation
        ):
            for related_reification in getattr(node, relation_name):
                (
                    reified_node_identifier,
                    reified_query_match_clauses,
                    reified_query_create_clauses,
                    reified_params_dict,
                ) = build_write_query_and_params_dict(related_reification, username=username)

                relation_dict = {
                    "reverse_name": relation.relation_config.reverse_name,
                    "relation_labels": relation.relation_config.relation_labels,
                    # **dict(related_reification.relation_properties),
                }

                (
                    relation_properties_cypher,
                    relation_properties_params,
                ) = unpack_dict_to_cypher_map_and_params(relation_dict)

                CREATE_CLAUSES += [
                    *reified_query_create_clauses,
                    f"CREATE ({node_identifier})-[:{relation_name.upper()} {relation_properties_cypher}]->({reified_node_identifier})",
                ]
                MATCH_CLAUSES += reified_query_match_clauses
                params_dict = {
                    **params_dict,
                    **reified_params_dict,
                    **relation_properties_params,
                }
        elif relation.relation_config.create_inline:
            for related_item in getattr(node, relation_name):
                extra_labels = ["CreateInline", "ReadInline"]
                if relation.relation_config.edit_inline:
                    extra_labels.append("EditInline")
                if relation.relation_config.delete_related_on_detach:
                    extra_labels.append("DeleteDetach")
                (
                    related_node_identifier,
                    query_match_clauses,
                    query_create_clauses,
                    query_params_dict,
                ) = build_write_query_and_params_dict(
                    related_item, extra_labels=extra_labels, username=username
                )

                CREATE_CLAUSES += [
                    *query_create_clauses,
                    f"CREATE ({node_identifier})-[:{relation_name.upper()}]->({related_node_identifier})",
                ]
                MATCH_CLAUSES += query_match_clauses
                params_dict = {**params_dict, **query_params_dict}

        else:
            for related_item in getattr(node, relation_name):
                relation_dict = {
                    "reverse_name": relation.relation_config.reverse_name,
                    "relation_labels": relation.relation_config.relation_labels,
                    **dict(getattr(related_item, "relation_properties", {})),
                }

                (
                    related_node_match_clauses,
                    related_node_create_clauses,
                    related_node_params,
                ) = build_write_query_for_related_node(
                    current_node_identifier=node_identifier,
                    related_node=related_item,
                    relation_label=relation_name,
                    relation_properties=relation_dict,
                )
                params_dict = {**params_dict, **related_node_params}
                MATCH_CLAUSES += related_node_match_clauses
                CREATE_CLAUSES += related_node_create_clauses

    # for embedded_node_name, embedded_node_definition in node.embedded_nodes.items():
    #    for embedded_node in getattr(node, rel)

    return node_identifier, MATCH_CLAUSES, CREATE_CLAUSES, params_dict


def read_query(cls: type[AbstractBaseNode]):
    label = cls.__name__
    query = f"""
        
        MATCH path_to_node = (node:{label} {{uid: $uid}})
        
        CALL {{
            WITH node, path_to_node
            {"""OPTIONAL MATCH path_to_direct_nodes = (node)-[]->(:BaseNode)""" if cls.outgoing_relations else ""}
            OPTIONAL MATCH path_through_read_nodes = (node)-[]->(:ReadInline)((:ReadInline)-[]->(:ReadInline)){{0,}}(:ReadInline)-[]->{{0,}}(:BaseNode)
            {"""OPTIONAL MATCH path_to_related_through_embedded = (node)-[]->(:Embedded)((:Embedded)-[]->(:Embedded)){ 0, }(:Embedded)-[]->{0,}(:BaseNode)""" if cls.embedded_nodes else ""}
            OPTIONAL MATCH path_to_reified = (node)-[]->(:ReifiedRelation)-[]->(:BaseNode)
            WITH apoc.coll.flatten([
                {"collect(path_to_direct_nodes)," if cls.outgoing_relations else ""}
                {"collect(path_to_related_through_embedded)," if cls.embedded_nodes else ""}
                collect(path_through_read_nodes),
                collect(path_to_node),
                collect(path_to_reified)
            ]) AS paths, node
            CALL apoc.convert.toTree(paths)
            YIELD value
            RETURN value as value
        }}
        {
        """WITH node, value
        CALL {
            WITH node
            CALL {
                WITH node
                OPTIONAL MATCH (node)<--(x WHERE (x:ReifiedRelation))(()<--()){ 0, }()<-[reverse_relation]-(related_node)
                WHERE NOT related_node:Embedded AND NOT related_node:ReifiedRelation
                WITH reverse_relation.reverse_name AS reverse_relation_type, collect(related_node{ .uid, .label, .real_type }) AS related_node_data
                RETURN collect({ t: reverse_relation_type, related_node_data: related_node_data }) AS via_reified
            }
            CALL {
                WITH node
                OPTIONAL MATCH (node)<-[reverse_relation]-(x WHERE (x:Embedded))(()<--()){ 0, }()<--(related_node)
                WHERE NOT related_node:Embedded AND NOT related_node:ReifiedRelation
                WITH reverse_relation.reverse_name AS reverse_relation_type, collect(related_node{ .uid, .label, .real_type }) AS related_node_data
                RETURN collect({ t: reverse_relation_type, related_node_data: related_node_data }) AS via_embedded
            }
            CALL {
                WITH node
                MATCH (node)<-[reverse_relation]-(related_node:BaseNode)
                WHERE NOT related_node:Embedded AND NOT related_node:ReifiedRelation
                WITH reverse_relation.reverse_name AS reverse_relation_type, collect(related_node{ .uid, .label, .real_type }) AS related_node_data
                RETURN collect({ t: reverse_relation_type, related_node_data: related_node_data }) AS direct_incoming
            }
            RETURN REDUCE(s = { }, item IN apoc.coll.flatten([direct_incoming, via_reified, via_embedded]) | apoc.map.setEntry(s, item.t, item.related_node_data)) AS reverse_relations
        }

        WITH value, node, reverse_relations
        RETURN apoc.map.mergeList([node, reverse_relations, value])""" if cls.incoming_relations else """ RETURN value """
        }
        
        """
    return query


def create_set_statement_for_properties(
    node: EditNodeBase, node_identifier: str
) -> tuple[str, dict[str, Any]]:
    properties = node.base_class.property_fields

    set_query = """
    
    """
    set_params = {}
    for property_name, property in properties.items():
        # Don't update uid
        if property_name == "uid":
            continue

        value = getattr(node, property_name, None)
        if value:
            key_identifier = get_unique_string()
            set_params[key_identifier] = convert_type_for_writing(value)
            set_query += f"""SET {node_identifier}.{property_name} = ${key_identifier}
            """

    return set_query, set_params


def build_properties_update_dict(node: EditNodeBase):
    property_fields = node.property_fields
    properties = {
        prop_name: convert_type_for_writing(prop_value)
        for prop_name, prop_value in dict(node).items()
        if prop_name in property_fields
    }
    properties["real_type"] = node.base_class.__name__
    return properties


def build_update_related_query(node, relation_name, start_node_identifier):
    related_item_array_identifier = get_unique_string()
    params = {
        related_item_array_identifier: [
            str(item.uid) for item in getattr(node, relation_name, [])
        ]
    }
    query = f"""
    // {node.__class__.__name__, node.uid}
    CALL {{ // Attach existing node if it is not attached
        WITH {start_node_identifier}
        UNWIND ${related_item_array_identifier} AS updated_related_item_uid
            MATCH (node_to_relate {{uid: updated_related_item_uid}})
            WHERE NOT ({start_node_identifier})-[:{relation_name.upper()}]->(node_to_relate)
            CREATE ({start_node_identifier})-[:{relation_name.upper()}]->(node_to_relate)
    }}
    // {node.__class__.__name__, node.uid}
    CALL {{ // If not in list but is related, delete relation
        WITH {start_node_identifier}
        MATCH ({start_node_identifier})-[existing_rel_to_delete:{relation_name.upper()}]->(currently_related_item)
        WHERE NOT currently_related_item.uid IN ${related_item_array_identifier}
        DELETE existing_rel_to_delete
    }}
    """
    return query, params


def build_update_inline_query_and_params(
    node: EditNodeBase,
    relation_name,
    start_node_identifier,
    username:str,
    delete_node_on_detach=False,
    accumulated_withs=None,
):
    if not accumulated_withs:
        accumulated_withs = set([start_node_identifier])

    update_relations_query = ""

    update_set_query = ""
    params = {}

    # Now, iterate through all the nodes and recursively build query to update
    related_nodes = getattr(node, relation_name, [])
    related_node_uid_list = [str(node.uid) for node in related_nodes]
    related_nodes_uid_list_param = get_unique_string()
    params.update({related_nodes_uid_list_param: related_node_uid_list})

    for related_node in related_nodes:
        related_node_identifier = get_unique_string()
        related_node_uid_param = get_unique_string()
        related_node_real_type_param = get_unique_string()

        params.update(
            {
                related_node_uid_param: str(related_node.uid),
                related_node_real_type_param: related_node.real_type,
            }
        )

        (
            target_update_relations_query,
            target_update_set_query,
            target_params,
        ) = build_node_update_query_and_params(
            related_node,
            related_node_identifier,
            username=username,
            accumulated_withs=set([*accumulated_withs, related_node_identifier]),
        )
        accumulated_withs.add(related_node_identifier)

        extra_labels = ["CreateInline", "ReadInline", "EditInline"]
        if node.outgoing_relations[
            relation_name
        ].relation_config.delete_related_on_detach:
            extra_labels.append("DeleteDetach")
        query_labels = labels_to_query_labels(related_node, extra_labels=extra_labels)

        # update_relations_query +=
        update_relations_query += f"""\n
        
        
        
        MERGE ({related_node_identifier}{query_labels} {{uid: ${related_node_uid_param}, real_type: ${related_node_real_type_param}}}) // {related_node.base_class.__name__}, {related_node.uid}, {related_node.label}
        ON CREATE
       
            {target_update_set_query}
            
        ON MATCH
            {target_update_set_query}
        
        WITH {", ".join(accumulated_withs)} // <<
          {target_update_relations_query}
        
        
        
        MERGE ({start_node_identifier})-[:{relation_name.upper()}]->({related_node_identifier})
        

      WITH {", ".join(accumulated_withs)} // <<<<
        """

        # update_relations_query += target_update_relations_query

        # update_set_query += target_update_set_query
        params.update(target_params)
    update_relations_query += f"""
    WITH {", ".join(accumulated_withs)} // <<<<
        
    CALL {{ // cleanup from {node.label}
       WITH {start_node_identifier}
       MATCH ({start_node_identifier})-[existing_rel_to_delete:{relation_name.upper()}]->(currently_related_item)
       
        WHERE NOT currently_related_item.uid IN ${related_nodes_uid_list_param}
        DELETE existing_rel_to_delete
        
        WITH currently_related_item
        {"""CALL {
                       WITH currently_related_item
            MATCH delete_path = (currently_related_item:DeleteDetach)(()-->(:DeleteDetach)){0,}(:DeleteDetach) 
            UNWIND nodes(delete_path) as x
           DETACH DELETE x 
           
        }""" if delete_node_on_detach else ""}

    }}"""

    return update_relations_query, update_set_query, params


def build_update_embedded_query_and_params(
    node: EmbeddedNodeBase | EditNodeBase,
    embedded_relation_name,
    
    start_node_identifier,
    username: str,
    accumulated_withs=None,
):
    print("Building embedded update query for", node.__class__.__name__)
    if not accumulated_withs:
        accumulated_withs = set([start_node_identifier])

    update_relations_query = ""

    update_set_query = ""
    params = {}

    # Now, iterate through all the nodes and recursively build query to update
    embedded_nodes = getattr(node, embedded_relation_name, [])
    embedded_node_uid_list = [str(node.uid) for node in embedded_nodes]
    embedded_nodes_uid_list_param = get_unique_string()
    params.update({embedded_nodes_uid_list_param: embedded_node_uid_list})

    for embedded_node in embedded_nodes:
        embedded_node_identifier = get_unique_string()
        embedded_node_uid_param = get_unique_string()
        embedded_node_real_type_param = get_unique_string()
        print("Adding embedded for", embedded_node.__class__.__name__)
        params.update(
            {
                embedded_node_uid_param: str(embedded_node.uid),
                embedded_node_real_type_param: embedded_node.real_type,
            }
        )

        (
            target_update_relations_query,
            target_update_set_query,
            target_params,
        ) = build_node_update_query_and_params(
            embedded_node,
            embedded_node_identifier,
            accumulated_withs=set([*accumulated_withs, embedded_node_identifier]),
            username=username
        )
        accumulated_withs.add(embedded_node_identifier)

        extra_labels = ["Embedded", "DeleteDetach"]

        query_labels = labels_to_query_labels(embedded_node, extra_labels=extra_labels)

        # update_relations_query +=
        update_relations_query += f"""\n
        MERGE ({embedded_node_identifier}{query_labels} {{uid: ${embedded_node_uid_param}, real_type: ${embedded_node_real_type_param}}}) // {embedded_node.base_class.__name__}, {embedded_node.uid}
        ON CREATE
            {target_update_set_query}
        ON MATCH
            {target_update_set_query}
        WITH {", ".join(accumulated_withs)} // <<
          {target_update_relations_query}
        MERGE ({start_node_identifier})-[:{embedded_relation_name.upper()}]->({embedded_node_identifier})
      WITH {", ".join(accumulated_withs)} // <<<<
        """

        # update_relations_query += target_update_relations_query

        # update_set_query += target_update_set_query
        params.update(target_params)
    update_relations_query += f"""
    WITH {", ".join(accumulated_withs)} // <<<<
        
    CALL  {{
       WITH {start_node_identifier}
       MATCH ({start_node_identifier})-[existing_rel_to_delete:{embedded_relation_name.upper()}]->(currently_related_item)
       
        WHERE NOT currently_related_item.uid IN ${embedded_nodes_uid_list_param}
        DELETE existing_rel_to_delete
        
        WITH currently_related_item
        CALL {{
            WITH currently_related_item
            MATCH delete_path = (currently_related_item:DeleteDetach)(()-->(:DeleteDetach)){{0,}}(:DeleteDetach) 
            UNWIND nodes(delete_path) as x
           DETACH DELETE x 
           
        }}
        
    }}"""

    return update_relations_query, update_set_query, params


def build_node_update_query_and_params(
    node: EditNodeBase, node_identifier: str, username: str, accumulated_withs=None
) -> tuple[str, str, dict[str, Any]]:
    if not accumulated_withs:
        accumulated_withs = set([node_identifier])

    properties_dict = build_properties_update_dict(node)
    properties_dict_param = get_unique_string()
    params: dict[str, Any] = {properties_dict_param: properties_dict}
    params["username"] = username
    update_set_query = f"""
    SET {node_identifier} = apoc.map.merge(${properties_dict_param}, {{created_when: coalesce({node_identifier}.created_when, datetime()), modified_when: datetime(), modified_by: $username}}) // {properties_dict}
    """
    update_relations_query = ""
    for embedded_name, embedded_definition in node.base_class.embedded_nodes.items():
        (
            embedded_update_related_query,
            embedded_update_set_query,
            embedded_params,
        ) = build_update_embedded_query_and_params(
            node, embedded_name, node_identifier, username=username, accumulated_withs=accumulated_withs, 
        )
        update_relations_query += embedded_update_related_query
        update_set_query += embedded_update_set_query
        params.update(embedded_params)

    for relation_name, relation in node.base_class.outgoing_relations.items():
        if not relation.relation_config.edit_inline:
            update_related_query, update_related_params = build_update_related_query(
                node, relation_name, node_identifier
            )
            update_relations_query += update_related_query
            params.update(update_related_params)
        if relation.relation_config.edit_inline:
            (
                relation_update_related_query,
                relation_update_set_query,
                relation_params,
            ) = build_update_inline_query_and_params(
                node,
                relation_name,
                
                node_identifier,
                username=username,
                delete_node_on_detach=relation.relation_config.delete_related_on_detach,
                
                accumulated_withs=accumulated_withs,
            )
            update_relations_query += relation_update_related_query
            update_set_query += relation_update_set_query
            params.update(relation_params)

    return update_relations_query, update_set_query, params


def update_query(node: EditNodeBase, username:str) -> tuple[str, dict[str, Any]]:
    node_identifier = get_unique_string()
    node_uid_param = get_unique_string()

    params = {node_uid_param: str(node.uid)}
    query = f"""MATCH ({node_identifier} {{uid: ${node_uid_param}}}) // {node.base_class.__name__}, {node.uid}, {node.label}"""

    (
        update_relations_query,
        update_set_query,
        node_update_params,
    ) = build_node_update_query_and_params(node, node_identifier, username=username)
    query += update_relations_query

    query += update_set_query

    query += f"""RETURN {node_identifier}{{.uid}}"""

    params.update(node_update_params)
    return query, params
