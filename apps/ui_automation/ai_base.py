import logging

logger = logging.getLogger('django')

import os

# 禁用 browser-use 遥测
os.environ['ANONYMIZED_TELEMETRY'] = 'false'

import asyncio
import functools
import json
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 加载环境变量
load_dotenv()

TASK_STATUS_ACTIONS = {'mark_task_complete', 'mark_task_failed', 'mark_task_skipped'}


def _normalize_action_params(action_name, action_params):
    """Normalize common LLM-generated action parameter variants to browser-use schema."""
    if isinstance(action_params, int):
        if action_name in TASK_STATUS_ACTIONS:
            return {'task_id': action_params}
        return {'index': action_params}

    if action_name == 'switch_tab' and isinstance(action_params, str) and not isinstance(action_params, dict):
        return {'tab_id': action_params}

    if not isinstance(action_params, dict):
        return action_params

    normalized_params = {}
    for key, value in action_params.items():
        normalized_key = key
        if key in {'element_index', 'element_id', 'node_id', 'id'} and action_name not in TASK_STATUS_ACTIONS:
            normalized_key = 'index'
        elif key in {'tab', 'target', 'target_id'} and action_name in {'switch_tab', 'switch'}:
            normalized_key = 'tab_id'
        elif key in {'content', 'value'} and action_name in {'input', 'input_text'}:
            normalized_key = 'text'
        normalized_params[normalized_key] = value
    return normalized_params


def _is_terminal_status_action(action_name, action_params):
    if action_name in TASK_STATUS_ACTIONS:
        return True
    if action_name != 'update_task_status' or not isinstance(action_params, dict):
        return False
    return str(action_params.get('status', '')).strip().lower() in {'completed', 'failed', 'skipped'}


def _enforce_single_task_step(actions):
    """
    Enforce single-task-per-step:
    once a terminal task status action appears, discard any later business actions.
    """
    if not isinstance(actions, list):
        return actions

    trimmed_actions = []
    terminal_seen = False
    dropped_count = 0

    for action in actions:
        if not isinstance(action, dict):
            trimmed_actions.append(action)
            continue

        if terminal_seen:
            dropped_count += 1
            continue

        trimmed_actions.append(action)
        for action_name, action_params in action.items():
            if _is_terminal_status_action(action_name, action_params):
                terminal_seen = True
                break
            if action_name == 'done':
                terminal_seen = True
                break

    if dropped_count:
        logger.warning(
            f"⚠️ Enforced single-task step boundary: dropped {dropped_count} action(s) after terminal status update"
        )

    return trimmed_actions


def _get_task_status_action_task_id(action):
    if not isinstance(action, dict):
        return None

    for action_name, action_params in action.items():
        if action_name in TASK_STATUS_ACTIONS and isinstance(action_params, dict):
            return action_params.get('task_id')
        if action_name == 'update_task_status' and isinstance(action_params, dict):
            status = str(action_params.get('status', '')).strip().lower()
            if status in {'completed', 'failed', 'skipped'}:
                return action_params.get('task_id')
    return None


def _has_real_business_action(action):
    if not isinstance(action, dict):
        return False
    return any(
        action_name not in {'mark_task_complete', 'mark_task_failed', 'mark_task_skipped', 'update_task_status', 'done'}
        for action_name in action.keys()
    )


