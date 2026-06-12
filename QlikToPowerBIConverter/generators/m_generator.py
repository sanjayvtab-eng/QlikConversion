from pathlib import Path
import re
from typing import Dict, List, Optional


class MGenerator:
    """Generate Power Query M scripts per-source and a single final combined query.

    generate() returns a dict with keys:
      - table_queries: mapping tableName -> M text
      - final_query: single combined M text including joins and final transforms
    """

    def _sanitize_name(self, name: Optional[str]) -> str:
        if not name:
            return "Source"
        sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name)
        if sanitized and sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
        return sanitized or "Source"

    def _m_string_literal(self, value: str) -> str:
        escaped = str(value).replace("\\", "\\\\").replace('"', '""')
        return f'"{escaped}"'

    def _source_expression(self, source_path: str, mapped_path: Optional[str]) -> str:
        path = mapped_path or source_path or ""
        normalized = path.strip('"\'')
        lower = normalized.lower()
        if lower.endswith((".xlsx", ".xls")):
            return f"Excel.Workbook(File.Contents({self._m_string_literal(normalized)}), null, true)"
        if lower.endswith(".csv"):
            return f"Csv.Document(File.Contents({self._m_string_literal(normalized)}), [Delimiter=\",\", Encoding=1252, QuoteStyle=QuoteStyle.Csv])"
        if lower.endswith(".qvd"):
            return f"// QVD source: {normalized}  // replace with a supported data source"
        return f"File.Contents({self._m_string_literal(normalized)})"

    def _infer_join_keys(self, left_cols: List[str], right_cols: List[str]) -> List[str]:
        left_set = {c for c in (left_cols or []) if c}
        right_set = {c for c in (right_cols or []) if c}
        keys = sorted(left_set & right_set)
        if keys:
            return keys
        left_id = {c for c in left_set if c.lower().endswith("id")}
        right_id = {c for c in right_set if c.lower().endswith("id")}
        return sorted(left_id & right_id)

    def _infer_column_types(self, cols: List[str]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for col in cols:
            if not col:
                continue
            tok = re.findall(r"[a-z0-9]+", col.lower())
            if any(t == "id" or t.endswith("id") for t in tok):
                mapping[col] = "Int64.Type"
                continue
            if any(t in {"count", "qty", "quantity"} for t in tok):
                mapping[col] = "Int64.Type"
                continue
            if any(t in {"date", "created", "updated", "datetime"} for t in tok):
                mapping[col] = "type date"
                continue
            if any(t in {"amount", "price", "total", "value", "number", "num"} for t in tok):
                mapping[col] = "type number"
                continue
            mapping[col] = "type text"
        return mapping

    def _format_filter_expression(self, expression: str) -> str:
        if not expression:
            return "true"
        m = re.match(r"([A-Za-z0-9_\.\[\]]+)\s*(=|<>|>=|<=|>|<)\s*(.+)", expression.strip())
        if m:
            field = m.group(1).split(".")[-1].strip('[]')
            op = m.group(2)
            val = m.group(3).strip()
            return f"[{field}] {op} {val}"
        return "true"

    def generate(self, analysis: dict) -> Dict[str, object]:
        metadata = analysis.get("metadata", {}) or {}
        file_paths = analysis.get("file_paths", {}) or {}
        operations = analysis.get("operations", []) or []

        load_steps = metadata.get("load_steps", []) or []
        columns_meta = metadata.get("columns", []) or []

        # Build table -> columns map
        table_columns: Dict[str, List[str]] = {}
        for step in load_steps:
            t = step.get("table")
            cols = step.get("columns") or []
            if t and cols:
                table_columns[t] = cols

        # Create per-source/table queries
        table_queries: Dict[str, str] = {}
        source_name_for_path: Dict[str, str] = {}

        # First, create one query per physical source file referenced in load_steps
        for step in load_steps:
            src = step.get("source_path")
            tbl = step.get("table")
            if not src:
                continue
            if src in source_name_for_path:
                continue
            query_name = self._sanitize_name(tbl or Path(src).stem or "Source")
            base = query_name
            idx = 1
            while query_name in table_queries:
                idx += 1
                query_name = f"{base}_{idx}"

            mapped = file_paths.get(src, src)
            expr = self._source_expression(src, mapped)
            lower = src.lower()
            lines: List[str] = ["let"]
            lines.append(f"    Source = {expr},")
            if lower.endswith((".xlsx", ".xls")):
                lines.append(f"    {query_name}_Sheet = Source{{0}}[Data],")
                lines.append(f"    {query_name}_Headers = Table.PromoteHeaders({query_name}_Sheet)")
                lines.append("in")
                lines.append(f"    {query_name}_Headers")
            elif lower.endswith(".csv"):
                lines.append(f"    {query_name}_Headers = Table.PromoteHeaders(Source)")
                lines.append("in")
                lines.append(f"    {query_name}_Headers")
            else:
                lines.append("in")
                lines.append("    Source")

            table_queries[query_name] = "\n".join(lines)
            source_name_for_path[src] = query_name

        # Next, create queries for RESIDENT loads (those that select from resident tables)
        for step in load_steps:
            if step.get("source_path"):
                continue
            resident = step.get("resident_table")
            target = step.get("table")
            if not resident or not target:
                continue
            target_name = self._sanitize_name(target)
            base = target_name
            idx = 1
            while target_name in table_queries:
                idx += 1
                target_name = f"{base}_{idx}"

            source_ref = f"{self._sanitize_name(resident)}_Headers"
            cols = step.get("columns") or []
            lines = ["let"]
            if cols:
                cols_lit = ", ".join(f'"{c}"' for c in cols)
                lines.append(f"    Source = {source_ref},")
                lines.append(f"    {target_name} = Table.SelectColumns(Source, {{{cols_lit}}}),")
                lines.append("in")
                lines.append(f"    {target_name}")
            else:
                lines.append(f"    Source = {source_ref}")
                lines.append("in")
                lines.append("    Source")

            table_queries[target_name] = "\n".join(lines)

        # Build final combined query: include all source loads, then perform resident/join transforms inline
        final_lines: List[str] = ["let"]

        # Include all physical sources in final query
        for src_path, qname in source_name_for_path.items():
            mapped = file_paths.get(src_path, src_path)
            expr = self._source_expression(src_path, mapped)
            lower = src_path.lower()
            final_lines.append(f"    {qname} = {expr},")
            if lower.endswith((".xlsx", ".xls")):
                final_lines.append(f"    {qname}_Sheet = {qname}{{0}}[Data],")
                final_lines.append(f"    {qname}_Headers = Table.PromoteHeaders({qname}_Sheet),")
            elif lower.endswith(".csv"):
                final_lines.append(f"    {qname}_Headers = Table.PromoteHeaders({qname}),")

        # Add RESIDENT loads as references to existing headers
        for step in load_steps:
            if step.get("source_path"):
                continue
            resident = step.get("resident_table")
            target = step.get("table")
            if not resident or not target:
                continue
            target_name = self._sanitize_name(target)
            cols = step.get("columns") or []
            if cols:
                cols_lit = ", ".join(f'"{c}"' for c in cols)
                final_lines.append(f"    {target_name} = Table.SelectColumns({self._sanitize_name(resident)}_Headers, {{{cols_lit}}}),")
            else:
                final_lines.append(f"    {target_name} = {self._sanitize_name(resident)}_Headers,")

        # Now process joins inline and generate merged result step name
        # Collect join definitions
        join_steps = [s for s in load_steps if s.get("join_type") and s.get("join_target")]
        merged_step_name = None
        for idx, j in enumerate(join_steps, start=1):
            left = j.get("join_target")
            right = j.get("resident_table") or None
            right_src = j.get("source_path") or None
            left_ref = f"{self._sanitize_name(left)}_Headers"
            if right:
                right_ref = f"{self._sanitize_name(right)}_Headers"
            elif right_src:
                right_ref = f"{source_name_for_path.get(right_src)}_Headers"
            else:
                continue

            left_cols = table_columns.get(left, [])
            right_cols = table_columns.get(right or "", [])
            keys = self._infer_join_keys(left_cols, right_cols) or ["ID"]
            join_kind_map = {
                "LEFT JOIN": "LeftOuter",
                "INNER JOIN": "Inner",
                "RIGHT JOIN": "RightOuter",
                "OUTER JOIN": "FullOuter",
                "JOIN": "LeftOuter",
            }
            join_kind = join_kind_map.get(j.get("join_type"), "LeftOuter")
            merged_step_name = self._sanitize_name(f"{left}_{right or right_src}_Merged")
            keys_lit = ", ".join(f'"{k}"' for k in keys)
            final_lines.append(
                f"    {merged_step_name} = Table.NestedJoin({left_ref}, {{{keys_lit}}}, {right_ref}, {{{keys_lit}}}, \"JoinedRows\", JoinKind.{join_kind}),"
            )
            # expand non-key columns from right
            expand_cols = [c for c in (right_cols or []) if c not in keys]
            if expand_cols:
                expand_lit = ", ".join(f'"{c}"' for c in expand_cols)
                expand_name = self._sanitize_name(f"{left}_{right or right_src}_Expanded")
                final_lines.append(f"    {expand_name} = Table.ExpandTableColumn({merged_step_name}, \"JoinedRows\", {{{expand_lit}}}),")
                current_final_ref = expand_name
            else:
                current_final_ref = merged_step_name

        # If no joins, pick a sensible final source
        if merged_step_name is None:
            # prefer last load step table, or first source
            final_candidate = None
            if load_steps:
                last = load_steps[-1]
                if last.get("table"):
                    final_candidate = self._sanitize_name(last["table"])
                elif last.get("source_path"):
                    final_candidate = source_name_for_path.get(last["source_path"])
            current_final_ref = final_candidate or (next(iter(table_queries.keys()), None) or "Source")

        # Apply final transforms: filters, types, selects, rename, drop, group
        # Filters
        filters = metadata.get("filters", []) or []
        if filters:
            expr = self._format_filter_expression(filters[0].get("expression", ""))
            final_lines.append(f"    FilteredRows = Table.SelectRows({current_final_ref}, each {expr}),")
            current_final_ref = "FilteredRows"

        # Type inference + select columns
        column_names = sorted({c["name"] for c in (columns_meta or []) if c.get("name")})
        if column_names:
            type_map = self._infer_column_types(column_names)
            overrides = metadata.get("column_types", {}) if isinstance(metadata, dict) else {}
            for col, tv in (overrides or {}).items():
                if col in type_map:
                    type_map[col] = tv
            type_list = ", ".join(f'{{"{col}", {type_map.get(col, "type any")}}}' for col in column_names)
            final_lines.append(f"    TypedColumns = Table.TransformColumnTypes({current_final_ref}, {{{type_list}}}),")
            current_final_ref = "TypedColumns"
            cols_lit = ", ".join(f'"{n}"' for n in column_names)
            final_lines.append(f"    SelectedColumns = Table.SelectColumns({current_final_ref}, {{{cols_lit}}}),")
            current_final_ref = "SelectedColumns"

        # Rename fields
        rename_fields = metadata.get("rename_fields", []) or []
        if rename_fields:
            mapping = rename_fields[0].get("mapping", "")
            if " as " in mapping.lower():
                left, right = [p.strip() for p in mapping.split(" as ", 1)]
                final_lines.append(f"    RenamedColumns = Table.RenameColumns({current_final_ref}, {{\"{left}\", \"{right}\"}}),")
                current_final_ref = "RenamedColumns"

        # Drop fields
        drop_fields = metadata.get("drop_fields", []) or []
        if drop_fields:
            dropped = ", ".join(f'"{f}"' for f in drop_fields[0].get("fields", []))
            final_lines.append(f"    DroppedColumns = Table.RemoveColumns({current_final_ref}, {{{dropped}}}),")
            current_final_ref = "DroppedColumns"

        # Group by
        aggs = metadata.get("aggregations", []) or []
        if aggs:
            group_by = aggs[0].get("group_by", [])
            group_lit = ", ".join(f'"{g}"' for g in group_by)
            final_lines.append(f"    GroupedRows = Table.Group({current_final_ref}, {{{group_lit}}}, {{}}),")
            current_final_ref = "GroupedRows"

        # APPLYMAP support: include comment to guide user
        if any(t.get("type") == "APPLYMAP" for t in (metadata.get("transformations") or [])):
            final_lines.append("    // APPLYMAP detected: implement lookup/merge in Power Query as needed.")

        # Trim trailing comma
        for i in range(len(final_lines) - 1, -1, -1):
            if final_lines[i].endswith(","):
                final_lines[i] = final_lines[i][:-1]
                break

        final_lines.append("in")
        final_lines.append(f"    {current_final_ref}")
        final_query = "\n".join(final_lines)

        return {"table_queries": table_queries, "final_query": final_query}
