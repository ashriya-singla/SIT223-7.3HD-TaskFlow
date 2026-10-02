"""Measure maintainability and enforce explicit, versioned quality thresholds."""
import json
from pathlib import Path

from radon.complexity import cc_visit
from radon.metrics import mi_visit

result = {}
for path in Path('taskflow').glob('*.py'):
    source = path.read_text()
    blocks = cc_visit(source)
    all_blocks = []
    def collect(block):
        all_blocks.append(block)
        for child in getattr(block, "closures", []):
            collect(child)
    for block in blocks:
        collect(block)
    maximum = max((block.complexity for block in all_blocks), default=0)
    maintainability = mi_visit(source, multi=True)
    result[str(path)] = {'maximum_complexity': maximum, 'maintainability_index': round(maintainability, 2)}
Path('reports/quality.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
if any(row['maximum_complexity'] > 15 or row['maintainability_index'] < 40 for row in result.values()):
    raise SystemExit('Quality gate failed: complexity <=15 and maintainability >=40 required')

import os
from datetime import UTC, datetime
if os.environ.get("TASKFLOW_RUNTIME"):
    history = Path(os.environ["TASKFLOW_RUNTIME"]) / "quality-history.jsonl"
    with history.open("a") as stream:
        stream.write(json.dumps({"at": datetime.now(UTC).isoformat(), "build": os.environ.get("BUILD_NUMBER"), "metrics": result}) + "\n")
    Path("reports/quality-history.json").write_text(json.dumps([json.loads(line) for line in history.read_text().splitlines()], indent=2))
