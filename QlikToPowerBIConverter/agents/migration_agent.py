import os
from pathlib import Path

from QlikToPowerBIConverter.parser.qlik_parser import QlikParser
from QlikToPowerBIConverter.utils.knowledge_loader import KnowledgeLoader


class MigrationAgent:
    """Build a rulebook-driven analysis model from Qlik metadata."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.parser = QlikParser()

        resolved_dir = Path(base_dir).resolve()
        if not (resolved_dir / "knowledge").exists():
            package_dir = Path(__file__).parent.parent
            resolved_dir = package_dir

        self.knowledge_loader = KnowledgeLoader(str(resolved_dir))

    def analyze(self, script: str) -> dict:
        # Load rulebook and mapping (used for reporting only)
        rulebook = self.knowledge_loader.load_rules()
        rule_mapping = self.knowledge_loader.get_rule_mapping()

        # Extract metadata from Qlik script
        metadata = self.parser.extract_metadata(script)

        # Derive operations list and attach transformation-level rule references
        ops = []
        transformations = []
        warnings = list(metadata.get("warnings", []))
        for item in metadata.get("transformations", []):
            op = item.get("type")
            if op and op not in ops:
                ops.append(op)
            rule = rule_mapping.get(op.lower()) if op else None
            if rule is None and op:
                rule = rule_mapping.get(op.lower().replace(" ", ""))
            if rule is None and op:
                warnings.append(f"No rulebook mapping for operation '{op}'")
                rule = {"concept": op, "equivalent": "Manual review required", "notes": "Not found", "type": "Unknown"}
            transformations.append({"operation": op, "rule": rule, "detail": item})

        return {
            "rulebook_summary": rulebook.splitlines()[:20],
            "operations": ops,
            "metadata": metadata,
            "source_files": metadata.get("sources", []),
            "tables": metadata.get("tables", []),
            "table_definitions": metadata.get("tables", []),
            "joins": metadata.get("joins", []),
            "load_steps": metadata.get("load_steps", []),
            "transformations": transformations,
            "warnings": warnings,
            "source_lines": len(self.parser.extract_lines(script)),
            "rule_mapping": rule_mapping,
        }
