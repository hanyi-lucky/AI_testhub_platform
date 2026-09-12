# -*- coding: utf-8 -*-
"""
UI自动化模块 Celery 任务

包装 TestExecutor，用于 UI 定时任务（UiScheduledTask）的异步执行。
与 core/management/commands/run_all_scheduled_tasks.py 中原 threading 逻辑保持一致：
  - 执行测试套件 / 测试用例
  - 更新任务统计与下次运行时间
  - 发送通知（复用 UiScheduledTaskViewSet._send_task_notification）
"""
from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def _maybe_send_ui_notification(task, success):
    """根据任务通知设置发送通知，复用 UiScheduledTaskViewSet._send_task_notification。"""
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

        from apps.ui_automation.views import UiScheduledTaskViewSet
        UiScheduledTaskViewSet()._send_task_notification(task, success=success)
    except Exception as e:
        logger.error(f"发送UI定时任务通知失败: {e}", exc_info=True)


def run_ui_suite(task_id):
    """执行 UI 测试套件（同步）。既被 Celery task 调用，也作为 threading fallback 的目标。"""
    from apps.ui_automation.models import UiScheduledTask
    from apps.ui_automation.test_executor import TestExecutor

    try:
        task = UiScheduledTask.objects.get(id=task_id)
    except UiScheduledTask.DoesNotExist:
        logger.error(f"UI定时任务不存在: {task_id}")
        return

    test_suite = task.test_suite
    if not test_suite:
        logger.error(f"UI定时任务 {task.name} 未配置测试套件")
        task.refresh_from_db()
        task.next_run_time = task.calculate_next_run()
        task.save()
        return

    test_case_count = test_suite.suite_test_cases.count()
    if test_case_count == 0:
        logger.error(f"UI定时任务 {task.name} 的测试套件没有用例")
        task.refresh_from_db()
        task.next_run_time = task.calculate_next_run()
        task.save()
        return

    # 更新套件执行状态
    test_suite.execution_status = 'running'
    test_suite.save()

    try:
        executor = TestExecutor(
            test_suite=test_suite,
            engine=task.engine,
            browser=task.browser,
            headless=task.headless,
            executed_by=task.created_by,
        )
        executor.run()

        task.refresh_from_db()
        task.successful_runs += 1
        task.last_result = {'status': 'success', 'test_case_count': test_case_count}
        task.next_run_time = task.calculate_next_run()
        task.save()

        logger.info(f"UI定时任务 {task.name} 执行成功")
        _maybe_send_ui_notification(task, success=True)

    except Exception as e:
        logger.error(f"UI定时任务 {task.name} 执行失败: {e}", exc_info=True)
        task.refresh_from_db()
        task.failed_runs += 1
        task.error_message = str(e)
        task.last_result = {'status': 'failed', 'error': str(e)}
        task.next_run_time = task.calculate_next_run()
        task.save()
        _maybe_send_ui_notification(task, success=False)


def run_ui_cases(task_id):
    """执行 UI 测试用例（同步，可多个）。既被 Celery task 调用，也作为 threading fallback。"""
    from apps.ui_automation.models import UiScheduledTask, TestCase as UiTestCase, TestSuite
    from apps.ui_automation.test_executor import TestExecutor

    try:
        task = UiScheduledTask.objects.get(id=task_id)
    except UiScheduledTask.DoesNotExist:
        logger.error(f"UI定时任务不存在: {task_id}")
        return

    if not task.test_cases:
        logger.error(f"UI定时任务 {task.name} 未配置测试用例")
        task.refresh_from_db()
        task.next_run_time = task.calculate_next_run()
        task.save()
        return

    test_cases_list = UiTestCase.objects.filter(id__in=task.test_cases)
    if not test_cases_list.exists():
        logger.error(f"UI定时任务 {task.name} 的测试用例不存在")
        task.refresh_from_db()
        task.next_run_time = task.calculate_next_run()
        task.save()
        return

    test_case_count = test_cases_list.count()
    success_count = 0
    failed_count = 0
    results = []

    for test_case in test_cases_list:
        temp_suite = None
        try:
            temp_suite = TestSuite.objects.create(
                project=task.project,
                name=f"[临时] {test_case.name}",
            )
            temp_suite.test_cases.add(test_case)
            temp_suite.execution_status = 'running'
            temp_suite.save()

            executor = TestExecutor(
                test_suite=temp_suite,
                engine=task.engine,
                browser=task.browser,
                headless=task.headless,
                executed_by=task.created_by,
            )
            executor.run()

            temp_suite.refresh_from_db()
            suite_executions = temp_suite.executions.all()
            if suite_executions.exists():
                last_execution = suite_executions.first()
                if last_execution.status == 'SUCCESS':
                    success_count += 1
                    results.append({'case_id': test_case.id, 'case_name': test_case.name, 'status': 'success'})
                else:
                    failed_count += 1
                    results.append({
                        'case_id': test_case.id, 'case_name': test_case.name,
                        'status': 'failed', 'error': last_execution.error_message,
                    })
        except Exception as e:
            logger.error(f"执行测试用例 {test_case.name} 失败: {e}")
            failed_count += 1
            results.append({
                'case_id': test_case.id, 'case_name': test_case.name,
                'status': 'failed', 'error': str(e),
            })
        finally:
            if temp_suite:
                temp_suite.delete()

    task.refresh_from_db()
    task.successful_runs += 1
    task.last_result = {
        'status': 'success' if failed_count == 0 else 'partial_success',
        'test_case_count': test_case_count,
        'success_count': success_count,
        'failed_count': failed_count,
        'results': results,
    }
    task.next_run_time = task.calculate_next_run()
    task.save()

    logger.info(f"UI定时任务 {task.name} 执行完成: 成功{success_count}, 失败{failed_count}")
    _maybe_send_ui_notification(task, success=(failed_count == 0))


@shared_task
def execute_ui_suite_task(task_id):
    """异步执行 UI 测试套件定时任务。"""
    run_ui_suite(task_id)


@shared_task
def execute_ui_cases_task(task_id):
    """异步执行 UI 测试用例定时任务。"""
    run_ui_cases(task_id)
