# -*- coding: utf-8 -*-
"""
API测试模块 Celery 任务

包装 utils.execute_test_suite / utils.execute_api_request，
用于定时任务（ScheduledTask）的异步执行。

与 views.ScheduledTaskViewSet._execute_task_async 的逻辑保持一致：
  - 更新 TaskExecutionLog 状态
  - 执行套件/请求
  - 更新任务统计
  - 发送通知（复用 ScheduledTaskViewSet._send_notification）
"""
from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def _run_scheduled_task(task_id, execution_log_id):
    """执行定时任务的核心逻辑（同步）。

    该函数既被 Celery task 调用，也可作为 threading fallback 的目标。

    Args:
        task_id: ScheduledTask 的 ID
        execution_log_id: TaskExecutionLog 的 ID
    """
    from .models import ScheduledTask, TaskExecutionLog
    from .utils import execute_test_suite, execute_api_request

    try:
        task = ScheduledTask.objects.get(id=task_id)
    except ScheduledTask.DoesNotExist:
        logger.error(f"定时任务不存在: {task_id}")
        return

    try:
        execution_log = TaskExecutionLog.objects.get(id=execution_log_id)
    except TaskExecutionLog.DoesNotExist:
        logger.error(f"执行日志不存在: {execution_log_id}")
        return

    logger.info(f"=== 开始执行API定时任务: {task.name} (task_id={task_id}) ===")

    try:
        # 更新执行状态
        execution_log.status = 'RUNNING'
        execution_log.start_time = timezone.now()
        execution_log.save()

        # 执行任务
        if task.task_type == 'TEST_SUITE':
            result = execute_test_suite(task.test_suite, task.environment, task.created_by)
        elif task.task_type == 'API_REQUEST':
            result = execute_api_request(task.api_request, task.environment, task.created_by)
        else:
            raise ValueError(f"未知的任务类型: {task.task_type}")

        # 更新执行结果
        execution_log.status = 'COMPLETED'
        execution_log.end_time = timezone.now()
        execution_log.result = result
        execution_log.save()

        # 更新任务统计
        task.update_run_stats(success=True)
        task.last_result = result
        task.save()

        _maybe_send_notification(task, execution_log, success=True)

        logger.info(f"API定时任务执行完成: {task.name}")

    except Exception as e:
        logger.error(f"API定时任务执行失败: {task.name}: {e}", exc_info=True)

        execution_log.status = 'FAILED'
        execution_log.end_time = timezone.now()
        execution_log.error_message = str(e)
        execution_log.save()

        # 更新任务统计
        task.update_run_stats(success=False)
        task.error_message = str(e)
        task.save()

        _maybe_send_notification(task, execution_log, success=False)


def _maybe_send_notification(task, execution_log, success):
    """根据任务通知设置发送通知，复用 views 里的 _send_notification 逻辑。"""
    try:
        notification_setting = None
        if hasattr(task, 'notification_settings'):
            notification_setting = task.notification_settings.first()

        if not (notification_setting and notification_setting.is_enabled):
            logger.info("通知设置未启用或不存在，跳过通知")
            return

        should = notification_setting.notify_on_success if success else notification_setting.notify_on_failure
        if not should:
            logger.info(f"通知设置中未启用{'成功' if success else '失败'}通知")
            return

        # 复用 ScheduledTaskViewSet 的通知实现
        from .views import ScheduledTaskViewSet
        ScheduledTaskViewSet()._send_notification(task, execution_log, success=success)
    except Exception as e:
        logger.error(f"发送API定时任务通知失败: {e}", exc_info=True)


@shared_task
def execute_scheduled_task(task_id, execution_log_id):
    """
    异步执行 API 定时任务（套件或单个请求）。

    Args:
        task_id: ScheduledTask 的 ID
        execution_log_id: TaskExecutionLog 的 ID
    """
    _run_scheduled_task(task_id, execution_log_id)
