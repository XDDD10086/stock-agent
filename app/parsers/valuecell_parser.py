from __future__ import annotations

import re


def parse_valuecell_text(raw_text: str) -> dict:
    text = _preprocess(raw_text)
    summary = _extract_summary(text)
    highlights = _extract_highlights(text)
    risk = _extract_risk_rating(text)
    table = _extract_markdown_table(text)
    return {
        "summary": summary,
        "highlights": highlights,
        "risk_rating": risk,
        "table": table,
    }


_NOISE_LINES = {
    "toggle sidebar",
    "新建会话",
    "所有会话",
    "收起",
    "展开",
    "深度研究",
    "市场观察",
    "行业研究",
    "个股探索",
    "策略回测",
    "pro",
    "·",
}

_NOISE_PREFIXES = (
    "research task:",
    "role:",
    "task:",
    "valuecell 正在执行任务",
    "理解问题意图",
    "构建分析策略",
    "审视当前上下文",
)

_CHINESE_RISK_MAP = {
    "红色": "red",
    "红灯": "red",
    "红": "red",
    "黄色": "yellow",
    "黄灯": "yellow",
    "黄": "yellow",
    "绿色": "green",
    "绿灯": "green",
    "绿": "green",
}


def _preprocess(raw_text: str) -> str:
    text = raw_text.strip()
    if not text:
        return ""

    if "ValueCell 已完成任务" in text:
        text = text.split("ValueCell 已完成任务", 1)[1]
    elif "ValueCell 正在执行任务" in text:
        text = text.split("ValueCell 正在执行任务", 1)[1]

    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue

        lowered = line.lower()
        if lowered in _NOISE_LINES:
            continue
        if any(lowered.startswith(prefix) for prefix in _NOISE_PREFIXES):
            continue
        if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", line):
            continue
        cleaned_lines.append(line)

    compact = "\n".join(cleaned_lines)
    compact = re.sub(r"\n{3,}", "\n\n", compact)
    return compact.strip()


def _extract_summary(text: str) -> str:
    patterns = [
        r"(?is)executive summary[:：]?\s*(.+?)(?:\n\s*\n|highlights[:：]?|risk rating[:：]?|$)",
        r"(?is)summary[:：]?\s*(.+?)(?:\n\s*\n|highlights[:：]?|risk rating[:：]?|$)",
        r"(?is)执行摘要[:：]?\s*(.+?)(?:\n\s*\n|核心风险点[:：]?|关键要点[:：]?|风险评级[:：]?|风险等级[:：]?|风险评价[:：]?|$)",
        r"(?is)摘要[:：]?\s*(.+?)(?:\n\s*\n|核心风险点[:：]?|关键要点[:：]?|风险评级[:：]?|风险等级[:：]?|风险评价[:：]?|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _clean(match.group(1))
    return _clean(text[:240]) if text else ""


def _extract_highlights(text: str) -> list[str]:
    patterns = [
        r"(?is)highlights[:：]?\s*(.+?)(?:\n\s*\n|risk rating[:：]?|$)",
        r"(?is)核心风险点[:：]?\s*(.+?)(?:\n\s*\n|风险评级[:：]?|风险等级[:：]?|风险评价[:：]?|结论[:：]?|$)",
        r"(?is)关键要点[:：]?\s*(.+?)(?:\n\s*\n|风险评级[:：]?|风险等级[:：]?|风险评价[:：]?|结论[:：]?|$)",
        r"(?is)要点[:：]?\s*(.+?)(?:\n\s*\n|风险评级[:：]?|风险等级[:：]?|风险评价[:：]?|结论[:：]?|$)",
    ]
    block = ""
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            block = match.group(1)
            break
    if not block:
        return []

    lines = [line.strip() for line in block.splitlines()]
    items: list[str] = []
    for line in lines:
        if not line:
            continue
        line = re.sub(r"^[-*•]\s*", "", line)
        line = re.sub(r"^\d+[\.、:：]\s*", "", line)
        item = _clean(line)
        if item:
            items.append(item)
    return [item for item in items if item][:6]


def _extract_risk_rating(text: str) -> str:
    english = re.search(r"(?is)risk\s*rating[:：]?\s*(red|yellow|green)", text)
    if english:
        return english.group(1).lower()

    chinese = re.search(
        r"(?is)风险(?:评级|等级|评估|评价)?[:：]?\s*(红色|黄色|绿色|红灯|黄灯|绿灯|红|黄|绿)",
        text,
    )
    if chinese:
        return _CHINESE_RISK_MAP[chinese.group(1)]

    chinese_inline = re.search(
        r"(?is)(?:最终|综合|总体)?(?:风险)?(?:评级|评价)?[:：]?\s*(红灯|黄灯|绿灯)",
        text,
    )
    if chinese_inline:
        return _CHINESE_RISK_MAP[chinese_inline.group(1)]

    if re.search(r"(高风险|风险偏高|显著回撤|强烈止损|红色预警)", text):
        return "red"
    if re.search(r"(中等风险|风险中性|谨慎|黄灯)", text):
        return "yellow"
    if re.search(r"(低风险|风险可控|绿灯|稳健)", text):
        return "green"

    return "unknown"


def _extract_markdown_table(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        return []

    for idx in range(len(lines) - 2):
        header_line = lines[idx]
        separator_line = lines[idx + 1]
        if not _is_separator_row(separator_line):
            continue

        headers = _split_row(header_line)
        if not headers:
            continue

        rows: list[dict] = []
        for data_line in lines[idx + 2 :]:
            if _is_separator_row(data_line):
                break
            cells = _split_row(data_line)
            if len(cells) != len(headers):
                continue
            rows.append({headers[i]: cells[i] for i in range(len(headers))})
        if rows:
            return rows
    return []


def _split_row(line: str) -> list[str]:
    content = line.strip().strip("|")
    return [_clean(cell) for cell in content.split("|")]


def _is_separator_row(line: str) -> bool:
    cells = _split_row(line)
    if not cells:
        return False
    for cell in cells:
        stripped = cell.replace(":", "").replace("-", "")
        if stripped:
            return False
    return True


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
