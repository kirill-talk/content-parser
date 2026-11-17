"""
Declarative parsing rule schemas and parser runner.
Provides a foundation for customizable, per-site field mapping and extraction rules.
"""

from typing import Dict, Any, List, Optional
import re
import html

class ParsingRule:
    """
    Represents an extraction or transformation rule for a specific field.
    Rule Types:
    - 'json_path': Extract from raw API item dict (e.g. 'title.rendered')
    - 'css_selector': Extract from HTML using CSS selector (e.g. '.main-content > p')
    - 'regex': Extract via regular expression pattern
    - 'static': Return a fixed literal value
    - 'custom_handler': Dispatch to named Python handler
    """
    def __init__(self, target_field: str, rule_type: str, source_path: str = "", default_value: Any = None, transform: Optional[str] = None):
        self.target_field = target_field
        self.rule_type = rule_type
        self.source_path = source_path
        self.default_value = default_value
        self.transform = transform

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_field": self.target_field,
            "rule_type": self.rule_type,
            "source_path": self.source_path,
            "default_value": self.default_value,
            "transform": self.transform
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParsingRule":
        return cls(
            target_field=data.get("target_field", ""),
            rule_type=data.get("rule_type", "json_path"),
            source_path=data.get("source_path", ""),
            default_value=data.get("default_value"),
            transform=data.get("transform")
        )

class SiteParsingSchema:
    """
    Full schema for a specific website profile, defining how to extract each Mach3Blocks target field.
    """
    def __init__(self, name: str, source_type: str = "wordpress_rest", rules: Optional[List[ParsingRule]] = None):
        self.name = name
        self.source_type = source_type
        self.rules = rules or []

    def add_rule(self, rule: ParsingRule):
        self.rules.append(rule)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source_type": self.source_type,
            "rules": [r.to_dict() for r in self.rules]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SiteParsingSchema":
        rules = [ParsingRule.from_dict(r) for r in data.get("rules", [])]
        return cls(
            name=data.get("name", "custom_profile"),
            source_type=data.get("source_type", "wordpress_rest"),
            rules=rules
        )
