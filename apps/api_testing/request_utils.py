"""
接口测试公共工具模块。

集中此前散落在 views.py / utils.py 中重复拷贝的逻辑：
- 环境变量 {{var}} 替换（字符串 / 递归 dict）
- 动态函数 ${func()} 解析（委托 core.VariableResolver）
- 环境变量合并（GLOBAL + LOCAL，局部覆盖全局）
- 请求组装（headers / params / body，支持 json / raw / form-urlencoded / form-data）
- 响应提取（extractors：json_path / header / status_code / regex）→ 供接口关联使用
"""
import json
import re

from .variable_resolver import VariableResolver


# ---------------------------------------------------------------------------
# 1. 环境变量 {{var}} 替换
# ---------------------------------------------------------------------------
def replace_env_variables(text, variables):
    """把文本中的 {{key}} 占位符替换为环境变量值。

    变量值支持两种形态：普通标量，或前端变量对象 {currentValue, initialValue}。
    """
    if not isinstance(text, str):
        return text
    result = text
    for key, value in (variables or {}).items():
        if isinstance(value, dict):
            replacement = str(value.get('currentValue', '') or value.get('initialValue', ''))
        else:
            replacement = str(value) if value is not None else ''
        result = result.replace(f'{{{{{key}}}}}', replacement)
    return result


def replace_env_variables_in_obj(data, variables):
    """递归替换 dict / list / str 中的 {{var}}。"""
    if isinstance(data, dict):
        return {k: replace_env_variables_in_obj(v, variables) for k, v in data.items()}
    if isinstance(data, list):
        return [replace_env_variables_in_obj(item, variables) for item in data]
    if isinstance(data, str):
        return replace_env_variables(data, variables)
    return data


def resolve_dynamic_in_obj(data, resolver):
    """递归解析 dict / list / str 中的 ${func()} 动态函数。"""
    if isinstance(data, dict):
        return {k: resolve_dynamic_in_obj(v, resolver) for k, v in data.items()}
    if isinstance(data, list):
        return [resolve_dynamic_in_obj(item, resolver) for item in data]
    if isinstance(data, str):
        return resolver.resolve(data)
    return data


def render(text, variables, resolver):
    """对单个字符串统一渲染：先替换 {{env}}，再解析 ${func()}。"""
    return resolver.resolve(replace_env_variables(text or '', variables))


def render_obj(data, variables, resolver):
    """对任意结构统一渲染：先替换 {{env}}，再解析 ${func()}。"""
    return resolve_dynamic_in_obj(replace_env_variables_in_obj(data, variables), resolver)


# ---------------------------------------------------------------------------
# 2. 环境变量合并（GLOBAL + LOCAL，局部覆盖全局）
# ---------------------------------------------------------------------------
def build_variables(environment=None, project=None, extra=None):
    """构建执行时使用的变量池。

    合并顺序（后者覆盖前者）：
      1. 激活的 GLOBAL 环境变量
      2. 激活的 LOCAL 环境变量（限定 project，或直接传入的 environment 所属项目）
      3. 显式传入的 environment（手动执行选定的环境，优先级最高）
      4. extra（运行期动态注入，如上一步响应提取结果，优先级最高）

    这样才真正实现了"全局 + 局部合并、局部覆盖全局"的语义，
    而不是旧实现里"只取单一 environment.variables"。
    """
    from .models import Environment

    merged = {}

    # 1. 全局激活环境
    for env in Environment.objects.filter(scope='GLOBAL', is_active=True):
        merged.update(env.variables or {})

    # 2. 局部激活环境（按项目）
    target_project = project
    if target_project is None and environment is not None:
        target_project = getattr(environment, 'project', None)
    if target_project is not None:
        for env in Environment.objects.filter(scope='LOCAL', is_active=True, project=target_project):
            merged.update(env.variables or {})

    # 3. 显式指定的环境（手动执行时前端传的 environment_id / 套件绑定的 environment）
    if environment is not None:
        merged.update(environment.variables or {})

    # 4. 运行期动态变量
    if extra:
        merged.update(extra)

    return merged


