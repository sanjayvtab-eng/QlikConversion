# converters/dax_converter.py

import json
import os

from parser.set_analysis_parser import SetAnalysisParser


class DaxConverter:

    def __init__(self):

        self.parser = SetAnalysisParser()

        mapping_path = os.path.join(
            "metadata",
            "table_mapping.json"
        )

        if os.path.exists(mapping_path):
            with open(mapping_path, "r", encoding="utf-8") as f:
                self.table_mapping = json.load(f)
        else:
            self.table_mapping = {}

    def get_table(self, field, default_table):
        return self.table_mapping.get(field, default_table)

    def _build_filter_clause(self, f, measure_table):
        """Convert a single parsed filter dict into a DAX filter string."""

        field     = f["field"]
        value     = str(f["value"])
        operator  = f["operator"]
        table_name = self.get_table(field, measure_table)

        # Multi-value  e.g.  North,South
        if "," in value:
            values = [v.strip() for v in value.split(",")]
            in_list = ",".join(f'"{v}"' for v in values)
            return f"{table_name}[{field}] IN {{{in_list}}}"

        # Comparison operators  > < >= <= <>
        if operator in (">", "<", ">=", "<=", "<>"):
            # Numeric value → no quotes
            try:
                float(value)
                return f"{table_name}[{field}] {operator} {value}"
            except ValueError:
                return f'{table_name}[{field}] {operator} "{value}"'

        # Equals — plain string, no single quotes
        return f'{table_name}[{field}] = "{value}"'

    def convert(self, expression, measure_table="FactSales"):

        parsed  = self.parser.parse(expression)
        agg     = parsed.get("aggregation")
        measure = parsed.get("measure")
        pattern = parsed.get("pattern")

        if not agg:
            return f"-- Unable to detect aggregation: {expression}"

        if not measure:
            return f"-- Unable to detect measure: {expression}"

        agg_map = {
            "Sum":   "SUM",
            "Count": "COUNT",
            "Avg":   "AVERAGE",
            "Min":   "MIN",
            "Max":   "MAX",
        }

        dax_agg = agg_map.get(agg, agg.upper())

        filters = parsed.get("filters", [])

        # -----------------------------------
        # DISTINCTCOUNT  (with or without filters)
        # -----------------------------------

        if parsed.get("distinct"):
            if not filters:
                return f"DISTINCTCOUNT({measure_table}[{measure}])"

            dax = (
                "CALCULATE(\n"
                f"    DISTINCTCOUNT({measure_table}[{measure}])"
            )
            for f in filters:
                dax += ",\n    " + self._build_filter_clause(f, measure_table)
            dax += "\n)"
            return dax

        # -----------------------------------
        # TOTAL
        # -----------------------------------

        if pattern == "TOTAL":
            return (
                "CALCULATE(\n"
                f"    {dax_agg}({measure_table}[{measure}]),\n"
                f"    ALL({measure_table})\n"
                ")"
            )

        # -----------------------------------
        # TOTAL FIELD
        # -----------------------------------

        if pattern == "TOTAL_FIELD":
            field = parsed.get("total_field")
            return (
                "CALCULATE(\n"
                f"    {dax_agg}({measure_table}[{measure}]),\n"
                "    ALLEXCEPT(\n"
                f"        {measure_table},\n"
                f"        {measure_table}[{field}]\n"
                "    )\n"
                ")"
            )

        # -----------------------------------
        # AGGR
        # -----------------------------------

        if parsed.get("aggr"):
            dim = parsed.get("aggr_dimension")
            return (
                "AVERAGEX(\n"
                f"    VALUES({measure_table}[{dim}]),\n"
                "    CALCULATE(\n"
                f"        SUM({measure_table}[{measure}])\n"
                "    )\n"
                ")"
            )

        # -----------------------------------
        # P()
        # -----------------------------------

        if parsed.get("p_function"):
            return (
                "CALCULATE(\n"
                f"    {dax_agg}({measure_table}[{measure}]),\n"
                f"    VALUES({measure_table}[Customer])\n"
                ")"
            )

        # -----------------------------------
        # E()
        # -----------------------------------

        if parsed.get("e_function"):
            return (
                "VAR Excluded =\n"
                "EXCEPT(\n"
                f"    ALL({measure_table}[Customer]),\n"
                f"    VALUES({measure_table}[Customer])\n"
                ")\n"
                "RETURN\n"
                "CALCULATE(\n"
                f"    {dax_agg}({measure_table}[{measure}]),\n"
                "    Excluded\n"
                ")"
            )

        # -----------------------------------
        # Ignore Selection {1}
        # -----------------------------------

        if parsed.get("ignore_selection"):
            return (
                "CALCULATE(\n"
                f"    {dax_agg}({measure_table}[{measure}]),\n"
                f"    ALL({measure_table})\n"
                ")"
            )

        # -----------------------------------
        # Standard CALCULATE
        # -----------------------------------

        if not filters:
            # No filters — simple aggregation, no CALCULATE wrapper needed
            return f"{dax_agg}({measure_table}[{measure}])"

        dax = (
            "CALCULATE(\n"
            f"    {dax_agg}({measure_table}[{measure}])"
        )

        for f in filters:
            dax += ",\n    " + self._build_filter_clause(f, measure_table)

        dax += "\n)"

        return dax