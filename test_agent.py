from QlikToPowerBIConverter.agents.migration_agent import MigrationAgent

script = """Customers:
LOAD CustomerID, CustomerName FROM Data;

Sales:
LOAD OrderID, Amount FROM Data WHERE Amount > 100;
"""

try:
    agent = MigrationAgent(base_dir='.')
    analysis = agent.analyze(script)
    print('Analysis successful!')
    print(f'Operations: {analysis.get("operations", [])}')
    tables = [t.get("name") for t in analysis.get("metadata", {}).get("tables", [])]
    print(f'Tables: {tables}')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
