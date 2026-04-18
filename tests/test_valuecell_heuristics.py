from app.providers.valuecell_runner import (
    has_meaningful_response,
    is_final_response_candidate,
    is_generation_in_progress,
    is_intermediate_progress,
)


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


def test_intermediate_progress_text_is_not_treated_as_final():
    text = "ValueCell 正在执行任务 收起 理解问题意图 构建分析策略 审视当前上下文"
    assert is_intermediate_progress(text)
    assert not has_meaningful_response(text)
    assert not is_final_response_candidate(text)


def test_final_candidate_requires_completion_signals_or_richer_content():
    assert is_final_response_candidate("执行摘要：公司现金流稳健。风险评级：黄灯。建议关注估值回落。")
    assert not is_final_response_candidate("短句但无结构")


def test_final_candidate_allows_completion_text_that_contains_thinking_labels():
    text = "ValueCell 已完成任务 展开 思考过程 执行摘要：公司现金流稳健。风险评级：黄灯。建议关注估值与成交量。"
    assert has_meaningful_response(text)
    assert is_final_response_candidate(text)
