import re
import json

class MGenerator:
    """
    Generate executable Power Query M code from parsed Qlik metadata.

    Each logical Qlik table block produces its own self-contained M
    query (``let … in …``).  The caller receives a list of
    ``{"table": name, "m_code": code}`` dicts — one per table — as
    well as a single combined string for convenience.
    """

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def generate(self, analysis: dict) -> str:
        """
        Backward-compatible entry point.

        Returns a single string that contains all per-table M queries
        separated by a blank line and a comment banner.
        """
        results = self.generate_per_table(analysis)
        if not results:
            return "// No table blocks found — nothing to generate."

        sections = []
        for entry in results:
            header = f"// ════════════════════════════════════════\n// Table: {entry['table']}\n// ════════════════════════════════════════"
            sections.append(f"{header}\n{entry['m_code']}")

        return "\n\n".join(sections)

    def generate_per_table(self, analysis: dict) -> list:
        """
        Return a list of dicts:
            [{"table": <name>, "m_code": <M query string>}, …]

        One entry per table block found in the analysis.
        """
        file_paths   = analysis.get("file_paths", {})
        table_blocks = analysis.get("table_blocks", [])

        # ── Fallback: old flat structure (pre-refactor callers) ───────
        if not table_blocks:
            table_blocks = self._build_legacy_block(analysis)

        results = []
        for block in table_blocks:
            name    = block.get("table", {}).get("name", "Query")
            m_code  = self._generate_block(block, file_paths, name)
            results.append({"table": name, "m_code": m_code})

        return results

    # ------------------------------------------------------------------
    # PER-BLOCK GENERATION
    # ------------------------------------------------------------------

    def _generate_block(
        self,
        block: dict,
        file_paths: dict,
        table_name: str,
    ) -> str:
        """Generate a complete ``let … in …`` M query for one table."""

        columns       = block.get("columns", [])
        filters       = block.get("filters", [])
        rename_fields = block.get("rename_fields", [])
        drop_fields   = block.get("drop_fields", [])
        aggregations  = block.get("aggregations", [])
        sources       = block.get("sources", [])
        joins         = block.get("joins", [])
        is_resident   = block.get("is_resident", False)
        operations    = [
            t.get("operation", t.get("type", ""))
            for t in block.get("transformations", [])
        ]

        lines = ["let"]

        # ── SOURCE ────────────────────────────────────────────────────
        current_step = self._emit_source(
            lines, sources, columns, file_paths, is_resident, table_name
        )

        # ── TYPE CHANGED COLUMNS (Only if NO aggregations exist) ──────
        if not aggregations:
            current_step = self._emit_type_changes(
                lines, columns, current_step, table_name
            )

        # ── FILTER / WHERE ────────────────────────────────────────────
        if filters:
            current_step = self._emit_filters(
                lines, filters, current_step
            )

        # ── SELECT COLUMNS ────────────────────────────────────────────
        column_names = self._unique_column_names(columns)
        if column_names and not aggregations:
            current_step = self._emit_select_columns(
                lines, column_names, current_step
            )

        # ── RENAME COLUMNS ────────────────────────────────────────────
        if rename_fields:
            current_step = self._emit_renames(
                lines, rename_fields, current_step
            )

        # ── DROP COLUMNS ──────────────────────────────────────────────
        if drop_fields:
            current_step = self._emit_drops(
                lines, drop_fields, current_step
            )

        # ── GROUP BY / AGGREGATIONS ───────────────────────────────────
        if aggregations:
            current_step = self._emit_group_by(
                lines, aggregations, current_step
            )

        # ── TYPE CHANGED COLUMNS (Moved here when aggregations exist) ──
        if aggregations:
            current_step = self._emit_type_changes(
                lines, columns, current_step, table_name
            )

        # ── ADVISORY COMMENTS ─────────────────────────────────────────
        if joins:
            lines.append(
                "    // JOIN detected — implement using Table.NestedJoin"
            )
        if "APPLYMAP" in operations:
            lines.append(
                "    // APPLYMAP detected — implement using Merge Queries"
            )

        # ── SANITIZE TRAILING COMMAS ──────────────────────────────────
        for idx in range(len(lines) - 1, -1, -1):
            stripped = lines[idx].rstrip()
            if stripped.endswith(",") and not stripped.startswith("//"):
                lines[idx] = stripped[:-1]
                break

        # ── FINAL OUTPUT ──────────────────────────────────────────────
        lines.append("in")
        lines.append(f"    {current_step}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # STEP EMITTERS
    # ------------------------------------------------------------------

    def _emit_source(
        self,
        lines: list,
        sources: list,
        columns: list,
        file_paths: dict,
        is_resident: bool,
        table_name: str,
    ) -> str:
        """Emit the Source step dynamically based on selected Data Platform."""
        
        def parse_db_connection(connection_str: str) -> tuple:
            server = "localhost"
            database = "Master"
            if not connection_str:
                return server, database
            
            # Key-aware parser to completely eliminate "Server=" prefixes inside quotes
            parts = connection_str.split(";")
            for part in parts:
                part_clean = part.strip()
                if not part_clean:
                    continue
                if "=" in part_clean:
                    k, v = part_clean.split("=", 1)
                    k_low = k.strip().lower()
                    v_val = v.strip()
                    if k_low in ["server", "host", "datasource", "data source"]:
                        server = v_val
                    elif k_low in ["database", "db", "initialcatalog", "initial catalog"]:
                        database = v_val
                else:
                    if part_clean == parts[0].strip():
                        server = part_clean
            return server, database

        # ── RESIDENT LOAD ─────────────────────────────────────────────
        file_sources = [s for s in sources if s.get("type") == "FILE"]
        res_sources  = [s for s in sources if s.get("type") == "RESIDENT"]

        if is_resident and res_sources:
            ref_table = res_sources[0]["path"]
            safe_ref  = self._safe_step_name(ref_table)
            step      = f"Source_{table_name}"
            lines.append(f"    {step} = {safe_ref},  // RESIDENT LOAD from {ref_table}")
            return step

        # Get values passed from frontend via request mapping variables
        platform = file_paths.get("platform_type", "Excel Workbook (.xlsx)")
        connection = file_paths.get("connection_details", "").strip()

        search_text = f"{platform} {connection} " + " ".join([str(s.get("path", "")) for s in sources])
        if table_blocks := file_paths.get("table_blocks", []):
            search_text += " " + (json.dumps(table_blocks) if isinstance(table_blocks, list) else str(table_blocks))

        detected_conn = None
        detected_args = None
        
        connectors_priority = [
            "MySQL.Database", "PostgreSQL.Database", "Excel.Workbook", "Csv.Document",
            "Sql.Database"
        ]
        
        # Scan for existing connector definitions
        for conn in connectors_priority:
            if conn in search_text:
                pos = search_text.find(conn)
                open_p = search_text.find("(", pos)
                if open_p != -1:
                    count = 0
                    close_p = -1
                    for i in range(open_p, len(search_text)):
                        if search_text[i] == '(':
                            count += 1
                        elif search_text[i] == ')':
                            count -= 1
                            if count == 0:
                                close_p = i
                                break
                    if close_p != -1:
                        detected_conn = conn
                        detected_args = search_text[open_p+1:close_p].strip()
                        
                        # Anti-nesting loop validation check
                        for inner_c in connectors_priority:
                            if inner_c in detected_args:
                                inner_pos = detected_args.find(inner_c)
                                inner_open = detected_args.find("(", inner_pos)
                                if inner_open != -1:
                                    inner_count = 0
                                    inner_close = -1
                                    for j in range(inner_open, len(detected_args)):
                                        if detected_args[j] == '(':
                                            inner_count += 1
                                        elif detected_args[j] == ')':
                                            inner_count -= 1
                                            if inner_count == 0:
                                                inner_close = j
                                                break
                                    if inner_close != -1:
                                        detected_conn = inner_c
                                        detected_args = detected_args[inner_open+1:inner_close].strip()
                        break

        # Fallback to UI explicit routing maps if expressions remain unpopulated
        if not detected_conn:
            platform_low = platform.lower()
            if "sql server" in platform_low:
                detected_conn = "Sql.Database"
            elif "postgresql" in platform_low:
                detected_conn = "PostgreSQL.Database"
            elif "mysql" in platform_low:
                detected_conn = "MySQL.Database"
            elif "csv" in platform_low:
                detected_conn = "Csv.Document"
            elif "sharepoint" in platform_low:
                detected_conn = "SharePoint.Files"
            else:
                detected_conn = "Excel.Workbook"

            if detected_conn in ["Sql.Database", "MySQL.Database", "PostgreSQL.Database"]:
                server, database = parse_db_connection(connection)
                detected_args = f'"{server}", "{database}"'
            else:
                # Sanitize outer string literal quotes from fallback setup
                clean_conn = connection.strip().strip('"\'')
                detected_args = f'"{clean_conn}"' if clean_conn else f'"{table_name}.xlsx"'

        # Extract Schema and Item metadata dynamically without hardcoding fallbacks
        schema_val = None
        item_val = None
        
        schema_match = re.search(r'Schema\s*=\s*"([^"]+)"', search_text, re.IGNORECASE)
        if not schema_match:
            schema_match = re.search(r"Schema\s*=\s*'([^']+)'", search_text, re.IGNORECASE)
        item_match = re.search(r'Item\s*=\s*"([^"]+)"', search_text, re.IGNORECASE)
        if not item_match:
            item_match = re.search(r"Item\s*=\s*'([^']+)'", search_text, re.IGNORECASE)
            
        if schema_match:
            schema_val = schema_match.group(1)
        if item_match:
            item_val = item_match.group(1)
            
        # Context extraction fallbacks
        if not schema_val:
            server, database = parse_db_connection(connection)
            if database and database != "Master":
                schema_val = database

        if not item_val:
            if sources and isinstance(sources[0], dict):
                item_val = sources[0].get("sheet") or sources[0].get("path")
            if not item_val or "/" in str(item_val) or "\\" in str(item_val):
                item_val = table_name

        step_src = f"Source_{table_name}"
        step_data = f"Source_{table_name}_Data"
        has_promote = "Table.PromoteHeaders" in search_text

        is_database = detected_conn in ["MySQL.Database", "Sql.Database", "PostgreSQL.Database", "Oracle.Database", "Odbc.DataSource", "Snowflake.Databases", "Databricks.Catalogs"]

        if is_database:
            lines.append(f'    {step_src} = {detected_conn}({detected_args}),')
            if schema_val:
                lines.append(f'    {step_data} = {step_src}{{[Schema="{schema_val}", Item="{item_val}"]}}[Data],')
            else:
                lines.append(f'    {step_data} = {step_src}{{[Item="{item_val}"]}}[Data],')
            
            if has_promote:
                step_hdr = f"Source_{table_name}_Headers"
                lines.append(f'    {step_hdr} = Table.PromoteHeaders({step_data}, [PromoteAllScalars=true]),')
                return step_hdr
            return step_data

        elif detected_conn == "Excel.Workbook":
            args_str = detected_args.strip()
            # Clean and isolate duplicated outer string literal quotes from path definitions
            if "File.Contents" in args_str:
                match = re.match(r'File\.Contents\((.*)\)', args_str, re.IGNORECASE)
                if match:
                    inner_path = match.group(1).strip().strip('"\'')
                    args_str = f'File.Contents("{inner_path}")'
            else:
                raw_path = args_str.strip('"\'')
                args_str = f'File.Contents("{raw_path}")'

            step_sheet = f"Source_{table_name}_Sheet"
            step_hdr = f"Source_{table_name}_Headers"
            lines.extend([
                f'    {step_src} = Excel.Workbook({args_str}, null, true),',
                f'    {step_sheet} = try {step_src}{{[Item="{item_val}", Kind="Sheet"]}} otherwise {step_src}{{0}},',
                f'    {step_data} = {step_sheet}[Data],',
            ])
            lines.append(f'    {step_hdr} = Table.PromoteHeaders({step_data}, [PromoteAllScalars=true]),')
            return step_hdr

        elif detected_conn == "Csv.Document":
            args_str = detected_args.strip()
            # Clean and isolate duplicated outer string literal quotes from path definitions
            if "File.Contents" in args_str:
                match = re.match(r'File\.Contents\((.*)\)', args_str, re.IGNORECASE)
                if match:
                    inner_path = match.group(1).strip().strip('"\'')
                    args_str = f'File.Contents("{inner_path}")'
            else:
                raw_path = args_str.strip('"\'')
                args_str = f'File.Contents("{raw_path}")'

            step_hdr = f"Source_{table_name}_Headers"
            lines.extend([
                f'    {step_src} = Csv.Document({args_str}, [Delimiter=",", Encoding=1252, QuoteStyle=QuoteStyle.None]),',
                f'    {step_hdr} = Table.PromoteHeaders({step_src}, [PromoteAllScalars=true]),'
            ])
            return step_hdr

        else:
            lines.append(f'    {step_src} = {detected_conn}({detected_args}),')
            return step_src

    # ------------------------------------------------------------------

    def _emit_type_changes(
        self,
        lines: list,
        columns: list,
        current_step: str,
        table_name: str,
    ) -> str:
        """Emit a Table.TransformColumnTypes step when columns carry explicit type information."""
        type_pairs = []
        for col in columns:
            name = col.get("name", "").strip() if isinstance(col, dict) else str(col).strip()
            if not name:
                continue
            name_lower = name.lower()
            if "id" in name_lower:
                type_pairs.append(f'{{"{name}", type text}}')
            elif "date" in name_lower:
                type_pairs.append(f'{{"{name}", type date}}')
            elif any(x in name_lower for x in ["amount", "amt", "sales", "net", "balance", "price", "rate", "emi", "value", "discount"]):
                type_pairs.append(f'{{"{name}", type number}}')
            elif any(x in name_lower for x in ["quantity", "qty", "count", "dpd", "year", "month", "creditscore"]):
                type_pairs.append(f'{{"{name}", Int64.Type}}')
            else:
                type_pairs.append(f'{{"{name}", type text}}')

        if type_pairs:
            pair_text = ", ".join(type_pairs)
            step = f"Typed_{table_name}"
            lines.append(f"    {step} = Table.TransformColumnTypes({current_step}, {{{pair_text}}}),")
            return step

        return current_step

    def _emit_filters(self, lines: list, filters: list, current_step: str) -> str:
        """Emit one Table.SelectRows step per WHERE clause."""
        step = current_step
        for i, f in enumerate(filters, start=1):
            expr     = f.get("expression", "true")
            new_step = f"FilteredRows_{i}" if len(filters) > 1 else "FilteredRows"
            lines.append(f'    {new_step} = Table.SelectRows({step}, each true), // WHERE {expr}')
            step = new_step
        return step

    def _emit_select_columns(self, lines: list, column_names: list, current_step: str) -> str:
        cols = ", ".join(f'"{c}"' for c in column_names)
        step = "SelectedColumns"
        lines.append(f"    {step} = Table.SelectColumns({current_step}, {{{cols}}}),")
        return step

    def _emit_renames(self, lines: list, rename_fields: list, current_step: str) -> str:
        rename_pairs = []
        for rf in rename_fields:
            mapping = rf.get("mapping", "")
            if " as " in mapping.lower():
                parts = re.split(r"\s+as\s+", mapping, flags=re.I)
                if len(parts) == 2:
                    old, new = parts[0].strip(), parts[1].strip()
                    rename_pairs.append(f'{{"{old}", "{new}"}}')

        if rename_pairs:
            pair_text = ", ".join(rename_pairs)
            step = "RenamedColumns"
            lines.append(f"    {step} = Table.RenameColumns({current_step}, {{{pair_text}}}),")
            return step
        return current_step

    def _emit_drops(self, lines: list, drop_fields: list, current_step: str) -> str:
        all_fields = []
        for df in drop_fields:
            all_fields.extend(df.get("fields", []))

        if all_fields:
            field_text = ", ".join(f'"{f}"' for f in all_fields)
            step = "DroppedColumns"
            lines.append(f"    {step} = Table.RemoveColumns({current_step}, {{{field_text}}}),")
            return step
        return current_step

    def _emit_group_by(self, lines: list, aggregations: list, current_step: str) -> str:
        all_groups = []
        all_aggs   = []
        for agg in aggregations:
            all_groups.extend(agg.get("group_by", []))
            all_aggs.extend(agg.get("aggregations", []))

        if all_groups:
            group_text = ", ".join(f'"{g}"' for g in all_groups)

            agg_func_map = {"Sum": "List.Sum", "Count": "List.Count", "Avg": "List.Average", "Min": "List.Min", "Max": "List.Max"}
            agg_type_map = {"Sum": "type nullable number", "Count": "Int64.Type", "Avg": "type nullable number", "Min": "type any", "Max": "type any"}

            agg_entries = []
            for a in all_aggs:
                func  = a.get("function", "")
                field = a.get("field", "")
                alias = a.get("alias", f"{func}_{field}")
                m_func = agg_func_map.get(func)
                m_type = agg_type_map.get(func, "type any")
                if m_func:
                    agg_entries.append(f'{{"{alias}", each {m_func}([{field}]), {m_type}}}')

            agg_text = ", ".join(agg_entries)
            step = "GroupedRows"
            lines.append(f"    {step} = Table.Group({current_step}, {{{group_text}}}, {{{agg_text}}}),")
            return step
        return current_step

    @staticmethod
    def _unique_column_names(columns: list) -> list:
        seen = set()
        result = []
        for col in columns:
            name = col.get("name", "").strip() if isinstance(col, dict) else str(col).strip()
            if name and name not in seen:
                seen.add(name)
                result.append(name)
        return sorted(result)

    @staticmethod
    def _safe_step_name(name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
        if safe and safe[0].isdigit():
            safe = "_" + safe
        return safe

    @staticmethod
    def _build_legacy_block(analysis: dict) -> list:
        metadata = analysis.get("metadata", {})
        if isinstance(metadata, dict) and any(isinstance(v, dict) and "columns" in v for v in metadata.values()):
            blocks = []
            for t_name, t_data in metadata.items():
                if isinstance(t_data, dict):
                    blocks.append({
                        "table": {"name": t_name, "line": 0},
                        "columns": t_data.get("columns", []),
                        "sources": [{"path": s.get("path", ""), "type": "FILE"} for s in analysis.get("source_files", [])],
                        "filters": [], "aggregations": [], "joins": analysis.get("joins", []),
                        "rename_fields": [], "drop_fields": [], "is_resident": False, "transformations": []
                    })
            if blocks: return blocks

        if isinstance(metadata, dict) and "tables" in metadata and isinstance(metadata["tables"], list):
            blocks = []
            for tbl in metadata["tables"]:
                t_name = tbl.get("name", "Query") if isinstance(tbl, dict) else str(tbl)
                t_cols = tbl.get("columns", []) if isinstance(tbl, dict) else []
                blocks.append({
                    "table": {"name": t_name, "line": 0}, "columns": t_cols,
                    "sources": [{"path": s.get("path", ""), "type": "FILE"} for s in analysis.get("source_files", [])],
                    "filters": metadata.get("filters", []), "aggregations": metadata.get("aggregations", []),
                    "joins": analysis.get("joins", []), "rename_fields": metadata.get("rename_fields", []),
                    "drop_fields": metadata.get("drop_fields", []), "is_resident": False,
                    "transformations": [{"operation": op, "type": op} for op in analysis.get("operations", [])]
                })
            return blocks

        return [{
            "table": {"name": "Query", "line": 0}, "columns": metadata.get("columns", []),
            "sources": [{"path": s.get("path", ""), "type": "FILE"} for s in analysis.get("source_files", [])],
            "filters": metadata.get("filters", []), "aggregations": metadata.get("aggregations", []),
            "joins": analysis.get("joins", []), "rename_fields": metadata.get("rename_fields", []),
            "drop_fields": metadata.get("drop_fields", []), "is_resident": False,
            "transformations": [{"operation": op, "type": op} for op in analysis.get("operations", [])]
        }]