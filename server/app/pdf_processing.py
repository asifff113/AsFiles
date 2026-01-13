"""
PDF Processing Module
Handles all PDF manipulation operations including merge, split, compress, rotate,
organize pages, add page numbers, watermark, protect/unlock, convert to PDF/A, and repair.
"""

from __future__ import annotations

import io
import os
import tempfile
from typing import Iterable, Literal, Optional
from pathlib import Path

from pypdf import PdfReader, PdfWriter, PageObject
from pypdf.errors import PdfReadError
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import Color, black, white, gray
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
import pikepdf
import fitz  # PyMuPDF for image compression


class PDFError(Exception):
    """Base exception for PDF operations."""
    pass


class PDFMerger:
    """Merge multiple PDF files into one."""
    
    @staticmethod
    def merge(buffers: Iterable[bytes]) -> bytes:
        """Merge multiple PDF byte streams into a single PDF."""
        payloads = list(buffers)
        if not payloads:
            raise PDFError("No PDF data provided.")
        
        writer = PdfWriter()
        
        for payload in payloads:
            try:
                reader = PdfReader(io.BytesIO(payload))
                for page in reader.pages:
                    writer.add_page(page)
            except PdfReadError as e:
                raise PDFError(f"Invalid PDF file: {e}")
            except Exception as e:
                raise PDFError(f"Error processing PDF: {e}")
        
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()


class PDFSplitter:
    """Split PDF files into smaller parts."""
    
    @staticmethod
    def split_pages(buffer: bytes, pages: list[int]) -> bytes:
        """Extract specific pages from a PDF."""
        try:
            reader = PdfReader(io.BytesIO(buffer))
            writer = PdfWriter()
            
            total_pages = len(reader.pages)
            for page_num in pages:
                if 0 <= page_num < total_pages:
                    writer.add_page(reader.pages[page_num])
                else:
                    raise PDFError(f"Page {page_num + 1} out of range (1-{total_pages})")
            
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except PdfReadError as e:
            raise PDFError(f"Invalid PDF file: {e}")
    
    @staticmethod
    def split_range(buffer: bytes, start: int, end: int) -> bytes:
        """Extract a range of pages from a PDF (0-indexed)."""
        try:
            reader = PdfReader(io.BytesIO(buffer))
            writer = PdfWriter()
            
            total_pages = len(reader.pages)
            start = max(0, start)
            end = min(end, total_pages)
            
            for i in range(start, end):
                writer.add_page(reader.pages[i])
            
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except PdfReadError as e:
            raise PDFError(f"Invalid PDF file: {e}")
    
    @staticmethod
    def split_every_n(buffer: bytes, n: int) -> list[bytes]:
        """Split PDF into chunks of N pages each."""
        try:
            reader = PdfReader(io.BytesIO(buffer))
            total_pages = len(reader.pages)
            results = []
            
            for start in range(0, total_pages, n):
                writer = PdfWriter()
                end = min(start + n, total_pages)
                for i in range(start, end):
                    writer.add_page(reader.pages[i])
                output = io.BytesIO()
                writer.write(output)
                results.append(output.getvalue())
            
            return results
        except PdfReadError as e:
            raise PDFError(f"Invalid PDF file: {e}")


