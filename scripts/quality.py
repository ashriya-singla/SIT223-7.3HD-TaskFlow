"""Measure maintainability and enforce explicit, versioned quality thresholds."""
import json
from pathlib import Path

from radon.complexity import cc_visit
from radon.metrics import mi_visit

result = {}
for path in Path('taskflow').glob('*.py'):
    source = path.read_text()
    blocks = cc_visit(source)
    maximum = max((block.complexity for block in blocks), default=0)
    maintainability = mi_visit(source, multi=True)
    result[str(path)] = {'maximum_complexity': maximum, 'maintainability_index': round(maintainability, 2)}
Path('reports/quality.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
if any(row['maximum_complexity'] > 15 or row['maintainability_index'] < 40 for row in result.values()):
    raise SystemExit('Quality gate failed: complexity <=15 and maintainability >=40 required')
