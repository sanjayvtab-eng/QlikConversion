import os
from pathlib import Path

from QlikToPowerBIConverter.parser.qlik_parser import QlikParser
from QlikToPowerBIConverter.utils.knowledge_loader import KnowledgeLoader


class MigrationAgent:
    """Build a rulebook-driven analysis model from Qlik metadata."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.parser = QlikParser()
        
        # Resolve base_dir: if it's "." or doesn't have a knowledge folder,
        # use the package directory instead
        resolved_dir = Path(base_dir).resolve()
        if not (resolved_dir / "knowledge").exists():
            # Fall back to the package's directory
            package_dir = Path(__file__).parent.parent
            resolved_dir = package_dir
        
        self.knowledge_loader = KnowledgeLoader(str(resolved_dir))

    def analyze(self, script: str) -> dict:
        rulebook = self.knowledge_loader.load_rules()
        rule_mapping = self.knowledge_loader.get_rule_mapping()
        metadata = self.parser.extract_metadata(script)
        operations = [item["type"] for item in metadata["transformations"]]

        transformations = []
        warnings = list(metadata.get("warnings", []))

        for item in metadata["transformations"]:
            operation = item["type"]
            key = operation.lower()
            rule = rule_mapping.get(key) or rule_mapping.get(operation.lower().replace(" ", " "))
            if rule is None:
                warnings.append(f"No authoritative rulebook mapping found for '{operation}'.")
                rule = {"concept": operation, "equivalent": "Manual review required", "notes": "Not found in rulebook", "type": "Unknown"}
            transformations.append({"operation": operation, "rule": rule, "detail": item})

        return {
            "rulebook_summary": rulebook.splitlines()[:10],
            "operations": list(dict.fromkeys(operations)),
            "metadata": metadata,
            "transformations": transformations,
            "warnings": warnings,
            "source_lines": len(self.parser.extract_lines(script)),
            "rule_mapping": rule_mapping,
        }
