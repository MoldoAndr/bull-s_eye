import json
from pathlib import Path

from scanners.osv_scanner import OSVScanner


def test_osv_scanner_parses_vulnerabilities():
    scanner = OSVScanner(Path("."))
    sample = {
        "results": [
            {
                "source": {"path": "package-lock.json", "type": "npm"},
                "packages": [
                    {
                        "package": {"name": "lodash", "ecosystem": "npm"},
                        "version": "4.17.20",
                        "vulnerabilities": [
                            {
                                "id": "GHSA-xxxx-xxxx-xxxx",
                                "summary": "Prototype pollution",
                                "details": "Details about the issue.",
                                "aliases": ["CVE-2020-8203"],
                                "severity": [{"type": "CVSS_V3", "score": "9.8"}],
                                "affected": [
                                    {
                                        "ranges": [
                                            {
                                                "type": "SEMVER",
                                                "events": [
                                                    {"introduced": "0"},
                                                    {"fixed": "4.17.21"},
                                                ],
                                            }
                                        ]
                                    }
                                ],
                                "references": [{"type": "ADVISORY", "url": "https://osv.dev/xyz"}],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    findings = scanner.parse_output(json.dumps(sample), "", 1)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "critical"
    assert finding.file_path == "package-lock.json"
    assert finding.rule_id == "GHSA-xxxx-xxxx-xxxx"
    assert "Affected versions" in finding.description
