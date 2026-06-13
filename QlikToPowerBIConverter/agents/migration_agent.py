from parser.qlik_parser import QlikParser
from utils.knowledge_loader import KnowledgeLoader


class MigrationAgent:
    """
    Build a rulebook-driven analysis model from Qlik metadata.
    Now operates per-table so every table block produces its own
    transformations, source references, and M-code output.
    """

    def __init__(self, base_dir: str):

        self.base_dir = base_dir
        self.parser   = QlikParser()
        self.knowledge_loader = KnowledgeLoader(base_dir)

    # ------------------------------------------------------------------

    def analyze(self, script: str) -> dict:

        rulebook     = self.knowledge_loader.load_rules()
        rule_mapping = self.knowledge_loader.get_rule_mapping()

        # Full metadata — now contains ``table_blocks`` (one entry per table)
        metadata = self.parser.extract_metadata(script)

        warnings:      list = list(metadata.get("warnings", []))
        all_operations: list = []
        processed_blocks: list = []

        # ── Process each table block independently ─────────────────────
        for block in metadata.get("table_blocks", []):

            block_transformations = []

            for item in block.get("transformations", []):

                operation = item["type"]

                if operation not in all_operations:
                    all_operations.append(operation)

                key  = operation.lower()
                rule = (
                    rule_mapping.get(key)
                    or rule_mapping.get(operation.lower())
                )

                if rule is None:
                    warnings.append(
                        f"No rulebook mapping found for '{operation}' "
                        f"in table '{block['table']['name']}'."
                    )
                    rule = {
                        "concept":    operation,
                        "equivalent": "Manual review required",
                        "notes":      "Not found in rulebook",
                        "type":       "Unknown",
                    }

                block_transformations.append(
                    {
                        "operation": operation,
                        "rule":      rule,
                        "detail":    item,
                    }
                )

            processed_blocks.append(
                {
                    # core identity
                    "table":           block["table"],
                    # per-table data used by MGenerator
                    "columns":         block["columns"],
                    "sources":         block["sources"],
                    "filters":         block["filters"],
                    "aggregations":    block["aggregations"],
                    "joins":           block["joins"],
                    "rename_fields":   block["rename_fields"],
                    "drop_fields":     block["drop_fields"],
                    "is_resident":     block.get("is_resident", False),
                    # enriched transformations
                    "transformations": block_transformations,
                }
            )

        return {
            # ── rulebook context ──────────────────────────────────────
            "rulebook_summary": rulebook.splitlines()[:10],
            "rule_mapping":     rule_mapping,

            # ── per-table blocks (primary output consumed by MGenerator)
            "table_blocks":     processed_blocks,

            # ── flat / global (backward-compat) ──────────────────────
            "operations":       list(dict.fromkeys(all_operations)),
            "metadata":         metadata,
            "source_files":     metadata.get("sources", []),
            "tables":           metadata.get("tables", []),
            "joins":            metadata.get("joins", []),
            "transformations":  [
                t
                for b in processed_blocks
                for t in b["transformations"]
            ],
            "warnings":         warnings,
            "source_lines":     len(self.parser.extract_lines(script)),
        }