import json
import re
from typing import Dict, List


class QlikParser:
    """Parse Qlik ETL scripts into structured metadata for conversion."""

    KEYWORDS = {
        "LOAD": r"\bLOAD\b",
        "RESIDENT LOAD": r"\bRESIDENT\b",
        "JOIN": r"\bJOIN\b",
        "LEFT JOIN": r"\bLEFT\s+JOIN\b",
        "INNER JOIN": r"\bINNER\s+JOIN\b",
        "RIGHT JOIN": r"\bRIGHT\s+JOIN\b",
        "OUTER JOIN": r"\bOUTER\s+JOIN\b",
        "CONCATENATE": r"\bCONCATENATE\b",
        "APPLYMAP": r"\bAPPLYMAP\b",
        "WHERE": r"\bWHERE\b",
        "GROUP BY": r"\bGROUP\s+BY\b",
        "DROP FIELD": r"\bDROP\s+FIELD\b",
        "RENAME FIELD": r"\bRENAME\s+FIELD\b",
        "STORE": r"\bSTORE\b",
        "VARIABLE": r"\b(LET|SET)\b",
    }

    def extract_metadata(self, script: str) -> Dict[str, object]:
        lines = self.extract_lines(script)
        tables = []
        sources = []
        columns = []
        joins = []
        filters = []
        aggregations = []
        transformations = []
        variables = []
        store_statements = []
        rename_fields = []
        drop_fields = []
        derived_columns = []

        for line in lines:
            stripped = line.strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_\-]*\s*:\s*$", stripped):
                tables.append({"name": stripped.replace(':', '').strip(), "line": lines.index(line) + 1})

            if re.search(r"\bLOAD\b", stripped, re.I):
                load_match = re.search(r"LOAD\s+(.*?)(?:FROM|WHERE|GROUP\s+BY|;|$)", stripped, re.I | re.S)
                if load_match:
                    raw_columns = load_match.group(1)
                    parsed_columns = [c.strip().split(" as ")[0].strip("[]") for c in raw_columns.split(',') if c.strip()]
                    columns.extend([{"name": c, "source": "LOAD", "line": lines.index(line) + 1} for c in parsed_columns if c])
                    transformations.append({"type": "LOAD", "line": lines.index(line) + 1, "columns": parsed_columns})

            if re.search(r"\bFROM\b", stripped, re.I):
                source_match = re.search(r"FROM\s+([^\s;]+)", stripped, re.I)
                if source_match:
                    src = source_match.group(1).strip("'\"")
                    sources.append({"path": src, "line": lines.index(line) + 1})

            join_match = re.search(r"\b(LEFT|INNER|RIGHT|OUTER)\s+JOIN\b|\bJOIN\b", stripped, re.I)
            if join_match:
                join_type = join_match.group(1) or "JOIN"
                join_type = join_type.upper()
                if join_type == "JOIN":
                    join_label = "JOIN"
                else:
                    join_label = f"{join_type} JOIN"
                joins.append({"type": join_label, "line": lines.index(line) + 1, "statement": stripped})
                transformations.append({"type": join_label, "line": lines.index(line) + 1, "detail": stripped})

            if re.search(r"\bCONCATENATE\b", stripped, re.I):
                transformations.append({"type": "CONCATENATE", "line": lines.index(line) + 1, "detail": stripped})

            if re.search(r"\bAPPLYMAP\b", stripped, re.I):
                apply_match = re.search(r"APPLYMAP\((.*)\)", stripped, re.I)
                transformations.append({"type": "APPLYMAP", "line": lines.index(line) + 1, "detail": apply_match.group(1) if apply_match else stripped})

            where_match = re.search(r"\bWHERE\s+(.*?)(?=;|$)", stripped, re.I)
            if where_match:
                filters.append({"expression": where_match.group(1).strip(), "line": lines.index(line) + 1})
                transformations.append({"type": "WHERE", "line": lines.index(line) + 1, "expression": where_match.group(1).strip()})

            group_match = re.search(r"\bGROUP\s+BY\s+(.*?)(?=;|$)", stripped, re.I)
            if group_match:
                groups = [item.strip() for item in group_match.group(1).split(',') if item.strip()]
                aggregations.append({"group_by": groups, "line": lines.index(line) + 1})
                transformations.append({"type": "GROUP BY", "line": lines.index(line) + 1, "group_by": groups})

            if re.search(r"\bDROP\s+FIELD\b", stripped, re.I):
                drop_match = re.search(r"DROP\s+FIELD\s+(.*?)(?=;|$)", stripped, re.I)
                drop_fields.append({"fields": [item.strip() for item in drop_match.group(1).split(',') if item.strip()], "line": lines.index(line) + 1})
                transformations.append({"type": "DROP FIELD", "line": lines.index(line) + 1, "fields": [item.strip() for item in drop_match.group(1).split(',') if item.strip()]})

            if re.search(r"\bRENAME\s+FIELD\b", stripped, re.I):
                rename_match = re.search(r"RENAME\s+FIELD\s+(.*?)(?=;|$)", stripped, re.I)
                rename_fields.append({"mapping": rename_match.group(1).strip(), "line": lines.index(line) + 1})
                transformations.append({"type": "RENAME FIELD", "line": lines.index(line) + 1, "mapping": rename_match.group(1).strip()})

            if re.search(r"\bSTORE\b", stripped, re.I):
                store_statements.append({"statement": stripped, "line": lines.index(line) + 1})

            var_match = re.search(r"\b(LET|SET)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)", stripped, re.I)
            if var_match:
                variables.append({"type": var_match.group(1).upper(), "name": var_match.group(2), "expression": var_match.group(3).strip(), "line": lines.index(line) + 1})

            derived_match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*\=\s*(.*)", stripped)
            if derived_match and not re.search(r"\b(LET|SET|LOAD|FROM|WHERE|GROUP|JOIN|STORE|RENAME|DROP)\b", stripped, re.I):
                derived_columns.append({"name": derived_match.group(1), "expression": derived_match.group(2).strip(), "line": lines.index(line) + 1})

        return {
            "tables": tables,
            "sources": sources,
            "columns": columns,
            "joins": joins,
            "filters": filters,
            "aggregations": aggregations,
            "transformations": transformations,
            "variables": variables,
            "store_statements": store_statements,
            "rename_fields": rename_fields,
            "drop_fields": drop_fields,
            "derived_columns": derived_columns,
            "warnings": [],
        }

    def extract_operations(self, script: str) -> Dict[str, object]:
        metadata = self.extract_metadata(script)
        operations = []

        for item in metadata["transformations"]:
            if item["type"] not in operations:
                operations.append(item["type"])

        return {
            "operations": operations,
            "metadata": metadata,
            "warnings": metadata["warnings"],
        }

    def extract_lines(self, script: str) -> List[str]:
        return [line.strip() for line in script.splitlines() if line.strip()]
