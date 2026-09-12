# -*- coding: utf-8 -*-
"""
pytest 配置文件
"""
import pytest
import os
import django

# 配置 Django 设置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()


def pytest_addoption(parser):
    """添加命令行选项"""
    parser.addoption("--device-id", action="store", default=None, help="设备ID")
    parser.addoption("--package-name", action="store", default=None, help="应用包名")


@pytest.fixture(scope="session")
def device_id(request):
    """设备ID fixture"""
    return request.config.getoption("--device-id") or os.environ.get('APP_DEVICE_ID')


@pytest.fixture(scope="session")
def package_name(request):
    """应用包名 fixture"""
    return request.config.getoption("--package-name") or os.environ.get('APP_PACKAGE_NAME')


@pytest.fixture(scope="session")
def test_case_id():
    """测试用例ID fixture"""
    return os.environ.get('APP_TEST_CASE_ID')


@pytest.fixture(scope="session")
def execution_id():
    """执行记录ID fixture"""
    return os.environ.get('APP_EXECUTION_ID')


@pytest.fixture(scope="session")
def username():
    """执行用户名 fixture"""
    return os.environ.get('APP_USERNAME', 'unknown')
