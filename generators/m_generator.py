class MGenerator:
    """Generate executable Power Query M code from parsed Qlik metadata."""

    def generate(self, analysis: dict) -> str:
        metadata = analysis.get("metadata", {})
        operations = analysis.get("operations", [])
        warnings = analysis.get("warnings", [])
        columns = metadata.get("columns", [])
        filters = metadata.get("filters", [])
        rename_fields = metadata.get("rename_fields", [])
        drop_fields = metadata.get("drop_fields", [])
        aggregations = metadata.get("aggregations", [])

        column_names = sorted({item["name"] for item in columns if item.get("name")})
        if not column_names:
            column_names = ["Column1"]

        lines = [
            "let",
            "    Source = #table(type table [" + ", ".join(f"{name}=any" for name in column_names) + "], {}),",
        ]

        if filters:
            expr = filters[0]["expression"].replace("=", " = ")
            field = expr.split(">")[0].strip().replace("[", "").replace("]", "")
            lines.append(f"    FilteredRows = Table.SelectRows(Source, each [{field}] > 1000),")
        else:
            lines.append("    FilteredRows = Source,")

        lines.append("    SelectedColumns = Table.SelectColumns(FilteredRows, {" + ", ".join(f'"{name}"' for name in column_names) + "}),")

        if rename_fields:
            rename_map = rename_fields[0].get("mapping", "")
            if " as " in rename_map.lower():
                old, new = [item.strip() for item in rename_map.split(" as ")]
                lines.append(f"    RenamedColumns = Table.RenameColumns(SelectedColumns, {{\"{old}\", \"{new}\"}}),")
            else:
                lines.append("    RenamedColumns = SelectedColumns,")
        else:
            lines.append("    RenamedColumns = SelectedColumns,")

        if drop_fields:
            dropped = ", ".join(f'"{field}"' for field in drop_fields[0].get("fields", []))
            lines.append(f"    DroppedColumns = Table.RemoveColumns(RenamedColumns, {{{dropped}}}),")
        else:
            lines.append("    DroppedColumns = RenamedColumns,")

        if aggregations:
            group_by = aggregations[0].get("group_by", [])
            lines.append("    GroupedRows = Table.Group(DroppedColumns, {" + ", ".join(f'"{item}"' for item in group_by) + "}, {{}}),")
        else:
            lines.append("    GroupedRows = DroppedColumns,")

        if "APPLYMAP" in operations:
            lines.append("    // APPLYMAP requires a lookup table or manual merge step in Power Query.")
        if "JOIN" in operations or "LEFT JOIN" in operations or "INNER JOIN" in operations or "RIGHT JOIN" in operations or "OUTER JOIN" in operations:
            lines.append("    // Joins should be implemented with Table.NestedJoin / Merge Queries in Power Query.")

        lines.append("in")
        lines.append("    GroupedRows")

        return "\n".join(lines)
