from app.utils.json_utils import parse_json_payload


def test_parse_json_payload_plain_json():
    parsed = parse_json_payload('{"approved": true, "missing_items": []}')
    assert parsed["approved"] is True


def test_parse_json_payload_fenced_block():
    text = """```json
    {"risk_rating":"yellow","highlights":["a","b"]}
    ```"""
    parsed = parse_json_payload(text)
    assert parsed["risk_rating"] == "yellow"


def test_parse_json_payload_extracts_embedded_object():
    text = "Model output: {\"target\":\"valuecell_web\",\"timeout_seconds\":900} End."
    parsed = parse_json_payload(text)
    assert parsed["target"] == "valuecell_web"
