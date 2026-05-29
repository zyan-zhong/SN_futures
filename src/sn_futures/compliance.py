from __future__ import annotations

from typing import Iterable


DISCLAIMER_HEADER = (
    "合规提示：本软件仅用于上海期货交易所沪锡期货（SN）的量化研究、仿真验证、报告生成与风险管理辅助。"
    "软件展示内容不构成任何投资建议、保本承诺、收益承诺或实盘交易招揽。"
)

DISCLAIMER_FOOTER = (
    "免责声明：模型输出、研究信号、预测区间、回测统计与风险评分均来源于历史数据和规则假设。"
    "历史结果不代表未来表现，任何实际应用均应遵守交易所规则、投资者适当性要求、内部合规审核与独立风险控制。"
)

PROHIBITED_TERMS = (
    "guaranteed return",
    "risk-free",
    "capital protected",
    "certain profit",
    "sure win",
    "保本",
    "稳赚",
    "保证收益",
    "无风险",
)


def compliance_hits(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in PROHIBITED_TERMS if term.lower() in lowered]


def ensure_compliant_text(text: str) -> str:
    hits = compliance_hits(text)
    if hits:
        raise ValueError(f"Output contains prohibited compliance terms: {', '.join(hits)}")
    return text


def with_disclaimer(lines: Iterable[str]) -> str:
    body = "\n".join(lines).strip()
    ensure_compliant_text(body)
    return f"{DISCLAIMER_HEADER}\n\n{body}\n\n{DISCLAIMER_FOOTER}\n"


def signal_label(signal: int) -> str:
    if signal > 0:
        return "多头研究观察"
    if signal < 0:
        return "空头研究观察"
    return "观望"
