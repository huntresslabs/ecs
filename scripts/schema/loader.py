# Licensed to Elasticsearch B.V. under one or more contributor
# license agreements. See the NOTICE file distributed with
# this work for additional information regarding copyright
# ownership. Elasticsearch B.V. licenses this file to you under
# the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# 	http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import copy
import git
import glob
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
import yaml

from generators import ecs_helpers
from _types import (
    Field,
    FieldEntry,
    FieldNestedEntry,
    MultiField,
    SchemaDetails,
)

# Loads main ECS schemas and optional additional schemas.
# They are deeply nested, then merged together.
# This script doesn't fill in defaults other than the bare minimum for a predictable
# deeply nested structure. It doesn't concern itself with what "should be allowed"
# in being a good ECS citizen. It just loads things and merges them together.

# The deeply nested structured returned by this script looks like this.
#
# [schema name]: {
#   'schema_details': {
#       'reusable': ...
#   },
#   'field_details': {
#       'type': ...
#   },
#   'fields': {
#       [field name]: {
#           'field_details': { ... }
#           'fields': {
#
#               (dotted key names replaced by deep nesting)
#               [field name]: {
#                   'field_details': { ... }
#                   'fields': {
#                   }
#               }
#           }
#       }
#   }

# Schemas at the top level always have all 3 keys populated.
# Leaf fields only have 'field_details' populated.
# Any intermediate field with other fields nested within them have 'fields' populated.
# Note that intermediate fields rarely have 'field_details' populated, but it's supported.
#   Examples of this are 'dns.answers', 'observer.egress'.


EXPERIMENTAL_SCHEMA_DIR = "experimental/schemas"


def load_schemas(
    ref: Optional[str] = None, included_files: Optional[List[str]] = []
) -> Dict[str, FieldEntry]:
    """Loads ECS and custom schemas. They are returned deeply nested and merged."""
    # ECS fields (from git ref or not)
    schema_files_raw: Dict[str, FieldNestedEntry] = (
        load_schemas_from_git(ref)
        if ref
        else load_schema_files(ecs_helpers.ecs_files())
    )
    fields: Dict[str, FieldEntry] = deep_nesting_representation(schema_files_raw)

    # Custom additional files
    if included_files and len(included_files) > 0:
        print("Loading user defined schemas: {0}".format(included_files))
        # If --ref provided and --include loading experimental schemas
        if ref and EXPERIMENTAL_SCHEMA_DIR in included_files:
            exp_schema_files_raw: Dict[str, FieldNestedEntry] = load_schemas_from_git(
                ref, target_dir=EXPERIMENTAL_SCHEMA_DIR
            )
            exp_fields: Dict[str, FieldEntry] = deep_nesting_representation(
                exp_schema_files_raw
            )
            fields = merge_fields(fields, exp_fields)
            included_files.remove(EXPERIMENTAL_SCHEMA_DIR)
        # Remaining additional custom files (never from git ref)
        custom_files: List[str] = ecs_helpers.glob_yaml_files(included_files)
        custom_fields: Dict[str, FieldEntry] = deep_nesting_representation(
            load_schema_files(custom_files)
        )
        fields = merge_fields(fields, custom_fields)
    return fields


def load_schema_files(files: List[str]) -> Dict[str, FieldNestedEntry]:
    fields_nested: Dict[str, FieldNestedEntry] = {}
    for f in files:
        new_fields: Dict[str, FieldNestedEntry] = read_schema_file(f)
        fields_nested = ecs_helpers.safe_merge_dicts(fields_nested, new_fields)
    return fields_nested


def load_schemas_from_git(
    ref: str, target_dir: Optional[str] = "schemas"
) -> Dict[str, FieldNestedEntry]:
    tree: git.objects.tree.Tree = ecs_helpers.get_tree_by_ref(ref)
    fields_nested: Dict[str, FieldNestedEntry] = {}

    # Handles case if target dir doesn't exists in git ref
    if ecs_helpers.path_exists_in_git_tree(tree, target_dir):
        for blob in tree[target_dir].blobs:
            if blob.name.endswith(".yml"):
                new_fields: Dict[str, FieldNestedEntry] = read_schema_blob(blob, ref)
                fields_nested = ecs_helpers.safe_merge_dicts(fields_nested, new_fields)
    else:
        raise KeyError(
            f"Target directory './{target_dir}' not present in git ref '{ref}'!"
        )
    return fields_nested


