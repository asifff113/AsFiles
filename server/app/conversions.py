"""
Document Conversion Module
Handles conversions between PDF, Word, PowerPoint, Excel, and image formats.
"""

from __future__ import annotations

import io
import os
import tempfile
import zipfile
from typing import Optional, Literal
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import img2pdf

try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    from docx import Document
    from docx.shared import Inches, Pt
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from pptx import Presentation
    from pptx.util import Inches as PPTXInches, Pt as PPTXPt
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


class ConversionError(Exception):
    """Base exception for conversion operations."""
    pass


class PDFToImageConverter:
    """Convert PDF pages to images."""
    
    @staticmethod
    def convert(
        buffer: bytes,
        format: Literal["jpg", "png"] = "jpg",
        dpi: int = 150,
        pages: Optional[list[int]] = None
    ) -> list[bytes]:
        """
        Convert PDF pages to images.
        
        Args:
            buffer: PDF file bytes
            format: Output format (jpg or png)
            dpi: Resolution in dots per inch
            pages: Specific page numbers (0-indexed), None for all pages
            
        Returns:
            List of image bytes for each page
        """
        if not PDF2IMAGE_AVAILABLE:
            raise ConversionError("pdf2image library not available. Install poppler.")
        
        try:
            # Convert all pages or specific pages
            if pages:
                # pdf2image uses 1-indexed pages
                first_page = min(pages) + 1
                last_page = max(pages) + 1
                images = convert_from_bytes(
                    buffer,
                    dpi=dpi,
                    first_page=first_page,
                    last_page=last_page
                )
            else:
                images = convert_from_bytes(buffer, dpi=dpi)
            
            results = []
            for i, img in enumerate(images):
                if pages and (i + (pages[0] if pages else 0)) not in pages:
                    continue
                    
                output = io.BytesIO()
                if format == "jpg":
                    img = img.convert("RGB")
                    img.save(output, format="JPEG", quality=85, optimize=True)
                else:
                    img.save(output, format="PNG", optimize=True)
                results.append(output.getvalue())
            
            return results
        except Exception as e:
            raise ConversionError(f"PDF to image conversion failed: {e}")
    
    @staticmethod
    def convert_to_zip(
        buffer: bytes,
        format: Literal["jpg", "png"] = "jpg",
        dpi: int = 150
    ) -> bytes:
        """Convert all PDF pages to images and return as ZIP file."""
        images = PDFToImageConverter.convert(buffer, format, dpi)
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, img_bytes in enumerate(images):
                filename = f"page_{i + 1:03d}.{format}"
                zf.writestr(filename, img_bytes)
        
        return zip_buffer.getvalue()


class ImageToPDFConverter:
    """Convert images to PDF."""
    
    @staticmethod
    def convert(
        image_buffers: list[bytes],
        page_size: Literal["a4", "letter", "fit"] = "a4",
        margin: float = 0.5  # inches
    ) -> bytes:
        """
        Convert multiple images to a single PDF.
        
        Args:
            image_buffers: List of image file bytes
            page_size: Page size or 'fit' to match image dimensions
            margin: Page margin in inches
            
        Returns:
            PDF file bytes
        """
        if not image_buffers:
            raise ConversionError("No images provided")
        
        try:
            if page_size == "fit":
                # Use img2pdf for exact image dimensions
                return img2pdf.convert(image_buffers)
            
            # Create PDF with specified page size
            page_sizes = {
                "a4": A4,
                "letter": letter,
            }
            size = page_sizes.get(page_size, A4)
            
            output = io.BytesIO()
            c = canvas.Canvas(output, pagesize=size)
            page_width, page_height = size
            margin_pts = margin * inch
            
            for img_bytes in image_buffers:
                img = Image.open(io.BytesIO(img_bytes))
                
                # Calculate available space
                available_width = page_width - (2 * margin_pts)
                available_height = page_height - (2 * margin_pts)
                
                # Scale image to fit
                img_width, img_height = img.size
                scale = min(available_width / img_width, available_height / img_height)
                
                new_width = img_width * scale
                new_height = img_height * scale
                
                # Center image
                x = margin_pts + (available_width - new_width) / 2
                y = margin_pts + (available_height - new_height) / 2
                
                # Save temp image for reportlab
                temp_img = io.BytesIO()
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(temp_img, format='JPEG', quality=95)
                temp_img.seek(0)
                
                from reportlab.lib.utils import ImageReader
                c.drawImage(ImageReader(temp_img), x, y, width=new_width, height=new_height)
                c.showPage()
            
            c.save()
            return output.getvalue()
            
        except Exception as e:
            raise ConversionError(f"Image to PDF conversion failed: {e}")


