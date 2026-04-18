from app.parsers.valuecell_parser import parse_valuecell_text


def test_parser_extracts_summary_highlights_and_risk():
    raw_text = """
    Executive Summary:
    The portfolio shows improving cash flow quality.

    Highlights:
    - Revenue trend stabilized
    - Gross margin recovered in Q2
    - Balance sheet remains strong

    Risk Rating: Yellow
    """

    parsed = parse_valuecell_text(raw_text)

    assert parsed["summary"].startswith("The portfolio shows")
    assert len(parsed["highlights"]) == 3
    assert parsed["risk_rating"] == "yellow"


def test_parser_returns_unknown_risk_when_not_found():
    parsed = parse_valuecell_text("No explicit risk label in this report.")
    assert parsed["risk_rating"] == "unknown"


def test_parser_extracts_markdown_table_rows():
    raw_text = """
    Summary: Snapshot table below.

    | Ticker | Signal | Risk |
    | --- | --- | --- |
    | AAPL | Hold | Yellow |
    | NVDA | Watch | Red |
    """
    parsed = parse_valuecell_text(raw_text)

    assert parsed["table"] == [
        {"Ticker": "AAPL", "Signal": "Hold", "Risk": "Yellow"},
        {"Ticker": "NVDA", "Signal": "Watch", "Risk": "Red"},
    ]


def test_parser_extracts_chinese_summary_highlights_and_risk():
    raw_text = """
    ValueCell 已完成任务

    执行摘要：
    组合处于中等风险区间，短期波动可能放大。

    核心风险点：
    1. 资金面边际走弱
    2. 行业估值处于偏高区间
    3. 宏观事件扰动仍在

    风险评级：黄灯
    """
    parsed = parse_valuecell_text(raw_text)

    assert "中等风险区间" in parsed["summary"]
    assert len(parsed["highlights"]) == 3
    assert parsed["risk_rating"] == "yellow"


def test_parser_removes_ui_noise_lines_before_extracting():
    raw_text = """
    Toggle Sidebar
    新建会话
    所有会话
    Research task: 请分析组合风险
    ValueCell 已完成任务
    收起
    理解问题意图

    Executive Summary:
    Liquidity risk is elevated after a concentrated rally.

    Risk Rating: Red
    """
    parsed = parse_valuecell_text(raw_text)

    assert parsed["summary"].startswith("Liquidity risk is elevated")
    assert parsed["risk_rating"] == "red"
