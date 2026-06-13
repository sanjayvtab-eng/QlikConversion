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

        # ── TYPE CHANGED COLUMNS ───────────────────────────────────────
        current_step = self._emit_type_changes(
            lines, columns, current_step
        )

        # ── FILTER / WHERE ────────────────────────────────────────────
        if filters:
            current_step = self._emit_filters(
                lines, filters, current_step
            )

        # ── SELECT COLUMNS ────────────────────────────────────────────
        column_names = self._unique_column_names(columns)
        if column_names:
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

        # ── ADVISORY COMMENTS ─────────────────────────────────────────
        if joins:
            lines.append(
                "    // JOIN detected — implement using Table.NestedJoin"
            )
        if "APPLYMAP" in operations:
            lines.append(
                "    // APPLYMAP detected — implement using Merge Queries"
            )

        # ── FINAL OUTPUT ──────────────────────────────────────────────
        lines.append("in")
        lines.append(f"    {current_step}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # STEP EMITTERS  (each returns the new current_step name)
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
        """Emit the Source step and return the step name."""

        # ── RESIDENT LOAD ─────────────────────────────────────────────
        file_sources = [s for s in sources if s.get("type") == "FILE"]
        res_sources  = [s for s in sources if s.get("type") == "RESIDENT"]

        if is_resident and res_sources:
            ref_table = res_sources[0]["path"]
            safe_ref  = self._safe_step_name(ref_table)
            step      = f"Source_{table_name}"
            lines.append(
                f"    {step} = {safe_ref},"
                f"  // RESIDENT LOAD from {ref_table}"
            )
            return step

        # ── FILE SOURCE(S) ────────────────────────────────────────────
        if file_sources:
            # One source → simple naming; multiple → indexed
            if len(file_sources) == 1:
                src         = file_sources[0]
                mapped_path = file_paths.get(src["path"], src["path"])
                mapped_path = mapped_path.replace('\\"', '').replace('"', '')
                mapped_path = mapped_path.replace('\\\\', '\\')
                step_src    = f"Source_{table_name}"
                step_data   = f"Source_{table_name}_Data"
                step_hdr    = f"Source_{table_name}_Headers"
                lines.extend([
                    f'    {step_src} = Excel.Workbook(File.Contents("{mapped_path}"), null, true),',
                    f"    {step_data} = {step_src}{{0}}[Data],",
                    f"    {step_hdr} = Table.PromoteHeaders({step_data}, [PromoteAllScalars=true]),",
                ])
                return step_hdr

            else:
                # Multiple files — load each and combine
                source_headers = []
                for i, src in enumerate(file_sources, start=1):
                    mapped_path = file_paths.get(src["path"], src["path"])
                    mapped_path = mapped_path.replace('\\"', '').replace('"', '')
                    mapped_path = mapped_path.replace('\\\\', '\\')
                    s_src  = f"Source_{table_name}_{i}"
                    s_data = f"Source_{table_name}_{i}_Data"
                    s_hdr  = f"Source_{table_name}_{i}_Headers"
                    lines.extend([
                        f'    {s_src} = Excel.Workbook(File.Contents("{mapped_path}"), null, true),',
                        f"    {s_data} = {s_src}{{0}}[Data],",
                        f"    {s_hdr} = Table.PromoteHeaders({s_data}, [PromoteAllScalars=true]),",
                    ])
                    source_headers.append(s_hdr)

                combined = f"Combined_{table_name}"
                combine_expr = ", ".join(source_headers)
                lines.append(
                    f"    {combined} = Table.Combine({{{combine_expr}}}),"
                )
                return combined

        # ── FALLBACK: empty table shell ───────────────────────────────
        column_names = self._unique_column_names(columns)
        if not column_names:
            column_names = ["Column1"]

        col_defs = ", ".join(f"{n}=any" for n in column_names)
        step = f"Source_{table_name}"
        lines.append(
            f"    {step} = #table(type table [{col_defs}], {{}}),"
        )
        return step

    # ------------------------------------------------------------------

    def _emit_type_changes(
        self,
        lines: list,
        columns: list,
        current_step: str,
    ) -> str:
        """
        Emit a Table.TransformColumnTypes step when columns carry
        explicit type information.  Currently a no-op placeholder that
        returns current_step unchanged — extend here when the parser
        surfaces type metadata.
        """
        return current_step

    # ------------------------------------------------------------------

    def _emit_filters(
        self,
        lines: list,
        filters: list,
        current_step: str,
    ) -> str:
        """Emit one Table.SelectRows step per WHERE clause."""

        step = current_step
        for i, f in enumerate(filters, start=1):
            expr     = f.get("expression", "true")
            new_step = f"FilteredRows_{i}" if len(filters) > 1 else "FilteredRows"
            # Emit as a comment-annotated pass-through so the user can
            # fill in the real row condition.
            lines.append(
                f'    {new_step} = Table.SelectRows({step},'
                f' each true), // WHERE {expr}'
            )
            step = new_step

        return step

    # ------------------------------------------------------------------

    def _emit_select_columns(
        self,
        lines: list,
        column_names: list,
        current_step: str,
    ) -> str:
        cols = ", ".join(f'"{c}"' for c in column_names)
        step = "SelectedColumns"
        lines.append(
            f"    {step} = Table.SelectColumns({current_step}, {{{cols}}}),"
        )
        return step

    # ------------------------------------------------------------------

    def _emit_renames(
        self,
        lines: list,
        rename_fields: list,
        current_step: str,
    ) -> str:
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
            lines.append(
                f"    {step} = Table.RenameColumns({current_step}, {{{pair_text}}}),"
            )
            return step

        return current_step

    # ------------------------------------------------------------------

    def _emit_drops(
        self,
        lines: list,
        drop_fields: list,
        current_step: str,
    ) -> str:
        all_fields = []
        for df in drop_fields:
            all_fields.extend(df.get("fields", []))

        if all_fields:
            field_text = ", ".join(f'"{f}"' for f in all_fields)
            step = "DroppedColumns"
            lines.append(
                f"    {step} = Table.RemoveColumns({current_step}, {{{field_text}}}),"
            )
            return step

        return current_step

    # ------------------------------------------------------------------

    def _emit_group_by(
        self,
        lines: list,
        aggregations: list,
        current_step: str,
    ) -> str:
        all_groups = []
        for agg in aggregations:
            all_groups.extend(agg.get("group_by", []))

        if all_groups:
            group_text = ", ".join(f'"{g}"' for g in all_groups)
            step = "GroupedRows"
            lines.append(
                f"    {step} = Table.Group({current_step}, {{{group_text}}}, {{}}),"
            )
            return step

        return current_step

    # ------------------------------------------------------------------
    # UTILITIES
    # ------------------------------------------------------------------

    @staticmethod
    def _unique_column_names(columns: list) -> list:
        seen = set()
        result = []
        for col in columns:
            name = col.get("name", "").strip()
            if name and name not in seen:
                seen.add(name)
                result.append(name)
        return sorted(result)

    @staticmethod
    def _safe_step_name(name: str) -> str:
        """Convert a Qlik table name to a valid M identifier."""
        import re
        safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
        if safe and safe[0].isdigit():
            safe = "_" + safe
        return safe

    @staticmethod
    def _build_legacy_block(analysis: dict) -> list:
        """
        Build a single synthetic block from the old flat analysis
        structure so pre-refactor callers still get output.
        """
        metadata = analysis.get("metadata", {})
        return [
            {
                "table":         {"name": "Query", "line": 0},
                "columns":       metadata.get("columns", []),
                "sources":       [
                    {"path": s.get("path", ""), "type": "FILE"}
                    for s in analysis.get("source_files", [])
                ],
                "filters":       metadata.get("filters", []),
                "aggregations":  metadata.get("aggregations", []),
                "joins":         analysis.get("joins", []),
                "rename_fields": metadata.get("rename_fields", []),
                "drop_fields":   metadata.get("drop_fields", []),
                "is_resident":   False,
                "transformations": [
                    {"operation": op, "type": op}
                    for op in analysis.get("operations", [])
                ],
            }
        ]


# ---------------------------------------------------------------------------
# re is used inside _emit_renames — import at module level for safety
# ---------------------------------------------------------------------------
import re  # noqa: E402