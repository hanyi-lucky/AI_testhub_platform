# -*- coding: utf-8 -*-
"""
测试执行器 - pytest + Allure 集成
"""
import os
import sys
import subprocess
import glob
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class AppTestExecutor:
    """APP测试执行器，封装 pytest 执行逻辑"""
    
    def __init__(self, base_path: Optional[str] = None):
        """
        初始化测试执行器
        
        Args:
            base_path: 基础路径，默认使用 Django BASE_DIR
        """
        if base_path is None:
            self.base_path = settings.BASE_DIR
        else:
            self.base_path = base_path
        
        if not os.path.exists(self.base_path):
            raise ValueError(f"测试项目路径不存在: {self.base_path}")
        
        self._current_process: Optional[subprocess.Popen] = None
        
        logger.info(f"初始化 AppTestExecutor，基础路径: {self.base_path}")
    
    def run_tests(
        self,
        test_case_id: int,
        device_id: str,
        package_name: str,
        execution_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        运行APP测试用例并生成报告
        
        Args:
            test_case_id: 测试用例ID
            device_id: 设备ID
            package_name: 应用包名
            execution_id: 执行记录ID
            username: 执行用户名，用于日志目录分组
            
        Returns:
            执行结果字典
        """
        logger.info(f"开始执行APP测试: test_case_id={test_case_id}, device={device_id}")
        
        original_cwd = os.getcwd()
        
        try:
            # 切换到项目根目录
            os.chdir(self.base_path)
            
            # 准备环境变量
            env = os.environ.copy()
            env['PYTHONPATH'] = self._build_pythonpath()
            env['DJANGO_SETTINGS_MODULE'] = 'backend.settings'
            # 强制子进程使用 UTF-8，避免 Windows 下 gbk 解码错误
            env['PYTHONUTF8'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # 传递执行参数到 pytest
            env['APP_TEST_CASE_ID'] = str(test_case_id)
            env['APP_DEVICE_ID'] = device_id
            env['APP_PACKAGE_NAME'] = package_name
            if execution_id:
                env['APP_EXECUTION_ID'] = str(execution_id)
            if username:
                env['APP_USERNAME'] = username
            
            # Allure 结果目录
            allure_results_dir = self._get_allure_results_dir(execution_id)
            os.makedirs(allure_results_dir, exist_ok=True)
            
            # 构建 pytest 参数
            pytest_args = [
                sys.executable, '-m', 'pytest',
                'apps/app_automation/tests/',  # 测试目录
                '-s', '-v',
                '--alluredir', allure_results_dir,
                '--tb=short',
            ]
            
            logger.info(f"执行命令: {' '.join(pytest_args)}")
            logger.info(f"工作目录: {os.getcwd()}")
            logger.info(f"PYTHONPATH: {env['PYTHONPATH']}")
            
            # 执行 pytest
            process = subprocess.Popen(
                pytest_args,
                cwd=self.base_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='ignore',
                bufsize=1,
                env=env
            )
            
            self._current_process = process
            
            # 准备日志文件
            log_file_path = self._get_log_file_path(username or 'unknown')
            
            # 收集输出并写入日志文件
            output_lines = []
            important_patterns = ['PASSED', 'FAILED', 'ERROR', 'SKIPPED', 'collected', 'passed', 'failed']
            
            log_file = open(log_file_path, 'a', encoding='utf-8')
            try:
                log_file.write(f"\n{'='*80}\n")
                log_file.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                              f"执行记录 ID: {execution_id}, 用例 ID: {test_case_id}, "
                              f"设备: {device_id}\n")
                log_file.write(f"{'='*80}\n")
                
                if process.stdout:
                    for line in process.stdout:
                        line = line.rstrip()
                        if line:
                            output_lines.append(line)
                            log_file.write(line + '\n')
                            if any(pattern in line for pattern in important_patterns):
                                logger.info(f"[pytest] {line}")
                
                log_file.write(f"\n[执行完毕]\n")
            finally:
                log_file.close()
            
            logger.info(f"执行日志已保存: {log_file_path}")
            
            # 等待执行完成
            exit_code = process.wait()
            self._current_process = None
            
            logger.info(f"pytest 执行完成，退出码: {exit_code}")
            
            # 解析测试结果
            test_results = self._parse_allure_results(allure_results_dir)
            
            # 生成 Allure 报告
            report_path = self._generate_allure_report(execution_id)
            
            return {
                'success': exit_code == 0,
                'exit_code': exit_code,
                'report_path': report_path,
                'test_results': test_results,
                'output': '\n'.join(output_lines[-50:]),  # 保留最后50行输出
            }
            
        except Exception as e:
            logger.error(f"执行测试失败: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
            }
        finally:
            os.chdir(original_cwd)
    
    def _get_log_file_path(self, username: str) -> str:
        """生成日志文件路径: logs/app_automation/{username}/{日期}.log"""
        today = datetime.now().strftime('%Y-%m-%d')
        log_dir = os.path.join(
            str(self.base_path), 'logs', 'app_automation', username
        )
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, f'{today}.log')
    
    def _build_pythonpath(self) -> str:
        """构建 PYTHONPATH 环境变量"""
        python_path_parts = [
            str(self.base_path),
            os.path.join(str(self.base_path), 'apps'),
        ]
        
        # 添加 sys.path 中的路径
        for p in sys.path:
            if p and os.path.exists(str(p)) and str(p) not in python_path_parts:
                p_str = str(p)
                if 'site-packages' in p_str or not p_str.endswith('.exe'):
                    python_path_parts.append(p_str)
        
        return os.pathsep.join(python_path_parts)
    
    def _get_allure_results_dir(self, execution_id: Optional[int] = None) -> str:
        """获取 Allure 结果目录: media/app-automation/allure-results/"""
        base_dir = os.path.join(settings.MEDIA_ROOT, 'app-automation', 'allure-results')
        
        if execution_id:
            return os.path.join(base_dir, f'execution_{execution_id}')
        
        return base_dir
    
    def _get_allure_report_dir(self, execution_id: Optional[int] = None) -> str:
        """获取 Allure 报告目录: media/app-automation/allure-reports/"""
        base_dir = os.path.join(settings.MEDIA_ROOT, 'app-automation', 'allure-reports')
        
        if execution_id:
            return os.path.join(base_dir, f'execution_{execution_id}')
        
        return base_dir
    
    def _generate_allure_report(self, execution_id: Optional[int] = None) -> Optional[str]:
        """
        生成 Allure 报告
        
        Args:
            execution_id: 执行记录ID
            
        Returns:
            报告目录路径，失败返回 None
        """
        try:
            allure_results_dir = self._get_allure_results_dir(execution_id)
            report_dir = self._get_allure_report_dir(execution_id)
            
            # 确保目录存在
            os.makedirs(report_dir, exist_ok=True)
            
            # 查找 allure 命令
            allure_path = self._find_allure_command()
            
            if not allure_path:
                logger.warning("未找到 Allure 命令，跳过报告生成")
                return None
            
            # 生成报告
            cmd = [allure_path, 'generate', allure_results_dir, '-o', report_dir, '--clean']
            
            logger.info(f"生成 Allure 报告: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info(f"Allure 报告生成成功: {report_dir}")
                return report_dir
            else:
                logger.error(f"Allure 报告生成失败: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Allure 报告生成超时")
            return None
        except Exception as e:
            logger.error(f"生成 Allure 报告失败: {str(e)}", exc_info=True)
            return None
    
    def _find_allure_command(self) -> Optional[str]:
        """查找项目内置的 Allure 命令"""
        import platform
        
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        if platform.system() == 'Windows':
            builtin_allure = base_dir / 'allure' / 'bin' / 'allure.bat'
        else:
            builtin_allure = base_dir / 'allure' / 'bin' / 'allure'
        
        if builtin_allure.exists():
            logger.info(f"使用项目内置 Allure: {builtin_allure}")
            return str(builtin_allure)
        
        logger.warning("未找到项目内置 Allure，请确认 allure 目录存在")
        return None
    
    def _parse_allure_results(self, results_dir: str) -> Dict[str, Any]:
        """
        解析 Allure 测试结果
        
        Args:
            results_dir: Allure 结果目录
            
        Returns:
            测试结果统计
        """
        try:
            # 查找所有测试结果文件
            result_files = glob.glob(os.path.join(results_dir, '*-result.json'))
            
            total = 0
            passed = 0
            failed = 0
            skipped = 0
            
            for result_file in result_files:
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        status = data.get('status', '').lower()
                        total += 1
                        
                        if status == 'passed':
                            passed += 1
                        elif status == 'failed':
                            failed += 1
                        elif status == 'skipped':
                            skipped += 1
                            
                except Exception as e:
                    logger.warning(f"解析结果文件失败: {result_file}, 错误: {e}")
            
            logger.info(f"测试结果统计: 总数={total}, 通过={passed}, 失败={failed}, 跳过={skipped}")
            
            return {
                'total': total,
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
            }
            
        except Exception as e:
            logger.error(f"解析 Allure 结果失败: {str(e)}", exc_info=True)
            return {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'skipped': 0,
            }
    
    def calculate_progress(self, execution_id: Optional[int] = None) -> int:
        """
        计算测试进度
        
        Args:
            execution_id: 执行记录ID
            
        Returns:
            进度百分比 (0-100)
        """
        try:
            results_dir = self._get_allure_results_dir(execution_id)
            
            if not os.path.exists(results_dir):
                return 0
            
            result_files = glob.glob(os.path.join(results_dir, '*-result.json'))
            
            if not result_files:
                return 0
            
            # 简单估算：每有一个结果文件，进度增加
            # 实际应用中可以根据总步骤数来计算
            file_count = len(result_files)
            progress = min(file_count * 10, 100)  # 假设有10个步骤
            
            return progress
            
        except Exception as e:
            logger.error(f"计算进度失败: {str(e)}")
            return 0
    
    def stop(self):
        """停止当前执行的测试"""
        if self._current_process:
            try:
                self._current_process.terminate()
                self._current_process.wait(timeout=5)
                logger.info("测试执行已停止")
            except subprocess.TimeoutExpired:
                self._current_process.kill()
                logger.warning("测试执行被强制终止")
            except Exception as e:
                logger.error(f"停止测试失败: {str(e)}")
            finally:
                self._current_process = None
