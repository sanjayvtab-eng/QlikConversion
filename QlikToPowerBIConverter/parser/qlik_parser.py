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

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def extract_metadata(self, script: str) -> Dict[str, object]:
        """
        Parse the full Qlik script and return metadata grouped
        per table block.  Each entry in ``table_blocks`` represents
        one logical table (TableName: … FROM … ;) with its own
        columns, source path, filters, aggregations, joins, renames,
        drops, and transformations.

        Global lists (variables, warnings …) are still returned at the
        top level for backward-compatibility.
        """

        raw_lines = script.splitlines()

        # ── Pass 1: split the script into per-table segments ──────────
        table_blocks = self._split_into_table_blocks(raw_lines)

        # ── Pass 2: parse each block independently ────────────────────
        parsed_blocks = [
            self._parse_block(block)
            for block in table_blocks
        ]

        # ── Pass 3: global items (variables / DROP FIELD / RENAME FIELD)
        #           that live outside any table block
        global_meta = self._parse_global(raw_lines, table_blocks)

        # Flatten for callers that still expect top-level lists
        all_columns        = []
        all_sources        = []
        all_joins          = []
        all_filters        = []
        all_aggregations   = []
        all_transformations = []
        all_rename_fields  = []
        all_drop_fields    = []

        for b in parsed_blocks:
            all_columns.extend(b["columns"])
            all_sources.extend(b["sources"])
            all_joins.extend(b["joins"])
            all_filters.extend(b["filters"])
            all_aggregations.extend(b["aggregations"])
            all_transformations.extend(b["transformations"])
            all_rename_fields.extend(b["rename_fields"])
            all_drop_fields.extend(b["drop_fields"])

        return {
            # ── per-table (new – used by MGenerator) ──────────────────
            "table_blocks":     parsed_blocks,

            # ── flat / global (backward-compat) ───────────────────────
            "tables":           [b["table"] for b in parsed_blocks],
            "sources":          all_sources,
            "columns":          all_columns,
            "joins":            all_joins,
            "filters":          all_filters,
            "aggregations":     all_aggregations,
            "transformations":  all_transformations,
            "variables":        global_meta["variables"],
            "store_statements": global_meta["store_statements"],
            "rename_fields":    all_rename_fields,
            "drop_fields":      all_drop_fields,
            "derived_columns":  [],
            "warnings":         [],
        }

    def extract_operations(self, script: str) -> dict:
        metadata = self.extract_metadata(script)
        operations = []
        for item in metadata["transformations"]:
            if item["type"] not in operations:
                operations.append(item["type"])
        return {
            "operations": operations,
            "metadata":   metadata,
            "warnings":   metadata["warnings"],
        }

    def extract_lines(self, script: str) -> List[str]:
        return [
            line.strip()
            for line in script.splitlines()
            if line.strip()
        ]

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    def _split_into_table_blocks(
        self,
        raw_lines: List[str]
    ) -> List[Dict]:
        """
        Identify logical table blocks.

        A block starts at a line that matches ``TableName:``
        (optionally followed by a LOAD on the same line) and ends at
        the first ``;`` that terminates a LOAD / RESIDENT statement,
        or at the next table label, whichever comes first.

        Returns a list of dicts:
            {
                "name":       str,          # table label
                "start_line": int,          # 0-based index into raw_lines
                "lines":      List[str],    # raw lines for this block
            }
        """

        TABLE_LABEL = re.compile(
            r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*$"
        )
        # A label that is part of the same line as LOAD:
        # e.g.  "SalesData: LOAD ..."
        INLINE_LABEL = re.compile(
            r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*(.+)$",
            re.I
        )

        blocks: List[Dict] = []
        current_name:  str        = None
        current_start: int        = None
        current_lines: List[str]  = []
        in_block:      bool       = False

        def flush():
            if current_name and current_lines:
                blocks.append(
                    {
                        "name":       current_name,
                        "start_line": current_start,
                        "lines":      list(current_lines),
                    }
                )

        for idx, raw in enumerate(raw_lines):
            stripped = raw.strip()

            if not stripped or stripped.startswith("//"):
                if in_block:
                    current_lines.append(stripped)
                continue

            # ── standalone label line: ``TableName:`` ─────────────────
            m_label = TABLE_LABEL.match(stripped)
            if m_label:
                flush()
                current_name  = m_label.group(1)
                current_start = idx
                current_lines = [stripped]
                in_block      = True
                continue

            # ── inline label + LOAD on same line ──────────────────────
            m_inline = INLINE_LABEL.match(stripped)
            if m_inline and re.search(r"\bLOAD\b|\bRESIDENT\b", m_inline.group(2), re.I):
                flush()
                current_name  = m_inline.group(1)
                current_start = idx
                current_lines = [stripped]
                in_block      = True
                # check for semicolon terminator on same line
                if stripped.endswith(";"):
                    flush()
                    current_name  = None
                    current_lines = []
                    in_block      = False
                continue

            if in_block:
                current_lines.append(stripped)
                if stripped.endswith(";"):
                    # End of this statement — close block
                    flush()
                    current_name  = None
                    current_lines = []
                    in_block      = False
            # lines before any table label (variables, etc.) are handled
            # by _parse_global

        # flush last open block
        flush()

        # ── If no explicit labels were found, treat whole script as one
        #    anonymous block so the rest of the pipeline still works ───
        if not blocks:
            blocks.append(
                {
                    "name":       "Query",
                    "start_line": 0,
                    "lines":      [l.strip() for l in raw_lines if l.strip()],
                }
            )

        return blocks

    # ------------------------------------------------------------------

    def _parse_block(self, block: Dict) -> Dict:
        """
        Parse a single table block and return its structured metadata.
        """

        name   = block["name"]
        lines  = block["lines"]

        columns        = []
        sources        = []
        joins          = []
        filters        = []
        aggregations   = []
        transformations = []
        rename_fields  = []
        drop_fields    = []
        is_resident    = False

        # Join the block back into one string so multi-line LOAD works
        full_text = " ".join(lines)

        # ── RESIDENT ──────────────────────────────────────────────────
        if re.search(r"\bRESIDENT\b", full_text, re.I):
            is_resident = True
            res_match = re.search(
                r"\bRESIDENT\s+([A-Za-z_][A-Za-z0-9_\-]*)",
                full_text, re.I
            )
            if res_match:
                sources.append(
                    {
                        "path":     res_match.group(1),
                        "type":     "RESIDENT",
                        "line":     block["start_line"],
                    }
                )

        # ── LOAD columns ──────────────────────────────────────────────
        load_match = re.search(
            r"\bLOAD\b\s+(.*?)(?:\bFROM\b|\bRESIDENT\b|\bWHERE\b|\bGROUP\s+BY\b|;|$)",
            full_text,
            re.I | re.S,
        )
        if load_match:
            raw_cols = load_match.group(1)
            parsed_columns = self._parse_column_list(raw_cols)
            for c in parsed_columns:
                if c:
                    columns.append(
                        {
                            "name":   c,
                            "source": "LOAD",
                            "line":   block["start_line"],
                        }
                    )
            transformations.append(
                {
                    "type":    "LOAD",
                    "line":    block["start_line"],
                    "columns": parsed_columns,
                }
            )

        # ── FROM ──────────────────────────────────────────────────────
        if not is_resident:
            from_match = re.search(
                r"\bFROM\b\s+\[?([^\];,]+?)(?:\]|\s*(?:WHERE|GROUP\s+BY|;|$))",
                full_text,
                re.I,
            )
            if from_match:
                src = (
                    from_match.group(1)
                    .strip()
                    .strip("'\"[]")
                )

                # Capture the connector spec, e.g.
                #   (ooxml, embedded labels, table is Customers)
                # so the generator can target the correct Excel sheet
                # instead of always using the first sheet ({0}).
                sheet_name = None
                conn_match = re.search(
                    r"\(\s*(?:ooxml|excel)[^)]*?\btable\s+is\s+"
                    r"([A-Za-z_][A-Za-z0-9_ ]*)",
                    full_text,
                    re.I,
                )
                if conn_match:
                    sheet_name = conn_match.group(1).strip()

                source_entry = {
                    "path": src,
                    "type": "FILE",
                    "line": block["start_line"],
                }
                if sheet_name:
                    source_entry["sheet"] = sheet_name

                sources.append(source_entry)

        # ── WHERE ─────────────────────────────────────────────────────
        where_match = re.search(
            r"\bWHERE\b\s+(.*?)(?:\bGROUP\s+BY\b|;|$)",
            full_text,
            re.I | re.S,
        )
        if where_match:
            expr = where_match.group(1).strip().rstrip(";").strip()
            filters.append(
                {
                    "expression": expr,
                    "line":       block["start_line"],
                }
            )
            transformations.append(
                {
                    "type":       "WHERE",
                    "line":       block["start_line"],
                    "expression": expr,
                }
            )

        # ── GROUP BY ──────────────────────────────────────────────────
        group_match = re.search(
            r"\bGROUP\s+BY\b\s+(.*?)(?:;|$)",
            full_text,
            re.I | re.S,
        )
        if group_match:
            groups = [
                g.strip()
                for g in group_match.group(1).split(",")
                if g.strip()
            ]

            # Extract aggregation function specs from the LOAD column
            # list, e.g. "Sum(SalesAmount) AS TotalSales" ->
            # {"function": "Sum", "field": "SalesAmount", "alias": "TotalSales"}
            agg_specs = []
            if load_match:
                for part in self._parse_column_list_raw_parts(load_match.group(1)):
                    agg_match = re.match(
                        r"^\s*(Sum|Count|Avg|Min|Max)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)"
                        r"\s*(?:AS\s+([A-Za-z_][A-Za-z0-9_]*))?\s*$",
                        part,
                        re.I,
                    )
                    if agg_match:
                        func  = agg_match.group(1).capitalize()
                        field = agg_match.group(2)
                        alias = agg_match.group(3) or f"{func}_{field}"
                        agg_specs.append(
                            {"function": func, "field": field, "alias": alias}
                        )

            aggregations.append(
                {
                    "group_by": groups,
                    "aggregations": agg_specs,
                    "line":     block["start_line"],
                }
            )
            transformations.append(
                {
                    "type":     "GROUP BY",
                    "line":     block["start_line"],
                    "group_by": groups,
                    "aggregations": agg_specs,
                }
            )

        # ── JOINs ─────────────────────────────────────────────────────
        for line_text in lines:
            join_match = re.search(
                r"\b(LEFT|INNER|RIGHT|OUTER)\s+JOIN\b|\bJOIN\b",
                line_text,
                re.I,
            )
            if join_match:
                jtype = (join_match.group(1) or "JOIN").upper()
                jlabel = "JOIN" if jtype == "JOIN" else f"{jtype} JOIN"
                joins.append(
                    {
                        "type":      jlabel,
                        "line":      block["start_line"],
                        "statement": line_text.strip(),
                    }
                )
                transformations.append(
                    {
                        "type":   jlabel,
                        "line":   block["start_line"],
                        "detail": line_text.strip(),
                    }
                )

        # ── APPLYMAP ──────────────────────────────────────────────────
        if re.search(r"\bAPPLYMAP\b", full_text, re.I):
            transformations.append(
                {
                    "type": "APPLYMAP",
                    "line": block["start_line"],
                    "detail": full_text,
                }
            )

        # ── RENAME FIELD ──────────────────────────────────────────────
        for line_text in lines:
            if re.search(r"\bRENAME\s+FIELD\b", line_text, re.I):
                rm = re.search(
                    r"RENAME\s+FIELD\s+(.*?)(?=;|$)",
                    line_text, re.I
                )
                if rm:
                    rename_fields.append(
                        {
                            "mapping": rm.group(1).strip(),
                            "line":    block["start_line"],
                        }
                    )

        # ── DROP FIELD ────────────────────────────────────────────────
        for line_text in lines:
            if re.search(r"\bDROP\s+FIELD\b", line_text, re.I):
                dm = re.search(
                    r"DROP\s+FIELD\s+(.*?)(?=;|$)",
                    line_text, re.I
                )
                if dm:
                    fields = [
                        f.strip()
                        for f in dm.group(1).split(",")
                        if f.strip()
                    ]
                    drop_fields.append(
                        {
                            "fields": fields,
                            "line":   block["start_line"],
                        }
                    )

        return {
            "table":         {"name": name, "line": block["start_line"]},
            "columns":       columns,
            "sources":       sources,
            "joins":         joins,
            "filters":       filters,
            "aggregations":  aggregations,
            "transformations": transformations,
            "rename_fields": rename_fields,
            "drop_fields":   drop_fields,
            "is_resident":   is_resident,
        }

    # ------------------------------------------------------------------

    def _parse_global(
        self,
        raw_lines: List[str],
        blocks: List[Dict]
    ) -> Dict:
        """Parse global-scope items: LET/SET variables, STORE statements."""

        # Build a set of line indices that belong to a block so we can
        # skip them here.
        block_line_sets = set()
        for b in blocks:
            start = b["start_line"]
            end   = start + len(b["lines"])
            for i in range(start, end):
                block_line_sets.add(i)

        variables        = []
        store_statements = []

        for idx, raw in enumerate(raw_lines):
            if idx in block_line_sets:
                continue
            stripped = raw.strip()
            if not stripped or stripped.startswith("//"):
                continue

            # Variables
            var_m = re.search(
                r"\b(LET|SET)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)",
                stripped, re.I
            )
            if var_m:
                variables.append(
                    {
                        "type":       var_m.group(1).upper(),
                        "name":       var_m.group(2),
                        "expression": var_m.group(3).strip(),
                        "line":       idx + 1,
                    }
                )

            # STORE
            if re.search(r"\bSTORE\b", stripped, re.I):
                store_statements.append(
                    {
                        "statement": stripped,
                        "line":      idx + 1,
                    }
                )

        return {
            "variables":        variables,
            "store_statements": store_statements,
        }

    # ------------------------------------------------------------------

    @staticmethod
    def _parse_column_list_raw_parts(raw: str) -> List[str]:
        """
        Split a raw LOAD column list on top-level commas (ignoring
        commas inside parentheses) WITHOUT extracting aliases —
        returns the raw expression text for each column, e.g.
            ["CustomerID", "Sum(SalesAmount) AS TotalSales", ...]
        """
        parts = []
        depth = 0
        current = []
        for ch in raw:
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            parts.append("".join(current).strip())
        return [p.rstrip(";").strip() for p in parts if p.strip()]

    @staticmethod
    def _parse_column_list(raw: str) -> List[str]:
        """
        Turn a raw column string like:
            ``LoanID, Num(Amount,'#,##0.00') AS PrincipalAmount, Date(...) AS DisbDate``
        into a list of output column names (the AS alias when present,
        otherwise the expression itself, stripped of Qlik functions).
        """

        # Split on top-level commas (ignoring commas inside parentheses)
        parts = []
        depth = 0
        current = []
        for ch in raw:
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            parts.append("".join(current).strip())

        result = []
        for part in parts:
            part = part.strip().rstrip(";").strip()
            if not part:
                continue

            # Extract AS alias
            as_match = re.search(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", part, re.I)
            if as_match:
                result.append(as_match.group(1))
            else:
                # Strip [] and Qlik function wrappers, keep simple names
                simple = re.sub(r"[\[\]'\"()]", "", part).strip()
                # If it still looks like an identifier, keep it
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", simple):
                    result.append(simple)
                else:
                    # Fall back: take last word
                    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", part)
                    if words:
                        result.append(words[-1])

        return result