from pathlib import Path

from scanners.lizard import LizardScanner
from config import settings


def test_lizard_scanner_flags_complex_functions():
    scanner = LizardScanner(Path("/repo"))
    settings.complexity_threshold = 10

    sample = """<?xml version="1.0" ?>
<cppncss>
  <measure type="Function">
    <labels>
      <label>Nr.</label>
      <label>NCSS</label>
      <label>CCN</label>
    </labels>
    <item name="simple(...) at /repo/src/app.py:1">
      <value>1</value>
      <value>4</value>
      <value>5</value>
    </item>
    <item name="complex(...) at /repo/src/app.py:10">
      <value>2</value>
      <value>30</value>
      <value>12</value>
    </item>
  </measure>
</cppncss>
"""

    findings = scanner.parse_output(sample, "", 0)

    assert len(findings) == 1
    finding = findings[0]
    assert "complex" in finding.title
    assert finding.file_path == "src/app.py"
    assert finding.severity in {"low", "medium", "high", "critical"}
