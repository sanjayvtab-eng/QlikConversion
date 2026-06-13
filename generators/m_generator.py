class MGenerator:
    """Generate executable Power Query M code from parsed Qlik metadata."""

    def generate(self, analysis: dict) -> str:

        metadata = analysis.get("metadata", {})
        file_paths = analysis.get("file_paths", {})

        columns = metadata.get("columns", [])
        filters = metadata.get("filters", [])
        rename_fields = metadata.get("rename_fields", [])
        drop_fields = metadata.get("drop_fields", [])
        aggregations = metadata.get("aggregations", [])

        source_files = analysis.get("source_files", [])

        lines = ["let"]

        # ============================================
        # SOURCE FILES
        # ============================================

        if source_files:

            source_step_names = []

            for idx, source in enumerate(source_files, start=1):

                original_path = source.get("path", "")

                mapped_path = file_paths.get(
                    original_path,
                    original_path
                )

                mapped_path = mapped_path.replace("\\", "\\\\")

                source_name = f"Source{idx}"

                source_step_names.append(source_name)

                lines.extend([
                    f'    {source_name} = Excel.Workbook(File.Contents("{mapped_path}"), null, true),',
                    f'    {source_name}_Data = {source_name}{{0}}[Data],',
                    f'    {source_name}_Headers = Table.PromoteHeaders({source_name}_Data, [PromoteAllScalars=true]),'
                ])

            current_step = f"{source_step_names[0]}_Headers"

        else:

            column_names = sorted(
                {
                    item["name"]
                    for item in columns
                    if item.get("name")
                }
            )

            if not column_names:
                column_names = ["Column1"]

            lines.append(
                "    Source = #table(type table ["
                + ", ".join(
                    f"{name}=any"
                    for name in column_names
                )
                + "], {}),"
            )

            current_step = "Source"

        # ============================================
        # FILTERS
        # ============================================

        if filters:

            lines.append(
                f"    FilteredRows = {current_step},"
            )

            current_step = "FilteredRows"

        # ============================================
        # SELECT COLUMNS
        # ============================================

        column_names = sorted(
            {
                item["name"]
                for item in columns
                if item.get("name")
            }
        )

        if column_names:

            cols = ", ".join(
                f'"{c}"'
                for c in column_names
            )

            lines.append(
                f"    SelectedColumns = Table.SelectColumns({current_step}, {{{cols}}}),"
            )

            current_step = "SelectedColumns"

        # ============================================
        # RENAME COLUMNS
        # ============================================

        if rename_fields:

            rename_map = rename_fields[0].get(
                "mapping",
                ""
            )

            if " as " in rename_map.lower():

                parts = rename_map.split(" as ")

                if len(parts) == 2:

                    old = parts[0].strip()
                    new = parts[1].strip()

                    lines.append(
                        f'    RenamedColumns = Table.RenameColumns({current_step}, {{{{"{old}", "{new}"}}}}),'
                    )

                    current_step = "RenamedColumns"

        # ============================================
        # DROP COLUMNS
        # ============================================

        if drop_fields:

            fields = drop_fields[0].get(
                "fields",
                []
            )

            if fields:

                field_text = ", ".join(
                    f'"{field}"'
                    for field in fields
                )

                lines.append(
                    f"    DroppedColumns = Table.RemoveColumns({current_step}, {{{field_text}}}),"
                )

                current_step = "DroppedColumns"

        # ============================================
        # GROUP BY
        # ============================================

        if aggregations:

            group_by = aggregations[0].get(
                "group_by",
                []
            )

            if group_by:

                group_text = ", ".join(
                    f'"{item}"'
                    for item in group_by
                )

                lines.append(
                    f"    GroupedRows = Table.Group({current_step}, {{{group_text}}}, {{}}),"
                )

                current_step = "GroupedRows"

        # ============================================
        # JOIN COMMENTS
        # ============================================

        joins = analysis.get("joins", [])

        if joins:

            lines.append(
                "    // JOIN detected - implement using Table.NestedJoin"
            )

        operations = analysis.get(
            "operations",
            []
        )

        if "APPLYMAP" in operations:

            lines.append(
                "    // APPLYMAP detected - implement using Merge Queries"
            )

        # ============================================
        # FINAL OUTPUT
        # ============================================

        lines.append("in")
        lines.append(f"    {current_step}")

        return "\n".join(lines)