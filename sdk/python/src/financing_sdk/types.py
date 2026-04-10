"""Result types for the Financing Agent SDK."""

from dataclasses import dataclass, field


@dataclass
class AnalysisResult:
    """Result from analyzing a financing offer."""

    analysis: str
    """Full plain English analysis text."""

    tool_calls: list[str] = field(default_factory=list)
    """MCP tools that were called during analysis."""


@dataclass
class UsageInfo:
    """Client usage statistics."""

    name: str
    company: str
    created_at: str
    total_calls: int
    last_called_at: str | None
