# -*- coding: utf-8 -*-
"""
Airtest 基础类 - 提供 Airtest 的基本设置和常用功能
"""
from airtest.core.api import (
    connect_device, ST, G, wait, click, snapshot, 
    init_device, start_app, stop_app, Template, sleep
)
from airtest.core.error import NoDeviceError, TargetNotFoundError
import os
import time
import logging
import threading
import queue
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class AirtestBase:
    """Airtest基础类，提供Airtest的基本设置和常用功能"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        'RETRY_COUNT': 3,
        'RETRY_INTERVAL': 5,
        'DEVICE_CONNECT_TIMEOUT': 30,
        'FIND_TIMEOUT': 10,
        'CLICK_DELAY': 0.5,
    }
    
    def __init__(self, device_id: Optional[str] = None, screenshots_dir: Optional[str] = None, username: Optional[str] = None):
        """
        初始化AirtestBase实例
        
        Args:
            device_id: 设备ID，例如Android设备的adb device ID
            screenshots_dir: 截图目录，如果未提供则使用默认目录
            username: 执行用户名，用于截图目录分组
        """
        self.device_id = device_id
        self.is_connected = False
        
        # 设置截图目录: media/app-automation/screenshots/{username}/
        if screenshots_dir:
            self.screenshots_dir = screenshots_dir
        else:
            self.screenshots_dir = os.path.join(
                settings.MEDIA_ROOT, 'app-automation', 'screenshots', username or 'unknown'
            )
        
        # 确保截图目录存在
        os.makedirs(self.screenshots_dir, exist_ok=True)
        logger.info(f"初始化AirtestBase实例，设备ID: {self.device_id}，截图目录: {self.screenshots_dir}")
    
    def setup_airtest(self, config: Optional[dict] = None) -> bool:
        """
        设置Airtest环境，连接设备
        
        Args:
            config: 配置字典，可选参数包括 RETRY_COUNT, RETRY_INTERVAL, DEVICE_CONNECT_TIMEOUT 等
            
        Returns:
            是否设置成功
        """
        # 合并配置
        cfg = {**self.DEFAULT_CONFIG}
        if config:
            cfg.update(config)
        
        retry_count = cfg['RETRY_COUNT']
        retry_interval = cfg['RETRY_INTERVAL']
        timeout = cfg['DEVICE_CONNECT_TIMEOUT']
        
        for attempt in range(retry_count):
            try:
                if self.device_id:
                    logger.info(f"尝试连接到设备: {self.device_id} (尝试 {attempt+1}/{retry_count})")
                    success = self._init_device_with_timeout(
                        platform='Android',
                        uuid=self.device_id,
                        timeout=timeout
                    )
                else:
                    logger.info(f"尝试连接到默认设备 (尝试 {attempt+1}/{retry_count})")
                    success = self._init_device_with_timeout(
                        platform='Android',
                        timeout=timeout
                    )
                
                if not success:
                    raise RuntimeError("设备连接失败")
                
                # 设置全局超时时间
                ST.FIND_TIMEOUT = cfg['FIND_TIMEOUT']
                if hasattr(ST, 'CLICK_DELAY'):
                    ST.CLICK_DELAY = cfg['CLICK_DELAY']
                
                self.is_connected = True
                logger.info("Airtest环境设置完成，设备已连接")
                return True
                
            except Exception as e:
                logger.error(f"设置Airtest环境时出错: {str(e)}", exc_info=True)
                
                if attempt < retry_count - 1:
                    logger.info(f"{retry_interval}秒后重试连接...")
                    time.sleep(retry_interval)
                else:
                    logger.error(f"经过 {retry_count} 次尝试后，无法连接设备")
                    return False
        
        return False
    
    def _init_device_with_timeout(self, platform: str, uuid: Optional[str] = None, timeout: int = 30) -> bool:
        """
        使用超时机制初始化设备
        
        Args:
            platform: 平台类型，如 'Android'
            uuid: 设备UUID（可选）
            timeout: 超时时间（秒）
            
        Returns:
            是否初始化成功
        """
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def call_init_device():
            try:
                logger.info(f"线程中开始调用 init_device()...")
                if uuid:
                    init_device(platform=platform, uuid=uuid)
                else:
                    init_device(platform=platform)
                logger.info(f"线程中 init_device() 调用完成")
                result_queue.put(True)
            except Exception as e:
                logger.error(f"线程中 init_device() 调用异常: {type(e).__name__}: {e}", exc_info=True)
                exception_queue.put(e)
        
        thread = threading.Thread(target=call_init_device, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            logger.error(f"init_device() 调用超时（{timeout}秒），设备可能无法连接")
            return False
        
        if not exception_queue.empty():
            raise exception_queue.get()
        
        if not result_queue.empty():
            logger.info(f"init_device() 调用完成，设备已连接")
            return True
        else:
            logger.warning(f"init_device() 调用完成，但未收到结果")
            return False
    
    def teardown_airtest(self) -> None:
        """清理Airtest环境，断开设备连接"""
        try:
            self._disconnect_device()
            self.is_connected = False
            logger.info("Airtest环境已清理")
        except Exception as e:
            logger.error(f"清理Airtest环境时出错: {str(e)}", exc_info=True)
    
    def _disconnect_device(self) -> None:
        """断开与设备的连接"""
        try:
            if G.DEVICE:
                G.DEVICE.disconnect()
                self.is_connected = False
                logger.info("设备连接已断开")
        except NoDeviceError:
            logger.info("没有设备连接，无需断开")
        except Exception as e:
            logger.error(f"断开设备连接时出错: {str(e)}", exc_info=True)
    
    def is_device_connected(self) -> bool:
        """
        检查设备是否已连接
        
        Returns:
            设备连接状态
        """
        device_connected = hasattr(G, 'DEVICE') and G.DEVICE is not None
        
        if device_connected != self.is_connected:
            self.is_connected = device_connected
            logger.info(f"设备连接状态更新: {'已连接' if device_connected else '已断开'}")
        
        return device_connected
    
    def screenshot(self, name: str) -> str:
        """
        截取屏幕并保存
        
        Args:
            name: 截图名称
            
        Returns:
            截图路径，失败返回空字符串
        """
        if not self.is_device_connected():
            logger.warning("设备未连接，无法截图")
            return ""
        
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(self.screenshots_dir, f'{name}_{timestamp}.png')
            snapshot(filename=screenshot_path)
            logger.info(f"截图已保存: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            logger.error(f"截图失败: {str(e)}", exc_info=True)
            return ""
    
    def open_app(self, package_name: str, retry_count: int = 3, retry_interval: int = 5) -> bool:
        """
        启动指定包名的应用，包含智能重试机制
        
        Args:
            package_name: 应用包名
            retry_count: 重试次数
            retry_interval: 重试间隔（秒）
            
        Returns:
            是否启动成功
        """
        if not self.is_connected:
            logger.error("设备未连接，无法启动应用")
            return False
        
        for attempt in range(retry_count):
            try:
                logger.info(f"尝试启动应用: {package_name} (尝试 {attempt+1}/{retry_count})")
                start_app(package_name)
                
                # 等待应用启动
                time.sleep(2)
                
                # 验证应用是否真正启动成功
                if self.is_app_running(package_name):
                    logger.info(f"成功启动应用: {package_name}")
                    return True
                else:
                    logger.warning(f"应用 {package_name} 启动后未检测到运行状态")
                
                if attempt < retry_count - 1:
                    logger.info(f"{retry_interval}秒后重试启动应用...")
                    time.sleep(retry_interval)
                    
            except Exception as e:
                logger.error(f"启动应用失败: {str(e)}", exc_info=True)
                if attempt < retry_count - 1:
                    logger.info(f"{retry_interval}秒后重试启动应用...")
                    time.sleep(retry_interval)
        
        logger.error(f"经过 {retry_count} 次尝试后，启动应用 {package_name} 失败")
        return False
    
    def close_app(self, package_name: str) -> bool:
        """
        关闭指定包名的应用
        
        Args:
            package_name: 应用包名
            
        Returns:
            是否关闭成功
        """
        if not self.is_connected:
            logger.warning("设备未连接，无需关闭应用")
            return True
        
        try:
            logger.info(f"尝试关闭应用: {package_name}")
            stop_app(package_name)
            logger.info(f"成功关闭应用: {package_name}")
            return True
        except Exception as e:
            logger.error(f"关闭应用失败: {str(e)}", exc_info=True)
            return False
    
    def is_app_installed(self, package_name: str) -> bool:
        """
        检查指定包名的应用是否已安装
        
        Args:
            package_name: 应用包名
            
        Returns:
            是否已安装
        """
        if not self.is_connected:
            logger.warning("设备未连接，无法检查应用安装状态")
            return False
        
        try:
            result = G.DEVICE.shell(f"pm list packages | grep {package_name}")
            installed = package_name in result
            logger.info(f"应用 {package_name} {'已安装' if installed else '未安装'}")
            return installed
        except Exception as e:
            logger.error(f"检查应用安装状态时出错: {str(e)}", exc_info=True)
            return False
    
    def is_app_running(self, package_name: str) -> bool:
        """
        检查指定包名的应用是否正在运行
        
        Args:
            package_name: 应用包名
            
        Returns:
            是否正在运行
        """
        if not self.is_connected:
            logger.warning("设备未连接，无法检查应用运行状态")
            return False
        
        try:
            # 尝试多种方法检查应用运行状态
            methods = [
                f"pidof {package_name}",
                f"ps | grep {package_name}",
                f"dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp' | grep {package_name}"
            ]
            
            for method in methods:
                try:
                    result = G.DEVICE.shell(method)
                    if result.strip():
                        logger.info(f"应用 {package_name} 正在运行")
                        return True
                except Exception:
                    continue
            
            logger.info(f"应用 {package_name} 未运行")
            return False
        except Exception as e:
            logger.error(f"检查应用运行状态时出错: {str(e)}", exc_info=True)
            return False