class PDFCompressor:
    """Compress PDF files to reduce size."""
    
    @staticmethod
    def compress(
        buffer: bytes, 
        compression_level: int = 50,
        mode: str = "smart"
    ) -> bytes:
        """
        Compress a PDF file with specified compression level.
        
        Args:
            buffer: PDF file bytes
            compression_level: 1-100 where 1 = max compression (smallest file, lowest quality)
                              and 100 = min compression (larger file, best quality)
            mode: "smart" = compress images only, keep text selectable
                  "aggressive" = convert pages to images (maximum compression)
        """
        # Clamp compression level between 1 and 100
        compression_level = max(1, min(100, compression_level))
        original_size = len(buffer)
        
        # Map compression level to JPEG quality (10-90)
        image_quality = int(10 + (compression_level / 100) * 80)  # 10-90 quality
        
        try:
            results = []
            
            # Method 1: Smart compression - compress only embedded images
            if mode == "smart":
                try:
                    doc = fitz.open(stream=buffer, filetype="pdf")
                    
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        image_list = page.get_images(full=True)
                        
                        for img_info in image_list:
                            xref = img_info[0]
                            
                            try:
                                # Extract image
                                base_image = doc.extract_image(xref)
                                if not base_image:
                                    continue
                                
                                image_bytes = base_image["image"]
                                
                                # Skip small images
                                if len(image_bytes) < 5000:
                                    continue
                                
                                # Open with PIL
                                pil_image = Image.open(io.BytesIO(image_bytes))
                                
                                # Convert to RGB for JPEG
                                if pil_image.mode in ('RGBA', 'P', 'LA'):
                                    background = Image.new('RGB', pil_image.size, (255, 255, 255))
                                    if pil_image.mode == 'P':
                                        pil_image = pil_image.convert('RGBA')
                                    if pil_image.mode in ('RGBA', 'LA'):
                                        background.paste(pil_image, mask=pil_image.split()[-1])
                                    pil_image = background
                                elif pil_image.mode != 'RGB':
                                    pil_image = pil_image.convert('RGB')
                                
                                # Resize large images based on compression level
                                max_dim = int(800 + (compression_level / 100) * 2200)  # 800-3000px
                                orig_w, orig_h = pil_image.size
                                if orig_w > max_dim or orig_h > max_dim:
                                    ratio = min(max_dim / orig_w, max_dim / orig_h)
                                    new_size = (int(orig_w * ratio), int(orig_h * ratio))
                                    pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)
                                
                                # Compress to JPEG
                                compressed_io = io.BytesIO()
                                pil_image.save(compressed_io, format='JPEG', quality=image_quality, optimize=True)
                                compressed_bytes = compressed_io.getvalue()
                                
                                # Only replace if smaller
                                if len(compressed_bytes) < len(image_bytes) * 0.85:
                                    page.replace_image(xref, stream=compressed_bytes)
                            except Exception:
                                continue
                    
                    # Save with garbage collection
                    smart_output = io.BytesIO()
                    doc.save(smart_output, garbage=4, deflate=True, clean=True)
                    doc.close()
                    
                    smart_result = smart_output.getvalue()
                    results.append((smart_result, "smart"))
                except Exception:
                    pass
            
            # Method 2: Aggressive - convert pages to images (for mode="aggressive" or as fallback)
            if mode == "aggressive" or not results:
                try:
                    dpi = int(72 + (compression_level / 100) * 128)  # 72-200 DPI
                    
                    original_doc = fitz.open(stream=buffer, filetype="pdf")
                    new_doc = fitz.open()
                    
                    for page_num in range(len(original_doc)):
                        page = original_doc[page_num]
                        rect = page.rect
                        
                        zoom = dpi / 72.0
                        mat = fitz.Matrix(zoom, zoom)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img_data = pix.tobytes("jpeg", jpg_quality=image_quality)
                        
                        new_page = new_doc.new_page(width=rect.width, height=rect.height)
                        new_page.insert_image(rect, stream=img_data)
                    
                    aggressive_output = io.BytesIO()
                    new_doc.save(aggressive_output, garbage=4, deflate=True, clean=True)
                    new_doc.close()
                    original_doc.close()
                    
                    aggressive_result = aggressive_output.getvalue()
                    results.append((aggressive_result, "aggressive"))
                except Exception:
                    pass
            
            # Method 3: pikepdf stream optimization
            try:
                with pikepdf.open(io.BytesIO(buffer)) as pdf:
                    pdf.remove_unreferenced_resources()
                    pikepdf_output = io.BytesIO()
                    pdf.save(
                        pikepdf_output,
                        compress_streams=True,
                        object_stream_mode=pikepdf.ObjectStreamMode.generate,
                        recompress_flate=True,
                    )
                    pikepdf_result = pikepdf_output.getvalue()
                    results.append((pikepdf_result, "pikepdf"))
            except Exception:
                pass
            
            if not results:
                raise PDFError("All compression methods failed")
            
            # Filter to results smaller than original
            smaller_results = [(r, name) for r, name in results if len(r) < original_size]
            
            if smaller_results:
                # Return the smallest one
                best_result = min(smaller_results, key=lambda x: len(x[0]))
                return best_result[0]
            else:
                # Return original if nothing helped
                return buffer
                    
        except Exception as e:
            raise PDFError(f"Compression failed: {e}")


