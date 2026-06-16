# parser/set_analysis_parser.py

import re


class SetAnalysisParser:

    def parse(self, expression):

        result = {
            "aggregation": None,
            "measure": None,
            "filters": []
        }

        # Aggregation
        agg = re.search(
            r"(Sum|Count|Avg|Min|Max)",
            expression,
            re.IGNORECASE
        )

        if agg:
            result["aggregation"] = agg.group(1)

        # Measure
        measure = re.search(
            r"\}\s*([A-Za-z_][A-Za-z0-9_]*)\)",
            expression
        )

        if measure:
            result["measure"] = measure.group(1)

        # Filters
        filters = re.findall(
            r"(\w+)=\{([^}]*)\}",
            expression
        )

        result["filters"] = filters

        return result