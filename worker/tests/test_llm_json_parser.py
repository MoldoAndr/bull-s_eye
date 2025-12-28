from llm.ollama_client import parse_llm_json_response


def test_parse_llm_json_response_handles_bold_keys():
    response = """
{
  **"purpose**": "fine-tune model",
  "summary": "Trains a model.",
  "complexity": "medium",
  "is_entrypoint": true,
  "is_test_file": false,
  "security_issues": [],
  "quality_issues": [],
  "positive_aspects": [],
  "dependencies_analysis": ""
}
"""
    parsed, method = parse_llm_json_response(response)
    assert parsed is not None
    assert parsed["purpose"] == "fine-tune model"
    assert method in {"direct", "sanitized"}


def test_parse_llm_json_response_handles_trailing_commas_and_fences():
    response = """Here you go:
```json
{
  "summary": "Valid JSON after cleanup.",
  "purpose": "Test",
  "complexity": "low",
  "is_entrypoint": false,
  "is_test_file": false,
  "security_issues": [],
  "quality_issues": [],
  "positive_aspects": [],
  "dependencies_analysis": "",
}
```
"""
    parsed, method = parse_llm_json_response(response)
    assert parsed is not None
    assert parsed["summary"] == "Valid JSON after cleanup."
    assert method == "sanitized"


def test_parse_llm_json_response_handles_inline_json():
    response = 'prefix {"summary":"ok","purpose":"x","complexity":"low","is_entrypoint":false,"is_test_file":false,"security_issues":[],"quality_issues":[],"positive_aspects":[],"dependencies_analysis":""} suffix'
    parsed, method = parse_llm_json_response(response)
    assert parsed is not None
    assert parsed["summary"] == "ok"
    assert method in {"direct", "sanitized"}
