"""Model definition of Tracing element from"""

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class V1SpanKind(Enum):
    SPAN_KIND_UNSPECIFIED = 0
    SPAN_KIND_INTERNAL = 1
    SPAN_KIND_SERVER = 2
    SPAN_KIND_CLIENT = 3
    SPAN_KIND_PRODUCER = 4
    SPAN_KIND_CONSUMER = 5


class V1KeyValue(BaseModel):
    key: str
    value: Any


class V1Span(BaseModel):
    trace_id: str = Field(alias="traceId")
    span_id: str = Field(alias="spanId")
    parent_span_id: str = Field(alias="parentSpanId")
    name: str
    kind: V1SpanKind
    start_time_unix_nano: int = Field(alias="startTimeUnixNano")
    end_time_unix_nano: int = Field(alias="endTimeUnixNano")
    attributes: List[V1KeyValue] = []

    class Config:
        use_enum_values = True


class V1InstrumentationScope(BaseModel):
    name: Optional[str] = ""
    version: Optional[str] = ""
    attributes: Optional[V1KeyValue] = None
    dropped_attributes_count: Optional[int] = 0


class V1ScopeSpan(BaseModel):
    scope: V1InstrumentationScope
    spans: List[V1Span] = []
    schema_url: Optional[str] = ""


class V1Resource(BaseModel):
    attributes: List[V1KeyValue] = []


class V1ResourceSpan(BaseModel):
    resource: V1Resource
    scope_spans: List[V1ScopeSpan] = Field(alias="scopeSpans")


class V1TraceData(BaseModel):
    resource_spans: List[V1ResourceSpan] = Field(alias="resourceSpans")
