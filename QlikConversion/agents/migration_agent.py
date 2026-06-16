class MigrationAutomationAgent:
    def __init__(self, qlik_excel, m_metadata):
        self.extractor = EnhancedExtractionAgent(qlik_excel, m_metadata)
        self.schema = self.extractor.load_m_query_metadata()
        self.parser = ContextAwareSetAnalysisParser(self.schema)
        self.validator = DAXValidationAgent(self.schema)

    def execute_migration_pipeline(self, output_excel_path):
        raw_data = self.extractor.extract_qlik_expressions()
        conversion_results = []
        validation_results = []
        
        for idx, row in raw_data.iterrows():
            m_name = row['Measure Name']
            qlik_raw = row['Qlik Expression']
            
            # Translate
            converted_dax = self.parser.convert_to_dax(qlik_raw)
            # Validate
            val_log = self.validator.validate_measure(m_name, converted_dax)
            
            conversion_results.append({
                "Measure Name": m_name,
                "Qlik Expression": qlik_raw,
                "Generated DAX": converted_dax,
                "Status": val_log["status"]
            })
            
            if val_log["errors"]:
                validation_results.append({
                    "Measure Name": m_name,
                    "Errors": "; ".join(val_log["errors"])
                })

        # Save to a structured Multi-Tab Excel spreadsheet
        with pd.ExcelWriter(output_excel_path) as writer:
            pd.DataFrame(conversion_results).to_excel(writer, sheet_name="Conversion Report", index=False)
            if validation_results:
                pd.DataFrame(validation_results).to_excel(writer, sheet_name="Validation & Error Logs", index=False)