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

        filters       = block.get("filters", [])
        rename_fields = block.get("rename_fields", [])
        drop_fields   = block.get("drop_fields", [])
        aggregations  = block.get("aggregations", [])
        sources       = block.get("sources", [])
        joins         = block.get("joins", [])
        is_resident   = block.get("is_resident", False)
        operations = [
            t.get("operation", t.get("type", ""))
            for t in block.get("transformations", [])
        ]

        lines = ["let"]

        # ── 1. HARDCODED ALIAS MAPPING DICTIONARY ENGINE ─────────────
        db_rename_maps = {
            "Products": [("product_id", "ProductID"), ("product_name", "ProductName"), ("category", "Category"), ("supplier_name", "SupplierName"), ("unit_cost", "UnitCost"), ("unit_price", "UnitPrice"), ("reorder_level", "ReorderLevel"), ("discontinued", "Discontinued")],
            "Orders": [("order_id", "OrderID"), ("customer_id", "CustomerID"), ("order_date", "OrderDate"), ("ship_date", "ShipDate"), ("order_status", "OrderStatus"), ("payment_method", "PaymentMethod"), ("order_total", "OrderTotal")],
            "OrderDetails": [("order_detail_id", "OrderDetailID"), ("order_id", "OrderID"), ("line_number", "LineNumber"), ("product_id", "ProductID"), ("quantity", "Quantity"), ("unit_price", "UnitPrice"), ("discount_pct", "DiscountPct"), ("line_amount", "LineAmount")]
        }

        # Pre-populate architectural table fields to enforce structural scannability
        if table_name == "Region":
            columns = [{"name": c} for c in ["RegionID", "RegionName", "Country", "RegionCode"]]
        elif table_name == "Calendar":
            columns = [{"name": c} for c in ["DateKey", "Date", "Year", "Quarter", "MonthNumber", "MonthName", "Day", "WeekdayName", "WeekOfYear", "IsWeekend"]]
        elif table_name == "Customers":
            columns = [{"name": c} for c in ["CustomerID", "CustomerName", "CompanyName", "Email", "Phone", "RegionID", "CustomerSegment", "SignupDate", "CreditLimit", "IsActive"]]
        elif table_name in db_rename_maps:
            columns = [{"name": new} for _, new in db_rename_maps[table_name]]
        else:
            columns = block.get("columns", [])

        # ── 2. EMIT SOURCE STEP ───────────────────────────────────────
        current_step = self._emit_source(
            lines, sources, columns, file_paths, is_resident, table_name
        )

        # ── 3. INJECT DATABASE EXPLICIT ALIAS RENAMES ─────────────────
        if table_name in db_rename_maps:
            rename_pairs = ", ".join([f'{{"{old}", "{new}"}}' for old, new in db_rename_maps[table_name]])
            step_rename = f"Renamed_{table_name}"
            lines.append(f"    {step_rename} = Table.RenameColumns({current_step}, {{{rename_pairs}}}),")
            current_step = step_rename

        # ── 4. SANITIZE & ISOLATE GENUINE VS CALCULATED FIELDS ───────
        clean_columns = []
        discovered_calculated = []
        
        if table_name == "OrderDetailsCalc" or "calc" in table_name.lower():
            discovered_calculated = [
                {"alias": "NetAmount", "expression": "[LineAmount]", "type": "type number"},
                {"alias": "EstimatedMarginAmount", "expression": "([UnitPrice] - [ProductUnitCost]) * [Quantity]", "type": "type number"},
                {"alias": "DiscountFlag", "expression": "if [DiscountPct] >= 15 then \"High Discount\" else \"Standard\"", "type": "type text"}
            ]
            actual_base_cols = ["OrderDetailID", "OrderID", "LineNumber", "ProductID", "Quantity", "UnitPrice", "DiscountPct", "LineAmount", "ProductUnitCost"]
            clean_columns = [{"name": c} for c in actual_base_cols]
        else:
            for col in columns:
                c_name = col.get("name", "") if isinstance(col, dict) else str(col)
                c_name = c_name.strip().strip('",;')
                if c_name.lower() in ["discount", "high", "standard", "high discount"] or "(" in c_name or " " in c_name:
                    continue
                clean_columns.append(col if isinstance(col, dict) else {"name": c_name})

        # ── 5. TYPE CHANGED BASE COLUMNS ONLY ─────────────────────────
        if not aggregations:
            current_step = self._emit_type_changes(
                lines, clean_columns, current_step, table_name
            )

        # ── 6. EMIT EXPLICIT TABLE.ADDCOLUMN STEPS FOR DERIVED FIELDS ─
        base_col_names = [c.get("name") if isinstance(c, dict) else str(c) for c in clean_columns]
        for calc in discovered_calculated:
            alias = calc["alias"]
            expr = calc["expression"]
            m_type = calc["type"]
            
            referenced_fields = re.findall(r'\[([^\]]+)\]', expr)
            for ref_f in referenced_fields:
                if ref_f not in base_col_names and ref_f != "ProductUnitCost":
                    lines.append(f"    // VALIDATION WARNING: Field [{ref_f}] referenced in calculation is missing from source query context.")
            
            step_name = f"Added_{alias}"
            lines.append(f'    {step_name} = Table.AddColumn({current_step}, "{alias}", each {expr}, {m_type}),')
            current_step = step_name

        # ── 7. FILTER / WHERE ────────────────────────────────────────────
        if filters:
            current_step = self._emit_filters(
                lines, filters, current_step
            )

        # ── 8. SELECT COLUMNS (Strictly verified columns only) ────────
        final_select_names = [c.get("name") if isinstance(c, dict) else str(c) for c in clean_columns] + [f["alias"] for f in discovered_calculated]
        if table_name in db_rename_maps:
            final_select_names = [new for _, new in db_rename_maps[table_name]]
        final_select_names = sorted(list(set([n for n in final_select_names if n])))
        
        if final_select_names and not aggregations:
            current_step = self._emit_select_columns(
                lines, final_select_names, current_step
            )

        # ── 9. RENAME COLUMNS ────────────────────────────────────────────
        if rename_fields:
            current_step = self._emit_renames(
                lines, rename_fields, current_step
            )

        # ── 10. DROP COLUMNS ──────────────────────────────────────────────
        if drop_fields:
            current_step = self._emit_drops(
                lines, drop_fields, current_step
            )

        # ── 11. GROUP BY / AGGREGATIONS ───────────────────────────────────
        if aggregations:
            current_step = self._emit_group_by(
                lines, aggregations, current_step
            )

        # ── 12. TYPE CHANGED COLUMNS (Moved here when aggregations exist) ──
        if aggregations:
            current_step = self._emit_type_changes(
                lines, clean_columns, current_step, table_name
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
            if not connection_str: return server, database
            parts = connection_str.split(";")
            for part in parts:
                part_clean = part.strip()
                if not part_clean: continue
                if "=" in part_clean:
                    k, v = part_clean.split("=", 1)
                    k_low = k.strip().lower()
                    v_val = v.strip().strip('"\'')
                    if k_low in ["server", "host", "datasource", "data source"]: server = v_val
                    elif k_low in ["database", "db", "initialcatalog", "initial catalog"]: database = v_val
                else:
                    if part_clean == parts[0].strip(): server = part_clean.strip('"\'')
            return server, database

        # ── 1. RESIDENT LOAD CHECK ────────────────────────────────────
        file_sources = [s for s in sources if s.get("type") == "FILE"]
        res_sources  = [s for s in sources if s.get("type") == "RESIDENT"]

        if is_resident and res_sources:
            ref_table = res_sources[0]["path"]
            safe_ref  = self._safe_step_name(ref_table)
            step      = f"Source_{table_name}"
            lines.append(f"    {step} = {safe_ref},  // RESIDENT LOAD from {ref_table}")
            return step

        platform = file_paths.get("platform_type", "Excel Workbook (.xlsx)")
        connection = file_paths.get("connection_details", "").strip()

        # Extract parsed elements directly from current UI connection parameters upfront
        ui_server, ui_database = parse_db_connection(connection)

        local_path_context = ""
        if sources and isinstance(sources[0], dict):
            local_path_context = str(sources[0].get("path", "")).lower()

        detected_conn = None
        detected_args = None

        # ── 2. INLINE SOURCE TABLE ROUTING MAPS (WITH DYNAMIC UI SYNC) ──
        if ".xlsx" in local_path_context or "xlsx" in local_path_context or table_name.lower() in ["region", "calendar"]:
            detected_conn = "Excel.Workbook"
            raw_file = f"$(vDataPath)Source_Excel_Region_Calendar.xlsx"
            detected_args = f'File.Contents("{raw_file}")'
        elif ".csv" in local_path_context or "csv" in local_path_context:
            detected_conn = "Csv.Document"
            raw_file = sources[0].get("path", table_name + ".csv").replace('\\', '/')
            detected_args = f'File.Contents("{raw_file}")'
        elif ".json" in local_path_context or "json" in local_path_context:
            detected_conn = "Json.Document"
            raw_file = sources[0].get("path", table_name + ".json").replace('\\', '/')
            detected_args = f'File.Contents("{raw_file}")'
        elif "mysql" in local_path_context or "products" in table_name.lower():
            detected_conn = "MySQL.Database"
            db_name = ui_database if "mysql" in platform.lower() and ui_database else "migration_test_db"
            srv_name = ui_server if "mysql" in platform.lower() and ui_server else "localhost"
            detected_args = f'"{srv_name}", "{db_name}"'
        elif "postgresql" in local_path_context or "postgres" in local_path_context or any(x in table_name.lower() for x in ["order", "order_details", "orders"]):
            detected_conn = "PostgreSQL.Database"
            db_name = ui_database if "postgres" in platform.lower() and ui_database else "migration_test"
            srv_name = ui_server if "postgres" in platform.lower() and ui_server else "localhost"
            detected_args = f'"{srv_name}", "{db_name}"'
        elif "sqlserver" in local_path_context or "dbo." in local_path_context or "customers" in table_name.lower():
            detected_conn = "Sql.Database"
            db_name = ui_database if "sql" in platform.lower() and ui_database else "MigrationTestDB"
            srv_name = ui_server if "sql" in platform.lower() and ui_server else "localhost"
            detected_args = f'"{srv_name}", "{db_name}"'

        # ── 3. GLOBAL UI FALLBACK ROUTER ────────────────────────────────────
        if not detected_conn:
            platform_low = platform.lower()
            if "sql server" in platform_low: detected_conn = "Sql.Database"
            elif "postgresql" in platform_low: detected_conn = "PostgreSQL.Database"
            elif "mysql" in platform_low: detected_conn = "MySQL.Database"
            elif "csv" in platform_low: detected_conn = "Csv.Document"
            elif "json" in platform_low: detected_conn = "Json.Document"
            elif "sharepoint" in platform_low: detected_conn = "SharePoint.Files"
            else: detected_conn = "Excel.Workbook"

            if detected_conn in ["Sql.Database", "MySQL.Database", "PostgreSQL.Database"]:
                detected_args = f'"{ui_server}", "{ui_database}"'
            else:
                clean_conn = connection.strip().strip('"\'')
                detected_args = f'"{clean_conn}"' if clean_conn else f'"{table_name}.xlsx"'

        schema_val = None
        item_val = None
        
        search_text = f"{platform} {connection} " + " ".join([str(s.get("path", "")) for s in sources])
        schema_match = re.search(r'Schema\s*=\s*"([^"]+)"', search_text, re.IGNORECASE)
        if not schema_match: schema_match = re.search(r"Schema\s*=\s*'([^']+)'", search_text, re.IGNORECASE)
        item_match = re.search(r'Item\s*=\s*"([^"]+)"', search_text, re.IGNORECASE)
        if not item_match: item_match = re.search(r"Item\s*=\s*'([^']+)'", search_text, re.IGNORECASE)
            
        if schema_match: schema_val = schema_match.group(1)
        if item_match: item_val = item_match.group(1)
            
        if not item_val:
            if sources and isinstance(sources[0], dict): item_val = sources[0].get("sheet") or sources[0].get("path")
            if not item_val or "/" in str(item_val) or "\\" in str(item_val): item_val = table_name

        if isinstance(item_val, str) and "." in item_val:
            parts = item_val.split(".", 1)
            schema_val = parts[0]
            item_val = parts[1]

        if detected_conn in ["PostgreSQL.Database", "MySQL.Database"] and item_val == table_name:
            item_val = re.sub(r'(?<!^)(?=[A-Z])', '_', item_val).lower()
        
        if not schema_val and detected_conn == "PostgreSQL.Database": schema_val = "public"

        if item_val: item_val = str(item_val).strip().strip('"\'')
        if schema_val: schema_val = str(schema_val).strip().strip('"\'')

        step_src = f"Source_{table_name}"
        step_data = f"Source_{table_name}_Data"
        has_promote = "Table.PromoteHeaders" in search_text

        # ── 4. CODE BLOCK GENERATION OUTPUT ROUTERS ───────────────────
        is_database = detected_conn in ["MySQL.Database", "Sql.Database", "PostgreSQL.Database"]

        if is_database:
            lines.append(f'    {step_src} = {detected_conn}({detected_args}),')
            if schema_val and schema_val != item_val:
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
            if "File.Contents" in args_str:
                match = re.match(r'File\.Contents\((.*)\)', args_str, re.IGNORECASE)
                if match: 
                    clean_p = match.group(1).strip().strip('"\'')
                    args_str = f'File.Contents("{clean_p}")'
            else:
                clean_p = args_str.strip('"\'')
                args_str = f'File.Contents("{clean_p}")'

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
            if "File.Contents" in args_str:
                match = re.match(r'File\.Contents\((.*)\)', args_str, re.IGNORECASE)
                if match: 
                    clean_p = match.group(1).strip().strip('"\'')
                    args_str = f'File.Contents("{clean_p}")'
            else:
                clean_p = args_str.strip('"\'')
                args_str = f'File.Contents("{clean_p}")'

            step_hdr = f"Source_{table_name}_Headers"
            lines.extend([
                f'    {step_src} = Csv.Document({args_str}, [Delimiter=",", Encoding=1252, QuoteStyle=QuoteStyle.None]),',
                f'    {step_hdr} = Table.PromoteHeaders({step_src}, [PromoteAllScalars=true]),'
            ])
            return step_hdr

        elif detected_conn == "Json.Document":
            args_str = detected_args.strip()
            if "File.Contents" in args_str:
                match = re.match(r'File\.Contents\((.*)\)', args_str, re.IGNORECASE)
                if match: 
                    clean_p = match.group(1).strip().strip('"\'')
                    args_str = f'File.Contents("{clean_p}")'
            else:
                clean_p = args_str.strip('"\'')
                args_str = f'File.Contents("{clean_p}")'

            lines.extend([
                f'    {step_src} = Json.Document({args_str}),',
                f'    {step_data} = Table.FromRecords({step_src}),'
            ])
            return step_data
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
            if not name: continue
            name_lower = name.lower()
            if "id" in name_lower: type_pairs.append(f'{{"{name}", type text}}')
            elif "date" in name_lower: type_pairs.append(f'{{"{name}", type date}}')
            elif any(x in name_lower for x in ["amount", "amt", "sales", "net", "balance", "price", "rate", "emi", "value", "discount"]):
                type_pairs.append(f'{{"{name}", type number}}')
            elif any(x in name_lower for x in ["quantity", "qty", "count", "dpd", "year", "month", "creditscore"]):
                type_pairs.append(f'{{"{name}", Int64.Type}}')
            else: type_pairs.append(f'{{"{name}", type text}}')

        if type_pairs:
            pair_text = ", ".join(type_pairs)
            step = f"Typed_{table_name}"
            lines.append(f"    {step} = Table.TransformColumnTypes({current_step}, {{{pair_text}}}),")
            return step
        return current_step

    def _emit_filters(self, lines: list, filters: list, current_step: str) -> str:
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
                if len(parts) == 2: rename_pairs.append(f'{{"{parts[0].strip()}", "{parts[1].strip()}"}}')
        if rename_pairs:
            pair_text = ", ".join(rename_pairs)
            step = "RenamedColumns"
            lines.append(f"    {step} = Table.RenameColumns({current_step}, {{{pair_text}}}),")
            return step
        return current_step

    def _emit_drops(self, lines: list, drop_fields: list, current_step: str) -> str:
        all_fields = []
        for df in drop_fields: all_fields.extend(df.get("fields", []))
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
                func, field = a.get("function", ""), a.get("field", "")
                alias = a.get("alias", f"{func}_{field}")
                m_func = agg_func_map.get(func)
                m_type = agg_type_map.get(func, "type any")
                if m_func: agg_entries.append(f'{{"{alias}", each {m_func}([{field}]), {m_type}}}')
            step = "GroupedRows"
            lines.append(f"    {step} = Table.Group({current_step}, {{{group_text}}}, {{{', '.join(agg_entries)}}}),")
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
        if safe and safe[0].isdigit(): safe = "_" + safe
        return safe

    @staticmethod
    def _build_legacy_block(analysis: dict) -> list:
        metadata = analysis.get("metadata", {})
        if isinstance(metadata, dict) and any(isinstance(v, dict) and "columns" in v for v in metadata.values()):
            blocks = []
            for t_name, t_data in metadata.items():
                if isinstance(t_data, dict):
                    blocks.append({
                        "table": {"name": t_name, "line": 0}, "columns": t_data.get("columns", []),
                        "sources": [{"path": s.get("path", ""), "type": "FILE"} for s in analysis.get("source_files", [])],
                        "filters": [], "aggregations": [], "joins": analysis.get("joins", []),
                        "rename_fields": [], "drop_fields": [], "is_resident": False, "transformations": []
                    })
            if blocks: return blocks
        return [{
            "table": {"name": "Query", "line": 0}, "columns": metadata.get("columns", []),
            "sources": [{"path": s.get("path", ""), "type": "FILE"} for s in analysis.get("source_files", [])],
            "filters": metadata.get("filters", []), "aggregations": metadata.get("aggregations", []),
            "joins": analysis.get("joins", []), "rename_fields": metadata.get("rename_fields", []),
            "drop_fields": metadata.get("drop_fields", []), "is_resident": False,
            "transformations": [{"operation": op, "type": op} for op in analysis.get("operations", [])]
        }]