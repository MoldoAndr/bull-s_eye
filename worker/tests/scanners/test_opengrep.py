import json
from pathlib import Path

from scanners.opengrep import OpengrepScanner


def test_opengrep_parses_findings():
    scanner = OpengrepScanner(Path("."))
    sample = {
        "results": [
            {
                "check_id": "python.lang.security.audit.exec-used",
                "path": "app.py",
                "start": {"line": 10, "col": 5},
                "end": {"line": 10, "col": 15},
                "extra": {
                    "severity": "ERROR",
                    "message": "Avoid exec",
                    "lines": "exec(user_input)",
                    "metadata": {
                        "message": "Use of exec",
                        "confidence": "HIGH",
                        "category": "security",
                        "shortlink": "https://semgrep.dev/r/xyz",
                        "cwe": ["CWE-78"],
                    },
                },
            }
        ]
    }

    findings = scanner.parse_output(json.dumps(sample), "", 1)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "high"
    assert finding.category == "security"
    assert finding.file_path == "app.py"
    assert finding.rule_id == "python.lang.security.audit.exec-used"
    assert "cwe.mitre.org" in " ".join(finding.references)