class PDFRotator:
    """Rotate PDF pages."""
    
    @staticmethod
    def rotate(
        buffer: bytes, 
        angle: int, 
        pages: Optional[list[int]] = None
    ) -> bytes:
        """
        Rotate PDF pages by specified angle.
        
        Args:
            buffer: PDF file bytes
            angle: Rotation angle (90, 180, 270, or -90)
            pages: List of page indices to rotate (0-indexed). None = all pages.
        """
        if angle not in (90, 180, 270, -90):
            raise PDFError("Angle must be 90, 180, 270, or -90")
        
        try:
            reader = PdfReader(io.BytesIO(buffer))
            writer = PdfWriter()
            
            total_pages = len(reader.pages)
            
            for i, page in enumerate(reader.pages):
                if pages is None or i in pages:
                    page.rotate(angle)
                writer.add_page(page)
            
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except PdfReadError as e:
            raise PDFError(f"Invalid PDF file: {e}")


class PDFOrganizer:
    """Reorder and delete PDF pages."""
    
    @staticmethod
    def reorder(buffer: bytes, new_order: list[int]) -> bytes:
        """
        Reorder PDF pages according to new_order list.
        
        Args:
            buffer: PDF file bytes
            new_order: List of page indices in desired order (0-indexed)
        """
        try:
            reader = PdfReader(io.BytesIO(buffer))
            writer = PdfWriter()
            
            total_pages = len(reader.pages)
            
            for page_idx in new_order:
                if 0 <= page_idx < total_pages:
                    writer.add_page(reader.pages[page_idx])
                else:
                    raise PDFError(f"Page {page_idx + 1} out of range")
            
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except PdfReadError as e:
            raise PDFError(f"Invalid PDF file: {e}")
    
    @staticmethod
    def delete_pages(buffer: bytes, pages_to_delete: list[int]) -> bytes:
        """Delete specified pages from PDF."""
        try:
            reader = PdfReader(io.BytesIO(buffer))
            writer = PdfWriter()
            
            delete_set = set(pages_to_delete)
            
            for i, page in enumerate(reader.pages):
                if i not in delete_set:
                    writer.add_page(page)
            
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except PdfReadError as e:
            raise PDFError(f"Invalid PDF file: {e}")


class PDFPageNumbers:
    """Add page numbers to PDF."""
    
    @staticmethod
    def add_page_numbers(
        buffer: bytes,
        position: Literal["bottom-center", "bottom-right", "bottom-left", 
                         "top-center", "top-right", "top-left"] = "bottom-center",
        start_number: int = 1,
        font_size: int = 12,
        margin: int = 36
    ) -> bytes:
        """Add page numbers to all pages of a PDF."""
        try:
            reader = PdfReader(io.BytesIO(buffer))
            writer = PdfWriter()
            
            total_pages = len(reader.pages)
            
            for i, page in enumerate(reader.pages):
                page_num = start_number + i
                
                # Create overlay with page number
                packet = io.BytesIO()
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)
                
                c = canvas.Canvas(packet, pagesize=(page_width, page_height))
                c.setFont("Helvetica", font_size)
                
                text = str(page_num)
                text_width = c.stringWidth(text, "Helvetica", font_size)
                
                # Calculate position
                positions = {
                    "bottom-center": (page_width / 2 - text_width / 2, margin),
                    "bottom-right": (page_width - margin - text_width, margin),
                    "bottom-left": (margin, margin),
                    "top-center": (page_width / 2 - text_width / 2, page_height - margin),
                    "top-right": (page_width - margin - text_width, page_height - margin),
                    "top-left": (margin, page_height - margin),
                }
                
                x, y = positions.get(position, positions["bottom-center"])
                c.drawString(x, y, text)
                c.save()
                
                # Merge overlay onto page
                packet.seek(0)
                overlay_reader = PdfReader(packet)
                overlay_page = overlay_reader.pages[0]
                
                page.merge_page(overlay_page)
                writer.add_page(page)
            
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except PdfReadError as e:
            raise PDFError(f"Invalid PDF file: {e}")