def read_schema_file(file_name: str) -> Dict[str, FieldNestedEntry]:
    """Read a raw schema yml file into a dict."""
    with open(file_name) as f:
        raw: List[FieldNestedEntry] = yaml.safe_load(f.read())
    return nest_schema(raw, file_name)


def read_schema_blob(
    blob: git.objects.blob.Blob, ref: str
) -> Dict[str, FieldNestedEntry]:
    """Read a raw schema yml git blob into a dict."""
    content: str = blob.data_stream.read().decode("utf-8")
    raw: List[FieldNestedEntry] = yaml.safe_load(content)
    file_name: str = "{} (git ref {})".format(blob.name, ref)
    return nest_schema(raw, file_name)


def nest_schema(
    raw: List[FieldNestedEntry], file_name: str
) -> Dict[str, FieldNestedEntry]:
    """
    Raw schema files are an array of schema details: [{'name': 'base', ...}]

    This function loops over the array (usually 1 schema per file) and turns it into
    a dict with the schema name as the key: { 'base': { 'name': 'base', ...}}
    """
    fields: Dict[str, FieldNestedEntry] = {}
    for schema in raw:
        if "name" not in schema:
            raise ValueError(
                "Schema file {} is missing mandatory attribute 'name'".format(file_name)
            )
        fields[schema["name"]] = schema
    return fields


def deep_nesting_representation(
    fields: Dict[str, FieldNestedEntry],
) -> Dict[str, FieldEntry]:
    deeply_nested: Dict[str, FieldEntry] = {}
    for name, flat_schema in fields.items():
        # We destructively select what goes into schema_details and child fields.
        # The rest is 'field_details'.
        flat_schema = flat_schema.copy()
        flat_schema["node_name"] = flat_schema["name"]

        # Schema-only details. Not present on other nested field groups.
        schema_details: SchemaDetails = {}
        for schema_key in ["root", "group", "reusable", "title", "settings", "aliases"]:
            if schema_key in flat_schema:
                schema_details[schema_key] = flat_schema.pop(schema_key)

        nested_schema = nest_fields(flat_schema.pop("fields", []))
        # Re-assemble new structure
        ecs_struct = {
            "schema_details": schema_details,
            # What's still in flat_schema is the field_details for the field set itself
            "field_details": flat_schema,
            "fields": nested_schema["fields"],
        }
        deeply_nested[name] = ecs_struct
        for alias in schema_details.get("aliases", []):
            deeply_nested[alias] = ecs_struct
    return deeply_nested


def nest_fields(field_array: List[Field]) -> Dict[str, Dict[str, FieldEntry]]:
    schema_root: Dict[str, Dict[str, FieldEntry]] = {"fields": {}}
    for field in field_array:
        nested_levels: List[str] = field["name"].split(".")
        parent_fields: List[str] = nested_levels[:-1]
        leaf_field: str = nested_levels[-1]
        # "nested_schema" is a cursor we move within the schema_root structure we're building.
        # Here we reset the cursor for this new field.
        nested_schema = schema_root["fields"]

        current_path = []
        for idx, level in enumerate(parent_fields):
            nested_schema.setdefault(level, {})
            # Where nested fields will live
            nested_schema[level].setdefault("fields", {})

            # Make type:object explicit for intermediate parent fields
            nested_schema[level].setdefault("field_details", {})
            field_details = nested_schema[level]["field_details"]
            field_details["node_name"] = level
            # Respect explicitly defined object fields
            if "type" in field_details and field_details["type"] in [
                "object",
                "nested",
            ]:
                field_details.setdefault("intermediate", False)
            else:
                field_details.setdefault("type", "object")
                field_details.setdefault("name", ".".join(parent_fields[: idx + 1]))
                field_details.setdefault("intermediate", True)

            # moving the nested_schema cursor deeper
            current_path.extend([level])
            nested_schema = nested_schema[level]["fields"]
        nested_schema.setdefault(leaf_field, {})
        # Overwrite 'name' with the leaf field's name. The flat_name is already computed.
        field["node_name"] = leaf_field
        nested_schema[leaf_field]["field_details"] = field
    return schema_root


