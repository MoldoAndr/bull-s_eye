import json
from pathlib import Path

from scanners.js_scanners import BiomeScanner


def test_biome_scanner_parses_diagnostics():
    scanner = BiomeScanner(Path("."))
    sample = {
        "diagnostics": [
            {
                "category": "lint/suspicious/noExplicitAny",
                "message": "Unexpected any. Specify a different type.",
                "severity": "error",
                "location": {
                    "path": "src/index.ts",
                    "span": {
                        "start": {"line": 3, "column": 5},
                        "end": {"line": 3, "column": 8},
                    },
                },
            }
        ]
    }

    findings = scanner.parse_output(json.dumps(sample), "", 1)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "high"
    assert finding.category == "reliability"
    assert finding.file_path == "src/index.ts"
