# -*- coding: utf-8 -*-
import subprocess
import logging
import platform

logger = logging.getLogger(__name__)


class DeviceManager:
    """设备管理器 - Android ADB 设备管理"""
    
    def __init__(self, adb_path='adb'):
        self.adb_path = adb_path
        # Don't verify ADB in __init__ to avoid blocking initialization
        # Verification will happen when methods are called
        
        # 设置跨平台的subprocess参数
        self.subprocess_kwargs = {}
        if platform.system() == 'Windows':
            self.subprocess_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    
    def _verify_adb(self):
        """验证ADB是否可用"""
        try:
            result = subprocess.run(
                [self.adb_path, 'version'],
                capture_output=True,
                text=True,
                timeout=5,
                **self.subprocess_kwargs
            )
            if result.returncode != 0:
                logger.warning(f"ADB验证失败: {result.stderr}")
                return False
            logger.info(f"ADB验证成功: {result.stdout.strip()}")
            return True
        except FileNotFoundError:
            logger.error(f"找不到ADB命令: {self.adb_path}")
            raise Exception(f"找不到ADB命令: {self.adb_path}，请检查ADB路径配置")
        except subprocess.TimeoutExpired:
            logger.error("ADB验证超时")
            raise Exception("ADB验证超时，请检查ADB是否正常工作")
        except Exception as e:
            logger.error(f"ADB验证异常: {str(e)}")
            raise
    
    def list_devices(self):
        """
        获取设备列表
        返回: [{'device_id': 'xxx', 'status': 'online', ...}, ...]
        """
        try:
            # Verify ADB is available before running commands
            self._verify_adb()
            
            logger.info(f"执行ADB命令: {self.adb_path} devices -l")
            result = subprocess.run(
                [self.adb_path, 'devices', '-l'],
                capture_output=True,
                text=True,
                timeout=10,
                **self.subprocess_kwargs
            )
            
            if result.returncode != 0:
                logger.error(f"ADB命令执行失败: {result.stderr}")
                raise Exception(f"ADB命令执行失败: {result.stderr}")
            
            logger.info(f"ADB输出: {result.stdout}")
            devices = []
            lines = result.stdout.strip().split('\n')[1:]  # 跳过第一行标题
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('*'):
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    device_id = parts[0]
                    status = 'online' if parts[1] == 'device' else 'offline'
                    
                    # 解析设备信息
                    device_info = {
                        'device_id': device_id,
                        'status': status,
                        'name': None,
                        'android_version': None,
                        'ip_address': None,
                        'port': 5555
                    }
                    
                    # 如果是远程设备，解析IP和端口
                    if ':' in device_id:
                        ip_port = device_id.split(':')
                        device_info['ip_address'] = ip_port[0]
                        device_info['port'] = int(ip_port[1]) if len(ip_port) > 1 else 5555
                    
                    # 获取设备详细信息
                    if status == 'online':
                        try:
                            device_info.update(self.get_device_info(device_id))
                        except Exception:
                            pass
                    
                    devices.append(device_info)
            
            logger.info(f"找到 {len(devices)} 个设备")
            return devices
            
        except subprocess.TimeoutExpired:
            logger.error("ADB命令执行超时")
            raise Exception("ADB命令执行超时")
        except Exception as e:
            logger.error(f"获取设备列表失败: {str(e)}")
            raise Exception(f"获取设备列表失败: {str(e)}")
    
    def get_device_info(self, device_id):
        """
        获取设备详细信息
        """
        info = {}
        
        try:
            # 获取设备名称
            result = subprocess.run(
                [self.adb_path, '-s', device_id, 'shell', 'getprop', 'ro.product.model'],
                capture_output=True,
                text=True,
                timeout=5,
                **self.subprocess_kwargs
            )
            if result.returncode == 0:
                info['name'] = result.stdout.strip()
            
            # 获取Android版本
            result = subprocess.run(
                [self.adb_path, '-s', device_id, 'shell', 'getprop', 'ro.build.version.release'],
                capture_output=True,
                text=True,
                timeout=5,
                **self.subprocess_kwargs
            )
            if result.returncode == 0:
                info['android_version'] = result.stdout.strip()
                
        except Exception as e:
            logger.warning(f"获取设备 {device_id} 详细信息失败: {str(e)}")
        
        return info
    
    def connect_device(self, ip_address, port=5555):
        """
        连接远程设备
        返回: {'device_id': 'xxx', 'status': 'online', ...} 或 None
        """
        try:
            device_address = f"{ip_address}:{port}"
            logger.info(f"连接设备: {device_address}")
            
            # 执行连接命令
            result = subprocess.run(
                [self.adb_path, 'connect', device_address],
                capture_output=True,
                text=True,
                timeout=30,
                **self.subprocess_kwargs
            )
            
            if result.returncode != 0:
                logger.error(f"连接失败: {result.stderr}")
                raise Exception(f"连接失败: {result.stderr}")
            
            # 检查连接结果
            output = result.stdout.strip()
            logger.info(f"连接结果: {output}")
            if 'connected' in output.lower() or 'already connected' in output.lower():
                # 获取设备信息
                device_info = {
                    'device_id': device_address,
                    'status': 'online',
                    'ip_address': ip_address,
                    'port': port,
                    'name': None,
                    'android_version': None
                }
                
                # 获取详细信息
                try:
                    device_info.update(self.get_device_info(device_address))
                except Exception as e:
                    logger.warning(f"获取设备详细信息失败: {str(e)}")
                
                logger.info(f"设备连接成功: {device_info}")
                return device_info
            else:
                logger.error(f"连接失败: {output}")
                raise Exception(f"连接失败: {output}")
                
        except subprocess.TimeoutExpired:
            logger.error("连接超时")
            raise Exception("连接超时，请检查设备网络")
        except Exception as e:
            logger.error(f"连接设备失败: {str(e)}")
            raise Exception(f"连接设备失败: {str(e)}")
    
    def disconnect_device(self, device_id: str) -> bool:
        """
        断开设备连接
        """
        try:
            logger.info(f"断开设备: {device_id}")
            result = subprocess.run(
                [self.adb_path, 'disconnect', device_id],
                capture_output=True,
                text=True,
                timeout=10,
                **self.subprocess_kwargs
            )
            
            success = result.returncode == 0
            if success:
                logger.info(f"设备断开成功: {device_id}")
            else:
                logger.error(f"设备断开失败: {result.stderr}")
            return success
            
        except Exception as e:
            logger.error(f"断开设备失败: {str(e)}")
            return False