def array_of_maps_to_map(array_vals: List[MultiField]) -> Dict[str, MultiField]:
    ret_map: Dict[str, MultiField] = {}
    for map_val in array_vals:
        name: str = map_val["name"]
        # if multiple name fields exist in the same custom definition this will take the last one
        ret_map[name] = map_val
    return ret_map


def map_of_maps_to_array(map_vals: Dict[str, MultiField]) -> List[MultiField]:
    ret_list: List[MultiField] = []
    for key in map_vals:
        ret_list.append(map_vals[key])
    return sorted(ret_list, key=lambda k: k["name"])


def dedup_and_merge_lists(
    list_a: List[MultiField], list_b: List[MultiField]
) -> List[MultiField]:
    list_a_map: Dict[str, MultiField] = array_of_maps_to_map(list_a)
    list_a_map.update(array_of_maps_to_map(list_b))
    return map_of_maps_to_array(list_a_map)


def merge_fields(
    a: Dict[str, FieldEntry], b: Dict[str, FieldEntry]
) -> Dict[str, FieldEntry]:
    """Merge ECS field sets with custom field sets."""
    a = copy.deepcopy(a)
    b = copy.deepcopy(b)
    for key in b:
        if key not in a:
            a[key] = b[key]
            continue
        # merge field details
        if "normalize" in b[key]["field_details"]:
            a[key].setdefault("field_details", {})
            a[key]["field_details"].setdefault("normalize", [])
            a[key]["field_details"]["normalize"].extend(
                b[key]["field_details"].pop("normalize")
            )
        if "multi_fields" in b[key]["field_details"]:
            a[key].setdefault("field_details", {})
            a[key]["field_details"].setdefault("multi_fields", [])
            a[key]["field_details"]["multi_fields"] = dedup_and_merge_lists(
                a[key]["field_details"]["multi_fields"],
                b[key]["field_details"]["multi_fields"],
            )
            # if we don't do this then the update call below will overwrite a's field_details, with the original
            # contents of b, which undoes our merging the multi_fields
            del b[key]["field_details"]["multi_fields"]
        a[key]["field_details"].update(b[key]["field_details"])
        # merge schema details
        if "schema_details" in b[key]:
            asd = a[key]["schema_details"]
            bsd = b[key]["schema_details"]
            if "reusable" in bsd:
                asd.setdefault("reusable", {})
                if "top_level" in bsd["reusable"]:
                    asd["reusable"]["top_level"] = bsd["reusable"]["top_level"]
                else:
                    asd["reusable"].setdefault("top_level", True)
                if "order" in bsd["reusable"]:
                    asd["reusable"]["order"] = bsd["reusable"]["order"]
                asd["reusable"].setdefault("expected", [])
                asd["reusable"]["expected"].extend(bsd["reusable"]["expected"])
                bsd.pop("reusable")
            if "settings" in bsd:
                asd.setdefault("settings", {})
                asd["settings"] = merge_fields(asd["settings"], bsd["settings"])
                # Prevents bsd["settings"] overwritting the merging we just did in the update below
                del bsd["settings"]
            asd.update(bsd)
        # merge nested fields
        if "fields" in b[key]:
            a[key].setdefault("fields", {})
            a[key]["fields"] = merge_fields(a[key]["fields"], b[key]["fields"])
    return a


def load_yaml_file(file_name):
    with open(file_name) as f:
        return yaml.safe_load(f.read())


# You know, for silent tests
def warn(message: str) -> None:
    print(message)


def eval_globs(globs):
    """Accepts an array of glob patterns or file names, returns the array of actual files"""
    all_files = []
    for g in globs:
        if g.endswith("/"):
            g += "*"
        new_files = glob.glob(g)
        if len(new_files) == 0:
            warn("{} did not match any files".format(g))
        else:
            all_files.extend(new_files)
    return all_files


def load_definitions(file_globs):
    sets = []
    for f in ecs_helpers.glob_yaml_files(file_globs):
        raw = load_yaml_file(f)
        sets.append(raw)
    return sets
