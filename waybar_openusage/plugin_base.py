"""Base class and types for provider plugins."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

log = logging.getLogger("waybar-openusage")


class LineType(Enum):
    PROGRESS = "progress"
    TEXT = "text"
    BADGE = "badge"


class FormatKind(Enum):
    PERCENT = "percent"
    DOLLARS = "dollars"
    COUNT = "count"


@dataclass
class ProgressLine:
    type: str = "progress"
    label: str = ""
    used: float = 0
    limit: float = 100
    format: dict = field(default_factory=lambda: {"kind": "percent"})
    resets_at: Optional[str] = None
    period_duration_ms: Optional[int] = None
    color: Optional[str] = None

    @property
    def fraction(self) -> float:
        if self.limit == 0:
            return 0
        return min(1.0, max(0.0, self.used / self.limit))

    @property
    def percent(self) -> float:
        return self.fraction * 100

    def to_dict(self) -> dict:
        d = {
            "type": self.type,
            "label": self.label,
            "used": self.used,
            "limit": self.limit,
            "format": self.format,
        }
        if self.resets_at:
            d["resetsAt"] = self.resets_at
        if self.period_duration_ms:
            d["periodDurationMs"] = self.period_duration_ms
        if self.color:
            d["color"] = self.color
        return d


@dataclass
class TextLine:
    type: str = "text"
    label: str = ""
    value: str = ""
    color: Optional[str] = None
    subtitle: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"type": self.type, "label": self.label, "value": self.value}
        if self.color:
            d["color"] = self.color
        if self.subtitle:
            d["subtitle"] = self.subtitle
        return d


@dataclass
class BadgeLine:
    type: str = "badge"
    label: str = ""
    text: str = ""
    color: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"type": self.type, "label": self.label, "text": self.text}
        if self.color:
            d["color"] = self.color
        return d


@dataclass
class PluginOutput:
    provider_id: str = ""
    display_name: str = ""
    plan: Optional[str] = None
    lines: list = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "providerId": self.provider_id,
            "displayName": self.display_name,
            "lines": [line.to_dict() for line in self.lines],
        }
        if self.plan:
            d["plan"] = self.plan
        if self.error:
            d["error"] = self.error
        return d

    @property
    def primary_progress(self) -> Optional[ProgressLine]:
        for line in self.lines:
            if isinstance(line, ProgressLine):
                return line
        return None


class ProviderPlugin:
    """Base class for all provider plugins."""

    id: str = ""
    name: str = ""
    brand_color: str = "#888888"

    def probe(self) -> PluginOutput:
        raise NotImplementedError

    def safe_probe(self) -> PluginOutput:
        try:
            return self.probe()
        except Exception as e:
            log.warning(f"Plugin {self.id} probe failed: {e}")
            output = PluginOutput(
                provider_id=self.id,
                display_name=self.name,
                error=str(e),
                lines=[BadgeLine(label="Status", text=str(e), color="#ef4444")],
            )
            return output
