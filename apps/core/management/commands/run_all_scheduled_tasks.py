from django.core.management.base import BaseCommand
from django.utils import timezone
import time
import logging
import sys
import threading

logger = logging.getLogger(__name__)


def dispatch(celery_task, fallback_callable, *args):
    """优先通过 Celery 分发任务；broker 不可用时回退到 threading。

    Args:
        celery_task: 已定义的 Celery task（含 .delay 方法）
        fallback_callable: 无 broker 时在本地线程执行的同步可调用对象
        *args: 传给 celery_task.delay / fallback_callable 的位置参数

    Returns:
        str: 'celery' 表示已通过 Celery 分发，'thread' 表示已回退到线程执行
    """
    try:
        celery_task.delay(*args)
        return 'celery'
    except Exception as e:
        # broker（Redis/kombu）不可用等连接类异常：回退到线程执行，
        # 保证没有 celery worker 时定时任务仍能正常工作。
        logger.warning(f"Celery 分发失败，回退到 threading 执行: {e}")
        thread = threading.Thread(target=fallback_callable, args=args, daemon=True)
        thread.start()
        return 'thread'


class Command(BaseCommand):
    help = '运行所有模块的定时任务调度器（API测试 + UI自动化 + APP自动化）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='检查间隔（秒），默认60秒'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='只执行一次检查，不循环'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        run_once = options['once']

        self.stdout.write(self.style.SUCCESS(f"{'='*60}"))
        self.stdout.write(self.style.SUCCESS("启动统一定时任务调度器"))
        self.stdout.write(self.style.SUCCESS(f"检查间隔: {interval}秒"))
        self.stdout.write(self.style.SUCCESS(f"调度模块: API测试 + UI自动化 + APP自动化"))
        self.stdout.write(self.style.SUCCESS(f"{'='*60}"))

        while True:
            try:
                now = timezone.now()
                self.stdout.write(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] 开始检查任务...")

                # 调度 API 测试模块的定时任务
                api_count = self.schedule_api_tasks()

                # 调度 UI 自动化模块的定时任务
                ui_count = self.schedule_ui_tasks()

                # 调度 APP 自动化模块的定时任务
                app_count = self.schedule_app_tasks()

                total_count = api_count + ui_count + app_count
                if total_count > 0:
                    self.stdout.write(self.style.SUCCESS(f"✓ 本次调度执行了 {total_count} 个任务 (API: {api_count}, UI: {ui_count}, APP: {app_count})"))
                else:
                    self.stdout.write("  没有需要执行的任务")

                if run_once:
                    self.stdout.write(self.style.WARNING("单次执行模式，调度器退出"))
                    break

                self.stdout.write(f"等待 {interval} 秒后进行下一次检查...")
                time.sleep(interval)

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\n\n调度器已停止"))
                break
            except Exception as e:
                logger.error(f"调度器运行出错: {e}", exc_info=True)
                self.stdout.write(self.style.ERROR(f"调度器运行出错: {e}"))
                if run_once:
                    break
                self.stdout.write(f"等待 {interval} 秒后重试...")
                time.sleep(interval)

    def schedule_api_tasks(self):
        """调度 API 测试模块的定时任务"""
        try:
            from apps.api_testing.models import ScheduledTask

            # 获取所有活跃的定时任务
            active_tasks = ScheduledTask.objects.filter(status='ACTIVE')
            executed_count = 0

            # 显示所有活跃任务的调试信息
            if active_tasks.exists():
                now = timezone.now()
                self.stdout.write(f"  [API] 活跃任务数: {active_tasks.count()}")
                for task in active_tasks:
                    if task.next_run_time:
                        time_diff = (task.next_run_time - now).total_seconds()
                        if time_diff > 0:
                            self.stdout.write(f"        - {task.name}: 距下次执行还有 {int(time_diff)} 秒")
                        else:
                            self.stdout.write(f"        - {task.name}: 应该立即执行！")
                    else:
                        self.stdout.write(f"        - {task.name}: 未设置下次执行时间")

            for task in active_tasks:
                if task.should_run_now():
                    self.stdout.write(f"  [API] 执行任务: {task.name}")
                    self.stdout.write(f"       类型: {task.get_task_type_display() if hasattr(task, 'get_task_type_display') else task.task_type}, 触发方式: {task.get_trigger_type_display() if hasattr(task, 'get_trigger_type_display') else task.trigger_type}")
                    try:
                        # 创建执行日志
                        from apps.api_testing.models import TaskExecutionLog
                        execution_log = TaskExecutionLog.objects.create(
                            task=task,
                            status='PENDING'
                        )

                        # 优先通过 Celery 分发，broker 不可用时回退到 threading
                        from apps.api_testing.tasks import execute_scheduled_task, _run_scheduled_task
                        mode = dispatch(
                            execute_scheduled_task,
                            _run_scheduled_task,
                            task.id,
                            execution_log.id,
                        )

                        executed_count += 1
                        self.stdout.write(self.style.SUCCESS(f"    ✓ 任务 {task.name} 已启动 ({mode})"))

                    except Exception as e:
                        logger.error(f"执行API任务 {task.name} 时出错: {e}", exc_info=True)
                        self.stdout.write(self.style.ERROR(f"    ✗ 任务 {task.name} 执行失败: {e}"))

            return executed_count

        except Exception as e:
            logger.error(f"调度API任务时出错: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"[API] 调度失败: {e}"))
            return 0

    def schedule_ui_tasks(self):
        """调度 UI 自动化模块的定时任务"""
        try:
            from apps.ui_automation.models import UiScheduledTask

            # 获取所有活跃的定时任务
            active_tasks = UiScheduledTask.objects.filter(status='ACTIVE')
            executed_count = 0

            # 显示所有活跃任务的调试信息
            if active_tasks.exists():
                now = timezone.now()
                self.stdout.write(f"  [UI]  活跃任务数: {active_tasks.count()}")
                for task in active_tasks:
                    if task.next_run_time:
                        time_diff = (task.next_run_time - now).total_seconds()
                        if time_diff > 0:
                            self.stdout.write(f"        - {task.name}: 距下次执行还有 {int(time_diff)} 秒")
                        else:
                            self.stdout.write(f"        - {task.name}: 应该立即执行！")
                    else:
                        self.stdout.write(f"        - {task.name}: 未设置下次执行时间")

            for task in active_tasks:
                if task.should_run_now():
                    self.stdout.write(f"  [UI]  执行任务: {task.name}")
                    self.stdout.write(f"       类型: {task.get_task_type_display()}, 触发方式: {task.get_trigger_type_display()}")
                    try:
                        # 更新任务执行时间和次数
                        task.last_run_time = timezone.now()
                        task.total_runs += 1
                        # 先保存，确保last_run_time被更新
                        task.save()

                        # 根据任务类型执行不同的逻辑
                        if task.task_type == 'TEST_SUITE':
                            # 执行测试套件
                            if not task.test_suite:
                                self.stdout.write(self.style.ERROR(f"    ✗ 任务 {task.name} 未配置测试套件"))
                                # 即使失败也要重新计算下次运行时间
                                task.refresh_from_db()
                                task.next_run_time = task.calculate_next_run()
                                task.save()
                                continue

                            test_suite = task.test_suite
                            test_case_count = test_suite.suite_test_cases.count()

                            if test_case_count == 0:
                                self.stdout.write(self.style.ERROR(f"    ✗ 任务 {task.name} 的测试套件没有用例"))
                                # 即使失败也要重新计算下次运行时间
                                task.refresh_from_db()
                                task.next_run_time = task.calculate_next_run()
                                task.save()
                                continue

                            # 更新套件执行状态
                            test_suite.execution_status = 'running'
                            test_suite.save()

                            # 优先通过 Celery 分发，broker 不可用时回退到 threading
                            from apps.ui_automation.tasks import execute_ui_suite_task, run_ui_suite
                            mode = dispatch(execute_ui_suite_task, run_ui_suite, task.id)
                            self.stdout.write(f"    UI套件任务分发方式: {mode}")

                        elif task.task_type == 'TEST_CASE':
                            # 执行单个或多个测试用例
                            if not task.test_cases:
                                self.stdout.write(self.style.ERROR(f"    ✗ 任务 {task.name} 未配置测试用例"))
                                # 即使失败也要重新计算下次运行时间
                                task.refresh_from_db()
                                task.next_run_time = task.calculate_next_run()
                                task.save()
                                continue

                            # 获取测试用例
                            from apps.ui_automation.models import TestCase as UiTestCase
                            test_cases_list = UiTestCase.objects.filter(id__in=task.test_cases)

                            if not test_cases_list.exists():
                                self.stdout.write(self.style.ERROR(f"    ✗ 任务 {task.name} 的测试用例不存在"))
                                # 即使失败也要重新计算下次运行时间
                                task.refresh_from_db()
                                task.next_run_time = task.calculate_next_run()
                                task.save()
                                continue

                            test_case_count = test_cases_list.count()
                            self.stdout.write(f"    准备执行 {test_case_count} 个测试用例")

                            # 优先通过 Celery 分发，broker 不可用时回退到 threading
                            from apps.ui_automation.tasks import execute_ui_cases_task, run_ui_cases
                            mode = dispatch(execute_ui_cases_task, run_ui_cases, task.id)
                            self.stdout.write(f"    UI用例任务分发方式: {mode}")

                        executed_count += 1
                        self.stdout.write(self.style.SUCCESS(f"    ✓ 任务 {task.name} 已启动"))

                    except Exception as e:
                        logger.error(f"执行UI任务 {task.name} 时出错: {e}", exc_info=True)
                        self.stdout.write(self.style.ERROR(f"    ✗ 任务 {task.name} 执行失败: {e}"))

            return executed_count

        except Exception as e:
            logger.error(f"调度UI任务时出错: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"[UI] 调度失败: {e}"))
            return 0

    def schedule_app_tasks(self):
        """调度 APP 自动化模块的定时任务"""
        try:
            from apps.app_automation.models import AppScheduledTask, AppTestExecution

            active_tasks = AppScheduledTask.objects.filter(status='ACTIVE')
            executed_count = 0

            if active_tasks.exists():
                now = timezone.now()
                self.stdout.write(f"  [APP] 活跃任务数: {active_tasks.count()}")
                for task in active_tasks:
                    if task.next_run_time:
                        time_diff = (task.next_run_time - now).total_seconds()
                        if time_diff > 0:
                            self.stdout.write(f"        - {task.name}: 距下次执行还有 {int(time_diff)} 秒")
                        else:
                            self.stdout.write(f"        - {task.name}: 应该立即执行！")
                    else:
                        self.stdout.write(f"        - {task.name}: 未设置下次执行时间")

            for task in active_tasks:
                if task.should_run_now():
                    self.stdout.write(f"  [APP] 执行任务: {task.name}")
                    self.stdout.write(f"       类型: {task.get_task_type_display()}, 触发方式: {task.get_trigger_type_display()}")
                    try:
                        # 更新统计
                        task.last_run_time = timezone.now()
                        task.total_runs += 1
                        task.next_run_time = task.calculate_next_run()
                        task.save()

                        device = task.device
                        if not device:
                            self.stdout.write(self.style.ERROR(f"    ✗ 任务 {task.name} 未配置设备"))
                            continue

                        package_name = task.app_package.package_name if task.app_package else ''

                        if task.task_type == 'TEST_SUITE' and task.test_suite:
                            suite_cases = task.test_suite.suite_cases.select_related('test_case').all()
                            if not suite_cases.exists():
                                self.stdout.write(self.style.ERROR(f"    ✗ 套件 {task.test_suite.name} 无用例"))
                                continue

                            executions = []
                            for sc in suite_cases:
                                execution = AppTestExecution.objects.create(
                                    test_case=sc.test_case,
                                    test_suite=task.test_suite,
                                    device=device,
                                    user=task.created_by,
                                    status='pending'
                                )
                                executions.append(execution)

                            task.test_suite.execution_status = 'running'
                            task.test_suite.save(update_fields=['execution_status'])

                            from apps.app_automation.tasks import execute_app_suite_task
                            execute_app_suite_task.delay(
                                suite_id=task.test_suite.id,
                                execution_ids=[e.id for e in executions],
                                package_name=package_name,
                                scheduled_task_id=task.id,
                            )

                        elif task.task_type == 'TEST_CASE' and task.test_case:
                            execution = AppTestExecution.objects.create(
                                test_case=task.test_case,
                                device=device,
                                user=task.created_by,
                                status='pending'
                            )
                            from apps.app_automation.tasks import execute_app_test_task
                            celery_task = execute_app_test_task.delay(
                                execution.id,
                                package_name=package_name,
                                scheduled_task_id=task.id,
                            )
                            execution.task_id = celery_task.id
                            execution.save(update_fields=['task_id'])

                        else:
                            self.stdout.write(self.style.ERROR(f"    ✗ 任务 {task.name} 配置不完整"))
                            continue

                        executed_count += 1
                        self.stdout.write(self.style.SUCCESS(f"    ✓ 任务 {task.name} 已启动"))

                    except Exception as e:
                        logger.error(f"执行APP任务 {task.name} 时出错: {e}", exc_info=True)
                        self.stdout.write(self.style.ERROR(f"    ✗ 任务 {task.name} 执行失败: {e}"))

            return executed_count

        except Exception as e:
            logger.error(f"调度APP任务时出错: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"[APP] 调度失败: {e}"))
            return 0
