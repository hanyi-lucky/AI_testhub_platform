import logging
import asyncio
from .ai_base import BaseBrowserAgent

logger = logging.getLogger('django')

class BrowserAgent(BaseBrowserAgent):
    """
    Browser Agent，支持文本模式与视觉模式。
    执行模式由 execution_mode 参数决定，透传给 BaseBrowserAgent：
      - 'text'：纯文本 DOM 模式（use_vision=False）
      - 'vision'：视觉模式（use_vision=True，需要多模态 LLM）
    """
    def __init__(self, execution_mode='text', enable_gif=True, case_name=None):
        super().__init__(execution_mode=execution_mode, enable_gif=enable_gif, case_name=case_name)

# ============================================================================
# EXPORTED FUNCTIONS (FACTORY)
# ============================================================================

def get_agent_class(execution_mode='text'):
    # 目前文本与视觉模式共用同一实现，模式差异由 execution_mode 参数在运行时体现
    return BrowserAgent

def run_ai_task_sync(task_description: str, planned_tasks=None, callback=None, should_stop=None, execution_mode='text'):
    agent = BrowserAgent(execution_mode=execution_mode)
    return asyncio.run(agent.run_task(task_description, planned_tasks, callback, should_stop))

def analyze_task_sync(task_description: str, execution_mode='text'):
    agent = BrowserAgent(execution_mode=execution_mode)
    return asyncio.run(agent.analyze_task(task_description))

def run_full_process_sync(task_description: str, analysis_callback=None, step_callback=None, should_stop=None, execution_mode='text', enable_gif=True, case_name=None):
    logger.info(f"DEBUG: Entering run_full_process_sync with execution_mode={execution_mode}, enable_gif={enable_gif}")

    agent = BrowserAgent(execution_mode=execution_mode, enable_gif=enable_gif, case_name=case_name)

    logger.info(f"DEBUG: Agent created successfully ({type(agent).__name__}), starting asyncio.run")
    return asyncio.run(agent.run_full_process(task_description, analysis_callback, step_callback, should_stop))
