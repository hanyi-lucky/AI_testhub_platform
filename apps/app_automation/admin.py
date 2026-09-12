# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import (
    AppDevice,
    AppElement,
    AppComponent,
    AppCustomComponent,
    AppComponentPackage,
    AppPackage,
    AppTestCase,
    AppTestExecution,
)


@admin.register(AppDevice)
class AppDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'name', 'status', 'android_version', 'connection_type', 'locked_by', 'updated_at')
    list_filter = ('status', 'connection_type')
    search_fields = ('device_id', 'name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AppElement)
class AppElementAdmin(admin.ModelAdmin):
    list_display = ('name', 'element_type', 'usage_count', 'is_active', 'created_at')
    list_filter = ('element_type', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'usage_count', 'last_used_at')


@admin.register(AppComponent)
class AppComponentAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'category', 'enabled', 'sort_order')
    list_filter = ('category', 'enabled')
    search_fields = ('name', 'type')


@admin.register(AppCustomComponent)
class AppCustomComponentAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'enabled', 'sort_order')
    list_filter = ('enabled',)
    search_fields = ('name', 'type')


@admin.register(AppComponentPackage)
class AppComponentPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'author', 'source', 'created_at')
    list_filter = ('source',)
    search_fields = ('name', 'author')


@admin.register(AppPackage)
class AppPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'package_name', 'created_by', 'created_at')
    search_fields = ('name', 'package_name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AppTestCase)
class AppTestCaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'app_package', 'timeout', 'created_by', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AppTestExecution)
class AppTestExecutionAdmin(admin.ModelAdmin):
    list_display = ('test_case', 'device', 'status', 'progress', 'pass_rate', 'created_at')
    list_filter = ('status',)
    search_fields = ('test_case__name',)
    readonly_fields = ('created_at', 'updated_at', 'started_at', 'finished_at', 'duration')
