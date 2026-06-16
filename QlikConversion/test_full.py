from QlikToPowerBIConverter.agents.migration_agent import MigrationAgent
from QlikToPowerBIConverter.generators.m_generator import MGenerator

# Read sample.qvs
with open('sample.qvs', 'r') as f:
    script = f.read()

try:
    agent = MigrationAgent(base_dir='.')
    generator = MGenerator()
    
    analysis = agent.analyze(script)
    m_code = generator.generate(analysis)
    
    print("✅ Full pipeline successful!")
    print(f"\nTables: {[t.get('name') for t in analysis['metadata'].get('tables', [])]}")
    print(f"Operations: {analysis.get('operations', [])}")
    print(f"\nGenerated M Code:\n{m_code}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
