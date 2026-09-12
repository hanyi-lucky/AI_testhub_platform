# -*- coding: utf-8 -*-
"""
OCR 工具类 - 基于 EasyOCR
"""
import os
import time
import logging
import hashlib
import re
from typing import Any, Dict, Optional, Tuple
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageEnhance

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

from airtest.core.api import G, sleep as airtest_sleep

logger = logging.getLogger(__name__)


class OCRHelper:
    """OCR 辅助类 - 提供图像文字识别功能"""
    
    # OCR结果缓存：key为(坐标区域hash, 图片hash)，value为(识别结果, 时间戳)
    _ocr_cache = {}
    _cache_ttl = 2.0  # 缓存有效期2秒
    _cache_max_size = 50  # 最大缓存条目数
    
    # EasyOCR reader实例（延迟初始化）
    _easyocr_reader = None
    
    def __init__(self, languages=None, use_gpu=False):
        """
        初始化 OCR 助手
        
        Args:
            languages: OCR 识别语言列表，默认为 ['en']（英文）
                      可选：['ch_sim', 'en'] (简体中文和英文)
            use_gpu: 是否使用 GPU 加速，默认 False
        """
        if not EASYOCR_AVAILABLE:
            logger.warning("EasyOCR 未安装，OCR 功能将不可用。请运行: pip install easyocr")
        
        self.languages = languages or ['en']
        self.use_gpu = use_gpu
    
    @classmethod
    def get_easyocr_reader(cls, languages=None, use_gpu=False):
        """
        获取或创建EasyOCR reader实例（延迟初始化，单例模式）
        
        Args:
            languages: 识别语言列表
            use_gpu: 是否使用 GPU
            
        Returns:
            easyocr.Reader 实例
        """
        if not EASYOCR_AVAILABLE:
            raise ImportError("EasyOCR 未安装，请运行: pip install easyocr")
        
        if cls._easyocr_reader is None:
            try:
                languages = languages or ['en']
                logger.info(f"初始化 EasyOCR reader (语言: {languages}, GPU: {use_gpu})...")
                logger.info("首次使用会下载模型，可能需要一些时间")
                cls._easyocr_reader = easyocr.Reader(languages, gpu=use_gpu)
                logger.info("EasyOCR reader 初始化完成")
            except Exception as e:
                logger.error(f"EasyOCR 初始化失败: {e}")
                raise
        return cls._easyocr_reader
    
    @staticmethod
    def _get_image_hash(img) -> str:
        """
        计算图片的hash值用于缓存
        
        Args:
            img: PIL Image 或 numpy array
            
        Returns:
            图片的 MD5 hash 值
        """
        if isinstance(img, Image.Image):
            img_array = np.array(img)
        else:
            img_array = img
        return hashlib.md5(img_array.tobytes()).hexdigest()
    
    @classmethod
    def _get_cache_key(cls, region: Tuple, img_hash: str) -> Tuple:
        """生成缓存key"""
        return (tuple(region), img_hash)
    
    @classmethod
    def _clean_cache(cls):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in cls._ocr_cache.items()
            if current_time - timestamp > cls._cache_ttl
        ]
        for key in expired_keys:
            cls._ocr_cache.pop(key, None)
        
        # 如果缓存仍然太大，删除最旧的条目
        if len(cls._ocr_cache) > cls._cache_max_size:
            sorted_items = sorted(
                cls._ocr_cache.items(),
                key=lambda x: x[1][1]  # 按时间戳排序
            )
            # 删除最旧的一半
            for key, _ in sorted_items[:len(sorted_items)//2]:
                cls._ocr_cache.pop(key, None)
    
    def recognize_text(self, img, min_confidence=0.3, use_cache=True) -> str:
        """
        识别图片中的文本
        
        Args:
            img: PIL Image 对象
            min_confidence: 最小置信度阈值
            use_cache: 是否使用缓存
            
        Returns:
            识别出的文本字符串
        """
        if not EASYOCR_AVAILABLE:
            logger.error("EasyOCR 未安装，无法进行文字识别")
            return ""
        
        # 检查缓存
        img_hash = None
        cache_key = None
        if use_cache:
            img_hash = self._get_image_hash(img)
            cache_key = (img_hash,)  # 简化的缓存键
            if cache_key in self._ocr_cache:
                result, timestamp = self._ocr_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    logger.debug(f"使用缓存 OCR 结果: {result}")
                    return result
        
        try:
            reader = self.get_easyocr_reader(self.languages, self.use_gpu)
            
            # 图像预处理
            if isinstance(img, Image.Image):
                # 转换为 RGB
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 图片较小时放大以提高识别率
                width, height = img.size
                if width < 1000 or height < 200:
                    scale_factor = 2
                    img = img.resize(
                        (width * scale_factor, height * scale_factor),
                        Image.LANCZOS
                    )
                    logger.debug(f"图片放大 {scale_factor} 倍以提高识别率")
                
                img_array = np.array(img)
            else:
                img_array = img
                if len(img_array.shape) == 2:
                    # 灰度图转 RGB
                    img_array = np.stack([img_array] * 3, axis=-1)
            
            # EasyOCR 识别
            results = reader.readtext(img_array)
            
            # 提取文本，按从左到右排序
            text_items = []
            for (bbox, text, confidence) in results:
                if float(confidence) >= min_confidence:
                    x_coord = bbox[0][0]  # 左上角的 x 坐标
                    text_items.append((x_coord, text, float(confidence)))
                    logger.debug(f"OCR: '{text}', 置信度: {confidence:.2f}, x: {x_coord:.1f}")
            
            # 按 x 坐标排序
            text_items.sort(key=lambda x: x[0])
            texts = [item[1] for item in text_items]
            combined_text = ' '.join(texts)
            
            # 缓存结果
            if use_cache and cache_key:
                self._ocr_cache[cache_key] = (combined_text, time.time())
                self._clean_cache()
            
            logger.info(f"OCR 识别结果: '{combined_text}'")
            return combined_text.strip()
            
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            return ""
    
    def recognize_number(self, img, allow_comma=True, use_cache=True) -> int:
        """
        识别图片中的数字
        
        Args:
            img: PIL Image 对象
            allow_comma: 是否允许逗号分隔符
            use_cache: 是否使用缓存
            
        Returns:
            识别出的数字（整数）
        """
        text = self.recognize_text(img, use_cache=use_cache)
        
        # 常见字符替换
        text = text.replace('o', '0').replace('O', '0')  # o/O -> 0
        text = text.replace('l', '1').replace('I', '1')  # l/I -> 1
        text = text.replace('?', '1')  # ? -> 1
        
        # 提取数字和逗号
        if allow_comma:
            digits = ''.join(filter(lambda x: x.isdigit() or x == ',', text))
            digits = digits.replace(',', '')
        else:
            digits = ''.join(filter(str.isdigit, text))
        
        try:
            number = int(digits) if digits else 0
            logger.info(f"提取数字: {number}")
            return number
        except ValueError:
            logger.error(f"无法将文本转换为数字: {text}")
            return 0
    
    @staticmethod
    def crop_region(region: Tuple[int, int, int, int], screenshot_path: Optional[str] = None) -> Image.Image:
        """
        裁剪屏幕指定区域
        
        Args:
            region: 坐标元组 (x1, y1, x2, y2)
            screenshot_path: 截图文件路径（可选，如果不提供则实时截图）
            
        Returns:
            裁剪后的 PIL Image
        """
        if screenshot_path and os.path.exists(screenshot_path):
            # 从文件加载
            img_cv = cv2.imread(screenshot_path)
        else:
            # 实时截图
            airtest_sleep(0.3)
            img_cv = G.DEVICE.snapshot()
            if img_cv is None:
                raise RuntimeError("截图失败，snapshot 返回 None")
        
        # 裁剪
        x1, y1, x2, y2 = region
        cropped = img_cv[y1:y2, x1:x2]
        
        # 转换为 PIL Image
        pil_img = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        
        # 增强对比度
        pil_img = ImageEnhance.Contrast(pil_img).enhance(2.0)
        
        return pil_img
    
    def recognize_region_text(self, region: Tuple[int, int, int, int], screenshot_path: Optional[str] = None) -> str:
        """
        识别屏幕指定区域的文本
        
        Args:
            region: 坐标元组 (x1, y1, x2, y2)
            screenshot_path: 截图文件路径（可选）
            
        Returns:
            识别出的文本
        """
        img = self.crop_region(region, screenshot_path)
        return self.recognize_text(img)
    
    def recognize_region_number(self, region: Tuple[int, int, int, int], screenshot_path: Optional[str] = None) -> int:
        """
        识别屏幕指定区域的数字
        
        Args:
            region: 坐标元组 (x1, y1, x2, y2)
            screenshot_path: 截图文件路径（可选）
            
        Returns:
            识别出的数字
        """
        img = self.crop_region(region, screenshot_path)
        return self.recognize_number(img)


# 全局单例实例
_ocr_helper_instance = None


def get_ocr_helper(languages=None, use_gpu=False) -> OCRHelper:
    """
    获取全局 OCR Helper 单例实例
    
    Args:
        languages: OCR 识别语言列表
        use_gpu: 是否使用 GPU
        
    Returns:
        OCRHelper 实例
    """
    global _ocr_helper_instance
    if _ocr_helper_instance is None:
        _ocr_helper_instance = OCRHelper(languages=languages, use_gpu=use_gpu)
    return _ocr_helper_instance
