"""The backend half of the API contract.

The serializers under ``apps/*/api/`` are the single description of what the portal
receives and sends.  This module renders them to an OpenAPI description, reduces that
description to the component names, their properties with each property's type, the
required names and the enum values, and compares the result to the snapshot committed
at ``backend/tests/snapshots/openapi-components.json``.  Renaming, adding, dropping or
retyping a serializer field therefore fails here until the snapshot is refreshed and
the portal's ``frontend/src/portal/api/types.ts`` follows.

Refresh the snapshot by setting ``UPDATE_OPENAPI_SNAPSHOT=1`` in the environment and
running this file; ``docs/developer/testing.rst`` spells the command out.
"""

import json
import os
from pathlib import Path
from typing import Any, TypedDict

import pytest
from drf_spectacular.generators import SchemaGenerator

from caldart.api_urls import API_PATH_PREFIX

SNAPSHOT_PATH = Path(__file__).resolve().parent / "snapshots" / "openapi-components.json"

#: The environment variable that rewrites the snapshot instead of asserting on it.
UPDATE_VARIABLE = "UPDATE_OPENAPI_SNAPSHOT"

#: The prefix every ``$ref`` in the generated document carries.
COMPONENT_REF_PREFIX = "#/components/schemas/"

#: What :func:`property_type` answers for a property the generator left untyped.
UNKNOWN_TYPE = "unknown"


class ComponentSummary(TypedDict, total=False):
    """One component reduced to the parts the portal's types have to agree with."""

    properties: dict[str, str]
    required: list[str]
    enum: list[str]
    #: A polymorphic (``oneOf``) component's member component names, sorted.
    one_of: list[str]
    #: A polymorphic component's discriminator property name.
    discriminator: str


def property_type(schema: dict[str, Any]) -> str:
    """Describe one property's type as a single comparable string.

    A scalar answers its OpenAPI type, with the format in parentheses when it has one:
    ``integer``, ``string``, ``string(date)``, ``string(date-time)``.  A reference to
    another component answers ``ref:<name>``, an array ``array<element>``, and a
    free-keyed object ``map<value>``, each describing the inner type the same way.  A
    property the generator marks nullable has ``|null`` appended.  A property with no
    type at all answers ``unknown``.
    """
    suffix = "|null" if schema.get("nullable") else ""
    if "$ref" in schema:
        return f"ref:{schema['$ref'].removeprefix(COMPONENT_REF_PREFIX)}{suffix}"
    if "allOf" in schema:
        # The generator wraps a reference in ``allOf`` whenever the property carries
        # its own description, default or read-only flag alongside the reference.
        return f"{property_type(schema['allOf'][0])}{suffix}"
    kind = schema.get("type", UNKNOWN_TYPE)
    if kind == "array":
        return f"array<{property_type(schema.get('items', {}))}>{suffix}"
    if kind == "object" and "additionalProperties" in schema:
        return f"map<{property_type(schema['additionalProperties'])}>{suffix}"
    if "format" in schema:
        return f"{kind}({schema['format']}){suffix}"
    return f"{kind}{suffix}"


def component_summaries(schema: dict[str, Any]) -> dict[str, ComponentSummary]:
    """Reduce an OpenAPI document to one summary per component schema.

    An enumeration component yields ``{"enum": [...]}`` with its values in declared
    order.  A polymorphic component -- one built from ``PolymorphicProxySerializer``,
    such as ``CheckoutResponse`` -- carries ``oneOf`` and a ``discriminator`` instead of
    its own properties, and yields ``{"one_of": [...], "discriminator": "..."}`` with the
    member component names sorted, so a member gained, dropped or renamed changes the
    summary.  Every other component yields ``{"properties": {...}, "required": [...]}``,
    where ``properties`` maps each property name to the type :func:`property_type`
    describes and ``required`` is sorted, so the summary is stable against a reordering
    of the serializer's field list but not against a rename or a change of type.  A
    document with no components yields an empty mapping.
    """
    components: dict[str, Any] = schema.get("components", {}).get("schemas", {})
    summaries: dict[str, ComponentSummary] = {}
    for name, component in sorted(components.items()):
        if "enum" in component:
            summaries[name] = {"enum": list(component["enum"])}
        elif "oneOf" in component:
            summaries[name] = {
                "one_of": sorted(
                    member["$ref"].removeprefix(COMPONENT_REF_PREFIX)
                    for member in component["oneOf"]
                ),
                "discriminator": component.get("discriminator", {}).get("propertyName", ""),
            }
        else:
            summaries[name] = {
                "properties": {
                    property_name: property_type(property_schema)
                    for property_name, property_schema in sorted(
                        component.get("properties", {}).items()
                    )
                },
                "required": sorted(component.get("required", [])),
            }
    return summaries


