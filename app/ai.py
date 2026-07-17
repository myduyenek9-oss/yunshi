from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import Settings

SYSTEM_PROMPT = """
你是一个中文个人运势分析助手。你会收到用户八字基础盘、当前流年/流月/流日信息，以及推送或问答任务。
要求：
1. 输出中文，语气温和、精致、明确，不恐吓，不制造焦虑。
2. 建议采用带层次的 Markdown 输出，段落清晰、标题美观、要点化表达。
3. 可以使用五行、十神、干支、冲合等传统命理依据，但最终要落到工作/学习、财务/决策、人际/沟通、健康/精力等可执行建议。
4. 不要编造输入中没有的出生信息、地点、性别或时间。
5. 不要给绝对化承诺，不要保证结果一定发生。
6. 医疗、投资、法律等高风险问题只能给谨慎提醒和行动框架，不能替代专业意见或给确定性诊断/收益/法律判断。
7. 每次输出都必须包含“仅供个人参考，不作为医疗、投资、法律等专业决策依据”的提醒。
8. 回答尽量控制在 5-8 个小段落或条目内，便于在卡片中优雅展示。
""".strip()


def _client(settings: Settings) -> OpenAI:
    settings.require_openai()
    if settings.openai_base_url:
        return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    return OpenAI(api_key=settings.openai_api_key)


def _context_json(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, indent=2)


def _mock_daily_report(context: dict[str, Any]) -> str:
    date = context["target_date"]
    day_master = context["day_master"]
    flow = context["flow"]
    relations = "；".join(
        f"{item.get('scope')}:{item.get('flow_ganzhi')} {item.get('ten_god_to_day_master')}" for item in context.get("relations", [])
    )
    relation_line = relations or "暂无明显冲合提示。"
    return f"""# ✨ 今日运势提醒 {date}

## 🌙 今日总览
你的日主为 **{day_master.get('stem')}（{day_master.get('element')}）**，今日流日为 **{flow['day']['ganzhi']}**。整体气场偏向“稳中推进”，适合把重要事项拆成小步完成，先保节奏，再追求结果。

## 📌 当日运势
- **工作/学习**：先做确定性高、反馈快的任务，再处理协作与沟通。
- **财务/决策**：适合稳健判断，重要支出建议二次确认。
- **人际/沟通**：表达尽量简洁直接，避免被情绪带节奏。
- **健康/精力**：注意作息、饮水和放松，别把自己用太满。
- **今日建议**：今天只要把一件关键事做扎实，就算赢。

## 🌸 当月运势
流月为 **{flow['month']['ganzhi']}**。本月更像是“铺垫期 + 观察期”，适合积累、复盘、修正节奏，少做冲动型决定。

## 🌟 当年运势
流年为 **{flow['year']['ganzhi']}**。年度主题更偏向长期能力建设与稳健推进，适合把精力放在可持续的方向上。

## 🔮 命理参考
{relation_line}

## 🧭 今日关键词
稳住、聚焦、少分心、先完成。

## 免责声明
仅供个人参考，不作为医疗、投资、法律等专业决策依据。
""".strip()


def _mock_answer(context: dict[str, Any], question: str, last_summary: str | None = None) -> str:
    return f"""### ✨ 结论

结合你的八字日主 **{context['day_master']['stem']}（{context['day_master']['element']}）** 和今日流日 **{context['flow']['day']['ganzhi']}** 来看，关于 **“{question}”**，更适合采用稳健、分步验证的方式推进。

### 📌 建议

- 先确认信息是否完整，再做决定。
- 优先推进低风险、可回收的动作。
- 若涉及健康、投资或法律，请保留足够余量并咨询专业人士。

### 🧭 今日提醒

今天的关键不是冲得快，而是走得稳。把节奏放慢一点，反而更容易做出对你更有利的选择。

### 免责声明

仅供个人参考，不作为医疗、投资、法律等专业决策依据。
""".strip()


def generate_daily_report(settings: Settings, context: dict[str, Any]) -> str:
    if settings.mock_ai:
        return _mock_daily_report(context)

    user_prompt = f"""
请根据以下八字与流日上下文，现场生成一份个人运势推送。输出为精致的 Markdown，标题清晰、分层明确、段落美观。
必须包含这些板块：
# ✨ 今日运势提醒
## 🌙 今日总览
## 📌 当日运势
## 🌸 当月运势
## 🌟 当年运势
## 🔮 命理参考
## 🧭 今日关键词
## 免责声明

写作要求：
- 语言自然，不要像模板拼接。
- 结合日主、五行、流日、流月、流年给出具体建议。
- 用 5-8 个要点或短段落组成，适合卡片式展示。
- 最后必须包含“仅供个人参考，不作为医疗、投资、法律等专业决策依据”。

上下文 JSON：
{_context_json(context)}
""".strip()
    response = _client(settings).chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
    )
    return response.choices[0].message.content or ""


def answer_question(settings: Settings, context: dict[str, Any], question: str, last_summary: str | None = None) -> str:
    if settings.mock_ai:
        return _mock_answer(context, question, last_summary)

    user_prompt = f"""
用户问题：{question}

请结合八字基础特征、当前流年/流月/流日，以及用户问题进行回答。
输出为精致的 Markdown，尽量采用以下结构：
### ✨ 结论
### 📌 建议
### 🧭 今日提醒
### 免责声明

回答要求：
- 语气温和、具体、可执行。
- 不要大段空话，不要机械模板。
- 如果涉及医疗、投资、法律等高风险内容，必须明确说明不能替代专业意见，不能给确定性结论。
- 结合最近一次运势摘要做补充，但不要重复堆砌。
- 最后必须包含“仅供个人参考，不作为医疗、投资、法律等专业决策依据”。

最近一次运势摘要：
{last_summary or '暂无'}

上下文 JSON：
{_context_json(context)}
""".strip()
    response = _client(settings).chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content or ""