def _extract_task_literals(task_description):
    if not task_description:
        return []

    text = str(task_description)
    literals = []
    literals.extend(re.findall(r'「([^」]+)」', text))
    literals.extend(re.findall(r'"([^"\n]+)"', text))
    literals.extend(re.findall(r"'([^'\n]+)'", text))
    literals.extend(re.findall(r'https?://[^\s]+', text))
    literals.extend(re.findall(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', text))

    deduped = []
    for item in literals:
        cleaned = str(item).strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


def _action_matches_pending_task(action, pending_task_description):
    if not isinstance(action, dict):
        return False

    literals = _extract_task_literals(pending_task_description)
    if not literals:
        return False

    action_payload = json.dumps(action, ensure_ascii=False)
    return any(literal in action_payload for literal in literals)


def _enforce_pending_status_settlement(actions, pending_task_id, pending_task_description=None):
    """
    If the previous step executed a task but forgot to mark it, the next step must settle
    that pending task status first and must not start the following business task in the same step.
    """
    if not pending_task_id or not isinstance(actions, list):
        return actions

    marked_pending_task = any(
        str(_get_task_status_action_task_id(action)) == str(pending_task_id)
        for action in actions
    )
    has_real_action = any(_has_real_business_action(action) for action in actions)

    if not (marked_pending_task and has_real_action):
        return actions

    real_actions = [action for action in actions if _has_real_business_action(action)]
    if pending_task_description and any(
        _action_matches_pending_task(action, pending_task_description)
        for action in real_actions
    ):
        return actions

    settled_actions = [
        action for action in actions
        if str(_get_task_status_action_task_id(action)) == str(pending_task_id)
    ]

    if settled_actions:
        logger.warning(
            f"⚠️ Settling pending task {pending_task_id} first: dropped business actions from the same step"
        )
        return settled_actions

    return actions


def _contains_auth_failure_signal(text):
    if not text:
        return False

    normalized = str(text).lower()
    keywords = [
        '登录失败', 'login failed', 'invalid credentials', 'incorrect password',
        '用户名或密码', '账号或密码', 'authentication failed', 'auth failed',
        'bad credentials', 'unauthorized', '401', '403'
    ]
    return any(keyword in normalized for keyword in keywords)

# ============================================================================
# PART 1: Common Patches (Pydantic, ActionModel, TokenCost, Basic Connection)
# ============================================================================

# Patch ChatOpenAI to allow setting attributes (required for browser-use token counting)
try:
    from pydantic import ConfigDict

    if hasattr(ChatOpenAI, 'model_config'):
        if isinstance(ChatOpenAI.model_config, dict):
            ChatOpenAI.model_config['extra'] = 'allow'
        else:
            ChatOpenAI.model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
    else:
        ChatOpenAI.model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
except ImportError:
    if hasattr(ChatOpenAI, 'model_config'):
        ChatOpenAI.model_config['extra'] = 'allow'

# 修改 ActionModel 配置以允许额外字段
try:
    from browser_use.tools.registry.views import ActionModel
    from pydantic import ConfigDict

    ActionModel.model_config = ConfigDict(arbitrary_types_allowed=True, extra='allow')
    logger.info("✅ Modified ActionModel.model_config to allow extra fields")
except Exception as e:
    logger.warning(f"⚠️ Failed to modify ActionModel config: {e}")

# Patch Agent.get_model_output 方法
try:
    from browser_use.agent.service import Agent
    from browser_use.agent.message_manager.service import AgentOutput
    import json as json_module

    _original_get_model_output = Agent.get_model_output


    async def _patched_get_model_output(self, input_messages):
        """修补后的 get_model_output，直接从 response.content 解析 JSON"""
        # logger.info("🔧 _patched_get_model_output called")

        if hasattr(self, '_task_was_done') and self._task_was_done:
            logger.info("🔧 Task was marked as done, stopping LLM interaction")
            raise KeyboardInterrupt("Task finished")

        kwargs = {'output_format': self.AgentOutput}

        # Add retry logic for LLM invocation with timeout
        max_retries = 2  # 重试次数为2次
        last_exception = None
        response = None
        for attempt in range(max_retries):
            try:
                # 添加超时控制，设置为60秒（支持硅基流动等大模型API的响应时间）
                response = await asyncio.wait_for(
                    self.llm.ainvoke(input_messages, **kwargs),
                    timeout=60.0  # 超时时间60秒
                )
                break
            except asyncio.TimeoutError as te:
                last_exception = te
                logger.warning(f"⚠️ LLM invocation timed out (attempt {attempt + 1}/{max_retries}): {te}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)  # 重试间隔0.5秒
            except Exception as e:
                last_exception = e
                logger.warning(f"⚠️ LLM invocation failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)  # 重试间隔0.5秒
        else:
            logger.error(f"❌ LLM invocation failed after {max_retries} attempts.")
            raise last_exception

        # 检查响应是否为空或无效
        if not response or not hasattr(response, 'content'):
            error_msg = "LLM returned invalid response (no content attribute)"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        # 检查content是否为空字符串
        content = response.content
        if not content or not isinstance(content, str) or not content.strip():
            error_msg = "LLM returned empty content - possible API error or timeout"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        try:
            if hasattr(response, 'content') and isinstance(response.content, str):
                # 处理带有 <thinking> 标签的响应
                content_text = response.content.strip()
                # 移除开头的 <thinking>...</thinking> 标签块
                import re
                thinking_pattern = r'^<thinking>.*?</thinking>\s*'
                if re.match(thinking_pattern, content_text, re.DOTALL):
                    content_text = re.sub(thinking_pattern, '', content_text, count=1, flags=re.DOTALL)
                    logger.info("🔧 Fixed: removed leading <thinking> block from response")

                content_dict = json_module.loads(content_text)

                # 规范化 action 字典
                if 'action' in content_dict:
                    import re
                    normalized_actions = []
                    for action_dict in content_dict['action']:
                        # 处理字符串格式的 action（如 "mark_task_complete(task_id=8)"）
                        if isinstance(action_dict, str):
                            match = re.match(r'(\w+)\(([^)]*)\)', action_dict.strip())
                            if match:
                                action_name = match.group(1)
                                params_str = match.group(2)
                                # 解析参数
                                if action_name in TASK_STATUS_ACTIONS:
                                    task_id_match = re.search(r'task_id=(\d+)', params_str)
                                    if task_id_match:
                                        normalized_actions.append({action_name: {'task_id': int(task_id_match.group(1))}})
                                        logger.info(f"🔧 Fixed: parsed string action '{action_dict}'")
                                elif action_name == 'update_task_status':
                                    task_id_match = re.search(r'task_id=(\d+)', params_str)
                                    status_match = re.search(r"status=['\"]?(\w+)['\"]?", params_str)
                                    if task_id_match and status_match:
                                        normalized_actions.append({
                                            action_name: {
                                                'task_id': int(task_id_match.group(1)),
                                                'status': status_match.group(1)
                                            }
                                        })
                                        logger.info(f"🔧 Fixed: parsed string action '{action_dict}'")
                                elif action_name == 'done':
                                    normalized_actions.append({'done': {}})
                            continue

                        normalized_action = {}
                        for action_name, action_params in action_dict.items():
                            normalized_value = _normalize_action_params(action_name, action_params)
                            # 忽略无效的字符串参数（如 {"click": "保存"}）
                            if isinstance(normalized_value, str) and action_name not in ['done', 'switch_tab']:
                                logger.warning(f"⚠️ Invalid action format: {action_name}: {normalized_value}, skipping")
                                continue
                            normalized_action[action_name] = normalized_value
                        if normalized_action:  # 只添加非空的 action
                            normalized_actions.append(normalized_action)
                    normalized_actions = _enforce_single_task_step(normalized_actions)
                    pending_task_id = getattr(self, '_pending_status_task_id', None)
                    pending_task_description = getattr(self, '_pending_status_task_description', None)
                    content_dict['action'] = _enforce_pending_status_settlement(
                        normalized_actions,
                        pending_task_id,
                        pending_task_description
                    )

                # 检查 action 数组外部的 mark_task_complete（错误格式）
                # 如果存在，将其添加到 action 数组中
                for action_name in [*TASK_STATUS_ACTIONS, 'update_task_status']:
                    if action_name not in content_dict:
                        continue
                    if 'action' not in content_dict:
                        content_dict['action'] = []
                    if isinstance(content_dict[action_name], dict):
                        content_dict['action'].append({action_name: content_dict[action_name]})
                        logger.info(f"🔧 Fixed: moved {action_name} into action array")
                    elif isinstance(content_dict[action_name], int) and action_name in TASK_STATUS_ACTIONS:
                        task_id = content_dict[action_name]
                        content_dict['action'].append({action_name: {'task_id': task_id}})
                        logger.info(f"🔧 Fixed: converted {action_name}({task_id}) to proper format and added to action array")

                parsed = AgentOutput.model_construct(
                    thinking=content_dict.get('thinking'),
                    evaluation_previous_goal=content_dict.get('evaluation_previous_goal'),
                    memory=content_dict.get('memory'),
                    next_goal=content_dict.get('next_goal'),
                    action=[]
                )

                class _ActionWrapper:
                    def __init__(self, action_dict):
                        self._action_dict = action_dict

                    def model_dump(self, **kwargs):
                        return self._action_dict

                    def get_index(self):
                        for action_params in self._action_dict.values():
                            if isinstance(action_params, dict) and 'index' in action_params:
                                return action_params['index']
                        return None

                action_list = []
                for action_dict in content_dict.get('action', []):
                    action_list.append(_ActionWrapper(action_dict))

                object.__setattr__(parsed, 'action', action_list)

                if len(parsed.action) > self.settings.max_actions_per_step:
                    parsed.action = parsed.action[:self.settings.max_actions_per_step]

                return parsed
        except Exception as e:
            # If our complex normalization fails, fall back to the original method
            logger.warning(f"⚠️ Custom output normalization failed, falling back: {e}")
            return await _original_get_model_output(self, input_messages)


    Agent.get_model_output = _patched_get_model_output
    logger.info("✅ Successfully patched Agent.get_model_output")
except Exception as e:
    logger.error(f"❌ Failed to patch Agent.get_model_output: {e}")

# Patch TokenCost
try:
    from browser_use.tokens.service import TokenCost
    from langchain_core.messages import HumanMessage, SystemMessage as LangChainSystemMessage, AIMessage


    def _patched_register_llm(self, llm):
        """修补后的 register_llm，修复 langchain 兼容性"""
        instance_id = str(id(llm))
        if instance_id in self.registered_llms:
            return llm

        self.registered_llms[instance_id] = llm
        _original_ainvoke = llm.ainvoke
        _token_service = self

        async def _fixed_tracked_ainvoke(messages, output_format=None, **kwargs):
            # Sanitize message contents
            def _content_to_str(content):
                if isinstance(content, str): return content
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, str):
                            parts.append(item)
                        elif isinstance(item, dict):
                            if 'text' in item:
                                parts.append(str(item['text']))
                            elif 'image' in item or 'image_url' in item:
                                parts.append("[image]")
                        else:
                            parts.append(str(item))
                    return "\n".join(parts)
                if isinstance(content, dict):
                    if 'text' in content: return str(content['text'])
                    if 'content' in content: return str(content['content'])
                    if 'image' in content or 'image_url' in content: return "[image]"
                return str(content)

            def _sanitize_message(msg):
                msg_type_name = type(msg).__name__
                content = getattr(msg, 'content', msg)
                content_str = _content_to_str(content)
                if msg_type_name == 'SystemMessage': return LangChainSystemMessage(content=content_str)
                if msg_type_name in ('HumanMessage', 'UserMessage'): return HumanMessage(content=content_str)
                if msg_type_name == 'AIMessage': return AIMessage(content=content_str)
                if isinstance(msg, (HumanMessage, LangChainSystemMessage, AIMessage)): return type(msg)(
                    content=content_str)
                return HumanMessage(content=str(content_str))

            sanitized_messages = [_sanitize_message(m) for m in messages]

            output_format = kwargs.pop('output_format', None)
            if output_format:
                kwargs['response_format'] = {"type": "json_object"}

            # Add retry logic for LLM invocation
            max_retries = 2  # 重试次数为2次
            last_exception = None
            for attempt in range(max_retries):
                try:
                    result = await _original_ainvoke(sanitized_messages, **kwargs)
                    break
                except Exception as e:
                    last_exception = e
                    if "response_format" in str(e):
                        kwargs.pop('response_format', None)
                        # retry immediately without response_format
                        continue

                    logger.warning(f"⚠️ LLM ainvoke failed (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5)  # 等待0.5秒
            else:
                logger.error(f"❌ LLM ainvoke failed after {max_retries} attempts.")
                raise last_exception

            # Enhance response parsing
            import json as json_module
            clean_content = result.content.strip() if hasattr(result, 'content') else str(result).strip()

            # 处理带有 <thinking> 标签的响应
            thinking_pattern = r'^<thinking>.*?</thinking>\s*'
            if re.match(thinking_pattern, clean_content, re.DOTALL):
                clean_content = re.sub(thinking_pattern, '', clean_content, count=1, flags=re.DOTALL)
                logger.info("🔧 Fixed in TokenCost: removed leading <thinking> block from response")

            # Remove Markdown
            if '```' in clean_content:
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', clean_content, re.DOTALL)
                if match:
                    clean_content = match.group(1).strip()
                else:
                    clean_content = re.sub(r'```[a-z]*', '', clean_content).replace('```', '').strip()

            parsed_data = None
            try:
                parsed_data = json_module.loads(clean_content)
            except:
                try:
                    match = re.search(r'(\{.*\})', clean_content, re.DOTALL)
                    if match: parsed_data = json_module.loads(match.group(1))
                except:
                    pass

            # Wrapper classes
            class _ActionWrapper:
                def __init__(self, action_dict):
                    self._dict = {}
                    for k, v in action_dict.items():
                        if isinstance(v, dict):
                            self._dict[k] = _normalize_action_params(k, v)
                        else:
                            self._dict[k] = v
                    for k, v in self._dict.items(): setattr(self, k, v)

                def model_dump(self, **kwargs):
                    return self._dict

                def get_index(self):
                    for v in self._dict.values():
                        if isinstance(v, dict) and 'index' in v: return v['index']
                    return None

            # Construct AgentOutput manually
            agent_output = None
            if parsed_data and 'action' in parsed_data:
                # Normalize actions
                normalized_actions = []
                for action_dict in parsed_data['action']:
                    # 处理字符串格式的 action（如 "mark_task_complete(task_id=8)"）
                    if isinstance(action_dict, str):
                        match = re.match(r'(\w+)\(([^)]*)\)', action_dict.strip())
                        if match:
                            action_name = match.group(1)
                            params_str = match.group(2)
                            # 解析参数
                            if action_name in TASK_STATUS_ACTIONS:
                                task_id_match = re.search(r'task_id=(\d+)', params_str)
                                if task_id_match:
                                    normalized_actions.append({action_name: {'task_id': int(task_id_match.group(1))}})
                                    logger.info(f"🔧 Fixed in TokenCost: parsed string action '{action_dict}'")
                            elif action_name == 'update_task_status':
                                task_id_match = re.search(r'task_id=(\d+)', params_str)
                                status_match = re.search(r"status=['\"]?(\w+)['\"]?", params_str)
                                if task_id_match and status_match:
                                    normalized_actions.append({
                                        action_name: {
                                            'task_id': int(task_id_match.group(1)),
                                            'status': status_match.group(1)
                                        }
                                    })
                                    logger.info(f"🔧 Fixed in TokenCost: parsed string action '{action_dict}'")
                            elif action_name == 'done':
                                normalized_actions.append({'done': {}})
                        continue

                    normalized_action = {}
                    for action_name, action_params in action_dict.items():
                        normalized_value = _normalize_action_params(action_name, action_params)
                        # 忽略无效的字符串参数（如 {"click": "保存"}）
                        if isinstance(normalized_value, str) and action_name not in ['done', 'switch_tab']:
                            logger.warning(f"⚠️ Invalid action format in TokenCost: {action_name}: {normalized_value}, skipping")
                            continue
                        normalized_action[action_name] = normalized_value
                    if normalized_action:  # 只添加非空的 action
                        normalized_actions.append(normalized_action)
                normalized_actions = _enforce_single_task_step(normalized_actions)
                pending_task_id = getattr(llm, '_pending_status_task_id', None)
                pending_task_description = getattr(llm, '_pending_status_task_description', None)
                parsed_data['action'] = _enforce_pending_status_settlement(
                    normalized_actions,
                    pending_task_id,
                    pending_task_description
                )

                # 检查 action 数组外部的 mark_task_complete（错误格式）
                for action_name in [*TASK_STATUS_ACTIONS, 'update_task_status']:
                    if action_name not in parsed_data:
                        continue
                    if isinstance(parsed_data[action_name], dict):
                        parsed_data['action'].append({action_name: parsed_data[action_name]})
                        logger.info(f"🔧 Fixed in TokenCost: moved {action_name} into action array")
                    elif isinstance(parsed_data[action_name], int) and action_name in TASK_STATUS_ACTIONS:
                        task_id = parsed_data[action_name]
                        parsed_data['action'].append({action_name: {'task_id': task_id}})
                        logger.info(f"🔧 Fixed in TokenCost: moved {action_name}(task_id={task_id}) into action array")

                try:
                    from browser_use.agent.message_manager.service import AgentOutput
                    agent_output = AgentOutput.model_construct(
                        thinking=parsed_data.get('thinking'),
                        evaluation_previous_goal=parsed_data.get('evaluation_previous_goal'),
                        memory=parsed_data.get('memory'),
                        next_goal=parsed_data.get('next_goal'),
                        action=[]
                    )
                    action_list = []
                    for action_dict in parsed_data.get('action', []):
                        action_list.append(_ActionWrapper(action_dict))
                    object.__setattr__(agent_output, 'action', action_list)
                except Exception as e:
                    logger.error(f"🔧 Failed to create AgentOutput: {e}")

            class _ResponseWrapper:
                def __init__(self, orig, completion_obj):
                    self._orig = orig
                    self.content = getattr(orig, 'content', '')
                    self.response_metadata = getattr(orig, 'response_metadata', {})
                    self.completion = completion_obj
                    usage = getattr(orig, 'usage', None) or (
                        orig.response_metadata.get('token_usage') if hasattr(orig, 'response_metadata') else None)
                    if not usage: usage = {}
                    # Fix usage
                    usage = dict(usage) if hasattr(usage, '__dict__') else usage
                    usage.setdefault('prompt_tokens', 0)
                    usage.setdefault('completion_tokens', 0)
                    usage.setdefault('total_tokens', 0)
                    self.usage = usage

                def __getattr__(self, name): return getattr(self._orig, name)

            wrapped = _ResponseWrapper(result, agent_output)
            if hasattr(wrapped, 'usage') and wrapped.usage:
                try:
                    _token_service.add_usage(llm.model, wrapped.usage)
                except:
                    pass

            return wrapped

        setattr(llm, 'ainvoke', _fixed_tracked_ainvoke)
        return llm


    TokenCost.register_llm = _patched_register_llm
    logger.info("✅ Successfully patched TokenCost.register_llm")
except Exception as e:
    logger.error(f"❌ Failed to patch TokenCost: {e}")

# Patch BrowserSession.connect (Windows CDP fix)
try:
    from browser_use.browser.session import BrowserSession
    import httpx

    _original_connect = BrowserSession.connect


    async def _patched_connect(self, cdp_url=None):
        if cdp_url: return await _original_connect(self, cdp_url=cdp_url)

        browser_profile = getattr(self, 'browser_profile', None)
        if hasattr(browser_profile, 'cdp_url') and browser_profile.cdp_url:
            return await _original_connect(self, cdp_url=browser_profile.cdp_url)

        port = 9222
        if hasattr(browser_profile, 'extra_chromium_args'):
            for arg in browser_profile.extra_chromium_args:
                if '--remote-debugging-port=' in str(arg):
                    try:
                        port = int(arg.split('=')[1]); break
                    except:
                        pass
        if hasattr(browser_profile, 'remote_debugging_port'):
            port = browser_profile.remote_debugging_port

        cdp_endpoint = f"http://localhost:{port}/json/version"

        for attempt in range(10): # 增加重试次数
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(cdp_endpoint)
                    if response.status_code == 200 and response.text:
                        version_info = response.json()
                        browser_profile.cdp_url = version_info['webSocketDebuggerUrl']
                        return await _original_connect(self, cdp_url=browser_profile.cdp_url)
            except Exception:
                if attempt < 4: await asyncio.sleep(1.0)

        return await _original_connect(self, cdp_url=cdp_url)


    BrowserSession.connect = _patched_connect
    logger.info("✅ Successfully patched BrowserSession.connect")
except Exception as e:
    logger.error(f"❌ Failed to patch BrowserSession.connect: {e}")

# Patch ClickElementAction parameters
try:
    from browser_use.tools.views import ClickElementAction

    _original_click_init = ClickElementAction.__init__


    def _patched_click_init(self, **kwargs):
        fixed_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, int) and key not in ['index']:
                fixed_kwargs['index'] = value
            else:
                fixed_kwargs[key] = value
        if len(kwargs) == 1:
            key, value = list(kwargs.items())[0]
            if isinstance(value, int) and key != 'index':
                fixed_kwargs = {'index': value}
        try:
            return _original_click_init(self, **fixed_kwargs)
        except TypeError:
            if fixed_kwargs and isinstance(list(fixed_kwargs.values())[0], int):
                return _original_click_init(self, **{'index': list(fixed_kwargs.values())[0]})
            raise


    ClickElementAction.__init__ = _patched_click_init
except Exception:
    pass

# Patch ToolRegistry
try:
    from browser_use.tools.registry.service import Registry as ToolRegistry

    # Force patch Registry class
    _original_execute_action = ToolRegistry.execute_action


    async def _patched_execute_action(self, action_name: str, params: dict, **kwargs):
        # 自动映射 switch_tab -> switch (强制映射)
        if action_name == 'switch_tab':
            logger.info(f"🔧 Force aliasing: switch_tab -> switch")
            action_name = 'switch'

        if isinstance(params, int):
            params = {'index': params}
        elif not isinstance(params, dict) and params is not None:
            # 针对 switch_tab 可能是纯字符串的情况
            if action_name in ['switch_tab', 'switch']:
                params = {'tab_id': params}
            else:
                params = {'value': params} if params else {}

        if isinstance(params, dict):
            normalized_params = _normalize_action_params(action_name, params)
            if normalized_params != params:
                logger.info(f"🔧 Normalized action params for {action_name}: {params} -> {normalized_params}")
            params = normalized_params

        # 针对点击增加延迟，确保 UI 更新 (如弹窗弹出、下拉框展开)
        if action_name in ['click_element', 'click']:
            result = await _original_execute_action(self, action_name, params, **kwargs)
            # 增加延迟到 1.5s，并强制在点击后等待浏览器渲染
            # 尤其是对于 element-plus 等 UI 框架，下拉列表渲染需要时间
            await asyncio.sleep(1.5)
            return result

        return await _original_execute_action(self, action_name, params, **kwargs)


    ToolRegistry.execute_action = _patched_execute_action
    logger.info("✅ Successfully patched ToolRegistry.execute_action with alias support")
except Exception as e:
    logger.error(f"❌ Failed to patch ToolRegistry: {e}")

# 全局当前执行模式，供截图看门狗补丁判断是否允许返回占位符。
# 由 BaseBrowserAgent.__init__ 设置。默认 'text' 以保持既有的容错行为。
_CURRENT_EXECUTION_MODE = 'text'

# Patch ScreenshotWatchdog GLOBALLY to fix timeouts
try:
    from browser_use.browser.watchdogs.screenshot_watchdog import ScreenshotWatchdog

    _original_on_screenshot_event = ScreenshotWatchdog.on_ScreenshotEvent

    # Check if already patched to avoid double patching
    if not getattr(_original_on_screenshot_event, '_is_patched_global', False):
        async def on_ScreenshotEvent(self, event):
            """
            Patched screenshot event handler with increased timeout and optimized parameters.
            """
            try:
                # Try original method first with strict timeout
                result = await asyncio.wait_for(
                    _original_on_screenshot_event(self, event),
                    timeout=3.0  # Reduced for fail-fast
                )
                return result
            except asyncio.TimeoutError:
                logger.warning(f"DEBUG: Watchdog timeout (3s), trying optimized approach...")
                try:
                    # Get CDP session
                    cdp_session = await self.browser_session.get_or_create_cdp_session(target_id=None)
                    if not cdp_session: raise Exception("Failed to get CDP session")

                    params = {'format': 'png', 'quality': 50, 'from_surface': True, 'capture_beyond_viewport': False}

                    # One quick retry
                    result = await asyncio.wait_for(
                        cdp_session.cdp_client.send.Page.captureScreenshot(params=params,
                                                                           session_id=cdp_session.session_id),
                        timeout=3.0
                    )
                    return result

                except Exception as ex:
                    # 文本模式下我们不希望因截图失败而中断流程，返回1x1占位符兜底。
                    # 视觉模式依赖真实截图，占位符会让模型"看不见"页面，因此不打占位符补丁，
                    # 而是把异常抛出，让 browser-use 走自身的重试/失败逻辑。
                    if _CURRENT_EXECUTION_MODE != 'text':
                        logger.error(f"DEBUG: Screenshot failed in vision mode, re-raising (no placeholder): {ex}")
                        raise
                    logger.warning(f"DEBUG: Screenshot failed optimized, returning placeholder: {ex}")
                    import base64
                    # 1x1 transparent pixel
                    placeholder = base64.b64decode(
                        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')
                    return {'data': placeholder}
            except Exception as e:
                logger.error(f"DEBUG: Screenshot unexpected error: {e}")
                # 视觉模式不返回占位符，抛出异常保留真实截图行为
                if _CURRENT_EXECUTION_MODE != 'text':
                    raise
                import base64
                placeholder = base64.b64decode(
                    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')
                return {'data': placeholder}


        on_ScreenshotEvent._is_patched_global = True
        ScreenshotWatchdog.on_ScreenshotEvent = on_ScreenshotEvent
        logger.info("✅ Applied Global ScreenshotWatchdog Patch")

    # Patch DOMWatchdog
    from browser_use.browser.watchdogs.dom_watchdog import DOMWatchdog

    _original_capture_clean_screenshot = DOMWatchdog._capture_clean_screenshot

    if not getattr(_original_capture_clean_screenshot, '_is_patched_global', False):
        async def _capture_clean_screenshot(self):
            try:
                # Very short timeout for DOM clean screenshot checks
                return await asyncio.wait_for(_original_capture_clean_screenshot(self), timeout=3.0)
            except Exception as e:
                logger.warning(f"DEBUG: Clean screenshot failed/timed out: {e}, continuing...")
                return None


        _capture_clean_screenshot._is_patched_global = True
        DOMWatchdog._capture_clean_screenshot = _capture_clean_screenshot
        logger.info("✅ Applied Global DOMWatchdog Patch")

except Exception as e:
    logger.error(f"❌ Failed to apply Global Watchdog patches: {e}")

# Patch Agent verdict
try:
    from browser_use.agent.service import Agent
    from browser_use.agent.message_manager.service import AgentOutput

    _original_judge_and_log = Agent._judge_and_log


    def _agent_output_getattr(self, name):
        if name == 'verdict':
            if hasattr(self, 'next_goal') and self.next_goal:
                if any(
                    w in str(self.next_goal).lower() for w in ['complete', 'done', 'finished', 'success']): return True
            if hasattr(self, 'evaluation_previous_goal') and self.evaluation_previous_goal:
                if any(w in str(self.evaluation_previous_goal).lower() for w in ['success', 'complete']): return True
            return False
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


    if not hasattr(AgentOutput, '__getattr__'):
        AgentOutput.__getattr__ = _agent_output_getattr


    async def _patched_judge_and_log(self):
        try:
            return await _original_judge_and_log(self)
        except AttributeError as e:
            if 'verdict' in str(e):
                return None
            raise


    Agent._judge_and_log = _patched_judge_and_log
except Exception:
    pass

# Patch LocalBrowserWatchdog._find_free_port to force port 9222 on Linux
try:
    from browser_use.browser.watchdogs.local_browser_watchdog import LocalBrowserWatchdog
    import platform

    _original_find_free_port = LocalBrowserWatchdog._find_free_port

    # 创建补丁函数 - 始终作为实例方法（接受 self）
    def _patched_find_free_port(self):
        if platform.system() == 'Linux':
            logger.info("🔧 Force using port 9222 for Linux environment")
            return 9222
        # 尝试调用原始方法，兼容不同签名
        try:
            return _original_find_free_port(self)
        except TypeError:
            # 如果原始方法不接受 self，尝试不带参数调用
            return _original_find_free_port()

    LocalBrowserWatchdog._find_free_port = _patched_find_free_port
    logger.info("✅ Successfully patched LocalBrowserWatchdog._find_free_port")
except Exception as e:
    logger.error(f"❌ Failed to patch LocalBrowserWatchdog._find_free_port: {e}")

# ============================================================================
# PART 2: Helper Classes
# ============================================================================

from langchain_core.callbacks import BaseCallbackHandler
from typing import Any


class RawResponseLogger(BaseCallbackHandler):
    def on_llm_new_token(self, token: str, **kwargs: Any) -> Any:
        pass

    def on_llm_end(self, response: Any, **kwargs: Any) -> Any:
        try:
            generation = response.generations[0][0]
            logger.info(f"DEBUG: Raw LLM Response: {generation.text}")
        except:
            pass


# ============================================================================
# PART 3: Base Browser Agent
# ============================================================================

from browser_use import Agent, Controller
from browser_use.browser.events import CloseTabEvent, SwitchTabEvent
from browser_use.browser.profile import BrowserProfile


def _resolve_llm_config_role(execution_mode):
    """
    根据执行模式选择 AIModelConfig 的 role，并返回可用的配置对象。

    - 视觉模式('vision')：优先使用 role='browser_use_vision' 的多模态配置，
      若未配置或未启用，则回退到 role='browser_use_text'。
    - 文本模式('text')：使用 role='browser_use_text'。

    返回 (config_obj, role_name)。config_obj 可能为 None（都没配置时）。
    """
    from apps.requirement_analysis.models import AIModelConfig

    if execution_mode == 'vision':
        config_obj = AIModelConfig.objects.filter(role='browser_use_vision', is_active=True).first()
        if config_obj:
            return config_obj, 'browser_use_vision'
        logger.warning("⚠️ 视觉模式未找到可用的 'browser_use_vision' 配置，回退到 'browser_use_text'")

    config_obj = AIModelConfig.objects.filter(role='browser_use_text', is_active=True).first()
    return config_obj, 'browser_use_text'


class BaseBrowserAgent:
    def __init__(self, execution_mode='text', enable_gif=True, case_name=None):
        # 尊重传入的执行模式，仅接受 'text' / 'vision'，其它值回退为 'text'
        if execution_mode not in ('text', 'vision'):
            logger.warning(f"⚠️ 未知 execution_mode='{execution_mode}'，回退为 'text'")
            execution_mode = 'text'
        self.execution_mode = execution_mode
        self.enable_gif = enable_gif  # GIF录制开关
        self.case_name = case_name or "Adhoc Task"  # 用例名称

        # 记录全局当前执行模式，供全局截图看门狗补丁判断是否返回占位符
        global _CURRENT_EXECUTION_MODE
        _CURRENT_EXECUTION_MODE = self.execution_mode

        # Select Config：按模式选择 LLM 角色（视觉优先 vision，回退 text）
        config_obj, role_name = _resolve_llm_config_role(self.execution_mode)
        logger.info(f"🧠 执行模式={self.execution_mode}，使用 LLM 角色={role_name}")

        model_config = {}
        if config_obj:
            model_config = {
                'api_key': config_obj.api_key,
                'base_url': config_obj.base_url,
                'model_name': config_obj.model_name,
                'provider': config_obj.model_type,
                'temperature': config_obj.temperature  # 读取配置的temperature
            }

        self.api_key = model_config.get('api_key') or os.getenv('AUTH_TOKEN')
        self.base_url = model_config.get('base_url') or os.getenv('BASE_URL')
        self.model_name = model_config.get('model_name') or os.getenv('MODEL_NAME')
        self.provider = model_config.get('provider', 'openai')

        if not self.api_key:
            raise ValueError(f"No API Key found for mode: {execution_mode}")

        # 智能temperature处理：特殊模型强制使用特定temperature值
        # 格式: {'模型名称关键字': temperature值}
        special_model_temperature_map = {
            'kimi-2.5': 1.0,  # Moonshot AI Kimi 2.5 只支持 temperature=1
            'kimi-k2.5': 1.0,  # Moonshot AI Kimi K2.5 只支持 temperature=1
            'kimi': 1.0,  # 通用Kimi模型匹配（兜底）
            # 未来可以在这里添加其他特殊模型，例如：
            # 'claude-3.5-sonnet': 0.7,
            # 'gpt-4-turbo': 0.0,
        }

        # 确定最终使用的temperature值
        final_temperature = 0.0  # 默认值
        model_name_lower = self.model_name.lower()

        # 1. 优先检查是否是特殊模型
        for model_keyword, temp in special_model_temperature_map.items():
            if model_keyword in model_name_lower:
                final_temperature = temp
                logger.info(f"✅ 检测到特殊模型 '{self.model_name}'，使用强制 temperature={temp}")
                break
        else:
            # 2. 如果不是特殊模型，使用配置中的值
            if 'temperature' in model_config:
                final_temperature = model_config['temperature']
                logger.info(f"📋 使用配置的 temperature={final_temperature}")
            else:
                # 3. 如果配置中没有，使用默认值
                final_temperature = 0.0
                logger.info(f"⚙️ 使用默认 temperature={final_temperature}")

        self.llm = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=final_temperature,
            callbacks=[RawResponseLogger()]
        )

        # browser-use requirement
        try:
            object.__setattr__(self.llm, 'provider', self.provider)
            object.__setattr__(self.llm, 'model', self.model_name)
        except:
            if not hasattr(self.llm, '__pydantic_extra__') or self.llm.__pydantic_extra__ is None:
                self.llm.__pydantic_extra__ = {}
            self.llm.__pydantic_extra__['provider'] = self.provider
            self.llm.__pydantic_extra__['model'] = self.model_name

    def _format_action(self, action):
        try:
            action_dict = {}
            if hasattr(action, 'model_dump'):
                action_dict = action.model_dump()
            elif hasattr(action, '_action_dict'):
                action_dict = action._action_dict
            elif hasattr(action, '_dict'):
                action_dict = action._dict
            elif isinstance(action, dict):
                action_dict = action
            else:
                return str(action)

            if not action_dict: return "待机"

            descriptions = []
            for name, params in action_dict.items():
                if not params and name not in ['scroll_down', 'scroll_up', 'done']: continue

                if name in ['go_to_url', 'navigate']:
                    url = params.get('url') if isinstance(params, dict) else params
                    descriptions.append(f"访问: {url}")
                elif name in ['click_element', 'click']:
                    index = params.get('index') if isinstance(params, dict) else params
                    descriptions.append(f"点击[{index}]")
                elif name in ['input_text', 'input']:
                    text = params.get('text') if isinstance(params, dict) else None
                    descriptions.append(f"输入: '{text}'")
                elif name == 'switch_tab':
                    index = params.get('index', params)
                    descriptions.append(f"切换标签 {index}")
                elif name == 'open_new_tab':
                    url = params.get('url', params)
                    descriptions.append(f"新标签打开: {url}")
                elif name == 'close_tab':
                    descriptions.append("关闭当前标签页")
                elif name == 'done':
                    descriptions.append("任务完成")
                else:
                    descriptions.append(f"{name}")
            return " | ".join(descriptions)
        except:
            return "执行操作"

    async def _verify_execution_llm(self):
        """在真正启动执行前做一次轻量连通性检查，避免浏览器启动后反复空转失败。"""
        try:
            await asyncio.wait_for(
                self.llm.ainvoke("Reply with OK."),
                timeout=20.0
            )
        except Exception as e:
            raise RuntimeError(f"Execution LLM unavailable: {e}") from e

    def _extract_structured_steps(self, text: str):
        """从原始任务文本中稳定提取步骤，作为 LLM 拆分失败时的兜底。"""
        if not text:
            return []

        normalized_text = str(text).replace('\r\n', '\n').replace('\r', '\n').strip()
        if not normalized_text:
            return []

        # 优先按行解析显式编号步骤
        numbered_line_pattern = re.compile(r'^\s*(\d+(?:\.\d+)*)[\.\s、:：-]+(.*)$')
        extracted_steps = []
        plain_lines = []

        for raw_line in normalized_text.split('\n'):
            line = raw_line.strip()
            if not line:
                continue
            match = numbered_line_pattern.match(line)
            if match:
                desc = match.group(2).strip()
                if desc:
                    extracted_steps.append(desc)
            else:
                plain_lines.append(line)

        if extracted_steps:
            if len(extracted_steps) == 1 and '\n' not in normalized_text:
                split_inline_text = re.sub(
                    r'\s+(?=\d+(?:\.\d+)*[\.\s、:：-]+)',
                    '\n',
                    normalized_text
                )
                if split_inline_text != normalized_text:
                    inline_steps = self._extract_structured_steps(split_inline_text)
                    if len(inline_steps) > 1:
                        return inline_steps
            return extracted_steps

        # 其次解析单行内多个编号步骤，例如：
        # "1.访问xx 2.搜索xx 3.点击xx"
        split_inline_text = re.sub(
            r'\s+(?=\d+(?:\.\d+)*[\.\s、:：-]+)',
            '\n',
            normalized_text
        )
        if split_inline_text != normalized_text:
            inline_steps = self._extract_structured_steps(split_inline_text)
            if inline_steps:
                return inline_steps

        # 最后退化为逐行文本
        return plain_lines or [normalized_text]

    def _normalize_steps(self, raw_steps, fallback_text: str):
        """清洗并展开步骤列表，避免多步被合并成一条。"""
        steps = raw_steps if isinstance(raw_steps, list) else []
        normalized_steps = []

        for step in steps:
            if step is None:
                continue
            desc = str(step).strip()
            if not desc:
                continue

            # 如果单个 step 里仍然包含多行/多编号步骤，继续拆开
            nested_steps = self._extract_structured_steps(desc)
            if nested_steps and not (len(nested_steps) == 1 and nested_steps[0] == desc):
                normalized_steps.extend(nested_steps)
            else:
                normalized_steps.append(desc)

        if not normalized_steps:
            normalized_steps = self._extract_structured_steps(fallback_text)

        cleaned_steps = []
        for desc in normalized_steps:
            current = str(desc).strip()
            while True:
                match = re.match(r'^\s*\d+(?:\.\d+)*[\.\s、:：-]+(.*)', current, re.S)
                if not match:
                    break
                current = match.group(1).strip()
            if current:
                cleaned_steps.append(current)

        return cleaned_steps or [fallback_text.strip()]

    def _compact_steps(self, steps):
        """合并过细的动作级步骤，收敛为核心业务子任务。"""
        if not steps:
            return []

        compacted = []
        i = 0
        total = len(steps)

        while i < total:
            current = str(steps[i]).strip()
            current_lower = current.lower()

            # 合并“打开浏览器 / 输入URL / 回车访问”这一类导航碎步
            if (
                ('浏览器' in current or 'browser' in current_lower or '地址栏' in current)
                and i + 1 < total
            ):
                window = " ".join(str(s).strip() for s in steps[i:i + 3])
                url_match = re.search(r'https?://[^\s]+', window)
                if url_match:
                    compacted.append(f"访问{url_match.group(0)}")
                    i += min(3, total - i)
                    continue

            # 合并“点击搜索框 / 输入关键词 / 点击搜索 / 等待结果”
            search_window = " ".join(str(s).strip() for s in steps[i:i + 4])
            if any(keyword in search_window for keyword in ['搜索框', '关键词', '百度一下', '搜索结果', 'search']):
                query_match = re.search(r"(?:输入搜索关键词[:：]?\s*|搜索)\s*['\"]?([^'\"\n]+?)['\"]?(?:\s|$)", search_window)
                if query_match:
                    query = query_match.group(1).strip()
                    query = re.sub(r'(并执行搜索|按钮或按下回车键|结果列表加载完成)$', '', query).strip()
                    compacted.append(f"搜索{query}")
                    i += min(4, total - i)
                    continue

            # 合并“点击第N条结果 + 新标签查看详情”
            if any(keyword in current for keyword in ['搜索结果', '结果', '标题链接', '查看详情']):
                if any(keyword in current for keyword in ['第二条', '第2条', '详情', '链接']):
                    compacted.append("点击第2条搜索结果查看详情")
                    i += 1
                    continue

            # 合并关闭标签页相关步骤
            if any(keyword in current for keyword in ['关闭', '标签页', '新标签页', 'close tab']):
                compacted.append("关闭该标签页")
                i += 1
                continue

            compacted.append(current)
            i += 1

        # 去重并保持顺序
        deduped = []
        for step in compacted:
            if not deduped or deduped[-1] != step:
                deduped.append(step)
        return deduped

    def _step_complexity_score(self, step: str) -> int:
        """粗略评估单个步骤是否包含多个动作。"""
        text = str(step).strip()
        if not text:
            return 0

        score = 0
        if len(text) >= 24:
            score += 1
        if len(text) >= 48:
            score += 1
        if any(token in text for token in ['并', '然后', '之后', '再', '并且', '同时', '且']):
            score += 1
        if any(token in text for token in ['点击', '输入', '搜索', '选择', '打开', '关闭', '提交', '保存', '查看', '切换']):
            action_hits = sum(text.count(token) for token in ['点击', '输入', '搜索', '选择', '打开', '关闭', '提交', '保存', '查看', '切换'])
            if action_hits >= 2:
                score += 1
        return score

    def _step_has_specific_requirements(self, step: str) -> bool:
        """判断步骤是否包含必须保留的字面值、断言或字段约束。"""
        text = str(step).strip()
        if not text:
            return False

        signals = 0
        if re.search(r'https?://', text):
            signals += 1
        if any(token in text for token in ['「', '」', '"', "'"]):
            signals += 1
        if re.search(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', text):
            signals += 1
        if re.search(r'\([^)]{2,}\)', text):
            signals += 1
        if any(token in text for token in ['标题为', '返回', '确认页面', '确认', '验证', '校验']):
            signals += 1
        if any(token in text for token in ['输入框', '按钮', '下拉', '单选', '日期', 'Password', 'Text input', 'Dropdown']):
            signals += 1
        return signals >= 2

    def _should_redecompose_explicit_steps(self, steps):
        """判断已编号任务是否复杂到需要模型二次整合。"""
        if not steps:
            return False

        detail_rich_count = sum(1 for step in steps if self._step_has_specific_requirements(step))
        if detail_rich_count >= max(2, len(steps) // 2):
            return False

        if len(steps) >= 10:
            return True

        complex_count = sum(1 for step in steps if self._step_complexity_score(step) >= 2)
        if complex_count >= max(2, len(steps) // 2):
            return True

        very_long_count = sum(1 for step in steps if len(str(step).strip()) >= 40)
        if very_long_count >= max(2, len(steps) // 2):
            return True

        return False

    async def _model_break_down_task(self, task_description: str, mode: str = 'break_down'):
        """调用模型拆分或重整任务步骤。"""
        if mode == 'recompose':
            prompt = (
                "You are given a task that already has numbered steps, but some steps may be too granular or redundant. "
                "Rewrite them into core business steps only. "
                "Rules: keep the original intent and order, merge mechanical browser operations into the surrounding business step, "
                "do not invent new goals, do not split into micro-actions like clicking an input box or waiting for page load. "
                "Preserve every concrete literal requirement from the original steps, including URLs, field labels, option values, dates, expected titles, "
                "expected result text, and quoted content. Do not replace them with vague phrases like '输入文本信息' or '验证成功'. "
                "Return JSON list of concise Chinese strings only.\n\n"
                f"Task:\n{task_description}"
            )
        else:
            prompt = (
                "Break down this task into core business steps only. "
                "Avoid micro-actions like opening the browser, clicking into an input box, or waiting for results unless they are the user's explicit goal. "
                "Preserve every concrete literal requirement from the original task, including URLs, field labels, option values, dates, expected titles, "
                "expected result text, and quoted content. Do not replace them with vague summaries like '输入文本信息' or '验证成功'. "
                "Keep the order and return JSON list of concise Chinese strings only.\n\n"
                f"Task:\n{task_description}"
            )

        response = await self.llm.ainvoke(prompt)
        content = response.content.strip() if hasattr(response, 'content') else str(response)

        steps = []
        try:
            import json
            match = re.search(r'(\[.*\])', content, re.DOTALL)
            if match:
                steps = json.loads(match.group(1))
        except Exception:
            pass

        return steps

    def _finalize_steps(self, steps, fallback_text: str):
        """统一收口步骤列表，保证输出可执行且尽量精简。"""
        return self._compact_steps(self._normalize_steps(steps, fallback_text))

    async def analyze_task(self, task_description: str):
        try:
            explicit_steps = self._extract_structured_steps(task_description)
            if len(explicit_steps) >= 2:
                if self._should_redecompose_explicit_steps(explicit_steps):
                    steps = await self._model_break_down_task(task_description, mode='recompose')
                    cleaned_steps = self._finalize_steps(steps, task_description)
                else:
                    cleaned_steps = self._normalize_steps(explicit_steps, task_description)
                return [{'id': i + 1, 'description': s, 'status': 'pending'} for i, s in enumerate(cleaned_steps)]

            steps = await self._model_break_down_task(task_description, mode='break_down')
            cleaned_steps = self._finalize_steps(steps, task_description)

            return [{'id': i + 1, 'description': s, 'status': 'pending'} for i, s in enumerate(cleaned_steps)]
        except Exception as e:
            logger.warning(f"⚠️ analyze_task fallback triggered: {e}")
            cleaned_steps = self._finalize_steps([], task_description)
            return [{'id': i + 1, 'description': s, 'status': 'pending'} for i, s in enumerate(cleaned_steps)]

    def _cleanup_zombie_chrome(self):
        """Clean up any existing Chrome processes on port 9222 (Linux only)"""
        import platform
        import psutil

        if platform.system() != 'Linux':
            return

        logger.info("🧹 Cleaning up zombie Chrome processes...")
        cleaned_count = 0
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Check for chrome/chromium
                    if proc.info['name'] and ('chrome' in proc.info['name'] or 'chromium' in proc.info['name']):
                        # Check command line for port 9222
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and any('9222' in str(arg) for arg in cmdline):
                            logger.info(f"Killing zombie chrome pid={proc.pid}")
                            proc.kill()
                            cleaned_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception as e:
            logger.warning(f"⚠️ Failed to cleanup zombie chrome: {e}")

        if cleaned_count > 0:
            logger.info(f"✅ Cleaned up {cleaned_count} zombie Chrome processes")

    def _create_browser_profile(self):
        # Default implementation, can be overridden
        chrome_path = None
        import platform

        system = platform.system()
        if system == 'Windows':
            paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
            ]
            for p in paths:
                if os.path.exists(p):
                    chrome_path = p
                    break
        elif system == 'Linux':
            # Linux 系统常见的 Chrome 路径 - 优先使用我们预装的浏览器
            paths = [
                # 优先使用Docker容器中预装的Chromium
                '/usr/bin/chromium-browser',
                '/usr/bin/chromium',
                '/usr/bin/google-chrome',
                # 检查Playwright安装的浏览器
                '/ms-playwright/chromium-*/chromium-linux/chromium',
                '/root/.cache/ms-playwright/chromium-*/chromium-linux/chromium',
                # 备用路径
                '/usr/bin/google-chrome-stable',
                '/opt/google/chrome/chrome',
                '/snap/bin/chromium',
            ]
            for p in paths:
                # 支持通配符路径
                if '*' in p:
                    import glob
                    matches = glob.glob(p)
                    if matches:
                        for match in matches:
                            if os.path.exists(match) and os.access(match, os.X_OK):
                                chrome_path = match
                                logger.info(f"找到浏览器: {chrome_path}")
                                break
                        if chrome_path:
                            break
                elif os.path.exists(p) and os.access(p, os.X_OK):
                    chrome_path = p
                    logger.info(f"找到浏览器: {chrome_path}")
                    break

            # 如果还是没找到，尝试查找Playwright的默认路径或让browser-use自行安装
            if not chrome_path:
                import glob
                playwright_paths = glob.glob('/ms-playwright/**/chromium', recursive=True)
                playwright_paths.extend(glob.glob('/root/.cache/ms-playwright/**/chromium', recursive=True))
                playwright_paths.extend(glob.glob('/ms-playwright/**/chromium-linux/chromium', recursive=True))
                playwright_paths.extend(glob.glob('/root/.cache/ms-playwright/**/chromium-linux/chromium', recursive=True))
                for p in playwright_paths:
                    if os.path.exists(p) and os.access(p, os.X_OK):
                        chrome_path = p
                        logger.info(f"通过Playwright找到浏览器: {chrome_path}")
                        break

                # 最后的备用方案：让browser-use自行处理浏览器安装
                if not chrome_path:
                    logger.info("未找到预装浏览器，将让browser-use自动安装")
                    chrome_path = None  # 让browser-use处理

        # 基础性能优化参数
        extra_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars', '--disable-notifications',
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows',
            '--disable-extensions',
            '--disable-web-security',  # 允许跨域请求
        ]

        # 根据操作系统添加特定参数
        if system == 'Linux':
            # Linux 服务器环境（特别是无头环境）必需的参数
            extra_args.extend([
                '--no-sandbox',  # Linux 必需：禁用沙箱
                '--disable-setuid-sandbox',  # Linux 必需：禁用 setuid 沙箱
                '--disable-dev-shm-usage',  # Linux 必需：使用 /tmp 而不是 /dev/shm
                '--disable-gpu',  # 禁用 GPU 加速（服务器通常无 GPU）
                '--headless=new',  # Linux 服务器使用无头模式
                '--disable-software-rasterizer',  # 禁用软件光栅化器
                '--remote-debugging-port=9222',  # 使用固定端口，避免随机端口导致连接失败
                '--remote-debugging-address=0.0.0.0', # 允许远程连接，而不仅仅是 127.0.0.1
                '--no-zygote',  # 减少进程数
                '--single-process',  # 单进程模式，虽然不稳定但能解决某些 Docker 环境下的 PID 问题
            ])
        else:
            # macOS 和 Windows 使用显示模式
            extra_args.extend([
                '--no-sandbox',  # 兼容性
                '--disable-gpu',
                '--remote-debugging-port=9222',
            ])

        return BrowserProfile(
            headless=(system == 'Linux'),  # Linux 使用无头模式，其他系统使用显示模式
            disable_security=True,
            executable_path=chrome_path,
            args=extra_args,
            wait_for_network_idle_page_load_time=0.2,
            minimum_wait_page_load_time=0.05,
            wait_between_actions=0.1,
            enable_default_extensions=False
        )

    async def run_task(self, task_description: str, planned_tasks=None, callback=None, should_stop=None):
        await self._verify_execution_llm()

        # Cleanup potential zombie processes before starting
        self._cleanup_zombie_chrome()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        controller = Controller()
        _task_was_done = False
        active_task_statuses = {'pending', 'in_progress'}

        async def emit_callback(payload):
            if not callback:
                return

            if asyncio.iscoroutinefunction(callback):
                await callback(payload)
            else:
                callback(payload)

        def is_placeholder_url(url: str) -> bool:
            normalized = (url or '').strip().lower()
            return (
                not normalized
                or normalized == 'about:blank'
                or normalized.startswith('chrome://newtab')
                or normalized.startswith('edge://newtab')
            )

        def is_close_step(description: str) -> bool:
            text = str(description or '').strip()
            return any(keyword in text for keyword in ['关闭', '关闭该标签页', '关闭标签页'])

        def get_next_active_task():
            if not planned_tasks:
                return None

            for task in planned_tasks:
                if task.get('status', 'pending') in active_task_statuses:
                    return task
            return None

        async def find_preferred_fallback_tab(browser_session, exclude_target_id=None):
            tabs = await browser_session.get_tabs()
            candidate_tabs = [tab for tab in tabs if tab.target_id != exclude_target_id]
            if not candidate_tabs:
                return None

            non_placeholder_tabs = [tab for tab in candidate_tabs if not is_placeholder_url(getattr(tab, 'url', ''))]
            return (non_placeholder_tabs or candidate_tabs)[-1]

        @controller.action('Done')
        async def done(success: bool = True, text: str = ""):
            nonlocal _task_was_done
            _task_was_done = True
            return f"Finished: {text}"

        @controller.action('close_tab')
        async def close_tab(browser_session=None):
            if browser_session is None or browser_session.agent_focus_target_id is None:
                raise ValueError("No active tab to close")
            target_id = browser_session.agent_focus_target_id
            fallback_tab = None
            try:
                fallback_tab = await find_preferred_fallback_tab(browser_session, exclude_target_id=target_id)
            except Exception as e:
                logger.warning(f"Failed to determine fallback tab before closing {target_id[-4:]}: {e}")

            event = browser_session.event_bus.dispatch(CloseTabEvent(target_id=target_id))
            await event

            if fallback_tab is not None:
                try:
                    await asyncio.sleep(0.15)
                    if browser_session.agent_focus_target_id != fallback_tab.target_id:
                        await browser_session.event_bus.dispatch(
                            SwitchTabEvent(target_id=fallback_tab.target_id)
                        )
                        logger.info(
                            f"↩️ Switched back to existing tab {fallback_tab.target_id[-4:]} "
                            f"({fallback_tab.url}) after closing {target_id[-4:]}"
                        )
                        await emit_callback({
                            'type': 'log',
                            'content': (
                                f"\n[System]\n关闭标签页后，已切回来源页 {fallback_tab.target_id[-4:]}\n"
                            )
                        })
                except Exception as e:
                    logger.warning(f"Failed to switch back to preferred tab after closing {target_id[-4:]}: {e}")

            next_active_task = get_next_active_task()
            if next_active_task and is_close_step(next_active_task.get('description')):
                logger.info(f"✅ Auto-marking close step task {next_active_task['id']} as completed after close_tab")
                await emit_callback({'task_id': int(next_active_task['id']), 'status': 'completed'})

            return f"Closed tab {target_id[-4:]}"

        @controller.action('mark_task_complete')
        async def mark_task_complete(task_id: int):
            logger.info(f"✅ Explicitly marking task {task_id} as completed")
            try:
                await emit_callback({'task_id': int(task_id), 'status': 'completed'})
            except Exception as e:
                logger.warning(f"Failed to execute mark_task_complete callback: {e}")
            return f"Task {task_id} marked completed"

        @controller.action('mark_task_failed')
        async def mark_task_failed(task_id: int):
            logger.info(f"❌ Explicitly marking task {task_id} as failed")
            try:
                await emit_callback({'task_id': int(task_id), 'status': 'failed'})
            except Exception as e:
                logger.warning(f"Failed to execute mark_task_failed callback: {e}")
            return f"Task {task_id} marked failed"

        @controller.action('mark_task_skipped')
        async def mark_task_skipped(task_id: int):
            logger.info(f"⏭️ Explicitly marking task {task_id} as skipped")
            try:
                await emit_callback({'task_id': int(task_id), 'status': 'skipped'})
            except Exception as e:
                logger.warning(f"Failed to execute mark_task_skipped callback: {e}")
            return f"Task {task_id} marked skipped"

        @controller.action('update_task_status')
        async def update_task_status(task_id: int, status: str):
            normalized_status = str(status).strip().lower()
            if normalized_status not in {'completed', 'failed', 'skipped', 'in_progress'}:
                raise ValueError(f"Unsupported task status: {status}")
            logger.info(f"🔄 Explicitly updating task {task_id} to {normalized_status}")
            try:
                await emit_callback({'task_id': int(task_id), 'status': normalized_status})
            except Exception as e:
                logger.warning(f"Failed to execute update_task_status callback: {e}")
            return f"Task {task_id} marked {normalized_status}"

        # 构建强化版 Prompt
        final_task = task_description
        if planned_tasks:
            final_task += "\n\nIMPORTANT INSTRUCTION:\n"
            final_task += "You have a list of sub-tasks. Execute strictly in order.\n"
            final_task += "CRITICAL: MUST call one of 'mark_task_complete', 'mark_task_failed', 'mark_task_skipped', or 'update_task_status(task_id=..., status=...)' IMMEDIATELY after determining each sub-task result. NEVER skip this step.\n"
            final_task += "IMPORTANT: If a sub-task (like opening a URL) is already fulfilled by the initial state, YOU MUST mark it complete in your VERY FIRST STEP.\n"
            final_task += "Sub-tasks (Execute in order):\n"
            cleaned_tasks = []
            for t in planned_tasks:
                desc = t['description']
                # 递归去除所有层级的重复序号，例如 "1. 1. xxx" -> "xxx"
                while True:
                    match = re.match(r'^\s*\d+[\.\s、:]+(.*)', desc)
                    if not match: break
                    desc = match.group(1).strip()
                cleaned_tasks.append(f"{t['id']}. {desc}")
            final_task += "\n".join(cleaned_tasks)

        # 极限效率版标记指令
        from datetime import datetime
        final_task += f"\n\nCURRENT TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        final_task += "\nCRITICAL PERFORMANCE & SYNC RULES:\n"
        final_task += "1. TASK COMPLETION MARKING RULES:\n"
        final_task += "   a) MARK AFTER COMPLETION: Call 'mark_task_complete(task_id=N)' ONLY AFTER you have SUCCESSFULLY COMPLETED task N.\n"
        final_task += "   b) MARK CURRENT TASK: Always mark the task you just completed, NOT the next task or previous tasks.\n"
        final_task += "   c) CHECK TASK ID: Before marking, verify: 'I just completed task N' - if N is already marked, check which task you actually completed.\n"
        final_task += "   d) DO NOT SKIP: Every sub-task must end with an explicit terminal status update: completed, failed, or skipped.\n"
        final_task += "   e) EXAMPLE SUCCESS: [{click: {...}}, {mark_task_complete: {task_id: 4}}]\n"
        final_task += "   f) EXAMPLE FAILURE: if task 4 cannot be completed after verification, call {mark_task_failed: {task_id: 4}}.\n"
        final_task += "   g) EXAMPLE SKIP: if task 4 is intentionally unnecessary, call {mark_task_skipped: {task_id: 4}}.\n"
        final_task += "   h) NO PRE-MARKING: Never mark a task before completing it. Never mark a task twice.\n"
        final_task += "   i) SINGLE-TASK STEP: If you mark task N in the current step, STOP there. Do NOT start task N+1 in the same step.\n"
        final_task += "   j) FORM EXAMPLE: Good: [{input: {...}}, {mark_task_complete: {task_id: 2}}] then next step handles task 3. Bad: [{mark_task_complete: {task_id: 1}}, {input: {...task 2...}}].\n"
        final_task += "2. NO JAVASCRIPT IN INPUT: When a task asks for a timestamp, YOU MUST compute the final string yourself (e.g., 'V8.01734892400').\n"
        final_task += "   - DO NOT output 'Date.now()' or '{{...}}' strings. Use the CURRENT TIME provided above to estimate a timestamp.\n"
        final_task += "3. DROPDOWN & MODAL ISOLATION: If an action (clicking a button/dropdown) triggers a UI change (modal opens/dropdown expands), YOU MUST STOP and WAIT for the next step to see the new elements. DO NOT attempt to interact with newly appeared elements (like dropdown options) in the same step as the click that opened them.\n"
        final_task += "4. TAB HANDLING: If clicking a link/result opens a new tab, DO NOT click the same result again. Immediately switch to the newest tab, verify the detail page there, then mark the current sub-task complete.\n"
        final_task += "5. ULTRALIGHT THINKING: Keep 'thinking' under 10 words. Just list next actions. Merge multiple INPUTS if they are on the same form, but NEVER merge a UI-opening click with its subsequent interaction. SPEED IS CRITICAL - respond as quickly as possible.\n"
        final_task += "6. FORM VALIDATION & ERROR DETECTION: When filling forms, you MUST:\n"
        final_task += "   a) Check for RED TEXT messages (validation errors) before clicking save/submit\n"
        final_task += "   b) If validation errors exist, COMPLETE ALL MISSING FIELDS first, then retry save\n"
        final_task += "   c) NEVER close a dialog/modal if there are validation errors - complete the form instead\n"
        final_task += "   d) Verify all required fields are filled before attempting to save\n"
        final_task += "   e) Common validation errors: missing required fields (red asterisk or red text), invalid format, etc.\n"
        final_task += "7. RETRY LOGIC: If a previous 'save' or 'submit' failed (e.g., error toast or validation error):\n"
        final_task += "   a) STOP and examine the page for validation errors (red text, error messages)\n"
        final_task += "   b) RE-VERIFY all fields - check dropdowns are actually selected, not just clicked\n"
        final_task += "   c) Re-select dropdowns and re-input text to ensure the form is complete\n"
        final_task += "   d) DO NOT close the dialog - stay and complete all missing fields\n"
        final_task += "   e) Often errors are caused by: missing project selection, unfilled required fields, incorrect format\n"
        final_task += "8. DO NOT REPEAT: If a task is complete, mark it and MOVE ON. Never click the same search result or link twice unless you verified the first click failed.\n"
        final_task += "9. VERIFICATION: Task 15/16 usually require checking the list. Ensure you are on the correct page and the new data is visible before marking complete.\n"
        final_task += "10. ELEMENT IDENTIFICATION: Carefully identify elements before clicking. AVOID clicking 'close' or 'cancel' buttons when filling forms. Check button labels, aria-labels, and icons to ensure you're clicking the correct element.\n"
        final_task += "11. ACTION PARAM FORMAT: For browser actions, always use browser-use native parameter names. Use 'index' for click/input/select actions, use 'text' for typed content, and never use aliases like 'element_id'.\n"
        final_task += "12. CREDENTIALS RULE: NEVER invent, replace, or guess credentials. Only use the username/password explicitly provided in the task. If login keeps failing with an explicit error like '登录失败' or '用户名或密码错误', stop retrying after a small number of attempts and mark the current login task as failed.\n"

        if 'qwen' in self.model_name.lower() or 'deepseek' in self.model_name.lower():
            final_task += "13. EXTREMELY MINIMIZE output tokens for speed. Keep responses as short as possible while maintaining accuracy.\n"

        # 核心修复: 清理 task 长文本中的 URL，防止中文标点紧贴 URL 导致 browser-use 解析错误
        # 例如 "http://localhost:3000，" -> "http://localhost:3000 "
        try:
            # 在中文标点前加空格，避免它们成为 URL 的一部分
            final_task = re.sub(r'(https?://[^\s\u4e00-\u9fa5]+?)(?=[，；。、！])', r'\1 ', final_task)
            logger.info(f"🔧 Optimized task description for URL extraction")
        except:
            pass

        browser_profile = self._create_browser_profile()

        agent = Agent(
            task=final_task,
            llm=self.llm,
            controller=controller,
            browser_profile=browser_profile,
            use_vision=(self.execution_mode == 'vision'),
            max_actions_per_step=10,  # 增加步进密度，减少总步骤数，降低超时风险
            max_retries=1,  # 减少重试次数以提高速度 (从2改为1)
            max_failures=2,  # 减少最大失败次数，避免过长等待 (从默认3改为2)
            llm_timeout=60,  # 设置LLM调用超时为60秒（支持硅基流动等大模型API）
            step_timeout=90,  # 设置每步超时为90秒
            generate_gif=self.enable_gif,  # 根据开关决定是否生成GIF
        )
        agent._task_was_done = False
        agent._pending_status_task_id = None
        agent._pending_status_task_description = None
        agent._auth_failure_task_id = None
        agent._auth_failure_count = 0

        # Callback helper - 添加任务标记跟踪
        last_processed_step = 0
        last_marked_task_id = 0  # 跟踪上一次标记的任务ID
        known_tab_ids = set()

        async def on_step_end(agent_instance):
            nonlocal last_processed_step, last_marked_task_id, known_tab_ids

            if should_stop:
                do_stop = await should_stop() if asyncio.iscoroutinefunction(should_stop) else should_stop()
                if do_stop: raise KeyboardInterrupt("User requested stop")

            if _task_was_done:
                raise KeyboardInterrupt("Done")

            history = getattr(agent_instance, 'history', [])
            if hasattr(history, 'history'): history = history.history

            if len(history) > last_processed_step:
                for i in range(last_processed_step, len(history)):
                    step = history[i]
                    # Log logic here
                    try:
                        actions = []
                        if hasattr(step, 'model_output') and hasattr(step.model_output, 'action'):
                            raw = step.model_output.action
                            actions = raw if isinstance(raw, list) else [raw]

                        current_active_task = get_next_active_task()
                        current_active_task_id = current_active_task.get('id') if current_active_task else None
                        current_active_task_desc = str(current_active_task.get('description', '')) if current_active_task else ''
                        if current_active_task_id and any(keyword in current_active_task_desc.lower() for keyword in ['登录', 'login']):
                            signal_text_parts = []
                            model_output = getattr(step, 'model_output', None)
                            for field_name in ['thinking', 'evaluation_previous_goal', 'memory', 'next_goal']:
                                value = getattr(model_output, field_name, None)
                                if value:
                                    signal_text_parts.append(str(value))

                            if _contains_auth_failure_signal(" ".join(signal_text_parts)):
                                if getattr(agent_instance, '_auth_failure_task_id', None) == current_active_task_id:
                                    agent_instance._auth_failure_count += 1
                                else:
                                    agent_instance._auth_failure_task_id = current_active_task_id
                                    agent_instance._auth_failure_count = 1

                                if agent_instance._auth_failure_count >= 3:
                                    logger.warning(
                                        f"⚠️ Login/auth failure threshold reached for task {current_active_task_id}; marking task failed"
                                    )
                                    await emit_callback({
                                        'type': 'log',
                                        'content': (
                                            f"\n[System]\n检测到登录连续失败 3 次，已自动将子任务 {current_active_task_id} 标记为失败并停止执行。\n"
                                        )
                                    })
                                    await emit_callback({
                                        'task_id': int(current_active_task_id),
                                        'status': 'failed'
                                    })
                                    raise KeyboardInterrupt("Repeated authentication failure")
                            elif getattr(agent_instance, '_auth_failure_task_id', None) == current_active_task_id:
                                agent_instance._auth_failure_count = 0

                        # 检查这一步是否调用了任务状态更新动作
                        step_has_task_complete = False
                        step_marked_task_id = None
                        for action in actions:
                            action_dict = action.model_dump() if hasattr(action, 'model_dump') else getattr(action,
                                                                                                            '_action_dict',
                                                                                                            {})
                            if 'mark_task_complete' in action_dict:
                                step_has_task_complete = True
                                step_marked_task_id = action_dict['mark_task_complete'].get('task_id')
                            elif 'mark_task_failed' in action_dict:
                                step_has_task_complete = True
                                step_marked_task_id = action_dict['mark_task_failed'].get('task_id')
                            elif 'mark_task_skipped' in action_dict:
                                step_has_task_complete = True
                                step_marked_task_id = action_dict['mark_task_skipped'].get('task_id')
                            elif 'update_task_status' in action_dict:
                                step_has_task_complete = True
                                payload = action_dict['update_task_status']
                                step_marked_task_id = payload.get('task_id')

                            if step_has_task_complete:
                                # 检查是否重复标记已完成的任务 - 提示但不自动修复
                                if planned_tasks:
                                    for task in planned_tasks:
                                        if task['id'] == step_marked_task_id and task.get('status') in ['completed', 'failed', 'skipped']:
                                            next_expected = last_marked_task_id + 1
                                            logger.warning(
                                                f"⚠️ Task {step_marked_task_id} is already terminal ({task.get('status')})! "
                                                f"You should mark task {next_expected} instead.")
                                            break
                                last_marked_task_id = step_marked_task_id
                                if getattr(agent_instance, '_pending_status_task_id', None) == step_marked_task_id:
                                    agent_instance._pending_status_task_id = None
                                    agent_instance._pending_status_task_description = None
                                break

                        # 检查这一步是否有实际操作（非mark_task_complete的操作）
                        has_real_action = False
                        has_link_open_action = False
                        for action in actions:
                            action_dict = action.model_dump() if hasattr(action, 'model_dump') else getattr(action,
                                                                                                            '_action_dict',
                                                                                                            {})
                            for key in action_dict.keys():
                                if key not in ['mark_task_complete', 'mark_task_failed', 'mark_task_skipped', 'update_task_status', 'done']:
                                    has_real_action = True
                                if key in ['click', 'open_new_tab', 'navigate', 'go_to_url']:
                                    has_link_open_action = True
                                    break
                            if has_real_action:
                                break

                        action_str = " | ".join([self._format_action(a) for a in actions])
                        log_content = f"\n[Step {i + 1}]\n执行: {action_str}\n"

                        if callback:
                            if asyncio.iscoroutinefunction(callback):
                                await callback({'type': 'log', 'content': log_content})
                            else:
                                callback({'type': 'log', 'content': log_content})

                        browser_session = getattr(agent_instance, 'browser_session', None)
                        if browser_session is not None:
                            try:
                                tabs = await browser_session.get_tabs()
                                current_tab_ids = {tab.target_id for tab in tabs}
                                if not known_tab_ids:
                                    known_tab_ids = current_tab_ids
                                else:
                                    new_tabs = [tab for tab in tabs if tab.target_id not in known_tab_ids]
                                    if new_tabs and has_link_open_action:
                                        newest_tab = new_tabs[-1]
                                        if browser_session.agent_focus_target_id != newest_tab.target_id:
                                            await browser_session.event_bus.dispatch(
                                                SwitchTabEvent(target_id=newest_tab.target_id)
                                            )
                                            logger.info(
                                                f"🔀 Auto-switched to newly opened tab {newest_tab.target_id[-4:]} after link click"
                                            )
                                            if callback:
                                                auto_switch_log = (
                                                    f"\n[System]\n检测到新标签页，已自动切换到 {newest_tab.target_id[-4:]}\n"
                                                )
                                                if asyncio.iscoroutinefunction(callback):
                                                    await callback({'type': 'log', 'content': auto_switch_log})
                                                else:
                                                    callback({'type': 'log', 'content': auto_switch_log})
                                    known_tab_ids = current_tab_ids
                            except Exception as tab_error:
                                logger.warning(f"⚠️ Failed to inspect/switch tabs after step {i + 1}: {tab_error}")

                        # 记录未标记任务的步骤（不自动修复，仅警告）
                        if has_real_action and not step_has_task_complete and planned_tasks:
                            next_expected_task_id = last_marked_task_id + 1
                            if next_expected_task_id <= len(planned_tasks):
                                # 检查这个任务是否还没有被标记
                                task_already_marked = False
                                for task in planned_tasks:
                                    if task['id'] == next_expected_task_id and task.get('status') in ['completed', 'failed', 'skipped']:
                                        task_already_marked = True
                                        last_marked_task_id = next_expected_task_id
                                        break

                                if not task_already_marked:
                                    # 记录警告，提示 AI 标记当前任务
                                    agent_instance._pending_status_task_id = next_expected_task_id
                                    pending_task_description = None
                                    if planned_tasks:
                                        for task in planned_tasks:
                                            if task.get('id') == next_expected_task_id:
                                                pending_task_description = task.get('description')
                                                break
                                    agent_instance._pending_status_task_description = pending_task_description
                                    logger.warning(
                                        f"⚠️ Step {i + 1} had actions but no task status update. "
                                        f"Please mark task {next_expected_task_id} as completed, failed, or skipped.")

                    except Exception as e:
                        logger.warning(f"⚠️ Error in on_step_end processing: {e}")
                last_processed_step = len(history)

        try:
            # Try to pass callback
            import inspect
            sig = inspect.signature(agent.run)
            if 'on_step_end' in sig.parameters:
                await agent.run(max_steps=100, on_step_end=on_step_end)
            else:
                await agent.run(max_steps=100)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            raise

        # 在任务结束时检查不一致的任务状态
        history = getattr(agent, 'history', [])
        if history:
            logger.info("🔍 Performing final task status consistency check")
            # 检查是否有任务执行了但未标记完成
            executed_tasks_info = self._find_executed_tasks(history)
            if (
                executed_tasks_info
                and executed_tasks_info.get('executed_actions', 0) > len(executed_tasks_info.get('marked_tasks', []))
                and executed_tasks_info.get('unmarked_actions')
            ):
                logger.warning(
                    f"⚠️ Found {executed_tasks_info['executed_actions']} executed actions, but only {len(executed_tasks_info['marked_tasks'])} tasks were explicitly marked complete")
                logger.warning(f"⚠️ Unmarked actions: {executed_tasks_info['unmarked_actions']}")
                logger.warning("⚠️ This indicates the AI agent did not follow the 'mark_task_complete' rule properly.")

        return history

    def _find_executed_tasks(self, history):
        """
        通过分析执行历史找出已执行但未标记完成的任务
        """
        if not history or not hasattr(history, 'steps'):
            return []

        executed_actions = {}  # 已执行的操作类型和索引，以及对应的步骤
        marked_tasks = set()  # 已标记完成的任务ID

        # 分析执行历史
        for step_idx, step in enumerate(getattr(history, 'steps', [])):
            # 检查每一步中的actions
            actions = getattr(step, 'actions', [])
            for action in actions:
                # 记录已执行的操作
                if hasattr(action, 'input'):
                    action_key = f"input_{action.input.index}"
                    executed_actions[action_key] = {
                        'step': step_idx,
                        'action': 'input',
                        'index': action.input.index
                    }
                elif hasattr(action, 'click'):
                    action_key = f"click_{action.click.index}"
                    executed_actions[action_key] = {
                        'step': step_idx,
                        'action': 'click',
                        'index': action.click.index
                    }
                elif hasattr(action, 'switch_tab'):
                    action_key = f"switch_tab_{action.switch_tab.tab_id}"
                    executed_actions[action_key] = {
                        'step': step_idx,
                        'action': 'switch_tab',
                        'tab_id': action.switch_tab.tab_id
                    }

                # 记录已标记完成的任务
                if hasattr(action, 'mark_task_complete'):
                    marked_tasks.add(action.mark_task_complete.task_id)

        # 理想情况下应该有一个映射机制来关联操作和任务，但由于我们没有这个映射，
        # 我们只能记录未标记完成的执行操作作为调试信息
        unmarked_actions = []
        for action_key, action_info in executed_actions.items():
            unmarked_actions.append({
                'action': action_info['action'],
                'step': action_info['step'],
                'details': action_key
            })

        return {
            'marked_tasks': list(marked_tasks),
            'executed_actions': len(executed_actions),
            'unmarked_actions': unmarked_actions
        }

    async def run_full_process(self, task_description: str, analysis_callback=None, step_callback=None,
                               should_stop=None):
        planned_tasks = await self.analyze_task(task_description)
        if analysis_callback:
            if asyncio.iscoroutinefunction(analysis_callback):
                await analysis_callback(planned_tasks)
            else:
                analysis_callback(planned_tasks)

        return await self.run_task(task_description, planned_tasks, step_callback, should_stop)
