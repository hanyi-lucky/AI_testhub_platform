"""
需求分析服务：调用真实 LLM 从需求文本中提取业务需求点。

设计目标：
- 复用 models.AIModelService 里已实现的真实 LLM 接入层（OpenAI 兼容 API）。
- 在同步视图里安全地跑 async 调用（asyncio.new_event_loop + 独立线程）。
- 降级健壮：没有可用 AI 配置、调用失败、或返回内容无法解析成 JSON 时，
  统一抛出异常，由调用方 fallback 到原有 mock 结果，绝不 500。

对外主入口：analyze_requirements_with_llm(text, title='') -> dict
返回结构与原有 mock 保持一致：
    {
        'analysis_report': str,
        'requirements_count': int,
        'requirements': [ {模型字段...}, ... ],
        'analysis_time': float,
    }
其中每个 requirement 的字段与 BusinessRequirement 模型对齐，可直接
用于 BusinessRequirement.objects.create(analysis=..., **req_data)。
"""

import asyncio
import json
import logging
import re
import threading
import time

from .models import AIModelConfig, AIModelService

logger = logging.getLogger(__name__)

# 调用 LLM 的整体超时（秒）
LLM_ANALYSIS_TIMEOUT = 120.0

# BusinessRequirement 合法取值
_VALID_TYPES = {'functional', 'performance', 'security', 'usability', 'interface', 'other'}
_VALID_LEVELS = {'high', 'medium', 'low'}

# 常见 category / priority 到模型合法值的映射
_TYPE_ALIASES = {
    '功能': 'functional', '功能需求': 'functional', 'function': 'functional',
    '性能': 'performance', '性能需求': 'performance',
    '安全': 'security', '安全需求': 'security',
    '可用性': 'usability', '易用性': 'usability', 'ui': 'usability', '交互': 'usability',
    '接口': 'interface', '接口需求': 'interface', 'api': 'interface',
}
_LEVEL_ALIASES = {
    '高': 'high', 'p0': 'high', 'p1': 'high', 'high': 'high',
    '中': 'medium', 'p2': 'medium', 'medium': 'medium', 'mid': 'medium',
    '低': 'low', 'p3': 'low', 'low': 'low',
}


def _get_analysis_config():
    """获取一个可用的需求分析 AI 配置。

    需求分析没有专属 role，复用 writer（测试用例编写专家）角色的启用配置。
    找不到返回 None，由调用方降级。
    """
    return AIModelConfig.objects.filter(role='writer', is_active=True).first()


def _build_messages(text):
    """构造需求分析 prompt。"""
    system_prompt = (
        "你是一位资深的需求分析专家。请从用户提供的需求文档中提取关键业务需求点。\n"
        "输出要求：\n"
        "1. 只输出一个 JSON 数组，不要输出任何解释性文字、开场白或结束语。\n"
        "2. 数组中每一项是一个对象，必须包含以下字段：\n"
        "   - requirement_id: 需求编号，形如 REQ001、REQ002（字符串）\n"
        "   - title: 需求名称（简短标题，字符串）\n"
        "   - description: 需求描述（字符串）\n"
        "   - priority: 优先级，取值 high / medium / low 之一（字符串）\n"
        "   - category: 需求类别，取值 functional / performance / security / "
        "usability / interface / other 之一（字符串）\n"
        "3. 需求点数量根据文档实际内容决定，覆盖核心功能，不要遗漏。\n"
        "4. 如果文档信息不足，也要基于已有内容合理提炼，至少输出 1 项。"
    )
    user_prompt = f"请分析以下需求文档，提取业务需求点并按要求输出 JSON 数组：\n\n{text}"
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _strip_code_fence(content):
    """去掉 LLM 返回内容里的 ```json ... ``` 代码块包裹，提取纯 JSON 文本。"""
    if not content:
        return content
    text = content.strip()

    # 去掉 ```json 或 ``` 开头 / ``` 结尾的代码块
    fence_match = re.search(r'```(?:json)?\s*(.+?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    # 没有代码块时，尝试截取第一个 [ 到最后一个 ] 之间的内容（JSON 数组）
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1].strip()

    return text