class PDFToWordConverter:
    """Convert PDF to Word document."""
    
    @staticmethod
    def convert(buffer: bytes) -> bytes:
        """
        Convert PDF to DOCX format.
        Note: This creates a basic text extraction. Complex layouts may not be preserved.
        """
        if not DOCX_AVAILABLE:
            raise ConversionError("python-docx library not available")
        
        if not PDFPLUMBER_AVAILABLE:
            raise ConversionError("pdfplumber library not available")
        
        try:
            doc = Document()
            
            with pdfplumber.open(io.BytesIO(buffer)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract text
                    text = page.extract_text()
                    if text:
                        for paragraph in text.split('\n\n'):
                            if paragraph.strip():
                                doc.add_paragraph(paragraph.strip())
                    
                    # Add page break between pages (except last)
                    if page_num < len(pdf.pages) - 1:
                        doc.add_page_break()
            
            output = io.BytesIO()
            doc.save(output)
            return output.getvalue()
            
        except Exception as e:
            raise ConversionError(f"PDF to Word conversion failed: {e}")


class WordToPDFConverter:
    """Convert Word documents to PDF."""
    
    @staticmethod
    def convert(buffer: bytes) -> bytes:
        """
        Convert DOCX to PDF format.
        Uses reportlab for cross-platform compatibility.
        """
        if not DOCX_AVAILABLE:
            raise ConversionError("python-docx library not available")
        
        try:
            doc = Document(io.BytesIO(buffer))
            
            output = io.BytesIO()
            c = canvas.Canvas(output, pagesize=letter)
            page_width, page_height = letter
            
            margin = 72  # 1 inch
            y_position = page_height - margin
            line_height = 14
            
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    y_position -= line_height
                    continue
                
                # Simple word wrapping
                words = text.split()
                lines = []
                current_line = []
                
                for word in words:
                    current_line.append(word)
                    test_line = ' '.join(current_line)
                    text_width = c.stringWidth(test_line, "Helvetica", 11)
                    
                    if text_width > (page_width - 2 * margin):
                        current_line.pop()
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]
                
                if current_line:
                    lines.append(' '.join(current_line))
                
                # Check for page break
                if y_position - (len(lines) * line_height) < margin:
                    c.showPage()
                    y_position = page_height - margin
                
                for line in lines:
                    c.setFont("Helvetica", 11)
                    c.drawString(margin, y_position, line)
                    y_position -= line_height
                
                y_position -= line_height / 2  # Paragraph spacing
            
            c.save()
            return output.getvalue()
            
        except Exception as e:
            raise ConversionError(f"Word to PDF conversion failed: {e}")