class PDFWatermark:
    """Add watermark to PDF."""
    
    @staticmethod
    def add_text_watermark(
        buffer: bytes,
        text: str,
        opacity: float = 0.3,
        angle: int = 45,
        font_size: int = 60,
        color: tuple[int, int, int] = (128, 128, 128)
    ) -> bytes:
        """Add text watermark to all pages."""
        try:
            reader = PdfReader(io.BytesIO(buffer))
            writer = PdfWriter()
            
            for page in reader.pages:
                packet = io.BytesIO()
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)
                
                c = canvas.Canvas(packet, pagesize=(page_width, page_height))
                c.setFont("Helvetica-Bold", font_size)
                c.setFillColor(Color(color[0]/255, color[1]/255, color[2]/255, alpha=opacity))
                
                # Center and rotate text
                c.saveState()
                c.translate(page_width / 2, page_height / 2)
                c.rotate(angle)
                text_width = c.stringWidth(text, "Helvetica-Bold", font_size)
                c.drawString(-text_width / 2, 0, text)
                c.restoreState()
                c.save()
                
                # Merge watermark
                packet.seek(0)
                watermark_reader = PdfReader(packet)
                watermark_page = watermark_reader.pages[0]
                
                page.merge_page(watermark_page)
                writer.add_page(page)
            
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except PdfReadError as e:
            raise PDFError(f"Invalid PDF file: {e}")
    
    @staticmethod
    def add_image_watermark(
        buffer: bytes,
        image_buffer: bytes,
        opacity: float = 0.3,
        position: Literal["center", "tile"] = "center",
        scale: float = 0.5
    ) -> bytes:
        """Add image watermark to all pages."""
        try:
            reader = PdfReader(io.BytesIO(buffer))
            writer = PdfWriter()
            
            # Prepare image
            img = Image.open(io.BytesIO(image_buffer))
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Apply opacity
            alpha = img.split()[3]
            alpha = alpha.point(lambda p: int(p * opacity))
            img.putalpha(alpha)
            
            for page in reader.pages:
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)
                
                packet = io.BytesIO()
                c = canvas.Canvas(packet, pagesize=(page_width, page_height))
                
                # Calculate scaled dimensions
                img_width = img.width * scale
                img_height = img.height * scale
                
                if position == "center":
                    x = (page_width - img_width) / 2
                    y = (page_height - img_height) / 2
                    
                    # Save image to temp and draw
                    temp_img = io.BytesIO()
                    img.save(temp_img, format='PNG')
                    temp_img.seek(0)
                    c.drawImage(temp_img, x, y, width=img_width, height=img_height, mask='auto')
                
                c.save()
                
                packet.seek(0)
                watermark_reader = PdfReader(packet)
                if watermark_reader.pages:
                    page.merge_page(watermark_reader.pages[0])
                writer.add_page(page)
            
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except Exception as e:
            raise PDFError(f"Watermark failed: {e}")


