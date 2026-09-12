# -*- coding: utf-8 -*-
"""
图片工具函数（Serializer 使用）
"""


def get_element_image_url(image_path):
    """
    构建元素图片URL（被 Serializer 使用）
    
    参数:
        image_path: 相对路径，如 "common/login.png"（已包含分类）
    
    返回:
        完整URL: "/app-automation-templates/common/login.png"
    """
    if not image_path:
        return None
    return f"/app-automation-templates/{image_path}"
