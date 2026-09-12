# -*- coding: utf-8 -*-
"""APP UI组件管理视图"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.db import transaction
import logging
import json
import yaml
from datetime import datetime
from .test_case_views import AppPagination

from ..models import AppComponent, AppCustomComponent, AppComponentPackage
from ..serializers import (
    AppComponentSerializer,
    AppCustomComponentSerializer,
    AppComponentPackageSerializer
)

logger = logging.getLogger(__name__)


class AppComponentViewSet(viewsets.ModelViewSet):
    """UI组件定义视图"""
    queryset = AppComponent.objects.all()
    serializer_class = AppComponentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination

    def get_queryset(self):
        queryset = AppComponent.objects.all()
        enabled = self.request.query_params.get('enabled')
        if enabled is not None:
            if enabled in ('1', 'true', 'True'):
                queryset = queryset.filter(enabled=True)
            elif enabled in ('0', 'false', 'False'):
                queryset = queryset.filter(enabled=False)
        return queryset.order_by('sort_order', '-updated_at')

    def list(self, request, *args, **kwargs):
        """获取组件列表"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })

    def create(self, request, *args, **kwargs):
        """创建组件"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """更新组件"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', False))
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'success': True,
            'data': serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """删除组件"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'success': True,
            'message': '删除成功'
        })


class AppCustomComponentViewSet(viewsets.ModelViewSet):
    """自定义组件视图"""
    queryset = AppCustomComponent.objects.all()
    serializer_class = AppCustomComponentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination

    def get_queryset(self):
        queryset = AppCustomComponent.objects.all()
        enabled = self.request.query_params.get('enabled')
        if enabled is not None:
            if enabled in ('1', 'true', 'True'):
                queryset = queryset.filter(enabled=True)
            elif enabled in ('0', 'false', 'False'):
                queryset = queryset.filter(enabled=False)
        return queryset.order_by('sort_order', '-updated_at')

    def list(self, request, *args, **kwargs):
        """获取自定义组件列表"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })

    def create(self, request, *args, **kwargs):
        """创建自定义组件"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """更新自定义组件"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', False))
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'success': True,
            'data': serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """删除自定义组件"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'success': True,
            'message': '删除成功'
        })


class AppComponentPackageViewSet(viewsets.ModelViewSet):
    """组件包视图集（用于导入/导出组件定义）"""
    queryset = AppComponentPackage.objects.all()
    serializer_class = AppComponentPackageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination

    def _parse_manifest(self, request) -> dict:
        """解析组件包清单"""
        if 'file' in request.FILES:
            upload = request.FILES['file']
            raw = upload.read()
            try:
                content = raw.decode('utf-8')
            except Exception:
                content = raw.decode('utf-8-sig')
            filename = upload.name.lower()
            if filename.endswith('.json'):
                return json.loads(content)
            return yaml.safe_load(content)

        manifest = request.data.get('manifest')
        if isinstance(manifest, dict):
            return manifest
        if isinstance(manifest, str) and manifest.strip():
            try:
                return json.loads(manifest)
            except Exception:
                return yaml.safe_load(manifest)
        raise ValueError("请上传组件包文件或提供manifest")

    def create(self, request, *args, **kwargs):
        """导入组件包"""
        try:
            manifest = self._parse_manifest(request)
        except Exception as error:
            return Response({
                'success': False,
                'message': f'解析组件包失败: {error}'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(manifest, dict):
            return Response({
                'success': False,
                'message': '组件包格式错误：manifest 必须为对象'
            }, status=status.HTTP_400_BAD_REQUEST)

        components = manifest.get('components') or []
        if not isinstance(components, list) or not components:
            return Response({
                'success': False,
                'message': '组件包缺少 components 列表'
            }, status=status.HTTP_400_BAD_REQUEST)

        overwrite = str(request.data.get('overwrite', '1')).lower() in ('1', 'true', 'yes')
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []

        with transaction.atomic():
            for item in components:
                if not isinstance(item, dict):
                    errors.append('组件定义格式错误')
                    continue
                component_type = item.get('type')
                if not component_type:
                    errors.append('组件缺少 type')
                    continue
                defaults = {
                    'name': item.get('name') or component_type,
                    'category': item.get('category', ''),
                    'description': item.get('description', ''),
                    'schema': item.get('schema') or {},
                    'default_config': item.get('default_config') or {},
                    'enabled': item.get('enabled', True),
                    'sort_order': item.get('sort_order', 0),
                }
                obj, created = AppComponent.objects.get_or_create(type=component_type, defaults=defaults)
                if created:
                    created_count += 1
                    continue
                if not overwrite:
                    skipped_count += 1
                    continue
                for key, value in defaults.items():
                    setattr(obj, key, value)
                obj.save()
                updated_count += 1

            if errors:
                return Response({
                    'success': False,
                    'message': '组件包包含错误: ' + ', '.join(errors),
                    'data': errors
                }, status=status.HTTP_400_BAD_REQUEST)

            package = AppComponentPackage.objects.create(
                name=manifest.get('name') or request.data.get('name') or 'component-package',
                version=manifest.get('version') or request.data.get('version', ''),
                description=manifest.get('description') or request.data.get('description', ''),
                author=manifest.get('author') or request.data.get('author', ''),
                source=request.data.get('source', 'upload'),
                manifest=manifest,
                created_by=request.user if request.user.is_authenticated else None
            )

        return Response({
            'success': True,
            'message': '组件包已安装',
            'data': {
                'package_id': package.id,
                'created': created_count,
                'updated': updated_count,
                'skipped': skipped_count
            }
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """导出组件包"""
        # 注意: 不能用 'format' 作参数名，它是 DRF DefaultRouter 的保留字
        export_format = str(request.query_params.get('export_format', 'yaml')).lower()
        include_disabled = str(request.query_params.get('include_disabled', '0')).lower() in ('1', 'true', 'yes')
        name = request.query_params.get('name', 'ui-component-pack')
        version = request.query_params.get('version', '') or datetime.now().strftime('%Y.%m.%d')
        author = request.query_params.get('author', '')
        description = request.query_params.get('description', '导出的组件包')

        queryset = AppComponent.objects.all()
        if not include_disabled:
            queryset = queryset.filter(enabled=True)

        components = []
        for item in queryset.order_by('sort_order', 'type'):
            components.append({
                'type': item.type,
                'name': item.name,
                'category': item.category,
                'description': item.description,
                'schema': item.schema or {},
                'default_config': item.default_config or {},
                'enabled': item.enabled,
                'sort_order': item.sort_order,
            })

        manifest = {
            'name': name,
            'version': version,
            'description': description,
            'author': author,
            'components': components,
        }

        if export_format == 'json':
            content = json.dumps(manifest, ensure_ascii=False, indent=2)
            content_type = 'application/json'
            filename = f'{name}.json'
        else:
            content = yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False)
            content_type = 'application/x-yaml'
            filename = f'{name}.yaml'

        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