class PDFProtection:
    """Encrypt and decrypt PDF files."""
    
    @staticmethod
    def encrypt(
        buffer: bytes,
        user_password: str,
        owner_password: Optional[str] = None,
        allow_printing: bool = True,
        allow_copying: bool = False
    ) -> bytes:
        """Encrypt PDF with password protection."""
        try:
            with pikepdf.open(io.BytesIO(buffer)) as pdf:
                permissions = pikepdf.Permissions(
                    print_lowres=allow_printing,
                    print_highres=allow_printing,
                    extract=allow_copying,
                    modify_other=False,
                    modify_annotation=False,
                    modify_form=False,
                    modify_assembly=False,
                )
                
                output = io.BytesIO()
                pdf.save(
                    output,
                    encryption=pikepdf.Encryption(
                        user=user_password,
                        owner=owner_password or user_password,
                        R=6,  # AES-256
                        allow=permissions
                    )
                )
                return output.getvalue()
        except Exception as e:
            raise PDFError(f"Encryption failed: {e}")
    
    @staticmethod
    def decrypt(buffer: bytes, password: str) -> bytes:
        """Remove password protection from PDF."""
        try:
            with pikepdf.open(io.BytesIO(buffer), password=password) as pdf:
                output = io.BytesIO()
                pdf.save(output)
                return output.getvalue()
        except pikepdf.PasswordError:
            raise PDFError("Incorrect password")
        except Exception as e:
            raise PDFError(f"Decryption failed: {e}")


class PDFRepair:
    """Attempt to repair damaged PDFs."""
    
    @staticmethod
    def repair(buffer: bytes) -> bytes:
        """Attempt to repair a damaged PDF file."""
        try:
            # First try with pikepdf which has good repair capabilities
            with pikepdf.open(
                io.BytesIO(buffer), 
                allow_overwriting_input=True
            ) as pdf:
                output = io.BytesIO()
                pdf.save(output, linearize=True)
                return output.getvalue()
        except Exception:
            pass
        
        # Fallback to pypdf
        try:
            reader = PdfReader(io.BytesIO(buffer), strict=False)
            writer = PdfWriter()
            
            for page in reader.pages:
                try:
                    writer.add_page(page)
                except Exception:
                    continue
            
            if len(writer.pages) == 0:
                raise PDFError("Could not recover any pages from PDF")
            
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except Exception as e:
            raise PDFError(f"Repair failed: {e}")


class PDFCropper:
    """Crop PDF pages."""
    
    @staticmethod
    def crop(
        buffer: bytes,
        left: float = 0,
        bottom: float = 0,
        right: float = 0,
        top: float = 0,
        pages: Optional[list[int]] = None
    ) -> bytes:
        """
        Crop PDF pages by specified margins (in points, 72 points = 1 inch).
        """
        try:
            reader = PdfReader(io.BytesIO(buffer))
            writer = PdfWriter()
            
            for i, page in enumerate(reader.pages):
                if pages is None or i in pages:
                    # Get current dimensions
                    media_box = page.mediabox
                    
                    # Apply crop
                    page.mediabox.lower_left = (
                        float(media_box.lower_left[0]) + left,
                        float(media_box.lower_left[1]) + bottom
                    )
                    page.mediabox.upper_right = (
                        float(media_box.upper_right[0]) - right,
                        float(media_box.upper_right[1]) - top
                    )
                
                writer.add_page(page)
            
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
        except PdfReadError as e:
            raise PDFError(f"Invalid PDF file: {e}")


