"""
Image Processing Module
Handles image editing operations including resize, rotate, blur, background removal, format conversion, etc.
"""

from __future__ import annotations

import io
from typing import Literal, Optional
from PIL import Image, ImageFilter, ImageEnhance
import numpy as np


class ImageError(Exception):
    """Base exception for image operations."""
    pass


class ImageProcessor:
    """Process and edit images with various operations."""
    
    @staticmethod
    def process(
        buffer: bytes,
        operation: Literal[
            "resize", "rotate", "blur", "format", "grayscale", 
            "brightness", "contrast", "flip", "remove_background", 
            "add_background"
        ],
        **kwargs
    ) -> bytes:
        """
        Process image with specified operation.
        
        Args:
            buffer: Image file bytes
            operation: Type of operation to perform
            **kwargs: Operation-specific parameters
            
        Returns:
            Processed image bytes
        """
        try:
            img = Image.open(io.BytesIO(buffer))
            
            if operation == "resize":
                img = ImageProcessor._resize(img, kwargs)
            elif operation == "rotate":
                img = ImageProcessor._rotate(img, kwargs)
            elif operation == "blur":
                img = ImageProcessor._blur(img, kwargs)
            elif operation == "format":
                img = ImageProcessor._convert_format(img, kwargs)
            elif operation == "grayscale":
                img = ImageProcessor._grayscale(img)
            elif operation == "brightness":
                img = ImageProcessor._adjust_brightness(img, kwargs)
            elif operation == "contrast":
                img = ImageProcessor._adjust_contrast(img, kwargs)
            elif operation == "flip":
                img = ImageProcessor._flip(img, kwargs)
            elif operation == "remove_background":
                img = ImageProcessor._remove_background(img)
            elif operation == "add_background":
                img = ImageProcessor._add_background(img, kwargs)
            else:
                raise ImageError(f"Unknown operation: {operation}")
            
            # Save to bytes
            output = io.BytesIO()
            output_format = kwargs.get("output_format", "PNG")
            
            if output_format.upper() in ("JPG", "JPEG"):
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                img.save(output, format="JPEG", quality=85, optimize=True)
            elif output_format.upper() == "WEBP":
                img.save(output, format="WEBP", quality=85)
            elif output_format.upper() == "BMP":
                img.save(output, format="BMP")
            elif output_format.upper() == "TIFF":
                img.save(output, format="TIFF")
            else:  # PNG default
                img.save(output, format="PNG", optimize=True)
            
            return output.getvalue()
            
        except Exception as e:
            raise ImageError(f"Image processing failed: {e}")
    
    @staticmethod
    def _resize(img: Image.Image, kwargs: dict) -> Image.Image:
        """Resize image to specified width/height or percentage."""
        resize_mode = kwargs.get("resize_mode", "percentage")  # percentage or dimensions
        
        if resize_mode == "percentage":
            percent = float(kwargs.get("percentage", 50))
            new_width = int(img.width * percent / 100)
            new_height = int(img.height * percent / 100)
        else:
            new_width = int(kwargs.get("width", img.width))
            new_height = int(kwargs.get("height", img.height))
            maintain_aspect = kwargs.get("maintain_aspect", True)
            
            if maintain_aspect:
                ratio = min(new_width / img.width, new_height / img.height)
                new_width = int(img.width * ratio)
                new_height = int(img.height * ratio)
        
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    @staticmethod
    def _rotate(img: Image.Image, kwargs: dict) -> Image.Image:
        """Rotate image by specified angle."""
        angle = float(kwargs.get("angle", 0))
        expand = kwargs.get("expand", True)
        return img.rotate(angle, expand=expand, resample=Image.Resampling.BICUBIC)
    
    @staticmethod
    def _blur(img: Image.Image, kwargs: dict) -> Image.Image:
        """Apply blur filter to image."""
        radius = int(kwargs.get("radius", 5))
        if radius < 1:
            return img
        return img.filter(ImageFilter.GaussianBlur(radius=radius))
    
    @staticmethod
    def _convert_format(img: Image.Image, kwargs: dict) -> Image.Image:
        """Convert image format (handled in main process method)."""
        return img
    
    @staticmethod
    def _grayscale(img: Image.Image) -> Image.Image:
        """Convert image to grayscale."""
        return img.convert("L")
    
    @staticmethod
    def _adjust_brightness(img: Image.Image, kwargs: dict) -> Image.Image:
        """Adjust image brightness."""
        factor = float(kwargs.get("factor", 1.0))
        enhancer = ImageEnhance.Brightness(img)
        return enhancer.enhance(factor)
    
    @staticmethod
    def _adjust_contrast(img: Image.Image, kwargs: dict) -> Image.Image:
        """Adjust image contrast."""
        factor = float(kwargs.get("factor", 1.0))
        enhancer = ImageEnhance.Contrast(img)
        return enhancer.enhance(factor)
    
    @staticmethod
    def _flip(img: Image.Image, kwargs: dict) -> Image.Image:
        """Flip image horizontally or vertically."""
        direction = kwargs.get("direction", "horizontal")  # horizontal or vertical
        if direction == "vertical":
            return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        else:
            return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    
    @staticmethod
    def _remove_background(img: Image.Image) -> Image.Image:
        """Remove background using color detection (simple method)."""
        # Convert to RGBA if needed
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        
        # Get the color at top-left corner (assumed to be background)
        data = np.array(img)
        
        # Get background color from corner
        bg_color = data[0, 0]
        
        # Create mask for background color (with tolerance)
        tolerance = 50
        mask = np.all(
            (data[..., :3] >= bg_color[:3] - tolerance) & 
            (data[..., :3] <= bg_color[:3] + tolerance),
            axis=2
        )
        
        # Apply mask to alpha channel
        data[mask, 3] = 0
        
        return Image.fromarray(data)
    
    @staticmethod
    def _add_background(img: Image.Image, kwargs: dict) -> Image.Image:
        """Add background color to transparent image."""
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        
        # Get background color (RGB hex format)
        bg_color_hex = kwargs.get("bg_color", "FFFFFF")
        try:
            bg_color = tuple(int(bg_color_hex[i:i+2], 16) for i in (0, 2, 4))
        except (ValueError, IndexError):
            bg_color = (255, 255, 255)
        
        # Create background image
        bg = Image.new("RGB", img.size, bg_color)
        
        # Paste image on background
        bg.paste(img, (0, 0), img)
        
        return bg
