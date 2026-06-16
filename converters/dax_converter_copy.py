# converters/dax_converter.py

from parser.set_analysis_parser import SetAnalysisParser


class DaxConverter:

    def __init__(self):
        self.parser = SetAnalysisParser()

    def convert(self, expression):

        parsed = self.parser.parse(expression)

        agg = parsed.get("aggregation")
        measure = parsed.get("measure")

        if not agg:
            return f"-- Unable to detect aggregation: {expression}"

        if not measure:
            return f"-- Unable to detect measure: {expression}"

        agg_map = {
            "Sum": "SUM",
            "Count": "COUNT",
            "Avg": "AVERAGE",
            "Min": "MIN",
            "Max": "MAX"
        }

        dax = "CALCULATE(\n"

        dax += (
            f"    {agg_map.get(agg, agg.upper())}"
            f"(Sales[{measure}])"
        )

        for field, value in parsed["filters"]:

            value = value.replace("'", "")
            value = value.replace('"', "")

            dax += (
                f",\n    Sales[{field}] = "
                f"\"{value}\""
            )

        dax += "\n)"

        return dax