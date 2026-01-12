"""
OCR (Optical Character Recognition) Module
Makes scanned PDFs searchable and selectable.
"""

from __future__ import annotations

import io
import os
import tempfile
from typing import Optional, Literal
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class OCRError(Exception):
    """Base exception for OCR operations."""
    pass


class PDFOCRProcessor:
    """Process scanned PDFs to make them searchable."""
    
    @staticmethod
    def is_tesseract_available() -> bool:
        """Check if Tesseract OCR is available on the system."""
        if not TESSERACT_AVAILABLE:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
    
    @staticmethod
    def extract_text(buffer: bytes, language: str = "eng") -> str:
        """
        Extract text from a scanned PDF using OCR.
        
        Args:
            buffer: PDF file bytes
            language: Tesseract language code (e.g., 'eng', 'fra', 'deu')
            
        Returns:
            Extracted text from all pages
        """
        if not PDF2IMAGE_AVAILABLE:
            raise OCRError("pdf2image library not available. Install poppler.")
        
        if not TESSERACT_AVAILABLE:
            raise OCRError("pytesseract library not available")
        
        if not PDFOCRProcessor.is_tesseract_available():
            raise OCRError("Tesseract OCR is not installed on this system")
        
        try:
            # Convert PDF to images
            images = convert_from_bytes(buffer, dpi=300)
            
            text_parts = []
            for i, img in enumerate(images):
                # Run OCR on each page
                page_text = pytesseract.image_to_string(img, lang=language)
                text_parts.append(f"--- Page {i + 1} ---\n{page_text}")
            
            return "\n\n".join(text_parts)
            
        except Exception as e:
            raise OCRError(f"OCR failed: {e}")
    
    @staticmethod
    def create_searchable_pdf(
        buffer: bytes,
        language: str = "eng",
        dpi: int = 300
    ) -> bytes:
        """
        Create a searchable PDF from a scanned PDF.
        Overlays invisible text layer on top of the original scanned images.
        
        Args:
            buffer: PDF file bytes
            language: Tesseract language code
            dpi: Resolution for image conversion
            
        Returns:
            Searchable PDF bytes
        """
        if not PDF2IMAGE_AVAILABLE:
            raise OCRError("pdf2image library not available")
        
        if not TESSERACT_AVAILABLE:
            raise OCRError("pytesseract library not available")
        
        if not PDFOCRProcessor.is_tesseract_available():
            raise OCRError("Tesseract OCR is not installed")
        
        try:
            # Convert PDF to images
            images = convert_from_bytes(buffer, dpi=dpi)
            
            writer = PdfWriter()
            
            for i, img in enumerate(images):
                # Get page dimensions
                width_px, height_px = img.size
                width_pt = width_px * 72 / dpi
                height_pt = height_px * 72 / dpi
                
                # Get OCR data with bounding boxes
                ocr_data = pytesseract.image_to_data(
                    img, 
                    lang=language,
                    output_type=pytesseract.Output.DICT
                )
                
                # Create a PDF page with the image
                img_pdf = io.BytesIO()
                c = canvas.Canvas(img_pdf, pagesize=(width_pt, height_pt))
                
                # Draw the original image
                temp_img = io.BytesIO()
                img.save(temp_img, format='PNG')
                temp_img.seek(0)
                
                from reportlab.lib.utils import ImageReader
                c.drawImage(
                    ImageReader(temp_img), 
                    0, 0, 
                    width=width_pt, 
                    height=height_pt
                )
                
                # Add invisible text layer
                c.setFillColor((1, 1, 1, 0))  # Invisible text
                
                n_boxes = len(ocr_data['text'])
                for j in range(n_boxes):
                    if int(ocr_data['conf'][j]) > 0:  # Only confident recognitions
                        text = ocr_data['text'][j]
                        if text.strip():
                            # Convert pixel coordinates to points
                            x = ocr_data['left'][j] * 72 / dpi
                            # Y is from top in OCR, from bottom in PDF
                            y = height_pt - (ocr_data['top'][j] * 72 / dpi) - (ocr_data['height'][j] * 72 / dpi)
                            
                            font_size = ocr_data['height'][j] * 72 / dpi * 0.8
                            if font_size > 0:
                                try:
                                    c.setFont("Helvetica", max(font_size, 4))
                                    # Make text invisible but selectable
                                    c.setFillColorRGB(1, 1, 1, alpha=0)
                                    c.drawString(x, y, text)
                                except Exception:
                                    pass
                
                c.save()
                
                # Read the created page and add to writer
                img_pdf.seek(0)
                reader = PdfReader(img_pdf)
                writer.add_page(reader.pages[0])
            
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
            
        except Exception as e:
            raise OCRError(f"OCR PDF creation failed: {e}")
    
    @staticmethod
    def ocr_image(
        image_buffer: bytes,
        language: str = "eng",
        output_format: Literal["text", "hocr", "tsv"] = "text"
    ) -> str:
        """
        Perform OCR on an image file.
        
        Args:
            image_buffer: Image file bytes
            language: Tesseract language code
            output_format: Output format (text, hocr, or tsv)
            
        Returns:
            Extracted text or structured data
        """
        if not TESSERACT_AVAILABLE:
            raise OCRError("pytesseract library not available")
        
        if not PDFOCRProcessor.is_tesseract_available():
            raise OCRError("Tesseract OCR is not installed")
        
        try:
            img = Image.open(io.BytesIO(image_buffer))
            
            if output_format == "hocr":
                return pytesseract.image_to_pdf_or_hocr(img, lang=language, extension='hocr').decode()
            elif output_format == "tsv":
                return pytesseract.image_to_data(img, lang=language)
            else:
                return pytesseract.image_to_string(img, lang=language)
                
        except Exception as e:
            raise OCRError(f"Image OCR failed: {e}")


def get_available_languages() -> list[str]:
    """Get list of available Tesseract language packs."""
    if not TESSERACT_AVAILABLE or not PDFOCRProcessor.is_tesseract_available():
        return []
    
    try:
        return pytesseract.get_languages()
    except Exception:
        return ["eng"]  # Default to English


def check_ocr_status() -> dict:
    """Check OCR system status and availability."""
    status = {
        "pytesseract_installed": TESSERACT_AVAILABLE,
        "pdf2image_installed": PDF2IMAGE_AVAILABLE,
        "tesseract_available": False,
        "tesseract_version": None,
        "available_languages": [],
    }
    
    if TESSERACT_AVAILABLE:
        try:
            status["tesseract_version"] = str(pytesseract.get_tesseract_version())
            status["tesseract_available"] = True
            status["available_languages"] = get_available_languages()
        except Exception:
            pass
    
    return status