def summary_differences(
    expected: dict[str, ComponentSummary], actual: dict[str, ComponentSummary]
) -> list[str]:
    """Describe every way ``actual`` departs from ``expected``, one line each.

    A component only ``expected`` has yields ``"<name>: gone from the schema"``; one
    only ``actual`` has yields ``"<name>: not in the snapshot"``; a component both
    carry whose summary differs yields
    ``"<name>: snapshot <expected summary>, schema <actual summary>"``.  Lines come
    back in component-name order, and an identical pair yields no lines.
    """
    differences: list[str] = []
    for name in sorted(set(expected) | set(actual)):
        if name not in actual:
            differences.append(f"{name}: gone from the schema")
        elif name not in expected:
            differences.append(f"{name}: not in the snapshot")
        elif expected[name] != actual[name]:
            differences.append(f"{name}: snapshot {expected[name]}, schema {actual[name]}")
    return differences


@pytest.fixture(scope="session")
def openapi_schema() -> dict[str, Any]:
    """The OpenAPI document the project's serializers and views generate."""
    # drf-spectacular's generator carries no annotations, so mypy sees both calls
    # as untyped; the document it returns is a plain JSON-shaped dict.
    generator = SchemaGenerator()  # type: ignore[no-untyped-call]
    schema: dict[str, Any] = generator.get_schema(request=None, public=True)  # type: ignore[no-untyped-call]
    return schema


@pytest.fixture(scope="session")
def generated_summaries(openapi_schema: dict[str, Any]) -> dict[str, ComponentSummary]:
    """The generated document reduced to one summary per component."""
    return component_summaries(openapi_schema)


def squawk_summaries() -> dict[str, ComponentSummary]:
    """A two-component fixture no serializer produces, for the comparison's own tests.

    ``Squawk`` carries a code, a description and a reference to ``Squawker``, which
    carries a name.  Nothing in the project generates either, so a test built on them
    keeps saying what it means however the real serializers change.
    """
    return {
        "Squawk": {
            "properties": {
                "code": "integer",
                "description": "string",
                "raised_by": "ref:Squawker",
            },
            "required": ["code", "raised_by"],
        },
        "Squawker": {"properties": {"name": "string"}, "required": ["name"]},
    }


def test_schema_describes_only_the_portal_api(openapi_schema: dict[str, Any]) -> None:
    """Every path in the document is mounted under ``/api/v1/``."""
    outside = [path for path in openapi_schema["paths"] if not path.startswith(API_PATH_PREFIX)]
    assert outside == []


def test_every_operation_describes_a_response(openapi_schema: dict[str, Any]) -> None:
    """No operation is left with the generator's empty fallback response.

    An operation the generator could not read answers ``{}`` under ``responses``; every
    view names its response explicitly, through a serializer or an ``@extend_schema``.
    """
    undescribed = [
        f"{method.upper()} {path}"
        for path, operations in openapi_schema["paths"].items()
        for method, operation in operations.items()
        if not operation.get("responses")
    ]
    assert undescribed == []


def test_schema_components_match_the_snapshot(
    generated_summaries: dict[str, ComponentSummary],
) -> None:
    """The serializers render exactly the components the snapshot records.

    Setting ``UPDATE_OPENAPI_SNAPSHOT=1`` rewrites the snapshot from the schema
    instead of comparing, and the test then reports as skipped.
    """
    if os.environ.get(UPDATE_VARIABLE) == "1":
        SNAPSHOT_PATH.write_text(
            json.dumps(generated_summaries, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        pytest.skip(f"{SNAPSHOT_PATH.name} rewritten from the generated schema")

    expected: dict[str, ComponentSummary] = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert summary_differences(expected, generated_summaries) == []


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        ({"type": "integer"}, "integer"),
        ({"type": "string", "format": "date"}, "string(date)"),
        ({"type": "string", "nullable": True}, "string|null"),
        ({"$ref": f"{COMPONENT_REF_PREFIX}Dart"}, "ref:Dart"),
        ({"allOf": [{"$ref": f"{COMPONENT_REF_PREFIX}DartRef"}]}, "ref:DartRef"),
        (
            {"allOf": [{"$ref": f"{COMPONENT_REF_PREFIX}DartRef"}], "nullable": True},
            "ref:DartRef|null",
        ),
        ({"type": "array", "items": {"type": "string"}}, "array<string>"),
        (
            {"type": "array", "items": {"$ref": f"{COMPONENT_REF_PREFIX}RatingsEnum"}},
            "array<ref:RatingsEnum>",
        ),
        (
            {"type": "object", "additionalProperties": {"type": "integer"}},
            "map<integer>",
        ),
        ({"description": "no type at all"}, UNKNOWN_TYPE),
    ],
    ids=[
        "scalar",
        "formatted",
        "nullable",
        "reference",
        "wrapped-reference",
        "nullable-reference",
        "array",
        "array-of-references",
        "map",
        "untyped",
    ],
)
def test_property_type_describes_one_property(schema: dict[str, Any], expected: str) -> None:
    """Each property shape the generator emits reduces to its own descriptor."""
    assert property_type(schema) == expected