# ---------------------------------------------------------------------------
# 3. 请求组装（headers / params / body）
# ---------------------------------------------------------------------------
def build_headers(raw_headers, variables, resolver):
    """兼容数组格式 [{key,value,enabled}] 和对象格式 {k:v}，渲染后返回 dict。"""
    headers = {}
    if isinstance(raw_headers, list):
        for item in raw_headers:
            if item.get('enabled', True) and item.get('key'):
                headers[item['key']] = render(str(item.get('value', '')), variables, resolver)
    elif isinstance(raw_headers, dict):
        for key, value in raw_headers.items():
            headers[key] = render(str(value), variables, resolver)
    return headers


def build_params(raw_params, variables, resolver):
    """渲染 URL 查询参数。"""
    params = {}
    for key, value in (raw_params or {}).items():
        params[key] = render(str(value), variables, resolver)
    return params


def build_body(raw_body, method, variables, resolver):
    """根据请求体类型组装 requests 调用所需的 kwargs。

    返回 (request_kwargs, body_repr)：
      - request_kwargs: 直接展开进 requests.request() 的关键字参数
        （json= / data= / files= 之一），不含公共的 url/headers/params。
      - body_repr: 用于历史记录展示的请求体快照。

    支持类型：json / raw / x-www-form-urlencoded / form-data / none。
    修复点：此前 urlencoded / form-data 被错误地当作 json= 发送。
    """
    if not raw_body or method not in ['POST', 'PUT', 'PATCH']:
        return {}, None

    body_type = raw_body.get('type', 'none')
    body_content = raw_body.get('data')

    if body_type == 'json':
        if isinstance(body_content, (dict, list)):
            rendered = render_obj(body_content, variables, resolver)
        else:
            rendered = render(body_content, variables, resolver) if isinstance(body_content, str) else body_content
        return {'json': rendered}, rendered

    if body_type == 'raw':
        rendered = render(body_content, variables, resolver) if isinstance(body_content, str) else body_content
        return {'data': rendered}, rendered

    if body_type == 'x-www-form-urlencoded':
        # 用 data= 以 application/x-www-form-urlencoded 编码发送
        form = _kv_list_to_dict(body_content, variables, resolver)
        return {'data': form}, form

    if body_type == 'form-data':
        # multipart/form-data：普通字段走 data=。为强制 requests 使用 multipart 编码，
        # 传入空 files= 触发边界生成（纯文本字段场景下足够；文件上传可后续扩展）。
        form = _kv_list_to_dict(body_content, variables, resolver)
        return {'data': form, 'files': {}}, form

    return {}, body_content


def _kv_list_to_dict(body_content, variables, resolver):
    """把 [{key,value,enabled}] 或 {k:v} 形态的表单内容渲染成扁平 dict。"""
    result = {}
    if isinstance(body_content, list):
        for item in body_content:
            if isinstance(item, dict) and item.get('enabled', True) and item.get('key'):
                result[item['key']] = render(str(item.get('value', '')), variables, resolver)
    elif isinstance(body_content, dict):
        for key, value in body_content.items():
            result[key] = render(str(value), variables, resolver)
    return result


# ---------------------------------------------------------------------------
# 4. 响应提取（接口关联的核心）
# ---------------------------------------------------------------------------
def extract_from_response(response, extractors):
    """按 extractors 规则从响应中提取值，返回 {变量名: 值} 供后续请求引用。

    extractors 每项结构：
      {
        "name": "token",              # 提取后写入变量池的变量名
        "type": "json_path" | "header" | "status_code" | "regex",
        "expression": "$.data.token", # json_path 表达式 / header 名 / 正则
      }

    对应模型里此前预留但从未执行的 post_request_script 能力。
    任一提取失败不影响其他，静默跳过（记录为 None）。
    """
    extracted = {}
    if not extractors:
        return extracted

    for rule in extractors:
        if not isinstance(rule, dict):
            continue
        name = rule.get('name')
        if not name:
            continue
        etype = rule.get('type', 'json_path')
        expr = rule.get('expression', '') or rule.get('json_path', '') or rule.get('header_name', '')
        value = None
        try:
            if etype == 'json_path':
                from jsonpath_ng import parse
                data = json.loads(response.text)
                matches = parse(expr).find(data)
                value = matches[0].value if matches else None
            elif etype == 'header':
                value = response.headers.get(expr)
            elif etype == 'status_code':
                value = response.status_code
            elif etype == 'regex':
                m = re.search(expr, response.text or '')
                value = m.group(1) if (m and m.groups()) else (m.group(0) if m else None)
        except Exception:
            value = None
        extracted[name] = value

    return extracted
