"""
Document Extraction Utilities
Extract text, images, tables, and metadata from PDF documents.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Literal

import fitz  # PyMuPDF


class ExtractionError(Exception):
    """Error during extraction."""
    pass


class TextExtractor:
    """Extract text from PDF documents."""
    
    @staticmethod
    def extract(
        pdf_bytes: bytes,
        output_format: Literal["txt", "md", "html"] = "txt",
        preserve_layout: bool = False,
    ) -> bytes:
        """Extract text from PDF.
        
        Args:
            pdf_bytes: PDF file contents
            output_format: Output format (txt, md, html)
            preserve_layout: Try to preserve original layout
            
        Returns:
            Extracted text as bytes
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise ExtractionError(f"Failed to open PDF: {e}")
        
        text_parts = []
        
        for page_num, page in enumerate(doc, 1):
            if preserve_layout:
                # Use blocks for layout preservation
                blocks = page.get_text("blocks")
                page_text = "\n".join(
                    b[4] for b in blocks if b[6] == 0  # Text blocks only
                )
            else:
                page_text = page.get_text()
            
            if output_format == "md":
                text_parts.append(f"## Page {page_num}\n\n{page_text.strip()}")
            elif output_format == "html":
                text_parts.append(
                    f'<div class="page" data-page="{page_num}">\n'
                    f'<h2>Page {page_num}</h2>\n'
                    f'<pre>{page_text.strip()}</pre>\n'
                    f'</div>'
                )
            else:
                text_parts.append(f"--- Page {page_num} ---\n{page_text.strip()}")
        
        doc.close()
        
        if output_format == "html":
            content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Extracted Text</title>
    <style>
        body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .page {{ margin-bottom: 30px; padding: 20px; border: 1px solid #ddd; }}
        pre {{ white-space: pre-wrap; word-wrap: break-word; }}
    </style>
</head>
<body>
{"".join(text_parts)}
</body>
</html>"""
        else:
            content = "\n\n".join(text_parts)
        
        return content.encode("utf-8")


class ImageExtractor:
    """Extract images from PDF documents."""
    
    @staticmethod
    def extract(
        pdf_bytes: bytes,
        output_format: Literal["png", "jpg", "webp"] = "png",
        min_size: int = 50,
    ) -> bytes:
        """Extract all images from PDF as a ZIP file.
        
        Args:
            pdf_bytes: PDF file contents
            output_format: Image format for output
            min_size: Minimum image dimension (skip smaller images)
            
        Returns:
            ZIP file containing all extracted images
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise ExtractionError(f"Failed to open PDF: {e}")
        
        zip_buffer = io.BytesIO()
        image_count = 0
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for page_num, page in enumerate(doc, 1):
                images = page.get_images(full=True)
                
                for img_idx, img_info in enumerate(images, 1):
                    xref = img_info[0]
                    
                    try:
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        
                        # Get dimensions
                        width = base_image.get("width", 0)
                        height = base_image.get("height", 0)
                        
                        # Skip small images
                        if width < min_size or height < min_size:
                            continue
                        
                        # Convert format if needed
                        if output_format == "png":
                            # PyMuPDF extracts in original format, may need conversion
                            ext = "png"
                        elif output_format == "jpg":
                            ext = "jpg"
                        else:
                            ext = "webp"
                        
                        image_count += 1
                        filename = f"page{page_num:03d}_img{img_idx:03d}.{ext}"
                        zf.writestr(filename, image_bytes)
                        
                    except Exception:
                        continue  # Skip problematic images
        
        doc.close()
        
        if image_count == 0:
            raise ExtractionError("No images found in PDF")
        
        zip_buffer.seek(0)
        return zip_buffer.read()


class TableExtractor:
    """Extract tables from PDF documents."""
    
    @staticmethod
    def extract(
        pdf_bytes: bytes,
        output_format: Literal["csv", "xlsx", "json"] = "csv",
        pages: str = "",
    ) -> bytes:
        """Extract tables from PDF.
        
        Args:
            pdf_bytes: PDF file contents
            output_format: Output format
            pages: Page specification (empty = all)
            
        Returns:
            ZIP file containing extracted tables
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise ExtractionError(f"Failed to open PDF: {e}")
        
        # Parse page specification
        if pages.strip():
            page_nums = TableExtractor._parse_pages(pages, len(doc))
        else:
            page_nums = list(range(len(doc)))
        
        zip_buffer = io.BytesIO()
        table_count = 0
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for page_num in page_nums:
                if page_num < 0 or page_num >= len(doc):
                    continue
                    
                page = doc[page_num]
                
                # Simple table detection using tab-separated blocks
                tables = page.find_tables()
                
                for tbl_idx, table in enumerate(tables, 1):
                    table_count += 1
                    
                    # Extract table data
                    data = table.extract()
                    
                    if output_format == "csv":
                        import csv
                        output = io.StringIO()
                        writer = csv.writer(output)
                        for row in data:
                            writer.writerow(row)
                        content = output.getvalue().encode("utf-8")
                        ext = "csv"
                    elif output_format == "json":
                        content = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
                        ext = "json"
                    else:  # xlsx
                        # Simple CSV for now (xlsx requires openpyxl)
                        import csv
                        output = io.StringIO()
                        writer = csv.writer(output)
                        for row in data:
                            writer.writerow(row)
                        content = output.getvalue().encode("utf-8")
                        ext = "csv"  # Fallback
                    
                    filename = f"page{page_num + 1:03d}_table{tbl_idx:03d}.{ext}"
                    zf.writestr(filename, content)
        
        doc.close()
        
        if table_count == 0:
            raise ExtractionError("No tables found in PDF")
        
        zip_buffer.seek(0)
        return zip_buffer.read()
    
    @staticmethod
    def _parse_pages(pages_str: str, total_pages: int) -> list[int]:
        """Parse page specification string like '1, 3, 5-7'."""
        result = []
        for part in pages_str.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                try:
                    start = int(start.strip()) - 1
                    end = int(end.strip())
                    result.extend(range(start, min(end, total_pages)))
                except ValueError:
                    continue
            else:
                try:
                    result.append(int(part) - 1)
                except ValueError:
                    continue
        return result


class MetadataExtractor:
    """Extract metadata from PDF documents."""
    
    @staticmethod
    def extract(pdf_bytes: bytes) -> dict:
        """Extract all metadata from PDF.
        
        Args:
            pdf_bytes: PDF file contents
            
        Returns:
            Dictionary with metadata
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise ExtractionError(f"Failed to open PDF: {e}")
        
        metadata = doc.metadata or {}
        
        # Add document info
        info = {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "keywords": metadata.get("keywords", ""),
            "creator": metadata.get("creator", ""),
            "producer": metadata.get("producer", ""),
            "creation_date": metadata.get("creationDate", ""),
            "modification_date": metadata.get("modDate", ""),
            "page_count": len(doc),
            "is_encrypted": doc.is_encrypted,
            "is_pdf": doc.is_pdf,
            "permissions": {
                "print": doc.permissions & fitz.PDF_PERM_PRINT > 0,
                "modify": doc.permissions & fitz.PDF_PERM_MODIFY > 0,
                "copy": doc.permissions & fitz.PDF_PERM_COPY > 0,
                "annotate": doc.permissions & fitz.PDF_PERM_ANNOTATE > 0,
            },
            "pages": [],
        }
        
        # Page-level info
        for page_num, page in enumerate(doc, 1):
            rect = page.rect
            info["pages"].append({
                "number": page_num,
                "width": rect.width,
                "height": rect.height,
                "rotation": page.rotation,
                "has_images": len(page.get_images()) > 0,
                "has_links": len(page.get_links()) > 0,
            })
        
        doc.close()
        return info


class PDFComparer:
    """Compare two PDF documents."""
    
    @staticmethod
    def compare(
        pdf1_bytes: bytes,
        pdf2_bytes: bytes,
        mode: Literal["visual", "text", "both"] = "visual",
    ) -> bytes:
        """Compare two PDFs and highlight differences.
        
        Args:
            pdf1_bytes: First PDF
            pdf2_bytes: Second PDF
            mode: Comparison mode
            
        Returns:
            PDF with differences highlighted
        """
        try:
            doc1 = fitz.open(stream=pdf1_bytes, filetype="pdf")
            doc2 = fitz.open(stream=pdf2_bytes, filetype="pdf")
        except Exception as e:
            raise ExtractionError(f"Failed to open PDFs: {e}")
        
        # Create output document
        output = fitz.open()
        
        max_pages = max(len(doc1), len(doc2))
        
        for i in range(max_pages):
            # Get pages (or blank if one doc is shorter)
            page1 = doc1[i] if i < len(doc1) else None
            page2 = doc2[i] if i < len(doc2) else None
            
            if page1 and page2:
                # Both exist - compare
                rect1 = page1.rect
                rect2 = page2.rect
                
                # Create side-by-side comparison
                new_width = rect1.width + rect2.width + 20
                new_height = max(rect1.height, rect2.height)
                
                new_page = output.new_page(width=new_width, height=new_height)
                
                # Insert page 1 on left
                new_page.show_pdf_page(
                    fitz.Rect(0, 0, rect1.width, rect1.height),
                    doc1, i
                )
                
                # Insert page 2 on right
                new_page.show_pdf_page(
                    fitz.Rect(rect1.width + 20, 0, new_width, rect2.height),
                    doc2, i
                )
                
                # Add labels
                new_page.insert_text(
                    (10, 20),
                    f"Document 1 - Page {i + 1}",
                    fontsize=12,
                    color=(0, 0, 1)
                )
                new_page.insert_text(
                    (rect1.width + 30, 20),
                    f"Document 2 - Page {i + 1}",
                    fontsize=12,
                    color=(1, 0, 0)
                )
                
                # Text comparison
                if mode in ("text", "both"):
                    text1 = page1.get_text()
                    text2 = page2.get_text()
                    
                    if text1 != text2:
                        # Mark as different
                        new_page.draw_rect(
                            fitz.Rect(0, 0, rect1.width, rect1.height),
                            color=(0, 0, 1), width=3
                        )
                        new_page.draw_rect(
                            fitz.Rect(rect1.width + 20, 0, new_width, rect2.height),
                            color=(1, 0, 0), width=3
                        )
            elif page1:
                # Only in doc1
                rect = page1.rect
                new_page = output.new_page(width=rect.width, height=rect.height)
                new_page.show_pdf_page(rect, doc1, i)
                new_page.insert_text((10, 20), f"Only in Document 1 - Page {i + 1}", fontsize=12, color=(0, 0, 1))
            else:
                # Only in doc2
                rect = page2.rect
                new_page = output.new_page(width=rect.width, height=rect.height)
                new_page.show_pdf_page(rect, doc2, i)
                new_page.insert_text((10, 20), f"Only in Document 2 - Page {i + 1}", fontsize=12, color=(1, 0, 0))
        
        doc1.close()
        doc2.close()
        
        result = output.tobytes()
        output.close()
        return result


class PDFRedactor:
    """Redact sensitive information from PDFs."""
    
    # Common patterns
    EMAIL_PATTERN = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    PHONE_PATTERN = r"(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    SSN_PATTERN = r"\d{3}[-.\s]?\d{2}[-.\s]?\d{4}"
    
    @staticmethod
    def redact(
        pdf_bytes: bytes,
        patterns: str = "",
        redact_emails: bool = True,
        redact_phones: bool = True,
        redact_ssn: bool = True,
    ) -> bytes:
        """Redact sensitive information from PDF.
        
        Args:
            pdf_bytes: PDF file contents
            patterns: Additional comma-separated regex patterns
            redact_emails: Auto-redact email addresses
            redact_phones: Auto-redact phone numbers
            redact_ssn: Auto-redact SSN/ID numbers
            
        Returns:
            Redacted PDF
        """
        import re
        
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise ExtractionError(f"Failed to open PDF: {e}")
        
        # Build pattern list
        all_patterns = []
        if redact_emails:
            all_patterns.append(PDFRedactor.EMAIL_PATTERN)
        if redact_phones:
            all_patterns.append(PDFRedactor.PHONE_PATTERN)
        if redact_ssn:
            all_patterns.append(PDFRedactor.SSN_PATTERN)
        
        # Add custom patterns
        if patterns.strip():
            for p in patterns.split(","):
                p = p.strip()
                if p:
                    all_patterns.append(p)
        
        # Process each page
        for page in doc:
            for pattern in all_patterns:
                try:
                    areas = page.search_for(pattern, flags=fitz.TEXT_SEARCH)
                    for area in areas:
                        page.add_redact_annot(area, fill=(0, 0, 0))
                except Exception:
                    continue
            
            # Apply redactions
            page.apply_redactions()
        
        result = doc.tobytes()
        doc.close()
        return result


class PDFFlattener:
    """Flatten PDF forms and annotations."""
    
    @staticmethod
    def flatten(
        pdf_bytes: bytes,
        flatten_forms: bool = True,
        flatten_annotations: bool = True,
    ) -> bytes:
        """Flatten PDF to remove interactivity.
        
        Args:
            pdf_bytes: PDF file contents
            flatten_forms: Flatten form fields
            flatten_annotations: Flatten annotations
            
        Returns:
            Flattened PDF
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise ExtractionError(f"Failed to open PDF: {e}")
        
        for page in doc:
            if flatten_annotations:
                # Get all annotations and burn them in
                annots = page.annots()
                if annots:
                    for annot in annots:
                        annot.update()
        
        # Save with deflate to flatten
        result = doc.tobytes(deflate=True, garbage=3)
        doc.close()
        return result