def _normalize_requirements(items):
    """把 LLM 返回的原始条目映射为 BusinessRequirement 模型可接受的字段。

    做防御式处理：缺字段用默认值补齐，非法枚举值归一化，保证 create() 不会报错。
    """
    if not isinstance(items, list):
        raise ValueError("LLM 返回的不是 JSON 数组")

    normalized = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue

        req_id = str(item.get('requirement_id') or f'REQ{idx:03d}').strip()
        title = str(item.get('title') or item.get('requirement_name') or f'需求点{idx}').strip()
        description = str(item.get('description') or title).strip()

        # priority -> requirement_level
        raw_priority = str(item.get('priority') or item.get('requirement_level') or 'medium').strip().lower()
        level = _LEVEL_ALIASES.get(raw_priority, raw_priority if raw_priority in _VALID_LEVELS else 'medium')

        # category -> requirement_type
        raw_category = str(item.get('category') or item.get('requirement_type') or 'functional').strip().lower()
        req_type = _TYPE_ALIASES.get(raw_category, raw_category if raw_category in _VALID_TYPES else 'functional')

        # module：优先使用 category 原文，否则默认
        module = str(item.get('module') or item.get('category') or '核心模块').strip() or '核心模块'

        normalized.append({
            'requirement_id': req_id[:50],
            'requirement_name': title[:200],
            'requirement_type': req_type,
            'module': module[:100],
            'requirement_level': level,
            'estimated_hours': int(item.get('estimated_hours') or 8),
            'description': description,
            'acceptance_criteria': str(item.get('acceptance_criteria') or '功能正常运行，满足需求描述').strip(),
        })

    if not normalized:
        raise ValueError("LLM 未返回有效的需求点")

    return normalized


async def _call_llm(config, text):
    """异步调用真实 LLM，返回原始文本内容。"""
    messages = _build_messages(text)
    response = await AIModelService.call_openai_compatible_api(config, messages)
    return response['choices'][0]['message']['content']


def _run_async(coro):
    """在独立线程里用新的事件循环跑 async 协程，避免与已有事件循环冲突。"""
    holder = {}

    def _worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            holder['result'] = loop.run_until_complete(
                asyncio.wait_for(coro, timeout=LLM_ANALYSIS_TIMEOUT)
            )
        except Exception as exc:  # noqa: BLE001 - 统一上抛由调用方降级
            holder['error'] = exc
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join()

    if 'error' in holder:
        raise holder['error']
    return holder.get('result')


def analyze_requirements_with_llm(text, title=''):
    """使用真实 LLM 分析需求文本。

    成功返回与原 mock 一致结构的 dict；任何失败（无配置 / 调用失败 /
    解析失败）都抛出异常，由调用方 fallback 到 mock。
    """
    if not text or not text.strip():
        raise ValueError("需求文本为空")

    config = _get_analysis_config()
    if not config:
        raise RuntimeError("未找到可用的 AI 模型配置（role=writer, is_active=True）")

    start = time.time()
    content = _run_async(_call_llm(config, text))
    elapsed = round(time.time() - start, 2)

    json_text = _strip_code_fence(content)
    try:
        items = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM 返回内容无法解析为 JSON: {exc}") from exc

    requirements = _normalize_requirements(items)

    doc_label = f'"{title}"' if title else '文档'
    analysis_report = (
        f'对{doc_label}的需求分析已完成（由 {config.get_model_type_display()} / '
        f'{config.model_name} 分析）。\n\n'
        f'共识别到 {len(requirements)} 个业务需求点。\n\n'
        f'需求文本摘要：{text[:200]}...'
    )

    return {
        'analysis_report': analysis_report,
        'requirements_count': len(requirements),
        'requirements': requirements,
        'analysis_time': elapsed,
    }
