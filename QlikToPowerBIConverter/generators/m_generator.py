from pathlib import Path
import re

class MGenerator:
    """Generate executable Power Query M code from parsed Qlik metadata."""

    def _sanitize_name(self, name: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name or "Source")
        if sanitized and sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
        return sanitized or "Source"

    def _source_step_name(self, source_path: str, table_name: str | None) -> str:
        if table_name:
            return self._sanitize_name(table_name)
        file_name = Path(source_path).stem
        return self._sanitize_name(file_name)

    def _source_expression(self, source_path: str) -> str:
        normalized = source_path.strip("'\"")
        file_name = Path(normalized.replace("\\", "/")).name
        lower_name = file_name.lower()
        if lower_name.endswith((".xlsx", ".xls")):
            return f'Excel.Workbook(File.Contents("{file_name}"), null, true)'
        if lower_name.endswith(".csv"):
            return f'Csv.Document(File.Contents("{file_name}"), [Delimiter=",", Encoding=1252, QuoteStyle=QuoteStyle.Csv])'
        if lower_name.endswith(".qvd"):
            return f'// QVD source: {normalized}  // replace with a supported data source'
        return f'File.Contents("{file_name}")'

    def _infer_join_keys(self, left_columns: list[str], right_columns: list[str]) -> list[str]:
        left_set = {col for col in left_columns if col}
        right_set = {col for col in right_columns if col}
        keys = sorted(left_set & right_set)
        if keys:
            return keys
        left_id = {col for col in left_set if col.lower().endswith("id")}
        right_id = {col for col in right_set if col.lower().endswith("id")}
        return sorted(left_id & right_id)

    def _infer_column_types(self, columns: list[str]) -> dict[str, str]:
        """Infer basic column types from column names."""
        type_map = {}

        for col in columns:
            lower_col = col.lower()
            tokens = re.findall(r"[a-z0-9]+", lower_col)

            if any(t == "id" or t.endswith("id") for t in tokens):
                type_map[col] = "Int64.Type"
                continue

            if any(t in {"count", "qty", "quantity"} for t in tokens):
                type_map[col] = "Int64.Type"
                continue

            if any(t in {"date", "created", "updated", "datetime"} for t in tokens):
                type_map[col] = "type date"
                continue

            if any(t in {"amount", "price", "total", "value", "number", "num"} for t in tokens):
                type_map[col] = "type number"
                continue

            type_map[col] = "type text"
        return type_map
    def _normalize_type_value(self, value: str) -> str:
        """Normalize a simple type keyword or return the M type string as-is.

        Accepts inputs like 'text', 'number', 'int', 'Int64.Type', 'type date', etc.
        """
        if not isinstance(value, str) or not value:
            return "type any"
        v = value.strip()
        lv = v.lower()
        if lv in ("text", "string"):
            return "type text"
        if lv in ("number", "decimal", "float"):
            return "type number"
        if lv in ("int", "int64", "integer"):
            return "Int64.Type"
        if lv in ("date", "datetime"):
            return "type date"
        # If the caller provided a full M type expression, use it directly
        return v

    def _format_filter_expression(self, expression: str) -> str:
        simple_match = re.match(r"([A-Za-z0-9_\.\[\]]+)\s*(=|<>|>=|<=|>|<)\s*(.+)", expression.strip())
        if simple_match:
            field = simple_match.group(1).strip()
            operator = simple_match.group(2)
            value = simple_match.group(3).strip()
            field_name = field.split('.')[-1].strip('[]')
            return f"[{field_name}] {operator} {value}"
        return "true"

    def generate(self, analysis: dict) -> str:
        metadata = analysis.get("metadata", {})
        operations = analysis.get("operations", [])
        columns = metadata.get("columns", [])
        filters = metadata.get("filters", [])
        rename_fields = metadata.get("rename_fields", [])
        drop_fields = metadata.get("drop_fields", [])
        aggregations = metadata.get("aggregations", [])
        load_steps = metadata.get("load_steps", [])

        source_definitions: list[tuple[str, str]] = []
        table_to_source: dict[str, str] = {}
        table_to_path: dict[str, str] = {}
        table_columns: dict[str, list[str]] = {}

        for step in load_steps:
            if step.get("table") and step.get("columns"):
                table_columns[step["table"]] = step["columns"]
            if step.get("source_path"):
                source_name = self._source_step_name(step["source_path"], step.get("table"))
                if source_name not in [name for name, _ in source_definitions]:
                    source_definitions.append((source_name, self._source_expression(step["source_path"])))
                    table_to_path[source_name] = step["source_path"]
                if step.get("table"):
                    table_to_source[step["table"]] = source_name

        current_step = None
        lines = ["let"]

        for source_name, expr in source_definitions:
            file_path = table_to_path.get(source_name, "")
            lower_path = file_path.lower()
            
            lines.append(f"    {source_name} = {expr},")
            
            if lower_path.endswith((".xlsx", ".xls")):
                sheet_name = f"{source_name}_Sheet"
                lines.append(f"    {sheet_name} = {source_name}{{[Item=\"Sheet1\",Kind=\"Sheet\"]}}[Data],")
                header_name = f"{source_name}_Headers"
                lines.append(f"    {header_name} = Table.PromoteHeaders({sheet_name}),")
                current_step = header_name
            elif lower_path.endswith(".csv"):
                header_name = f"{source_name}_Headers"
                lines.append(f"    {header_name} = Table.PromoteHeaders({source_name}),")
                current_step = header_name
            else:
                current_step = source_name

        join_steps = [step for step in load_steps if step.get("join_type") and step.get("join_target") and step.get("resident_table")]
        for join in join_steps:
            left_table = join["join_target"]
            right_table = join["resident_table"]
            left_name = table_to_source.get(left_table, self._sanitize_name(left_table))
            right_name = table_to_source.get(right_table, self._sanitize_name(right_table))
            
            left_path = table_to_path.get(left_name, "")
            right_path = table_to_path.get(right_name, "")
            if left_path.lower().endswith((".xlsx", ".xls", ".csv")):
                left_name = f"{left_name}_Headers"
            if right_path.lower().endswith((".xlsx", ".xls", ".csv")):
                right_name = f"{right_name}_Headers"
            
            left_cols = table_columns.get(left_table, [])
            right_cols = table_columns.get(right_table, [])
            join_keys = self._infer_join_keys(left_cols, right_cols)
            if not join_keys:
                join_keys = ["ID"]

            join_kind_map = {
                "LEFT JOIN": "LeftOuter",
                "INNER JOIN": "Inner",
                "RIGHT JOIN": "RightOuter",
                "OUTER JOIN": "FullOuter",
                "JOIN": "LeftOuter",
            }
            join_kind = join_kind_map.get(join["join_type"], "LeftOuter")
            merge_name = self._sanitize_name(f"{left_table}_{right_table}_Merged")
            joined_table_name = "JoinedTable"
            keys_literal = "{" + ", ".join(f'\"{key}\"' for key in join_keys) + "}"
            lines.append(
                f"    {merge_name} = Table.NestedJoin({left_name}, {keys_literal}, {right_name}, {keys_literal}, \"{joined_table_name}\", JoinKind.{join_kind}),"
            )

            expand_columns = [col for col in right_cols if col not in join_keys]
            if expand_columns:
                expand_name = self._sanitize_name(f"{left_table}_{right_table}_Expanded")
                expand_list = "{" + ", ".join(f'\"{col}\"' for col in expand_columns) + "}"
                lines.append(
                    f"    {expand_name} = Table.ExpandTableColumn({merge_name}, \"{joined_table_name}\", {expand_list}),"
                )
                current_step = expand_name
            else:
                current_step = merge_name

        if current_step is None:
            column_names = sorted({item["name"] for item in columns if item.get("name")})
            if not column_names:
                column_names = ["Column1"]
            lines.append(
                "    Source = #table(type table [" + ", ".join(f'{name}=any' for name in column_names) + "], {}),"
            )
            current_step = "Source"

        if filters:
            expression = self._format_filter_expression(filters[0]["expression"])
            lines.append(f"    FilteredRows = Table.SelectRows({current_step}, each {expression}),")
            current_step = "FilteredRows"

        column_names = sorted({item["name"] for item in columns if item.get("name")})
        if column_names:
            type_map = self._infer_column_types(column_names)
            # Allow explicit overrides from metadata: metadata["column_types"] = {"Country": "text"}
            overrides = metadata.get("column_types", {}) if isinstance(metadata, dict) else {}
            for col, tv in overrides.items():
                if col in type_map:
                    type_map[col] = self._normalize_type_value(tv)

            type_list = ", ".join(f'{{"{col}", {type_map.get(col, "type any")}}}' for col in column_names)
            type_spec = "{" + type_list + "}"
            lines.append(
                f"    TypedColumns = Table.TransformColumnTypes({current_step}, {type_spec}),"
            )
            current_step = "TypedColumns"
            
            lines.append(
                "    SelectedColumns = Table.SelectColumns(" + current_step + ", {" + ", ".join(f'\"{name}\"' for name in column_names) + "}),"
            )
            current_step = "SelectedColumns"

        if rename_fields:
            rename_map = rename_fields[0].get("mapping", "")
            if " as " in rename_map.lower():
                old, new = [item.strip() for item in rename_map.split(" as ")]
                lines.append(f"    RenamedColumns = Table.RenameColumns({current_step}, {{\"{old}\", \"{new}\"}}),")
                current_step = "RenamedColumns"

        if drop_fields:
            dropped = ", ".join(f'\"{field}\"' for field in drop_fields[0].get("fields", []))
            lines.append(f"    DroppedColumns = Table.RemoveColumns({current_step}, {{{dropped}}}),")
            current_step = "DroppedColumns"

        if aggregations:
            group_by = aggregations[0].get("group_by", [])
            lines.append(
                "    GroupedRows = Table.Group(" + current_step + ", {" + ", ".join(f'\"{item}\"' for item in group_by) + "}, {{}}),"
            )
            current_step = "GroupedRows"

        if "APPLYMAP" in operations:
            lines.append("    // APPLYMAP requires a lookup table or manual merge step in Power Query.")
        if any(join_type in operations for join_type in ["JOIN", "LEFT JOIN", "INNER JOIN", "RIGHT JOIN", "OUTER JOIN"]):
            lines.append("    // The actual join has been converted using Table.NestedJoin.")

        for index in range(len(lines) - 1, -1, -1):
            if lines[index].endswith(","):
                lines[index] = lines[index][:-1]
                break

        lines.append("in")
        lines.append(f"    {current_step}")

        return "\n".join(lines)

