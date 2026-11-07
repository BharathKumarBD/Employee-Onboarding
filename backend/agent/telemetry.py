"""Node-level telemetry and token accounting for Aarambh-AI multi-agent graph.

Tracks per-node latency, LLM token usage, and estimated cost.
Telemetry is yielded as SSE events alongside normal agent events.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# Approximate pricing per 1K tokens (USD) — update to match your model
# Defaults shown are for gpt-4o-mini class models
_PROMPT_COST_PER_1K = 0.00015
_COMPLETION_COST_PER_1K = 0.00060


@dataclass
class NodeTrace:
    name: str
    start_ms: float = field(default_factory=lambda: time.time() * 1000)
    end_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def latency_ms(self) -> float:
        return self.end_ms - self.start_ms if self.end_ms else 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost_usd(self) -> float:
        return (
            self.prompt_tokens * _PROMPT_COST_PER_1K / 1000
            + self.completion_tokens * _COMPLETION_COST_PER_1K / 1000
        )

    def finish(self) -> None:
        self.end_ms = time.time() * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.name,
            "latency_ms": round(self.latency_ms, 1),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd, 6),
        }


class TelemetryTracker:
    """Accumulates node traces across the multi-agent graph execution."""

    def __init__(self) -> None:
        self._nodes: list[NodeTrace] = []
        self._start_ms: float = time.time() * 1000

    def start_node(self, name: str) -> NodeTrace:
        trace = NodeTrace(name=name)
        self._nodes.append(trace)
        return trace

    def record_tokens(self, trace: NodeTrace, prompt: int, completion: int) -> None:
        trace.prompt_tokens += prompt
        trace.completion_tokens += completion

    @property
    def total_latency_ms(self) -> float:
        return time.time() * 1000 - self._start_ms

    @property
    def total_tokens(self) -> int:
        return sum(n.total_tokens for n in self._nodes)

    @property
    def total_cost_usd(self) -> float:
        return sum(n.cost_usd for n in self._nodes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_latency_ms": round(self.total_latency_ms, 1),
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "nodes": [n.to_dict() for n in self._nodes],
        }

    def summary_label(self) -> str:
        """Human-readable one-liner for the UI trace button."""
        ms = round(self.total_latency_ms)
        tok = self.total_tokens
        cost = self.total_cost_usd
        return f"⚡ Trace: {ms:,}ms · {tok:,} tokens (${cost:.5f})"

