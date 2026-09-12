# -*- coding: utf-8 -*-
"""APP元素管理视图"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.http import FileResponse
from django.conf import settings
from pathlib import Path
from .test_case_views import AppPagination
import hashlib
import re
import logging

from ..models import AppElement
from ..serializers import AppElementSerializer

logger = logging.getLogger(__name__)


class AppElementViewSet(viewsets.ModelViewSet):
    """APP元素管理 ViewSet"""
    queryset = AppElement.objects.filter(is_active=True)
    serializer_class = AppElementSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination
    # ⚠️ 移除 SearchFilter，使用自定义搜索逻辑
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['element_type', 'is_active', 'project']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_destroy(self, instance):
        """
        删除元素时同时删除物理文件
        """
        # 如果是图片类型，删除物理文件
        if instance.element_type == 'image' and instance.config:
            image_path = instance.config.get('image_path')
            if image_path:
                try:
                    # 构造完整文件路径
                    template_base = self.get_template_base_path()
                    file_path = template_base / image_path
                    
                    # 删除文件
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"删除图片文件: {file_path}")
                    else:
                        logger.warning(f"图片文件不存在: {file_path}")
                except Exception as e:
                    logger.error(f"删除图片文件失败: {str(e)}")
                    # 继续删除数据库记录，即使文件删除失败
        
        # 删除数据库记录
        instance.delete()
    
    def get_queryset(self):
        """
        自定义查询集，支持名称和标签搜索
        
        - 名称：模糊匹配（LIKE）
        - 标签：精确匹配 JSONField 数组中的元素
        """
        queryset = super().get_queryset()
        
        # 获取搜索关键词
        search = self.request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            from django.db import connection
            import json
            
            if 'mysql' in connection.vendor:
                # MySQL: 使用 JSON_CONTAINS 查询
                search_json = json.dumps(search)  # "登录" → '"登录"'
                
                # 不使用表名前缀，让 Django 自动处理
                queryset = queryset.extra(
                    where=["name LIKE %s OR JSON_CONTAINS(tags, %s)"],
                    params=[f'%{search}%', search_json]
                )
            else:
                # PostgreSQL: 使用 @> 运算符
                queryset = queryset.filter(
                    Q(name__icontains=search) | 
                    Q(tags__contains=[search])
                )
        
        return queryset
    
    def get_template_base_path(self):
        """
        获取模板基础路径
        参考 Smart AI Test 的实现：图片存放在 app 目录下的 Template 文件夹
        
        返回: apps/app_automation/Template/
        """
        # __file__ = .../views/element_views.py
        # .parent = .../views/
        # .parent.parent = .../app_automation/
        return Path(__file__).resolve().parent.parent / "Template"
    
    @action(detail=False, methods=['post'], url_path='upload')
    def upload_image(self, request):
        """
        上传元素图片
        
        功能：
        1. 接收图片文件上传
        2. 计算文件哈希
        3. 检测是否重复
        4. 保存到指定分类目录
        5. 返回图片路径和哈希值
        """
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({
                'code': 400,
                'msg': '未接收到文件',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取参数
        category = request.data.get('category', 'common')
        element_id = request.data.get('element_id')  # 编辑模式时传递，用于排除自身
        
        try:
            # ✅ 业务逻辑内联：计算文件哈希
            file_obj.seek(0)
            hasher = hashlib.md5()
            for chunk in file_obj.chunks():
                hasher.update(chunk)
            file_hash = hasher.hexdigest()
            file_obj.seek(0)
            
            # ✅ 业务逻辑内联：检查是否重复（排除当前元素）
            query = AppElement.objects.filter(
                config__file_hash=file_hash,
                is_active=True
            )
            if element_id:
                query = query.exclude(id=element_id)
            
            existing = query.first()
            
            if existing:
                return Response({
                    'code': 400,
                    'msg': '图片已存在',
                    'success': False,
                    'detail': f'该图片的哈希值为 {file_hash}，已被其他元素使用',
                    'suggestion': '建议复制现有元素或上传不同的图片',
                    'data': {
                        'existing_element': {
                            'id': existing.id,
                            'name': existing.name,
                            'image_path': existing.config.get('image_path')
                        }
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ✅ 业务逻辑内联：保存图片到 Template 目录
            template_base = self.get_template_base_path()
            category_path = template_base / category
            category_path.mkdir(parents=True, exist_ok=True)
            
            # 使用原始文件名
            file_path = category_path / file_obj.name
            
            # 保存文件
            with open(file_path, 'wb+') as destination:
                for chunk in file_obj.chunks():
                    destination.write(chunk)
            
            # 构建相对路径（直接返回 category/filename.png）
            relative_path = f"{category}/{file_obj.name}"
            
            logger.info(f"用户 {request.user.username} 上传图片: {relative_path}, 哈希: {file_hash}")
            
            return Response({
                'code': 0,
                'msg': '上传成功',
                'success': True,
                'data': {
                    'image_path': relative_path,
                    'file_hash': file_hash,
                    'url': f"/app-automation-templates/{relative_path}"
                }
            })
        
        except Exception as e:
            logger.error(f"上传图片失败: {str(e)}")
            return Response({
                'code': 500,
                'msg': f'上传失败: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='image-categories')
    def image_categories(self, request):
        """
        获取图片分类列表
        
        返回所有可用的图片分类目录
        """
        try:
            # ✅ 业务逻辑内联：从 Template 目录获取分类列表
            template_base = self.get_template_base_path()
            
            if not template_base.exists():
                return Response({
                    'code': 0,
                    'msg': '获取成功',
                    'success': True,
                    'data': []
                })
            
            categories = []
            for item in template_base.iterdir():
                if item.is_dir():
                    # 计算目录下的图片数量
                    image_count = sum(1 for f in item.iterdir() if f.is_file() and f.suffix.lower() in ['.png', '.jpg', '.jpeg'])
                    
                    categories.append({
                        'name': item.name,
                        'count': image_count,
                        'path': str(item.relative_to(template_base))
                    })
            
            # 按名称排序
            categories.sort(key=lambda x: x['name'])
            
            return Response({
                'code': 0,
                'msg': '获取成功',
                'success': True,
                'data': categories
            })
        except Exception as e:
            logger.error(f"获取分类列表失败: {str(e)}")
            return Response({
                'code': 500,
                'msg': f'获取失败: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='image-categories/create')
    def create_image_category(self, request):
        """
        创建新的图片分类
        
        参数：
        - name: 分类名称（只能包含字母、数字、下划线、中划线）
        """
        category_name = request.data.get('name', '').strip()
        
        if not category_name:
            return Response({
                'code': 400,
                'msg': '分类名称不能为空',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ✅ 业务逻辑内联：验证分类名称
        if not re.match(r'^[a-zA-Z0-9_\-\u4e00-\u9fa5]+$', category_name):
            return Response({
                'code': 400,
                'msg': '分类名称只能包含字母、数字、下划线、中划线和中文',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # ✅ 业务逻辑内联：在 Template 目录创建分类
            template_base = self.get_template_base_path()
            category_path = template_base / category_name
            
            if category_path.exists():
                return Response({
                    'code': 400,
                    'msg': '分类已存在',
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            category_path.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"用户 {request.user.username} 创建图片分类: {category_name}")
            
            return Response({
                'code': 0,
                'msg': '创建成功',
                'success': True,
                'data': {
                    'name': category_name
                }
            })
        except Exception as e:
            logger.error(f"创建分类失败: {str(e)}")
            return Response({
                'code': 500,
                'msg': f'创建失败: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['delete'], url_path='image-categories/(?P<name>[^/.]+)')
    def delete_image_category(self, request, name=None):
        """
        删除图片分类（仅删除空目录）
        
        参数：
        - name: 分类名称
        """
        if not name:
            return Response({
                'code': 400,
                'msg': '分类名称不能为空',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # ✅ 业务逻辑内联：从 Template 目录删除分类
            template_base = self.get_template_base_path()
            category_path = template_base / name
            
            if not category_path.exists():
                return Response({
                    'code': 404,
                    'msg': '分类不存在',
                    'success': False
                }, status=status.HTTP_404_NOT_FOUND)
            
            # 检查是否为空目录
            if any(category_path.iterdir()):
                return Response({
                    'code': 400,
                    'msg': '分类不为空，无法删除。请先删除分类下的所有图片。',
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 删除空目录
            category_path.rmdir()
            
            logger.info(f"用户 {request.user.username} 删除图片分类: {name}")
            
            return Response({
                'code': 0,
                'msg': '删除成功',
                'success': True
            })
        except Exception as e:
            logger.error(f"删除分类失败: {str(e)}")
            return Response({
                'code': 500,
                'msg': f'删除失败: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'], url_path='preview')
    def preview(self, request, pk=None):
        """
        获取元素图片预览
        
        返回图片文件（用于前端显示）
        """
        element = self.get_object()
        
        if element.element_type != 'image':
            return Response({
                'code': 400,
                'msg': '该元素不是图片类型',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取图片路径
        image_path = element.config.get('image_path')
        
        if not image_path:
            return Response({
                'code': 404,
                'msg': '图片路径不存在',
                'success': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ✅ 业务逻辑内联：从 Template 目录构造完整文件路径
        template_base = self.get_template_base_path()
        file_path = template_base / image_path
        
        if not file_path.exists():
            return Response({
                'code': 404,
                'msg': '图片文件不存在',
                'success': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            return FileResponse(open(file_path, 'rb'), content_type='image/png')
        except Exception as e:
            logger.error(f"读取图片失败: {str(e)}")
            return Response({
                'code': 500,
                'msg': f'读取图片失败: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='crop-image')
    def crop_image(self, request):
        """
        裁剪图片并保存
        
        参数：
        - image_data: Base64 图片数据
        - x, y, width, height: 裁剪区域坐标
        - element_name: 元素名称
        - category: 图片分类
        - element_type: 元素类型（image/pos/region）
        
        返回：
        - 裁剪后的图片路径
        - 文件哈希
        - 坐标信息
        """
        try:
            from PIL import Image
            import io
            import base64
            import time
            
            # 获取参数
            image_data = request.data.get('image_data', '')
            x = int(request.data.get('x', 0))
            y = int(request.data.get('y', 0))
            width = int(request.data.get('width', 100))
            height = int(request.data.get('height', 100))
            element_name = request.data.get('element_name', 'captured_element')
            category = request.data.get('category', 'common')
            element_type = request.data.get('element_type', 'image')  # image/pos/region
            
            # 解码 Base64 图片
            if image_data.startswith('data:image'):
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # 裁剪图片
            cropped = image.crop((x, y, x + width, y + height))
            
            # 保存到临时缓冲区
            buffer = io.BytesIO()
            cropped.save(buffer, format='PNG')
            buffer.seek(0)
            
            # 计算哈希
            file_hash = hashlib.md5(buffer.getvalue()).hexdigest()
            buffer.seek(0)
            
            # 检查重复
            existing = AppElement.objects.filter(
                config__file_hash=file_hash,
                is_active=True
            ).first()
            
            if existing:
                return Response({
                    'code': 400,
                    'msg': '该图片已存在',
                    'success': False,
                    'data': {
                        'existing_element': {
                            'id': existing.id,
                            'name': existing.name,
                            'image_path': existing.config.get('image_path')
                        }
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 保存文件（统一使用 Template 目录）
            base_path = self.get_template_base_path()
            category_path = base_path / category
            category_path.mkdir(parents=True, exist_ok=True)
            
            # 使用元素名称 + 时间戳作为文件名
            filename = f"{element_name}_{int(time.time())}.png"
            file_path = category_path / filename
            
            with open(file_path, 'wb') as f:
                f.write(buffer.getvalue())
            
            # 构建相对路径
            relative_path = f"{category}/{filename}"
            
            logger.info(f"用户 {request.user.username} 裁剪图片: {relative_path}, 哈希: {file_hash}")
            
            return Response({
                'code': 0,
                'msg': '裁剪成功',
                'success': True,
                'data': {
                    'image_path': relative_path,
                    'file_hash': file_hash,
                    'url': f"/app-automation-templates/{relative_path}",
                    'coordinates': {
                        'x': x,
                        'y': y,
                        'width': width,
                        'height': height
                    },
                    'element_type': element_type
                }
            })
            
        except Exception as e:
            logger.error(f"裁剪图片失败: {str(e)}")
            return Response({
                'code': 500,
                'msg': f'裁剪失败: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