class PDFEditor:
    """Add text, images, and shapes to PDF."""
    
    @staticmethod
    def add_text(
        buffer: bytes,
        text: str,
        page_num: int = 0,
        x: float = 100,
        y: float = 100,
        font_size: int = 12,
        color: str = "black"
    ) -> bytes:
        """Add text annotation to a PDF page."""
        try:
            import fitz
            doc = fitz.open(stream=buffer, filetype="pdf")
            
            if page_num >= len(doc):
                page_num = 0
            
            page = doc[page_num]
            
            # Parse color
            color_map = {
                "black": (0, 0, 0),
                "red": (1, 0, 0),
                "green": (0, 0.5, 0),
                "blue": (0, 0, 1),
                "white": (1, 1, 1),
            }
            text_color = color_map.get(color.lower(), (0, 0, 0))
            
            # Insert text at position (y is from top in fitz)
            page_height = page.rect.height
            point = fitz.Point(x, page_height - y)
            
            page.insert_text(
                point,
                text,
                fontsize=font_size,
                color=text_color,
            )
            
            output = io.BytesIO()
            doc.save(output)
            doc.close()
            return output.getvalue()
        except Exception as e:
            raise PDFError(f"Failed to add text: {e}")
    
    @staticmethod
    def add_image(
        buffer: bytes,
        image_buffer: bytes,
        page_num: int = 0,
        x: float = 100,
        y: float = 100,
        width: float = 200,
        height: float = 200,
    ) -> bytes:
        """Add image to a PDF page."""
        try:
            import fitz
            doc = fitz.open(stream=buffer, filetype="pdf")
            
            if page_num >= len(doc):
                page_num = 0
            
            page = doc[page_num]
            page_height = page.rect.height
            
            # Create rectangle for image (y from top)
            rect = fitz.Rect(x, page_height - y - height, x + width, page_height - y)
            
            # Insert image
            page.insert_image(rect, stream=image_buffer)
            
            output = io.BytesIO()
            doc.save(output)
            doc.close()
            return output.getvalue()
        except Exception as e:
            raise PDFError(f"Failed to add image: {e}")
    
    @staticmethod
    def add_rectangle(
        buffer: bytes,
        page_num: int = 0,
        x: float = 100,
        y: float = 100,
        width: float = 200,
        height: float = 100,
        color: str = "blue",
        fill: bool = False,
        opacity: float = 1.0,
    ) -> bytes:
        """Add rectangle shape to a PDF page."""
        try:
            import fitz
            doc = fitz.open(stream=buffer, filetype="pdf")
            
            if page_num >= len(doc):
                page_num = 0
            
            page = doc[page_num]
            page_height = page.rect.height
            
            # Parse color
            color_map = {
                "black": (0, 0, 0),
                "red": (1, 0, 0),
                "green": (0, 0.5, 0),
                "blue": (0, 0, 1),
                "yellow": (1, 1, 0),
                "orange": (1, 0.5, 0),
            }
            stroke_color = color_map.get(color.lower(), (0, 0, 1))
            
            # Create rectangle (y from top)
            rect = fitz.Rect(x, page_height - y - height, x + width, page_height - y)
            
            fill_color = stroke_color if fill else None
            page.draw_rect(rect, color=stroke_color, fill=fill_color, fill_opacity=opacity)
            
            output = io.BytesIO()
            doc.save(output)
            doc.close()
            return output.getvalue()
        except Exception as e:
            raise PDFError(f"Failed to add rectangle: {e}")


