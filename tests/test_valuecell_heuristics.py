from app.providers.valuecell_runner import has_meaningful_response, is_generation_in_progress


def test_detects_generation_in_progress_keywords():
    assert is_generation_in_progress("模型正在思考中，请稍候...")
    assert is_generation_in_progress("Generating response...")
    assert is_generation_in_progress("Typing...")


def test_detects_generation_complete_text():
    assert not is_generation_in_progress("Risk Rating: Yellow. Summary is ready.")


def test_has_meaningful_response_requires_substance():
    assert not has_meaningful_response("")
    assert not has_meaningful_response("ok")
    assert has_meaningful_response("Executive Summary: revenue trend stabilized and risks are manageable.")
