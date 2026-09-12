"""
数据工厂API视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from django.contrib.auth.models import User
from django.db.models import Q, Count
from django.utils import timezone
from django.http import HttpResponse
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import sync_to_async
import asyncio

import logging
from pathlib import Path

from .models import DataFactoryRecord
from .serializers import DataFactoryRecordSerializer, ToolExecuteSerializer
from .tool_list import get_categories, get_tool_list
from .tools.string_tools import StringTools
from .tools.encoding_tools import EncodingTools
from .tools.random_tools import RandomTools
from .tools.encryption_tools import EncryptionTools
from .tools.test_data_tools import TestDataTools
from .tools.json_tools import JsonTools
from .tools.crontab_tools import CrontabTools
from .tools.image_tools import ImageTools

logger = logging.getLogger(__name__)

class DataFactoryPagination(PageNumberPagination):
    """数据工厂自定义分页"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class DataFactoryViewSet(viewsets.ModelViewSet):
    """数据工厂视图集"""
    queryset = DataFactoryRecord.objects.all()
    serializer_class = DataFactoryRecordSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = DataFactoryPagination

    def get_queryset(self):
        """获取当前用户的记录"""
        return DataFactoryRecord.objects.filter(user=self.request.user).only(
            'id', 'user', 'tool_name', 'tool_category', 'tool_scenario',
            'input_data', 'output_data', 'is_saved', 'tags', 'created_at', 'updated_at'
        ).order_by('-created_at')

    def filter_queryset(self, queryset):
        """自定义过滤逻辑，支持JSONField的过滤"""
        # 支持tags字段的过滤（JSONField）
        tags_contains = self.request.query_params.get('tags__contains')
        if tags_contains:
            queryset = queryset.filter(tags__contains=tags_contains)

        # 支持tool_name的模糊查询
        tool_name_icontains = self.request.query_params.get('tool_name__icontains')
        if tool_name_icontains:
            queryset = queryset.filter(tool_name__icontains=tool_name_icontains)

        # 支持tool_category的精确过滤
        tool_category = self.request.query_params.get('tool_category')
        if tool_category:
            queryset = queryset.filter(tool_category=tool_category)

        return queryset

    def list(self, request, *args, **kwargs):
        """重写list方法以正确处理分页"""
        try:
            # 生成缓存键，忽略时间戳参数
            query_params = request.query_params.copy()
            query_params.pop('_t', None)  # 移除时间戳参数
            
            cache_key = f'data_factory_history_{request.user.id}_{query_params.get("page", 1)}_{query_params.get("page_size", 10)}_{query_params.get("tool_category", "")}_{query_params.get("tool_name__icontains", "")}_{query_params.get("tags__contains", "")}'
            
            # 检查缓存，但如果有时间戳参数则不使用缓存
            if '_t' not in request.query_params:
                cached_data = cache.get(cache_key)
                if cached_data:
                    return Response(cached_data)
            
            # 获取并过滤查询集
            queryset = self.get_queryset()
            queryset = self.filter_queryset(queryset)
            
            # 分页处理
            page = self.paginate_queryset(queryset)
            if page is not None:
                # 序列化数据
                serializer = self.get_serializer(page, many=True)
                serializer_data = serializer.data
                
                # 获取分页响应
                paginated_response = self.get_paginated_response(serializer_data)
                
                # 缓存结果，3分钟过期
                if '_t' not in request.query_params:
                    cache.set(cache_key, paginated_response.data, 180)
                
                return paginated_response
            
            serializer = self.get_serializer(queryset, many=True)
            serializer_data = serializer.data
            return Response(serializer_data)
        except Exception as e:
            logger.error(f'列表方法错误: {str(e)}', exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        """执行工具并保存结果"""
        serializer = ToolExecuteSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            result = self.execute_tool(
                data['tool_name'],
                data['tool_category'],
                data['input_data']
            )

            if 'error' in result:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)

            if data.get('is_saved', True):
                try:
                    # 创建记录
                    record = DataFactoryRecord.objects.create(
                        user=request.user,
                        tool_name=data['tool_name'],
                        tool_category=data['tool_category'],
                        tool_scenario=data['tool_scenario'],
                        input_data=data['input_data'],
                        output_data=result,
                        is_saved=data.get('is_saved', True),
                        tags=data.get('tags', None)
                    )
                    result['record_id'] = str(record.id)
                    result['created_at'] = record.created_at.isoformat()
                    
                    # 清除相关缓存
                    self.clear_user_cache(request.user.id)
                except Exception as e:
                    return Response({'error': f'保存记录失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response(result, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """删除数据工厂记录"""
        try:
            logger.info(f'开始删除记录: ID={kwargs.get("pk")}, 用户ID={request.user.id}')
            # 使用self.get_object()获取记录，它会自动处理权限过滤
            instance = self.get_object()
            logger.info(f'成功获取记录: ID={instance.id}, 用户ID={instance.user.id}')
            
            # 删除记录
            instance.delete()
            logger.info(f'成功删除记录: ID={kwargs.get("pk")}')
            
            # 清除相关缓存
            self.clear_user_cache(request.user.id)
            logger.info(f'成功清除缓存: 用户ID={request.user.id}')
            
            return Response({'message': '删除成功'}, status=status.HTTP_200_OK)
        except DataFactoryRecord.DoesNotExist:
            logger.error(f'记录不存在: ID={kwargs.get("pk")}, 用户ID={request.user.id}')
            return Response({'error': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f'删除记录失败: {str(e)}, ID={kwargs.get("pk")}, 用户ID={request.user.id}', exc_info=True)
            return Response({'error': f'删除失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def clear_user_cache(self, user_id):
        """清除用户相关的缓存"""
        # 清除统计信息缓存
        cache.delete(f'data_factory_statistics_{user_id}')
        # 清除标签缓存
        cache.delete(f'data_factory_tags_{user_id}')
        # 清除历史记录缓存
        try:
            # 遍历所有缓存键，删除与当前用户相关的历史记录缓存
            if hasattr(cache, '_cache'):
                # 对于LocMemCache
                keys_to_delete = []
                for key in cache._cache:
                    # 匹配包含 data_factory_history 和用户ID的缓存键
                    if 'data_factory_history' in key and str(user_id) in key:
                        keys_to_delete.append(key)
                for key in keys_to_delete:
                    cache.delete(key)
            elif hasattr(cache, 'keys'):
                # 对于支持keys()方法的缓存后端
                for key in cache.keys():
                    # 匹配包含 data_factory_history 和用户ID的缓存键
                    if 'data_factory_history' in key and str(user_id) in key:
                        cache.delete(key)
        except Exception as e:
            logger.error(f'清除历史记录缓存失败: {str(e)}')
        # 历史记录缓存会在3分钟后自动过期（作为备份）

    def execute_tool(self, tool_name: str, tool_category: str, input_data: dict):
        """执行工具"""
        try:
            logger.info(f'开始执行工具: {tool_name}, 分类: {tool_category}, 输入数据: {input_data}')
            
            # 字符工具
            if tool_category == 'string':
                result = self.execute_string_tool(tool_name, input_data)
            # 编码工具
            elif tool_category == 'encoding':
                result = self.execute_encoding_tool(tool_name, input_data)
            # 随机工具
            elif tool_category == 'random':
                result = self.execute_random_tool(tool_name, input_data)
            # 加密工具
            elif tool_category == 'encryption':
                result = self.execute_encryption_tool(tool_name, input_data)
            # 测试数据（包含测试数据和Mock数据）
            elif tool_category == 'test_data':
                if tool_name.startswith('mock_'):
                    result = self.execute_mock_tool(tool_name, input_data)
                else:
                    result = self.execute_test_data_tool(tool_name, input_data)
            # JSON工具
            elif tool_category == 'json':
                result = self.execute_json_tool(tool_name, input_data)
            # Crontab工具
            elif tool_category == 'crontab':
                result = self.execute_crontab_tool(tool_name, input_data)
            else:
                error_msg = f'不支持的工具分类: {tool_category}'
                logger.error(error_msg)
                return {'error': error_msg}
            
            logger.info(f'工具执行完成: {tool_name}, 结果: {"成功" if "error" not in result else "失败"}')
            return result
        except Exception as e:
            error_msg = f'工具执行失败: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {'error': error_msg}

    def execute_string_tool(self, tool_name: str, input_data: dict | str):
        """执行字符工具"""
        tool_mapping = {
            'remove_whitespace': StringTools.remove_whitespace,
            'replace_string': StringTools.replace_string,
            'escape_string': StringTools.escape_string,
            'unescape_string': StringTools.unescape_string,
            'word_count': StringTools.word_count,
            'text_diff': StringTools.text_diff,
            'regex_test': StringTools.regex_test,
            'case_convert': StringTools.case_convert,
            'string_format': StringTools.string_format
        }

        if tool_name not in tool_mapping:
            return {'error': f'不支持的字符工具: {tool_name}'}
        # 如果 input_data 是字符串，包装为 {'text': input_data}
        if isinstance(input_data, str):
            if tool_name in ['remove_whitespace', 'word_count', 'text_diff', 'string_format']:
                input_data = {'text': input_data}
            elif tool_name == 'regex_test':
                # 需要pattern和text，尝试解析
                input_data = {'pattern': input_data, 'text': ''}
            elif tool_name in ['case_convert']:
                input_data = {'text': input_data, 'convert_type': 'upper'}
            else:
                input_data = {'text': input_data}

        return tool_mapping[tool_name](**input_data)

    def execute_encoding_tool(self, tool_name: str, input_data: dict | str):
        """执行编码工具"""
        tool_mapping = {
            'generate_barcode': EncodingTools.generate_barcode,
            'generate_qrcode': EncodingTools.generate_qrcode,
            'decode_qrcode': EncodingTools.decode_qrcode,
            'timestamp_convert': EncodingTools.timestamp_convert,
            'base_convert': EncodingTools.base_convert,
            'unicode_convert': EncodingTools.unicode_convert,
            'ascii_convert': EncodingTools.ascii_convert,
            'color_convert': EncodingTools.color_convert,
            'base64_encode': EncodingTools.base64_encode,
            'base64_decode': EncodingTools.base64_decode,
            'url_encode': EncodingTools.url_encode,
            'url_decode': EncodingTools.url_decode,
            'jwt_decode': EncodingTools.jwt_decode,
            'image_to_base64': ImageTools.image_to_base64,
            'base64_to_image': ImageTools.base64_to_image
        }

        if tool_name not in tool_mapping:
            return {'error': f'不支持的编码工具: {tool_name}'}

        # 处理字符串输入
        if isinstance(input_data, str):
            if tool_name == 'timestamp_convert':
                input_data = {'timestamp': input_data, 'convert_type': 'to_datetime'}
            elif tool_name in ['base_convert', 'unicode_convert', 'ascii_convert', 'color_convert']:
                input_data = {'text': input_data}
            elif tool_name in ['base64_encode', 'base64_decode']:
                input_data = {'text': input_data, 'encoding': 'utf-8'}
            elif tool_name in ['url_encode', 'url_decode']:
                input_data = {'data': input_data, 'encoding': 'utf-8'}
            elif tool_name == 'jwt_decode':
                input_data = {'token': input_data, 'verify': False}
            elif tool_name in ['generate_barcode', 'generate_qrcode']:
                input_data = {'data': input_data}
            elif tool_name == 'decode_qrcode':
                input_data = {'image_data': input_data, 'image_format': 'png'}
            elif tool_name == 'image_to_base64':
                input_data = {'image_data': input_data, 'image_format': 'png', 'include_prefix': True}
            elif tool_name == 'base64_to_image':
                input_data = {'base64_str': input_data}
            else:
                input_data = {'text': input_data}
        return tool_mapping[tool_name](**input_data)

    def execute_random_tool(self, tool_name: str, input_data: dict | str):
        """执行随机工具"""
        tool_mapping = {
            'random_int': RandomTools.random_int,
            'random_float': RandomTools.random_float,
            'random_string': RandomTools.random_string,
            'random_uuid': RandomTools.random_uuid,
            'random_mac_address': RandomTools.random_mac_address,
            'random_ip_address': RandomTools.random_ip_address,
            'random_date': RandomTools.random_date,
            'random_boolean': RandomTools.random_boolean,
            'random_color': RandomTools.random_color,
            'random_password': RandomTools.random_password,
            'random_sequence': RandomTools.random_sequence
        }

        if tool_name not in tool_mapping:
            return {'error': f'不支持的随机工具: {tool_name}'}
        # 处理字符串输入 - 大部分随机工具不需要输入，直接返回空字典
        if isinstance(input_data, str):
            if tool_name == 'random_int':
                input_data = {'min_val': 1, 'max_val': 100, 'count': 1}
            elif tool_name == 'random_float':
                input_data = {'min_val': 0.0, 'max_val': 1.0, 'precision': 2, 'count': 1}
            elif tool_name == 'random_string':
                input_data = {'length': 8, 'char_type': 'all', 'count': 1}
            elif tool_name == 'random_uuid':
                input_data = {'version': 4, 'count': 1}
            elif tool_name == 'random_mac_address':
                input_data = {'separator': ':', 'count': 1}
            elif tool_name == 'random_ip_address':
                input_data = {'ip_version': 4, 'count': 1}
            elif tool_name == 'random_date':
                input_data = {'start_date': '2024-01-01', 'end_date': '2024-12-31', 'count': 1}
            elif tool_name == 'random_boolean':
                input_data = {'count': 1}
            elif tool_name == 'random_color':
                input_data = {'format': 'hex', 'count': 1}
            elif tool_name == 'random_password':
                input_data = {'length': 12, 'include_uppercase': True, 'include_lowercase': True,
                              'include_digits': True, 'include_special': True}
            elif tool_name == 'random_sequence':
                input_data = {'sequence': [], 'count': 1, 'unique': False}
            else:
                input_data = {'count': 1}
        return tool_mapping[tool_name](**input_data)

    def execute_encryption_tool(self, tool_name: str, input_data: dict | str):
        """执行加密工具"""
        tool_mapping = {
            'md5_hash': EncryptionTools.md5_hash,
            'sha1_hash': EncryptionTools.sha1_hash,
            'sha256_hash': EncryptionTools.sha256_hash,
            'sha512_hash': EncryptionTools.sha512_hash,
            'hash_comparison': EncryptionTools.hash_comparison,
            'aes_encrypt': EncryptionTools.aes_encrypt,
            'aes_decrypt': EncryptionTools.aes_decrypt,
            'password_strength': EncryptionTools.password_strength,
            'generate_salt': EncryptionTools.generate_salt
        }

        if tool_name not in tool_mapping:
            return {'error': f'不支持的加密工具: {tool_name}'}
        # 处理字符串输入
        if isinstance(input_data, str):
            if tool_name in ['md5_hash', 'sha1_hash', 'sha256_hash', 'sha512_hash',
                             'password_strength', 'generate_salt']:
                input_data = {'text': input_data}
            elif tool_name == 'hash_comparison':
                input_data = {'text': input_data, 'hash_value': ''}
            elif tool_name in ['aes_encrypt', 'aes_decrypt']:
                input_data = {'text': input_data, 'password': 'default_password', 'mode': 'CBC'}
            else:
                input_data = {'text': input_data}
        return tool_mapping[tool_name](**input_data)

    def execute_test_data_tool(self, tool_name: str, input_data: dict | str):
        """执行测试数据工具"""
        tool_mapping = {
            'generate_chinese_name': TestDataTools.generate_chinese_name,
            'generate_chinese_phone': TestDataTools.generate_chinese_phone,
            'generate_chinese_email': TestDataTools.generate_chinese_email,
            'generate_chinese_address': TestDataTools.generate_chinese_address,
            'generate_id_card': TestDataTools.generate_id_card,
            'generate_company_name': TestDataTools.generate_company_name,
            'generate_bank_card': TestDataTools.generate_bank_card,
            'generate_user_profile': TestDataTools.generate_user_profile,
            'generate_hk_id_card': TestDataTools.generate_hk_id_card,
            'generate_business_license': TestDataTools.generate_business_license,
            'generate_coordinates': TestDataTools.generate_coordinates
        }

        if tool_name not in tool_mapping:
            return {'error': f'不支持的测试数据工具: {tool_name}'}
        # 处理字符串输入 - 测试数据工具大部分不需要输入参数
        if isinstance(input_data, str):
            if tool_name in ['generate_chinese_name', 'generate_chinese_phone', 'generate_chinese_email',
                             'generate_chinese_address', 'generate_id_card', 'generate_company_name',
                             'generate_bank_card', 'generate_hk_id_card', 'generate_business_license',
                             'generate_coordinates']:
                input_data = {'count': 1}
            elif tool_name == 'generate_user_profile':
                input_data = {'count': 1}
            else:
                input_data = {'count': 1}
        return tool_mapping[tool_name](**input_data)

    def execute_json_tool(self, tool_name: str, input_data: dict | str):
        """执行JSON工具"""
        tool_mapping = {
            'format_json': JsonTools.format_json,
            'validate_json': JsonTools.validate_json,
            'json_to_xml': JsonTools.json_to_xml,
            'xml_to_json': JsonTools.xml_to_json,
            'json_to_yaml': JsonTools.json_to_yaml,
            'yaml_to_json': JsonTools.yaml_to_json,
            'json_diff_enhanced': JsonTools.json_diff_enhanced,
            'jsonpath_query': JsonTools.jsonpath_query,
            'json_path_list': JsonTools.json_path_list,
            'json_flatten': JsonTools.json_flatten
        }

        if tool_name not in tool_mapping:
            return {'error': f'不支持的JSON工具: {tool_name}'}

        # 处理字符串输入
        if isinstance(input_data, str):
            if tool_name in ['format_json', 'validate_json', 'json_to_xml', 'json_to_yaml', 'json_path_list',
                             'json_flatten']:
                input_data = {'json_str': input_data}
            elif tool_name == 'xml_to_json':
                input_data = {'xml_str': input_data}
            elif tool_name == 'yaml_to_json':
                input_data = {'yaml_str': input_data}
            elif tool_name == 'json_diff_enhanced':
                input_data = {'json_str1': input_data, 'json_str2': ''}
            elif tool_name == 'jsonpath_query':
                input_data = {'json_str': input_data, 'jsonpath_expr': ''}
            else:
                input_data = {'json_str': input_data}
        return tool_mapping[tool_name](**input_data)

    def execute_mock_tool(self, tool_name: str, input_data: dict | str):
        """执行Mock数据工具"""
        tool_mapping = {
            'mock_string': JsonTools.mock_data,
            'mock_number': JsonTools.mock_data,
            'mock_boolean': JsonTools.mock_data,
            'mock_email': JsonTools.mock_data,
            'mock_phone': JsonTools.mock_data,
            'mock_date': JsonTools.mock_data,
            'mock_datetime': JsonTools.mock_data,
            'mock_name': JsonTools.mock_data,
            'mock_address': JsonTools.mock_data,
            'mock_url': JsonTools.mock_data,
            'mock_uuid': JsonTools.mock_data,
            'mock_ip': JsonTools.mock_data
        }

        if tool_name not in tool_mapping:
            return {'error': f'不支持的Mock工具: {tool_name}'}

        data_type = tool_name.replace('mock_', '')

        if isinstance(input_data, str):
            input_data = {'data_type': data_type, 'count': 1}
        else:
            input_data['data_type'] = data_type

        return tool_mapping[tool_name](**input_data)

    def execute_crontab_tool(self, tool_name: str, input_data: dict | str):
        """执行Crontab工具"""
        tool_mapping = {
            'generate_expression': CrontabTools.generate_expression,
            'parse_expression': CrontabTools.parse_expression,
            'get_next_runs': CrontabTools.get_next_runs,
            'validate_expression': CrontabTools.validate_expression
        }

        if tool_name not in tool_mapping:
            return {'error': f'不支持的Crontab工具: {tool_name}'}

        if isinstance(input_data, str):
            if tool_name == 'generate_expression':
                input_data = {'minute': '*', 'hour': '*', 'day': '*', 'month': '*', 'weekday': '*'}
            elif tool_name == 'parse_expression':
                input_data = {'expression': input_data}
            elif tool_name == 'get_next_runs':
                input_data = {'expression': input_data, 'count': 10}
            elif tool_name == 'validate_expression':
                input_data = {'expression': input_data}
            else:
                input_data = {'expression': input_data}
        return tool_mapping[tool_name](**input_data)

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """获取所有工具分类"""
        try:
            # 生成缓存键（分类数据是静态的，不需要用户ID）
            cache_key = 'data_factory_categories'
            
            # 检查缓存
            cached_categories = cache.get(cache_key)
            if cached_categories:
                return Response(cached_categories)
            
            # 获取分类数据
            categories = get_categories()
            
            # 为每个分类添加工具列表
            tool_list = get_tool_list()
            for category in categories:
                category['tools'] = [tool for tool in tool_list if tool['scenario'] == category['scenario']]
            
            categories_data = {
                'categories': categories,
                'total_tools': sum(len(cat['tools']) for cat in categories)
            }
            
            # 缓存结果，30分钟过期（分类数据很少变化）
            cache.set(cache_key, categories_data, 1800)
            
            return Response(categories_data)
        except Exception as e:
            logger.error(f'获取分类列表失败: {str(e)}', exc_info=True)
            return Response(
                {'error': f'获取分类列表失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def tags(self, request):
        """获取所有标签列表"""
        try:
            # 生成缓存键
            cache_key = f'data_factory_tags_{request.user.id}'
            
            # 检查缓存
            cached_tags = cache.get(cache_key)
            if cached_tags:
                return Response(cached_tags)
            
            # 同步获取标签，获取当前用户的所有记录
            queryset = DataFactoryRecord.objects.filter(user=request.user)
            
            # 获取所有唯一的标签
            tag_set = set()
            for record in queryset:
                if record.tags and isinstance(record.tags, list):
                    tag_set.update(record.tags)
            
            tags = sorted(list(tag_set))
            
            # 缓存结果，5分钟过期
            cache_data = {
                'tags': tags,
                'count': len(tags)
            }
            cache.set(cache_key, cache_data, 300)

            return Response(cache_data)
        except Exception as e:
            return Response(
                {'error': f'获取标签列表失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def batch_generate(self, request):
        """批量生成数据"""
        tool_name = request.data.get('tool_name')
        tool_category = request.data.get('tool_category')
        tool_scenario = request.data.get('tool_scenario')
        count = request.data.get('count', 10)
        input_data = request.data.get('input_data', {})

        if not tool_name or not tool_category:
            return Response(
                {'error': '缺少必要参数: tool_name 或 tool_category'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 检查是否适合缓存（如随机工具不适合缓存）
        import hashlib
        import json
        non_cacheable_tools = ['random_', 'mock_']
        is_cacheable = not any(tool_name.startswith(prefix) for prefix in non_cacheable_tools)
        
        if is_cacheable:
            # 生成缓存键
            cache_key = f'data_factory_batch_{tool_name}_{tool_category}_{count}_{hashlib.md5(json.dumps(input_data, sort_keys=True).encode()).hexdigest()}'
            
            # 检查缓存
            cached_result = cache.get(cache_key)
            if cached_result:
                # 如果需要保存记录
                if request.data.get('is_saved', True):
                    try:
                        # 创建记录
                        record = DataFactoryRecord.objects.create(
                            user=request.user,
                            tool_name=tool_name,
                            tool_category=tool_category,
                            tool_scenario=tool_scenario,
                            input_data=input_data,
                            output_data={'results': cached_result['results'], 'count': len(cached_result['results'])},
                            is_saved=True
                        )
                        # 清除相关缓存
                        self.clear_user_cache(request.user.id)
                    except Exception as e:
                        logger.error(f'保存记录失败: {str(e)}', exc_info=True)
                        pass  # 保存失败不影响返回结果
                return Response(cached_result)

        # 批量生成
        results = []
        for i in range(count):
            result = self.execute_tool(tool_name, tool_category, input_data)
            if 'error' not in result:
                results.append(result)

        # 构建响应数据
        response_data = {
            'results': results,
            'count': len(results),
            'total_requested': count
        }

        # 缓存结果（如果适合缓存）
        if is_cacheable:
            # 设置缓存，5分钟过期
            cache.set(cache_key, response_data, 300)

        # 保存记录
        if request.data.get('is_saved', True):
            # 创建记录
            record = DataFactoryRecord.objects.create(
                user=request.user,
                tool_name=tool_name,
                tool_category=tool_category,
                tool_scenario=tool_scenario,
                input_data=input_data,
                output_data={'results': results, 'count': len(results)},
                is_saved=True
            )
            # 清除相关缓存
            self.clear_user_cache(request.user.id)

        return Response(response_data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取使用统计"""
        # 生成缓存键
        cache_key = f'data_factory_statistics_{request.user.id}'
        
        # 检查缓存
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)
        
        # 预计算映射
        category_map = dict(DataFactoryRecord.TOOL_CATEGORIES)
        scenario_map = dict(DataFactoryRecord.TOOL_SCENARIOS)
        
        # 1. 计算总记录数（使用聚合查询）
        total_records = DataFactoryRecord.objects.filter(
            user=request.user
        ).count()
        
        # 2. 按分类统计（使用聚合查询）
        category_stats = {}
        category_counts = DataFactoryRecord.objects.filter(
            user=request.user
        ).values('tool_category').annotate(count=Count('tool_category')).order_by()
        
        for item in category_counts:
            cat_name = item['tool_category']
            cat_display = category_map.get(cat_name, cat_name)
            category_stats[cat_display] = item['count']
        
        # 确保所有分类都有统计数据
        for cat_name, cat_display in DataFactoryRecord.TOOL_CATEGORIES:
            if cat_display not in category_stats:
                category_stats[cat_display] = 0
        
        # 3. 按场景统计（使用聚合查询）
        scenario_stats = {}
        scenario_counts = DataFactoryRecord.objects.filter(
            user=request.user
        ).values('tool_scenario').annotate(count=Count('tool_scenario')).order_by()
        
        for item in scenario_counts:
            sce_name = item['tool_scenario']
            sce_display = scenario_map.get(sce_name, sce_name)
            scenario_stats[sce_display] = item['count']
        
        # 确保所有场景都有统计数据
        for sce_name, sce_display in DataFactoryRecord.TOOL_SCENARIOS:
            if sce_display not in scenario_stats:
                scenario_stats[sce_display] = 0
        
        # 4. 获取最近使用的工具（只选择需要的字段）
        recent_tools = []
        recent_records = DataFactoryRecord.objects.filter(
            user=request.user
        ).only(
            'tool_name', 'tool_category', 'tool_scenario', 'created_at'
        ).order_by('-created_at')[:10]
        
        for record in recent_records:
            recent_tools.append({
                'tool_name': record.tool_name,
                'tool_category_display': record.get_tool_category_display(),
                'tool_scenario_display': record.get_tool_scenario_display(),
                'created_at': record.created_at
            })
        
        # 构建响应数据
        stats_data = {
            'total_records': total_records,
            'category_stats': category_stats,
            'scenario_stats': scenario_stats,
            'recent_tools': recent_tools
        }
        
        # 缓存结果，5分钟过期
        cache.set(cache_key, stats_data, 300)
        
        return Response(stats_data)

    @action(detail=False, methods=['get'])
    def download_static_file(self, request):
        """
        下载static_files/img目录下的文件
        用于条形码和二维码的下载和预览
        """
        filename = request.query_params.get('filename')

        if not filename:
            return Response(
                {'error': '缺少必要参数: filename'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 调用工具类验证文件
        result = EncodingTools.download_static_file(filename)

        if 'error' in result:
            return Response(
                {'error': result['error']},
                status=status.HTTP_404_NOT_FOUND
            )

        # 读取文件内容
        file_path = Path(result['file_path'])

        try:
            # 同步读取文件
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # 根据文件扩展名确定MIME类型
            mime_types = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.svg': 'image/svg+xml',
                '.bmp': 'image/bmp',
                '.webp': 'image/webp'
            }

            file_ext = file_path.suffix.lower()
            content_type = mime_types.get(file_ext, 'application/octet-stream')

            # 返回文件内容
            response = HttpResponse(file_content, content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = str(len(file_content))

            return response
        except Exception as e:
            return Response(
                {'error': f'文件读取失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def variable_functions(self, request):
        """获取所有变量函数列表（用于变量助手）
        
        返回格式：
        [
            {
                'name': 'random_int',
                'syntax': '${random_int(min, max, count)}',
                'desc': '生成随机整数',
                'example': '${random_int(100, 999, 1)}'
                'category': '随机数'
            },
            ...
        ]
        """
        # 生成缓存键（变量函数列表是静态的）
        cache_key = 'data_factory_variable_functions'
        
        # 检查缓存
        cached_functions = cache.get(cache_key)
        if cached_functions:
            return Response(cached_functions)
        
        # 获取变量函数列表
        tool_list = get_tool_list()
        logger.info(f'获取到工具列表，共 {len(tool_list)} 个工具')
        
        # 定义工具函数的语法模板
        syntax_templates = {
            # 随机工具
            'random_int': '${random_int(min, max, count)}',
            'random_float': '${random_float(min, max, precision, count)}',
            'random_digits': '${random_digits(length, count)}',
            'random_string': '${random_string(length, char_type, count)}',
            'random_letters': '${random_letters(length, count)}',
            'random_chinese': '${random_chinese(length, count)}',
            'random_uuid': '${random_uuid(version, count)}',
            'random_guid': '${random_guid(version, count)}',
            'random_mac': '${random_mac(separator, count)}',
            'random_mac_address': '${random_mac_address(separator, count)}',
            'random_ip': '${random_ip(ip_version, count)}',
            'random_ip_address': '${random_ip_address(ip_version, count)}',
            'random_boolean': '${random_boolean(count)}',
            'random_color': '${random_color(format, count)}',
            'random_password': '${random_password(length, count)}',
            'random_sequence': '${random_sequence(sequence, count, unique)}',
            'random_date': '${random_date(start_date, end_date, count, date_format)}',
            
            # 测试数据工具
            'random_phone': '${random_phone(count)}',
            'random_email': '${random_email(count)}',
            'random_id_card': '${random_id_card(count)}',
            'random_name': '${random_name(count)}',
            'random_company': '${random_company(count)}',
            'random_address': '${random_address(count)}',
            'generate_chinese_name': '${generate_chinese_name(gender, count)}',
            'generate_chinese_phone': '${generate_chinese_phone(count)}',
            'generate_chinese_email': '${generate_chinese_email(count)}',
            'generate_chinese_address': '${generate_chinese_address(full_address, count)}',
            'generate_id_card': '${generate_id_card(count)}',
            'generate_company_name': '${generate_company_name(count)}',
            'generate_bank_card': '${generate_bank_card(count)}',
            'generate_hk_id_card': '${generate_hk_id_card(count)}',
            'generate_business_license': '${generate_business_license(count)}',
            'generate_user_profile': '${generate_user_profile(count)}',
            'generate_coordinates': '${generate_coordinates(count)}',
            
            # 字符工具
            'remove_whitespace': '${remove_whitespace(text, type)}',
            'replace_string': '${replace_string(text, old, new, count)}',
            'word_count': '${word_count(text)}',
            'regex_test': '${regex_test(pattern, text, flags)}',
            'case_convert': '${case_convert(text, case_type)}',
            
            # 编码工具
            'timestamp_convert': '${timestamp_convert(timestamp, convert_type)}',
            'base64_encode': '${base64_encode(text, encoding)}',
            'base64_decode': '${base64_decode(text, encoding)}',
            'url_encode': '${url_encode(data, encoding)}',
            'url_decode': '${url_decode(data, encoding)}',
            'unicode_convert': '${unicode_convert(text, convert_type)}',
            'ascii_convert': '${ascii_convert(text, convert_type)}',
            'color_convert': '${color_convert(color, from_type, to_type)}',
            'base_convert': '${base_convert(number, from_base, to_base)}',
            'generate_barcode': '${generate_barcode(data, format)}',
            'generate_qrcode': '${generate_qrcode(data)}',
            'decode_qrcode': '${decode_qrcode(image_path)}',
            'image_to_base64': '${image_to_base64(image_path)}',
            'base64_to_image': '${base64_to_image(base64_data, output_path)}',
            
            # 加密工具
            'md5': '${md5(text)}',
            'sha1': '${sha1(text)}',
            'sha256': '${sha256(text)}',
            'md5_hash': '${md5_hash(text)}',
            'sha1_hash': '${sha1_hash(text)}',
            'sha256_hash': '${sha256_hash(text)}',
            'sha512_hash': '${sha512_hash(text)}',
            'hash_comparison': '${hash_comparison(hash1, hash2)}',
            'aes_encrypt': '${aes_encrypt(text, password, mode)}',
            'aes_decrypt': '${aes_decrypt(encrypted_text, password, mode)}',
            'jwt_decode': '${jwt_decode(token, verify, secret)}',
            'password_strength': '${password_strength(password)}',
            'generate_salt': '${generate_salt(length)}',
            
            # Crontab工具
            'generate_expression': '${generate_expression(minute, hour, day, month, weekday)}',
            'parse_expression': '${parse_expression(expression)}',
            'get_next_runs': '${get_next_runs(expression, count)}',
            'validate_expression': '${validate_expression(expression)}',
            
            # 时间日期函数
            'timestamp': '${timestamp()}',
            'timestamp_sec': '${timestamp_sec()}',
            'datetime': '${datetime(format_str)}',
            'date': '${date(format_str)}',
            'time': '${time(format_str)}',
            'date_offset': '${date_offset(days, hours, minutes, format_str)}',
        }
        
        # 定义示例模板
        example_templates = {
            # 随机工具
            'random_int': '${random_int(100, 999, 1)}',
            'random_float': '${random_float(0, 1, 2, 1)}',
            'random_digits': '${random_digits(6, 1)}',
            'random_string': '${random_string(8, all, 1)}',
            'random_letters': '${random_letters(8, 1)}',
            'random_chinese': '${random_chinese(2, 1)}',
            'random_uuid': '${random_uuid(4, 1)}',
            'random_guid': '${random_guid(4, 1)}',
            'random_mac': '${random_mac(:, 1)}',
            'random_mac_address': '${random_mac_address(:, 1)}',
            'random_ip': '${random_ip(4, 1)}',
            'random_ip_address': '${random_ip_address(4, 1)}',
            'random_boolean': '${random_boolean(1)}',
            'random_color': '${random_color(hex, 1)}',
            'random_password': '${random_password(12, 1)}',
            'random_sequence': '${random_sequence([a,b,c], 1, false)}',
            'random_date': '${random_date(2024-01-01, 2024-12-31, 1, %Y-%m-%d)}',
            
            # 测试数据工具
            'random_phone': '${random_phone(1)}',
            'random_email': '${random_email(1)}',
            'random_id_card': '${random_id_card(1)}',
            'random_name': '${random_name(1)}',
            'random_company': '${random_company(1)}',
            'random_address': '${random_address(1)}',
            'generate_chinese_name': '${generate_chinese_name(random, 1)}',
            'generate_chinese_phone': '${generate_chinese_phone(1)}',
            'generate_chinese_email': '${generate_chinese_email(1)}',
            'generate_chinese_address': '${generate_chinese_address(true, 1)}',
            'generate_id_card': '${generate_id_card(1)}',
            'generate_company_name': '${generate_company_name(1)}',
            'generate_bank_card': '${generate_bank_card(1)}',
            'generate_hk_id_card': '${generate_hk_id_card(1)}',
            'generate_business_license': '${generate_business_license(1)}',
            'generate_user_profile': '${generate_user_profile(1)}',
            'generate_coordinates': '${generate_coordinates(1)}',
            
            # 字符工具
            'remove_whitespace': '${remove_whitespace(hello world, all)}',
            'replace_string': '${replace_string(hello world, world, test, 1)}',
            'word_count': '${word_count(hello world)}',
            'regex_test': '${regex_test(hello123, ^[a-z]+\\d+$, gi)}',
            'case_convert': '${case_convert(hello, upper)}',
            
            # 编码工具
            'timestamp_convert': '${timestamp_convert(1234567890, to_datetime)}',
            'base64_encode': '${base64_encode(123456, utf-8)}',
            'base64_decode': '${base64_decode(MTIzNDU2, utf-8)}',
            'url_encode': '${url_encode(hello world, utf-8)}',
            'url_decode': '${url_decode(hello%20world, utf-8)}',
            'unicode_convert': '${unicode_convert(你好, to_unicode)}',
            'ascii_convert': '${ascii_convert(ABC, to_ascii)}',
            'color_convert': '${color_convert(#ff0000, hex, rgb)}',
            'base_convert': '${base_convert(10, 10, 16)}',
            'generate_barcode': '${generate_barcode(123456, code128)}',
            'generate_qrcode': '${generate_qrcode(https://example.com)}',
            'decode_qrcode': '${decode_qrcode(/path/to/qrcode.png)}',
            'image_to_base64': '${image_to_base64(/path/to/image.png)}',
            'base64_to_image': '${base64_to_image(data:image/png;base64,..., /path/to/output.png)}',
            
            # 加密工具
            'md5': '${md5(123456)}',
            'sha1': '${sha1(123456)}',
            'sha256': '${sha256(123456)}',
            'md5_hash': '${md5_hash(123456)}',
            'sha1_hash': '${sha1_hash(123456)}',
            'sha256_hash': '${sha256_hash(123456)}',
            'sha512_hash': '${sha512_hash(123456)}',
            'hash_comparison': '${hash_comparison(hash1, hash2)}',
            'aes_encrypt': '${aes_encrypt(hello, password, CBC)}',
            'aes_decrypt': '${aes_decrypt(encrypted, password, CBC)}',
            'jwt_decode': '${jwt_decode(token, false, secret)}',
            'password_strength': '${password_strength(myPassword123)}',
            'generate_salt': '${generate_salt(16)}',
            
            # Crontab工具
            'generate_expression': '${generate_expression(*, *, *, *, *)}',
            'parse_expression': '${parse_expression(0 0 * * *)}',
            'get_next_runs': '${get_next_runs(0 0 * * *, 5)}',
            'validate_expression': '${validate_expression(0 0 * * *)}',
            
            # 时间日期函数
            'timestamp': '${timestamp()}',
            'timestamp_sec': '${timestamp_sec()}',
            'datetime': '${datetime(%Y-%m-%d %H:%M:%S)}',
            'date': '${date(%Y-%m-%d)}',
            'time': '${time(%H:%M:%S)}',
            'date_offset': '${date_offset(1, 0, 0, %Y-%m-%d)}',
        }
        
        # 定义分类映射
        category_map = {
            'random_int': '随机数',
            'random_float': '随机数',
            'random_digits': '随机数',
            'random_string': '随机数',
            'random_letters': '随机数',
            'random_chinese': '随机数',
            'random_uuid': '随机数',
            'random_guid': '随机数',
            'random_mac': '随机数',
            'random_mac_address': '随机数',
            'random_ip': '随机数',
            'random_ip_address': '随机数',
            'random_boolean': '随机数',
            'random_color': '随机数',
            'random_password': '随机数',
            'random_sequence': '随机数',
            'random_date': '随机数',
            'random_phone': '测试数据',
            'random_email': '测试数据',
            'random_id_card': '测试数据',
            'random_name': '测试数据',
            'random_company': '测试数据',
            'random_address': '测试数据',
            'generate_chinese_name': '测试数据',
            'generate_chinese_phone': '测试数据',
            'generate_chinese_email': '测试数据',
            'generate_chinese_address': '测试数据',
            'generate_id_card': '测试数据',
            'generate_company_name': '测试数据',
            'generate_bank_card': '测试数据',
            'generate_hk_id_card': '测试数据',
            'generate_business_license': '测试数据',
            'generate_user_profile': '测试数据',
            'generate_coordinates': '测试数据',
            'remove_whitespace': '字符串',
            'replace_string': '字符串',
            'word_count': '字符串',
            'regex_test': '字符串',
            'case_convert': '字符串',
            'timestamp_convert': '编码转换',
            'base64_encode': '编码转换',
            'base64_decode': '编码转换',
            'url_encode': '编码转换',
            'url_decode': '编码转换',
            'unicode_convert': '编码转换',
            'ascii_convert': '编码转换',
            'color_convert': '编码转换',
            'base_convert': '编码转换',
            'generate_barcode': '编码转换',
            'generate_qrcode': '编码转换',
            'decode_qrcode': '编码转换',
            'image_to_base64': '编码转换',
            'base64_to_image': '编码转换',
            'md5': '加密',
            'sha1': '加密',
            'sha256': '加密',
            'md5_hash': '加密',
            'sha1_hash': '加密',
            'sha256_hash': '加密',
            'sha512_hash': '加密',
            'hash_comparison': '加密',
            'aes_encrypt': '加密',
            'aes_decrypt': '加密',
            'jwt_decode': '加密',
            'password_strength': '加密',
            'generate_salt': '加密',
            'generate_expression': 'Crontab',
            'parse_expression': 'Crontab',
            'get_next_runs': 'Crontab',
            'validate_expression': 'Crontab',
            'timestamp': '时间日期',
            'timestamp_sec': '时间日期',
            'datetime': '时间日期',
            'date': '时间日期',
            'time': '时间日期',
            'date_offset': '时间日期',
        }
        
        # 生成变量函数列表
        variable_functions = []
        
        # 从工具列表生成函数信息
        for tool in tool_list:
            tool_name = tool['name']
            if tool_name in syntax_templates:
                variable_functions.append({
                    'name': tool_name,
                    'syntax': syntax_templates[tool_name],
                    'desc': tool.get('description', '无描述'),
                    'example': example_templates.get(tool_name, syntax_templates[tool_name]),
                    'category': category_map.get(tool_name, '其他')
                })
        
        # 添加时间日期函数
        time_functions = ['timestamp', 'timestamp_sec', 'datetime', 'date', 'time', 'date_offset']
        time_function_descriptions = {
            'timestamp': '获取当前时间戳（毫秒）',
            'timestamp_sec': '获取当前时间戳（秒）',
            'datetime': '获取当前日期时间，支持自定义格式',
            'date': '获取当前日期，支持自定义格式',
            'time': '获取当前时间，支持自定义格式',
            'date_offset': '获取偏移后的日期时间，支持自定义格式'
        }
        for func_name in time_functions:
            if func_name not in [f['name'] for f in variable_functions]:
                variable_functions.append({
                    'name': func_name,
                    'syntax': syntax_templates[func_name],
                    'desc': time_function_descriptions[func_name],
                    'example': example_templates.get(func_name, syntax_templates[func_name]),
                    'category': '时间日期'
                })
        
        # 缓存结果，30分钟过期（静态数据）
        cache.set(cache_key, variable_functions, 1800)

        return Response(variable_functions)
