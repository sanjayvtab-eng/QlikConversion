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
        lines = script.splitlines()
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
        load_steps = []
        warnings = []

        def split_load_columns(raw_columns: str) -> List[dict]:
            items = [item.strip() for item in re.split(r',(?![^\(]*\))', raw_columns) if item.strip()]
            parsed = []
            for item in items:
                alias_match = re.search(r"\s+as\s+([A-Za-z_][A-Za-z0-9_]*)$", item, re.I)
                if alias_match:
                    name = alias_match.group(1).strip()
                else:
                    name = item.split('.')[-1].strip('[] ').strip()
                if name:
                    parsed.append({"name": name, "raw": item})
            return parsed

        def normalize_statement(statement_text: str) -> str:
            text = re.sub(r"(?<!:)//.*", "", statement_text)
            return re.sub(r"\s+", " ", text).strip()

        def add_statement(statement_text: str, line_number: int, table_name: str | None):
            normalized = normalize_statement(statement_text)
            if not normalized:
                return

            source_path = None
            resident_table = None
            join_type = None
            join_target = None
            load_columns = []

            load_match = re.search(
                r"\bLOAD\s+(.*?)(?:\bFROM\b|\bRESIDENT\b|\bWHERE\b|\bGROUP\s+BY\b|\bCONCATENATE\b|\b(?:LEFT|INNER|RIGHT|OUTER)\s+JOIN\b|\bJOIN\b|;|$)",
                normalized,
                re.I | re.S,
            )
            if load_match:
                raw_columns = load_match.group(1)
                parsed_columns = split_load_columns(raw_columns)
                load_columns = [item["name"] for item in parsed_columns if item["name"]]
                columns.extend(
                    [
                        {
                            "name": name,
                            "source": "LOAD",
                            "line": line_number,
                        }
                        for name in load_columns
                    ]
                )

            source_match = re.search(
                r"\bFROM\s+(\[[^\]]+\]|'[^']*'|\"[^\"]*\"|[^\s;]+)",
                normalized,
                re.I,
            )
            if source_match:
                source_path = source_match.group(1).strip("'\"[]")
                if source_path:
                    sources.append({"path": source_path, "line": line_number})

            resident_match = re.search(r"\bRESIDENT\s+([A-Za-z_][A-Za-z0-9_]*)", normalized, re.I)
            if resident_match:
                resident_table = resident_match.group(1).strip()

            join_match = re.search(r"\b(LEFT|INNER|RIGHT|OUTER)?\s*JOIN\b", normalized, re.I)
            if join_match:
                keyword = join_match.group(1)
                join_type = f"{keyword.upper()} JOIN" if keyword else "JOIN"
                join_target_match = re.search(r"JOIN\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)", normalized, re.I)
                if join_target_match:
                    join_target = join_target_match.group(1).strip()
                joins.append(
                    {
                        "type": join_type,
                        "line": line_number,
                        "statement": normalized,
                        "join_target": join_target,
                        "resident_table": resident_table,
                    }
                )
                transformations.append(
                    {
                        "type": join_type,
                        "line": line_number,
                        "detail": normalized,
                    }
                )

            if load_match:
                transformations.append(
                    {
                        "type": "LOAD",
                        "line": line_number,
                        "columns": load_columns,
                        "source": source_path,
                        "resident": resident_table,
                        "table": table_name,
                    }
                )
                load_steps.append(
                    {
                        "table": table_name,
                        "columns": load_columns,
                        "source_path": source_path,
                        "resident_table": resident_table,
                        "join_type": join_type,
                        "join_target": join_target,
                        "statement": normalized,
                        "line": line_number,
                    }
                )

            if re.search(r"\bCONCATENATE\b", normalized, re.I):
                transformations.append(
                    {
                        "type": "CONCATENATE",
                        "line": line_number,
                        "detail": normalized,
                    }
                )

            if re.search(r"\bAPPLYMAP\b", normalized, re.I):
                apply_match = re.search(r"APPLYMAP\((.*)\)", normalized, re.I)
                transformations.append(
                    {
                        "type": "APPLYMAP",
                        "line": line_number,
                        "detail": apply_match.group(1).strip() if apply_match else normalized,
                    }
                )

            where_match = re.search(r"\bWHERE\s+(.*?)(?=;|$)", normalized, re.I)
            if where_match:
                expression = where_match.group(1).strip()
                filters.append({"expression": expression, "line": line_number})
                transformations.append(
                    {
                        "type": "WHERE",
                        "line": line_number,
                        "expression": expression,
                    }
                )

            group_match = re.search(r"\bGROUP\s+BY\s+(.*?)(?=;|$)", normalized, re.I)
            if group_match:
                groups = [
                    item.strip()
                    for item in re.split(r',(?![^\(]*\))', group_match.group(1))
                    if item.strip()
                ]
                aggregations.append({"group_by": groups, "line": line_number})
                transformations.append(
                    {
                        "type": "GROUP BY",
                        "line": line_number,
                        "group_by": groups,
                    }
                )

            drop_match = re.search(r"\bDROP\s+FIELD\s+(.*?)(?:\s+FROM\b|;|$)", normalized, re.I)
            if drop_match:
                fields = [item.strip() for item in drop_match.group(1).split(",") if item.strip()]
                if fields:
                    drop_fields.append({"fields": fields, "line": line_number})
                    transformations.append(
                        {
                            "type": "DROP FIELD",
                            "line": line_number,
                            "fields": fields,
                        }
                    )

            rename_match = re.search(r"\bRENAME\s+FIELD\s+(.*?)(?=;|$)", normalized, re.I)
            if rename_match:
                mapping = rename_match.group(1).strip()
                if mapping:
                    rename_fields.append({"mapping": mapping, "line": line_number})
                    transformations.append(
                        {
                            "type": "RENAME FIELD",
                            "line": line_number,
                            "mapping": mapping,
                        }
                    )

            if re.search(r"\bSTORE\b", normalized, re.I):
                store_statements.append({"statement": normalized, "line": line_number})

            var_match = re.search(r"\b(LET|SET)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)", normalized, re.I)
            if var_match:
                variables.append(
                    {
                        "type": var_match.group(1).upper(),
                        "name": var_match.group(2),
                        "expression": var_match.group(3).strip(),
                        "line": line_number,
                    }
                )

            derived_match = re.search(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", normalized)
            if derived_match and not re.search(
                r"\b(?:LET|SET|LOAD|FROM|WHERE|GROUP|JOIN|STORE|RENAME|DROP|CONCATENATE|APPLYMAP)\b",
                normalized,
                re.I,
            ):
                derived_columns.append(
                    {
                        "name": derived_match.group(1),
                        "expression": derived_match.group(2).strip(),
                        "line": line_number,
                    }
                )

        current_statement = []
        current_start = 1
        pending_table = None

        for line_index, raw_line in enumerate(lines):
            stripped = raw_line.strip()
            if not stripped:
                continue

            label_match = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*$", stripped)
            if label_match:
                if current_statement:
                    add_statement(" ".join(current_statement), current_start, pending_table)
                    current_statement = []
                pending_table = label_match.group(1).strip()
                tables.append({"name": pending_table, "line": line_index + 1})
                continue

            code_line = re.sub(r"(?<!:)//.*$", "", stripped).strip()
            if not code_line:
                continue

            if not current_statement:
                current_start = line_index + 1
            current_statement.append(code_line)

            if code_line.endswith(";"):
                add_statement(" ".join(current_statement), current_start, pending_table)
                current_statement = []
                pending_table = None

        if current_statement:
            add_statement(" ".join(current_statement), current_start, pending_table)

        unique_sources = []
        seen_paths = set()
        for item in sources:
            if item["path"] not in seen_paths:
                seen_paths.add(item["path"])
                unique_sources.append(item)

        return {
            "tables": tables,
            "sources": unique_sources,
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
            "load_steps": load_steps,
            "warnings": warnings,
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