"""Compare stage facts while tests separately assert timing and route details."""

from collections.abc import Mapping
from paper_fetch.tracing import TraceEvent


def trace_facts(value):
    if isinstance(value, TraceEvent):
        return value.stage, value.component, value.outcome
    if isinstance(value, Mapping) and {"stage", "component", "outcome"} <= value.keys():
        return value["stage"], value["component"], value["outcome"]
    if isinstance(value, (list, tuple)):
        return [trace_facts(item) for item in value]
    return value