class PDFToExcelConverter:
    """Convert PDF tables to Excel."""
    
    @staticmethod
    def convert(buffer: bytes) -> bytes:
        """
        Extract tables from PDF and convert to Excel.
        """
        if not OPENPYXL_AVAILABLE:
            raise ConversionError("openpyxl library not available")
        
        if not PDFPLUMBER_AVAILABLE:
            raise ConversionError("pdfplumber library not available")
        
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Extracted Data"
            
            row_offset = 1
            
            with pdfplumber.open(io.BytesIO(buffer)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    
                    if tables:
                        for table in tables:
                            for row in table:
                                for col_idx, cell in enumerate(row):
                                    ws.cell(
                                        row=row_offset, 
                                        column=col_idx + 1, 
                                        value=cell if cell else ""
                                    )
                                row_offset += 1
                            row_offset += 1  # Space between tables
                    else:
                        # If no tables found, extract text
                        text = page.extract_text()
                        if text:
                            ws.cell(row=row_offset, column=1, value=f"--- Page {page_num + 1} ---")
                            row_offset += 1
                            for line in text.split('\n'):
                                ws.cell(row=row_offset, column=1, value=line)
                                row_offset += 1
                            row_offset += 1
            
            output = io.BytesIO()
            wb.save(output)
            return output.getvalue()
            
        except Exception as e:
            raise ConversionError(f"PDF to Excel conversion failed: {e}")


class ExcelToPDFConverter:
    """Convert Excel to PDF."""
    
    @staticmethod
    def convert(buffer: bytes) -> bytes:
        """Convert Excel file to PDF format with better formatting."""
        if not OPENPYXL_AVAILABLE:
            raise ConversionError("openpyxl library not available")
        
        try:
            wb = openpyxl.load_workbook(io.BytesIO(buffer), data_only=True)
            
            output = io.BytesIO()
            c = canvas.Canvas(output, pagesize=letter)
            page_width, page_height = letter
            
            margin = 40
            
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                
                # Calculate column widths based on content
                col_widths = {}
                max_row = 0
                for row_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
                    max_row = max(max_row, row_idx)
                    for col_idx, cell_value in enumerate(row):
                        if cell_value is not None:
                            width = len(str(cell_value)) * 6 + 10
                            col_widths[col_idx] = max(col_widths.get(col_idx, 60), min(width, 120))
                
                # Calculate total width needed
                total_width = sum(col_widths.values())
                available_width = page_width - (2 * margin)
                
                # Scale if needed
                if total_width > available_width:
                    scale_factor = available_width / total_width
                    col_widths = {k: v * scale_factor for k, v in col_widths.items()}
                
                y_position = page_height - margin
                row_height = 16
                
                # Sheet title
                c.setFont("Helvetica-Bold", 12)
                c.drawString(margin, y_position, f"Sheet: {sheet_name}")
                y_position -= row_height * 1.5
                
                # Draw table
                for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                    if y_position < margin + row_height * 2:
                        c.showPage()
                        y_position = page_height - margin
                    
                    # Use bold for first row (headers)
                    if row_idx == 0:
                        c.setFont("Helvetica-Bold", 9)
                    else:
                        c.setFont("Helvetica", 9)
                    
                    x_position = margin
                    for col_idx, cell_value in enumerate(row):
                        if x_position > page_width - margin:
                            break
                            
                        if cell_value is not None:
                            # Handle numeric formatting
                            if isinstance(cell_value, (int, float)):
                                if isinstance(cell_value, float):
                                    text = f"{cell_value:.2f}"
                                else:
                                    text = str(cell_value)
                            else:
                                text = str(cell_value)
                            
                            # Truncate if too long
                            col_w = col_widths.get(col_idx, 60)
                            max_chars = int(col_w / 6)
                            if len(text) > max_chars:
                                text = text[:max_chars-2] + ".."
                            
                            c.drawString(x_position, y_position, text)
                        
                        x_position += col_widths.get(col_idx, 60)
                    
                    y_position -= row_height
                
                # New page for each sheet
                c.showPage()
                y_position = page_height - margin
            
            c.save()
            return output.getvalue()
            
        except Exception as e:
            raise ConversionError(f"Excel to PDF conversion failed: {e}")


class PDFToPowerPointConverter:
    """Convert PDF to PowerPoint."""
    
    @staticmethod
    def convert(buffer: bytes, dpi: int = 150) -> bytes:
        """
        Convert PDF to PowerPoint by converting each page to an image slide.
        """
        if not PPTX_AVAILABLE:
            raise ConversionError("python-pptx library not available")
        
        if not PDF2IMAGE_AVAILABLE:
            raise ConversionError("pdf2image library not available")
        
        try:
            # Convert PDF pages to images
            images = convert_from_bytes(buffer, dpi=dpi)
            
            # Create PowerPoint presentation
            prs = Presentation()
            prs.slide_width = PPTXInches(13.333)  # 16:9 widescreen
            prs.slide_height = PPTXInches(7.5)
            
            blank_layout = prs.slide_layouts[6]  # Blank layout
            
            for img in images:
                slide = prs.slides.add_slide(blank_layout)
                
                # Save image to bytes
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                # Calculate dimensions to fit slide
                slide_width = prs.slide_width
                slide_height = prs.slide_height
                
                img_width, img_height = img.size
                scale = min(
                    slide_width / PPTXInches(img_width / dpi),
                    slide_height / PPTXInches(img_height / dpi)
                )
                
                new_width = int(img_width / dpi * scale)
                new_height = int(img_height / dpi * scale)
                
                left = (slide_width - PPTXInches(new_width)) / 2
                top = (slide_height - PPTXInches(new_height)) / 2
                
                slide.shapes.add_picture(
                    img_buffer,
                    PPTXInches(0.25),
                    PPTXInches(0.25),
                    width=slide_width - PPTXInches(0.5),
                    height=slide_height - PPTXInches(0.5)
                )
            
            output = io.BytesIO()
            prs.save(output)
            return output.getvalue()
            
        except Exception as e:
            raise ConversionError(f"PDF to PowerPoint conversion failed: {e}")


class PowerPointToPDFConverter:
    """Convert PowerPoint to PDF."""
    
    @staticmethod
    def convert(buffer: bytes) -> bytes:
        """
        Convert PowerPoint to PDF using the best available method.
        Priority: LibreOffice (unlimited) → PowerPoint COM (Windows) → CloudConvert API → Basic
        """
        import platform
        import os
        
        # Try LibreOffice first (unlimited, free, installed in Docker)
        try:
            return PowerPointToPDFConverter._convert_with_libreoffice(buffer)
        except Exception as e:
            print(f"LibreOffice failed: {e}, trying other methods...")
        
        # On Windows, try to use PowerPoint COM for accurate conversion
        if platform.system() == "Windows":
            try:
                return PowerPointToPDFConverter._convert_with_com(buffer)
            except Exception as e:
                print(f"COM conversion failed: {e}, trying CloudConvert...")
                pass
        
        # Try CloudConvert API as fallback (limited free quota)
        cloudconvert_key = os.environ.get('CLOUDCONVERT_API_KEY')
        if cloudconvert_key:
            try:
                return PowerPointToPDFConverter._convert_with_cloudconvert(buffer, cloudconvert_key)
            except Exception as e:
                print(f"CloudConvert failed: {e}, trying basic method...")
        
        # Final fallback: basic text extraction
        return PowerPointToPDFConverter._convert_basic(buffer)
    
    @staticmethod
    def _convert_with_cloudconvert(buffer: bytes, api_key: str) -> bytes:
        """Convert using CloudConvert API (25 free/day)."""
        import requests
        import time
        
        headers = {"Authorization": f"Bearer {api_key}"}
        base_url = "https://api.cloudconvert.com/v2"
        
        # Step 1: Create job
        job_response = requests.post(
            f"{base_url}/jobs",
            headers=headers,
            json={
                "tasks": {
                    "upload-file": {"operation": "import/upload"},
                    "convert-file": {
                        "operation": "convert",
                        "input": ["upload-file"],
                        "output_format": "pdf"
                    },
                    "export-file": {
                        "operation": "export/url",
                        "input": ["convert-file"]
                    }
                }
            }
        )
        job_response.raise_for_status()
        job_data = job_response.json()
        
        # Step 2: Upload file
        upload_task = next(t for t in job_data["data"]["tasks"] if t["name"] == "upload-file")
        upload_url = upload_task["result"]["form"]["url"]
        upload_params = upload_task["result"]["form"]["parameters"]
        
        files = {"file": ("input.pptx", buffer, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        upload_response = requests.post(upload_url, data=upload_params, files=files)
        upload_response.raise_for_status()
        
        # Step 3: Wait for conversion
        job_id = job_data["data"]["id"]
        for _ in range(60):  # Wait up to 60 seconds
            time.sleep(1)
            status_response = requests.get(f"{base_url}/jobs/{job_id}", headers=headers)
            status_data = status_response.json()
            
            if status_data["data"]["status"] == "finished":
                # Get download URL
                export_task = next(t for t in status_data["data"]["tasks"] if t["name"] == "export-file")
                download_url = export_task["result"]["files"][0]["url"]
                
                # Download PDF
                pdf_response = requests.get(download_url)
                return pdf_response.content
            elif status_data["data"]["status"] == "error":
                raise ConversionError("CloudConvert conversion failed")
        
        raise ConversionError("CloudConvert conversion timed out")
    
    @staticmethod
    def _convert_with_com(buffer: bytes) -> bytes:
        """Convert using Microsoft PowerPoint COM (Windows only)."""
        import tempfile
        import os
        
        try:
            import comtypes.client
        except ImportError:
            raise ConversionError("comtypes not available")
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as tmp_pptx:
            tmp_pptx.write(buffer)
            pptx_path = tmp_pptx.name
        
        pdf_path = pptx_path.replace('.pptx', '.pdf')
        
        try:
            powerpoint = comtypes.client.CreateObject("PowerPoint.Application")
            powerpoint.Visible = 1
            
            presentation = powerpoint.Presentations.Open(pptx_path)
            presentation.SaveAs(pdf_path, 32)  # 32 = ppSaveAsPDF
            presentation.Close()
            powerpoint.Quit()
            
            with open(pdf_path, 'rb') as f:
                result = f.read()
            
            return result
        finally:
            # Cleanup
            if os.path.exists(pptx_path):
                os.unlink(pptx_path)
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)
    
    @staticmethod
    def _convert_with_libreoffice(buffer: bytes) -> bytes:
        """Convert using LibreOffice."""
        import tempfile
        import subprocess
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pptx_path = os.path.join(tmpdir, 'input.pptx')
            
            with open(pptx_path, 'wb') as f:
                f.write(buffer)
            
            # Try different LibreOffice paths
            soffice_paths = [
                'soffice',
                '/usr/bin/soffice',
                '/usr/bin/libreoffice',
                'C:\\Program Files\\LibreOffice\\program\\soffice.exe',
                'C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe',
            ]
            
            for soffice in soffice_paths:
                try:
                    result = subprocess.run([
                        soffice,
                        '--headless',
                        '--convert-to', 'pdf',
                        '--outdir', tmpdir,
                        pptx_path
                    ], capture_output=True, timeout=120)
                    
                    pdf_path = os.path.join(tmpdir, 'input.pdf')
                    if os.path.exists(pdf_path):
                        with open(pdf_path, 'rb') as f:
                            return f.read()
                except FileNotFoundError:
                    continue
                except subprocess.TimeoutExpired:
                    raise ConversionError("LibreOffice conversion timed out")
            
            raise ConversionError("LibreOffice not found")
    
    @staticmethod
    def _convert_basic(buffer: bytes) -> bytes:
        """Basic fallback: render slides as images then combine to PDF."""
        if not PPTX_AVAILABLE:
            raise ConversionError("python-pptx library not available")
        
        try:
            prs = Presentation(io.BytesIO(buffer))
            
            # Get slide dimensions
            slide_width = prs.slide_width.pt
            slide_height = prs.slide_height.pt
            
            output = io.BytesIO()
            c = canvas.Canvas(output, pagesize=(slide_width, slide_height))
            
            for slide_num, slide in enumerate(prs.slides, 1):
                # Draw white background
                c.setFillColorRGB(1, 1, 1)
                c.rect(0, 0, slide_width, slide_height, fill=1)
                
                # Try to extract shapes with better positioning
                shapes_data = []
                
                for shape in slide.shapes:
                    try:
                        if hasattr(shape, 'left') and hasattr(shape, 'top'):
                            x = shape.left.pt if hasattr(shape.left, 'pt') else 50
                            y = slide_height - (shape.top.pt if hasattr(shape.top, 'pt') else 50)
                            width = shape.width.pt if hasattr(shape, 'width') and hasattr(shape.width, 'pt') else 400
                            
                            if hasattr(shape, "text") and shape.text.strip():
                                shapes_data.append({
                                    'x': x,
                                    'y': y,
                                    'text': shape.text.strip(),
                                    'width': width
                                })
                    except:
                        pass
                
                # Sort by vertical position (top to bottom)
                shapes_data.sort(key=lambda s: -s['y'])
                
                for shape_data in shapes_data:
                    text = shape_data['text']
                    x = max(30, shape_data['x'])
                    y = shape_data['y']
                    max_width = shape_data['width']
                    
                    # Determine font size based on position (titles are usually at top)
                    if y > slide_height - 100:
                        font_size = 24
                        c.setFont("Helvetica-Bold", font_size)
                    else:
                        font_size = 14
                        c.setFont("Helvetica", font_size)
                    
                    # Word wrap
                    words = text.split()
                    lines = []
                    current_line = []
                    
                    for word in words:
                        current_line.append(word)
                        test_line = ' '.join(current_line)
                        if c.stringWidth(test_line, "Helvetica", font_size) > max_width - 20:
                            current_line.pop()
                            if current_line:
                                lines.append(' '.join(current_line))
                            current_line = [word]
                    
                    if current_line:
                        lines.append(' '.join(current_line))
                    
                    for line in lines:
                        if y > 30:
                            c.drawString(x, y, line)
                            y -= font_size + 4
                
                # Add slide number at bottom
                c.setFont("Helvetica", 10)
                c.setFillColorRGB(0.5, 0.5, 0.5)
                c.drawString(slide_width - 50, 20, str(slide_num))
                
                c.showPage()
            
            c.save()
            return output.getvalue()
            
        except Exception as e:
            raise ConversionError(f"PowerPoint to PDF conversion failed: {e}")


class HTMLToPDFConverter:
    """Convert HTML/URL to PDF."""
    
    @staticmethod
    async def convert_url(url: str) -> bytes:
        """Convert a webpage URL to PDF using pyppeteer."""
        try:
            from pyppeteer import launch
            import os
            import asyncio
            
            # Use system Chromium if available (Docker)
            chromium_path = os.environ.get('PUPPETEER_EXECUTABLE_PATH', None)
            
            browser = await launch(
                headless=True,
                executablePath=chromium_path,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            page = await browser.newPage()
            
            # Set viewport to capture full page
            await page.setViewport({'width': 1920, 'height': 1080})
            
            # Navigate to page
            await page.goto(url, waitUntil='networkidle0', timeout=60000)
            
            # Scroll through entire page to trigger lazy loading
            await page.evaluate('''async () => {
                await new Promise((resolve) => {
                    let totalHeight = 0;
                    const distance = 500;
                    const timer = setInterval(() => {
                        const scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        if (totalHeight >= scrollHeight) {
                            clearInterval(timer);
                            window.scrollTo(0, 0);
                            resolve();
                        }
                    }, 100);
                });
            }''')
            
            # Wait for images to load
            await page.evaluate('''async () => {
                const images = document.querySelectorAll('img');
                await Promise.all(
                    Array.from(images).map(img => {
                        if (img.complete) return Promise.resolve();
                        return new Promise((resolve) => {
                            img.addEventListener('load', resolve);
                            img.addEventListener('error', resolve);
                            setTimeout(resolve, 5000);
                        });
                    })
                );
            }''')
            
            # Extra wait for any animations/transitions
            await asyncio.sleep(2)
            
            pdf_bytes = await page.pdf({
                'format': 'A4',
                'printBackground': True,
                'margin': {
                    'top': '1cm',
                    'bottom': '1cm',
                    'left': '1cm',
                    'right': '1cm'
                }
            })
            
            await browser.close()
            return pdf_bytes
            
        except ImportError:
            raise ConversionError("pyppeteer library not available")
        except Exception as e:
            raise ConversionError(f"HTML to PDF conversion failed: {e}")
    
    @staticmethod
    def convert_html_string(html: str) -> bytes:
        """Convert HTML string to PDF using reportlab."""
        try:
            from reportlab.platypus import SimpleDocTemplate, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
            
            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=letter)
            styles = getSampleStyleSheet()
            
            # Simple HTML to text conversion
            import re
            text = re.sub(r'<[^>]+>', ' ', html)
            text = ' '.join(text.split())
            
            story = [Paragraph(text, styles['Normal'])]
            doc.build(story)
            
            return output.getvalue()
            
        except Exception as e:
            raise ConversionError(f"HTML to PDF conversion failed: {e}")
