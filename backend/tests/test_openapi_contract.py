"""The backend half of the API contract.

The serializers under ``apps/*/api/`` are the single description of what the portal
receives and sends.  This module renders them to an OpenAPI description, reduces that
description to the component names, their property names and their enum values, and
compares the result to the snapshot committed at
``backend/tests/snapshots/openapi-components.json``.  Renaming, adding or dropping a
serializer field therefore fails here until the snapshot is refreshed and the portal's
``frontend/src/portal/api/types.ts`` follows.

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


class ComponentSummary(TypedDict, total=False):
    """One component reduced to the parts the portal's types have to agree with."""

    properties: list[str]
    required: list[str]
    enum: list[str]


def component_summaries(schema: dict[str, Any]) -> dict[str, ComponentSummary]:
    """Reduce an OpenAPI document to one summary per component schema.

    An enumeration component yields ``{"enum": [...]}`` with its values in declared
    order.  Every other component yields ``{"properties": [...], "required": [...]}``
    with both lists sorted, so the summary is stable against a reordering of the
    serializer's field list but not against a rename.  A document with no components
    yields an empty mapping.
    """
    components: dict[str, Any] = schema.get("components", {}).get("schemas", {})
    summaries: dict[str, ComponentSummary] = {}
    for name, component in sorted(components.items()):
        if "enum" in component:
            summaries[name] = {"enum": list(component["enum"])}
        else:
            summaries[name] = {
                "properties": sorted(component.get("properties", {})),
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
    schema: dict[str, Any] = SchemaGenerator().get_schema(request=None, public=True)
    return schema


@pytest.fixture(scope="session")
def generated_summaries(openapi_schema: dict[str, Any]) -> dict[str, ComponentSummary]:
    """The generated document reduced to one summary per component."""
    return component_summaries(openapi_schema)


def test_schema_describes_only_the_portal_api(openapi_schema: dict[str, Any]) -> None:
    """Every path in the document is mounted under ``/api/v1/``."""
    outside = [path for path in openapi_schema["paths"] if not path.startswith(API_PATH_PREFIX)]
    assert outside == []


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

    expected: dict[str, ComponentSummary] = json.loads(
        SNAPSHOT_PATH.read_text(encoding="utf-8")
    )
    assert summary_differences(expected, generated_summaries) == []


def test_a_renamed_field_is_reported_against_the_snapshot(
    generated_summaries: dict[str, ComponentSummary],
) -> None:
    """Renaming one property of one component is reported with both spellings."""
    renamed: dict[str, ComponentSummary] = dict(generated_summaries)
    renamed["MembershipStatus"] = {
        "properties": ["expires_on", "is_lifetime", "membership_plan", "status"],
        "required": ["expires_on", "is_lifetime", "plan", "status"],
    }

    differences = summary_differences(generated_summaries, renamed)

    assert differences == [
        "MembershipStatus: snapshot "
        "{'properties': ['expires_on', 'is_lifetime', 'plan', 'status'], "
        "'required': ['expires_on', 'is_lifetime', 'plan', 'status']}, "
        "schema {'properties': ['expires_on', 'is_lifetime', 'membership_plan', 'status'], "
        "'required': ['expires_on', 'is_lifetime', 'plan', 'status']}"
    ]


def test_a_dropped_component_is_reported_against_the_snapshot(
    generated_summaries: dict[str, ComponentSummary],
) -> None:
    """A serializer that stops appearing in the schema is named as gone."""
    without_payments = {
        name: summary for name, summary in generated_summaries.items() if name != "Payment"
    }

    differences = summary_differences(generated_summaries, without_payments)

    assert differences == ["Payment: gone from the schema"]


def test_an_added_component_is_reported_against_the_snapshot(
    generated_summaries: dict[str, ComponentSummary],
) -> None:
    """A serializer the snapshot has never seen is named as unrecorded."""
    with_extra: dict[str, ComponentSummary] = dict(generated_summaries)
    with_extra["Squawk"] = {"properties": ["code"], "required": ["code"]}

    differences = summary_differences(generated_summaries, with_extra)

    assert differences == ["Squawk: not in the snapshot"]


def test_identical_summaries_report_no_differences(
    generated_summaries: dict[str, ComponentSummary],
) -> None:
    """Comparing the generated summaries with themselves reports nothing."""
    assert summary_differences(generated_summaries, dict(generated_summaries)) == []