def test_component_summaries_record_each_property_type() -> None:
    """A component summary maps every property name to the property's type."""
    document = {
        "components": {
            "schemas": {
                "Squawk": {
                    "properties": {
                        "code": {"type": "integer"},
                        "reported_on": {"type": "string", "format": "date"},
                    },
                    "required": ["code"],
                }
            }
        }
    }

    summaries = component_summaries(document)

    assert summaries["Squawk"]["properties"] == {
        "code": "integer",
        "reported_on": "string(date)",
    }


def test_component_summaries_record_enum_values_in_order() -> None:
    """An enumeration component keeps its values in the order the schema declares."""
    document = {"components": {"schemas": {"SquawkSeverityEnum": {"enum": ["low", "high"]}}}}

    summaries = component_summaries(document)

    assert summaries["SquawkSeverityEnum"] == {"enum": ["low", "high"]}


def test_component_summaries_record_a_polymorphic_component() -> None:
    """A ``oneOf`` component summarizes its member names and its discriminator."""
    document = {
        "components": {
            "schemas": {
                "CheckoutResponse": {
                    "oneOf": [
                        {"$ref": f"{COMPONENT_REF_PREFIX}StripeCheckoutResponse"},
                        {"$ref": f"{COMPONENT_REF_PREFIX}MockCheckoutResponse"},
                    ],
                    "discriminator": {"propertyName": "provider"},
                }
            }
        }
    }

    summaries = component_summaries(document)

    assert summaries["CheckoutResponse"] == {
        "one_of": ["MockCheckoutResponse", "StripeCheckoutResponse"],
        "discriminator": "provider",
    }


def test_a_renamed_field_is_reported_against_the_snapshot() -> None:
    """Renaming one property of one component is reported with both spellings."""
    renamed = squawk_summaries()
    renamed["Squawk"] = {
        "properties": {
            "code": "integer",
            "description": "string",
            "reported_by": "ref:Squawker",
        },
        "required": ["code", "reported_by"],
    }

    differences = summary_differences(squawk_summaries(), renamed)

    assert differences == [
        "Squawk: snapshot "
        "{'properties': {'code': 'integer', 'description': 'string', "
        "'raised_by': 'ref:Squawker'}, 'required': ['code', 'raised_by']}, "
        "schema {'properties': {'code': 'integer', 'description': 'string', "
        "'reported_by': 'ref:Squawker'}, 'required': ['code', 'reported_by']}"
    ]


def test_a_retyped_field_is_reported_against_the_snapshot() -> None:
    """A property that keeps its name but changes type is reported as a difference."""
    retyped = squawk_summaries()
    retyped["Squawk"]["properties"]["code"] = "string"

    differences = summary_differences(squawk_summaries(), retyped)

    assert len(differences) == 1


def test_a_dropped_component_is_reported_against_the_snapshot() -> None:
    """A serializer that stops appearing in the schema is named as gone."""
    without_squawker = {
        name: summary for name, summary in squawk_summaries().items() if name != "Squawker"
    }

    differences = summary_differences(squawk_summaries(), without_squawker)

    assert differences == ["Squawker: gone from the schema"]


def test_an_added_component_is_reported_against_the_snapshot() -> None:
    """A serializer the snapshot has never seen is named as unrecorded."""
    with_extra = squawk_summaries()
    with_extra["SquawkNote"] = {"properties": {"body": "string"}, "required": ["body"]}

    differences = summary_differences(squawk_summaries(), with_extra)

    assert differences == ["SquawkNote: not in the snapshot"]


def test_identical_summaries_report_no_differences() -> None:
    """Comparing a set of summaries with an identical copy reports nothing."""
    assert summary_differences(squawk_summaries(), squawk_summaries()) == []
