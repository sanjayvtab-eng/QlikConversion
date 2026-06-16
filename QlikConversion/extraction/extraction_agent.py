import pandas as pd
import json

class EnhancedExtractionAgent:
    def __init__(self, excel_path, m_metadata_path=None):
        self.excel_path = excel_path
        self.m_metadata_path = m_metadata_path
        self.schema_context = {}

    def extract_qlik_expressions(self) -> pd.DataFrame:
        """Reads Excel file containing raw Qlik expressions and mapping metadata."""
        # Expects columns like: [Measure Name], [Qlik Expression], [Description]
        df = pd.read_excel(self.excel_path)
        return df

    def load_m_query_metadata(self):
        """Consumes the JSON/Tabular metadata exported by your M Query Generator."""
        if not self.m_metadata_path:
            return None
        
        with open(self.m_metadata_path, 'r') as f:
            # Contains tables, columns, data types, and relationships
            self.schema_context = json.load(f)
        return self.schema_context