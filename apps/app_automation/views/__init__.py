# -*- coding: utf-8 -*-
"""
APP自动化测试 Views 包
"""
from .project_views import AppProjectViewSet
from .config_views import AppConfigViewSet
from .device_views import AppDeviceViewSet
from .element_views import AppElementViewSet
from .component_views import (
    AppComponentViewSet,
    AppCustomComponentViewSet,
    AppComponentPackageViewSet,
)
from .test_case_views import (
    AppPackageViewSet,
    AppTestCaseViewSet,
)
from .execution_views import AppTestExecutionViewSet
from .suite_views import AppTestSuiteViewSet
from .scheduled_task_views import AppScheduledTaskViewSet, AppNotificationLogViewSet
from .dashboard_views import AppDashboardViewSet

__all__ = [
    # 项目管理
    'AppProjectViewSet',
    
    # 配置管理
    'AppConfigViewSet',
    
    # 设备管理
    'AppDeviceViewSet',
    
    # 元素管理
    'AppElementViewSet',
    
    # 组件管理
    'AppComponentViewSet',
    'AppCustomComponentViewSet',
    'AppComponentPackageViewSet',
    
    # 测试用例
    'AppPackageViewSet',
    'AppTestCaseViewSet',
    
    # 测试套件
    'AppTestSuiteViewSet',
    
    # 定时任务
    'AppScheduledTaskViewSet',
    'AppNotificationLogViewSet',
    
    # 执行管理
    'AppTestExecutionViewSet',
    
    # 仪表盘
    'AppDashboardViewSet',
]