class PDFSigner:
    """Add signatures to PDF."""
    
    @staticmethod
    def add_signature_image(
        buffer: bytes,
        signature_buffer: bytes,
        page_num: int = 0,
        x: float = 100,
        y: float = 100,
        width: float = 200,
        height: float = 80,
    ) -> bytes:
        """Add signature image to a PDF page."""
        try:
            import fitz
            doc = fitz.open(stream=buffer, filetype="pdf")
            
            if page_num >= len(doc):
                page_num = len(doc) - 1  # Default to last page for signatures
            
            page = doc[page_num]
            page_height = page.rect.height
            
            # Create rectangle for signature (y from top)
            rect = fitz.Rect(x, page_height - y - height, x + width, page_height - y)
            
            # Insert signature image
            page.insert_image(rect, stream=signature_buffer)
            
            output = io.BytesIO()
            doc.save(output)
            doc.close()
            return output.getvalue()
        except Exception as e:
            raise PDFError(f"Failed to add signature: {e}")
    
    @staticmethod
    def add_text_signature(
        buffer: bytes,
        name: str,
        page_num: int = -1,  # -1 means last page
        x: float = 100,
        y: float = 100,
        font_size: int = 24,
        include_date: bool = True,
    ) -> bytes:
        """Add text-based signature to a PDF page."""
        try:
            import fitz
            from datetime import datetime
            
            doc = fitz.open(stream=buffer, filetype="pdf")
            
            if page_num < 0 or page_num >= len(doc):
                page_num = len(doc) - 1  # Default to last page
            
            page = doc[page_num]
            page_height = page.rect.height
            
            # Create signature text
            signature_text = name
            if include_date:
                date_str = datetime.now().strftime("%Y-%m-%d")
                signature_text = f"{name}\nSigned: {date_str}"
            
            # Position (y from top)
            point = fitz.Point(x, page_height - y)
            
            # Draw signature line
            line_start = fitz.Point(x, page_height - y + 5)
            line_end = fitz.Point(x + len(name) * font_size * 0.6, page_height - y + 5)
            page.draw_line(line_start, line_end, color=(0, 0, 0), width=1)
            
            # Insert signature text with a cursive-style font
            page.insert_text(
                point,
                signature_text,
                fontsize=font_size,
                color=(0, 0, 0.5),  # Dark blue for signature
            )
            
            output = io.BytesIO()
            doc.save(output)
            doc.close()
            return output.getvalue()
        except Exception as e:
            raise PDFError(f"Failed to add text signature: {e}")
    
    @staticmethod
    def add_drawn_signature(
        buffer: bytes,
        stroke_data: list,  # List of points [{x, y}, ...]
        page_num: int = -1,
        x_offset: float = 100,
        y_offset: float = 100,
        scale: float = 1.0,
        color: str = "blue",
    ) -> bytes:
        """Add a hand-drawn signature from stroke data."""
        try:
            import fitz
            
            doc = fitz.open(stream=buffer, filetype="pdf")
            
            if page_num < 0 or page_num >= len(doc):
                page_num = len(doc) - 1
            
            page = doc[page_num]
            page_height = page.rect.height
            
            color_map = {
                "black": (0, 0, 0),
                "blue": (0, 0, 0.7),
                "darkblue": (0, 0, 0.5),
            }
            stroke_color = color_map.get(color.lower(), (0, 0, 0.7))
            
            # Draw the signature strokes
            if stroke_data and len(stroke_data) > 1:
                for i in range(len(stroke_data) - 1):
                    p1 = stroke_data[i]
                    p2 = stroke_data[i + 1]
                    
                    start = fitz.Point(
                        x_offset + p1.get("x", 0) * scale,
                        page_height - (y_offset + p1.get("y", 0) * scale)
                    )
                    end = fitz.Point(
                        x_offset + p2.get("x", 0) * scale,
                        page_height - (y_offset + p2.get("y", 0) * scale)
                    )
                    
                    page.draw_line(start, end, color=stroke_color, width=2)
            
            output = io.BytesIO()
            doc.save(output)
            doc.close()
            return output.getvalue()
        except Exception as e:
            raise PDFError(f"Failed to add drawn signature: {e}")


def get_pdf_info(buffer: bytes) -> dict:
    """Get information about a PDF file."""
    try:
        reader = PdfReader(io.BytesIO(buffer))
        
        info = {
            "pages": len(reader.pages),
            "encrypted": reader.is_encrypted,
            "metadata": {},
        }
        
        if reader.metadata:
            for key in ["/Title", "/Author", "/Subject", "/Creator", "/Producer"]:
                if key in reader.metadata:
                    info["metadata"][key.replace("/", "")] = reader.metadata[key]
        
        if reader.pages:
            first_page = reader.pages[0]
            info["page_size"] = {
                "width": float(first_page.mediabox.width),
                "height": float(first_page.mediabox.height),
            }
        
        return info
    except PdfReadError as e:
        raise PDFError(f"Invalid PDF file: {e}")
