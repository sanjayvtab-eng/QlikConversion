import re
from pathlib import Path


class KnowledgeLoader:
    """Loads the Qlik migration rulebook used by the migration agent."""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    def load_rules(self) -> str:
        rule_file = self.base_dir / "knowledge" / "qlik_rules.md"
        if not rule_file.exists():
            raise FileNotFoundError(f"Rulebook not found: {rule_file}")
        return rule_file.read_text(encoding="utf-8")

    def get_rule_mapping(self) -> dict:
        text = self.load_rules()
        rules = {}

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line.startswith("|") or "---" in line:
                continue

            parts = [part.strip() for part in line.strip("|").split("|")]
            if len(parts) < 4:
                continue

            concept, equivalent, notes, rule_type = parts[:4]
            concept_key = self._normalize(concept)
            rules[concept_key] = {
                "concept": concept,
                "equivalent": equivalent,
                "notes": notes,
                "type": rule_type,
            }

            aliases = self._build_aliases(concept)
            for alias in aliases:
                rules.setdefault(alias, rules[concept_key])

        return rules

    def _build_aliases(self, concept: str) -> list:
        text = self._normalize(concept)
        aliases = []
        lowered = text.lower()

        if "load ... from" in lowered:
            aliases.append("load")
        if "resident load" in lowered:
            aliases.append("resident load")
        if "concatenate load" in lowered:
            aliases.append("concatenate")
        if "left join" in lowered:
            aliases.append("left join")
        if "inner join" in lowered:
            aliases.append("inner join")
        if "join (load)" in lowered:
            aliases.append("join")
        if "applymap" in lowered:
            aliases.append("applymap")
        if "load ... where" in lowered:
            aliases.append("where")
        if "load ... group by" in lowered:
            aliases.append("group by")
        return aliases

    def _normalize(self, value: str) -> str:
        value = value.lower().replace("`", "").strip()
        value = re.sub(r"\s+", " ", value)
        return value
