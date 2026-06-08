import re
from pathlib import Path


class KnowledgeLoader:
    """Loads the Qlik migration rulebook used by the migration agent."""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir).resolve()
        # Try to find the knowledge directory
        self.knowledge_dir = self._find_knowledge_dir()

    def _find_knowledge_dir(self) -> Path:
        """Find the knowledge directory by searching common locations."""
        # First, try base_dir/knowledge
        if (self.base_dir / "knowledge").exists():
            return self.base_dir / "knowledge"
        
        # If base_dir is the package dir (e.g., QlikToPowerBIConverter), knowledge is direct child
        if (self.base_dir / "knowledge").exists():
            return self.base_dir / "knowledge"
        
        # If base_dir is repo root, knowledge is in QlikToPowerBIConverter/knowledge
        if (self.base_dir / "QlikToPowerBIConverter" / "knowledge").exists():
            return self.base_dir / "QlikToPowerBIConverter" / "knowledge"
        
        # Try using this module's location (package-relative)
        module_dir = Path(__file__).parent.parent  # Go up from utils/ to QlikToPowerBIConverter/
        if (module_dir / "knowledge").exists():
            return module_dir / "knowledge"
        
        # Last resort: raise error with helpful message
        raise FileNotFoundError(
            f"Cannot find 'knowledge' directory. Searched in:\n"
            f"  - {self.base_dir / 'knowledge'}\n"
            f"  - {self.base_dir / 'QlikToPowerBIConverter' / 'knowledge'}\n"
            f"  - {module_dir / 'knowledge'}\n"
        )

    def load_rules(self) -> str:
        rule_file = self.knowledge_dir / "qlik_rules.md"
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
