"""
DocFlow API - Comprehensive Document Processing Server
Handles all document transformations including PDF, Word, Excel, PowerPoint, and images.
"""

from __future__ import annotations

import io
import asyncio
from typing import List, Optional, Literal
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import fitz  # PyMuPDF

from fastapi import FastAPI, File, HTTPException, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

# Import local modules
from .pptx_merge import MergeError, merge_presentations
from .pdf_processing import (
    PDFError,
    PDFMerger,
    PDFSplitter,
    PDFCompressor,
    PDFRotator,
    PDFOrganizer,
    PDFPageNumbers,
    PDFWatermark,
    PDFProtection,
    PDFRepair,
    PDFCropper,
    PDFEditor,
    PDFSigner,
    get_pdf_info,
)
from .conversions import (
    ConversionError,
    PDFToImageConverter,
    ImageToPDFConverter,
    PDFToWordConverter,
    WordToPDFConverter,
    PDFToExcelConverter,
    ExcelToPDFConverter,
    PDFToPowerPointConverter,
    PowerPointToPDFConverter,
    HTMLToPDFConverter,
)
from .ocr import (
    OCRError,
    PDFOCRProcessor,
    check_ocr_status,
    get_available_languages,
)
from .extraction import (
    ExtractionError,
    TextExtractor,
    ImageExtractor,
    TableExtractor,
    MetadataExtractor,
    PDFComparer,
    PDFRedactor,
    PDFFlattener,
)
from .ai_features import (
    AIError,
    AISummarizer,
    AIChatPDF,
    AITranslator,
    check_ai_status,
)


app = FastAPI(
    title="DocFlow API",
    description="Comprehensive document processing API for PDF, Word, Excel, PowerPoint, and images.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Health & Status
# =============================================================================

@app.get("/api/health")
async def health_check():
    """Check API health status."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/status/ocr")
async def ocr_status():
    """Check OCR system status."""
    return check_ocr_status()


# =============================================================================
# PPTX Operations
# =============================================================================

@app.post("/api/pptx/merge")
async def merge_pptx(files: List[UploadFile] = File(...)):
    """Merge multiple PPTX files into one."""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Add at least two PPTX files.")

    payloads: list[bytes] = []
    for upload in files:
        filename = (upload.filename or "").lower()
        if not filename.endswith(".pptx"):
            raise HTTPException(status_code=400, detail=f"Unsupported file: {upload.filename}")
        payloads.append(await upload.read())

    try:
        merged = merge_presentations(payloads)
    except MergeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Merge failed.") from exc

    headers = {"Content-Disposition": "attachment; filename=merged.pptx"}
    return StreamingResponse(
        io.BytesIO(merged),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers=headers,
    )


# =============================================================================
# PDF Core Operations
# =============================================================================

@app.post("/api/pdf/merge")
async def merge_pdf(files: List[UploadFile] = File(...)):
    """Merge multiple PDF files into one."""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Add at least two PDF files.")
    
    payloads: list[bytes] = []
    for upload in files:
        filename = (upload.filename or "").lower()
        if not filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"Unsupported file: {upload.filename}")
        payloads.append(await upload.read())
    
    try:
        merged = PDFMerger.merge(payloads)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Merge failed.")
    
    headers = {"Content-Disposition": "attachment; filename=merged.pdf"}
    return StreamingResponse(
        io.BytesIO(merged),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/split")
async def split_pdf(
    file: UploadFile = File(...),
    pages: str = Form(...),  # Comma-separated page numbers (1-indexed)
):
    """Split/extract specific pages from a PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Parse page numbers (convert to 0-indexed)
        page_list = [int(p.strip()) - 1 for p in pages.split(",") if p.strip().isdigit()]
        if not page_list:
            raise HTTPException(status_code=400, detail="Invalid page numbers")
        
        buffer = await file.read()
        result = PDFSplitter.split_pages(buffer, page_list)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Split failed.")
    
    headers = {"Content-Disposition": "attachment; filename=split.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/split-range")
async def split_pdf_range(
    file: UploadFile = File(...),
    start: int = Form(...),  # 1-indexed
    end: int = Form(...),    # 1-indexed, inclusive
):
    """Extract a range of pages from a PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFSplitter.split_range(buffer, start - 1, end)  # Convert to 0-indexed
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Split failed.")
    
    headers = {"Content-Disposition": "attachment; filename=split.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/compress")
async def compress_pdf(
    file: UploadFile = File(...),
    quality: Literal["low", "medium", "high"] = Form("medium"),
):
    """Compress a PDF file."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFCompressor.compress(buffer, quality)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Compression failed.")
    
    headers = {"Content-Disposition": "attachment; filename=compressed.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/rotate")
async def rotate_pdf(
    file: UploadFile = File(...),
    angle: int = Form(...),  # 90, 180, 270, or -90
    pages: Optional[str] = Form(None),  # Comma-separated, 1-indexed. None = all
):
    """Rotate PDF pages."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        page_list = None
        if pages:
            page_list = [int(p.strip()) - 1 for p in pages.split(",") if p.strip().isdigit()]
        
        buffer = await file.read()
        result = PDFRotator.rotate(buffer, angle, page_list)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Rotation failed.")
    
    headers = {"Content-Disposition": "attachment; filename=rotated.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/organize")
async def organize_pdf(
    file: UploadFile = File(...),
    order: str = Form(...),  # Comma-separated page order (1-indexed)
):
    """Reorder PDF pages."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        new_order = [int(p.strip()) - 1 for p in order.split(",") if p.strip().isdigit()]
        if not new_order:
            raise HTTPException(status_code=400, detail="Invalid page order")
        
        buffer = await file.read()
        result = PDFOrganizer.reorder(buffer, new_order)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Organize failed.")
    
    headers = {"Content-Disposition": "attachment; filename=organized.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/delete-pages")
async def delete_pdf_pages(
    file: UploadFile = File(...),
    pages: str = Form(...),  # Comma-separated pages to delete (1-indexed)
):
    """Delete specific pages from a PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        page_list = [int(p.strip()) - 1 for p in pages.split(",") if p.strip().isdigit()]
        if not page_list:
            raise HTTPException(status_code=400, detail="Invalid page numbers")
        
        buffer = await file.read()
        result = PDFOrganizer.delete_pages(buffer, page_list)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Delete failed.")
    
    headers = {"Content-Disposition": "attachment; filename=edited.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/page-numbers")
async def add_page_numbers(
    file: UploadFile = File(...),
    position: Literal["bottom-center", "bottom-right", "bottom-left", 
                     "top-center", "top-right", "top-left"] = Form("bottom-center"),
    start_number: int = Form(1),
    font_size: int = Form(12),
):
    """Add page numbers to a PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFPageNumbers.add_page_numbers(buffer, position, start_number, font_size)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to add page numbers.")
    
    headers = {"Content-Disposition": "attachment; filename=numbered.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/watermark")
async def add_watermark(
    file: UploadFile = File(...),
    text: str = Form(...),
    opacity: float = Form(0.3),
    angle: int = Form(45),
    font_size: int = Form(60),
):
    """Add text watermark to a PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFWatermark.add_text_watermark(buffer, text, opacity, angle, font_size)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Watermark failed.")
    
    headers = {"Content-Disposition": "attachment; filename=watermarked.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/protect")
async def protect_pdf(
    file: UploadFile = File(...),
    password: str = Form(...),
    owner_password: Optional[str] = Form(None),
    allow_printing: bool = Form(True),
    allow_copying: bool = Form(False),
):
    """Encrypt and password-protect a PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFProtection.encrypt(buffer, password, owner_password, allow_printing, allow_copying)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Protection failed.")
    
    headers = {"Content-Disposition": "attachment; filename=protected.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/unlock")
async def unlock_pdf(
    file: UploadFile = File(...),
    password: str = Form(...),
):
    """Remove password protection from a PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFProtection.decrypt(buffer, password)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unlock failed.")
    
    headers = {"Content-Disposition": "attachment; filename=unlocked.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/repair")
async def repair_pdf(file: UploadFile = File(...)):
    """Attempt to repair a damaged PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFRepair.repair(buffer)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Repair failed.")
    
    headers = {"Content-Disposition": "attachment; filename=repaired.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/crop")
async def crop_pdf(
    file: UploadFile = File(...),
    left: float = Form(0),
    bottom: float = Form(0),
    right: float = Form(0),
    top: float = Form(0),
    pages: Optional[str] = Form(None),  # Comma-separated, 1-indexed
):
    """Crop PDF pages by specified margins (in points, 72 points = 1 inch)."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        page_list = None
        if pages:
            page_list = [int(p.strip()) - 1 for p in pages.split(",") if p.strip().isdigit()]
        
        buffer = await file.read()
        result = PDFCropper.crop(buffer, left, bottom, right, top, page_list)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Crop failed.")
    
    headers = {"Content-Disposition": "attachment; filename=cropped.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


# =============================================================================
# PDF Editing & Signing
# =============================================================================

@app.post("/api/pdf/edit/add-text")
async def edit_pdf_add_text(
    file: UploadFile = File(...),
    text: str = Form(...),
    page: int = Form(1),
    x: float = Form(100),
    y: float = Form(100),
    font_size: int = Form(12),
    color: str = Form("black"),
):
    """Add text to a PDF page."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFEditor.add_text(buffer, text, page - 1, x, y, font_size, color)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to add text.")
    
    headers = {"Content-Disposition": "attachment; filename=edited.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/edit/add-image")
async def edit_pdf_add_image(
    file: UploadFile = File(...),
    image: UploadFile = File(...),
    page: int = Form(1),
    x: float = Form(100),
    y: float = Form(100),
    width: float = Form(200),
    height: float = Form(200),
):
    """Add image to a PDF page."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    allowed_image_exts = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
    if not any(image.filename.lower().endswith(ext) for ext in allowed_image_exts):
        raise HTTPException(status_code=400, detail="Image must be JPG, PNG, GIF, BMP, or WebP")
    
    try:
        buffer = await file.read()
        image_buffer = await image.read()
        result = PDFEditor.add_image(buffer, image_buffer, page - 1, x, y, width, height)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to add image.")
    
    headers = {"Content-Disposition": "attachment; filename=edited.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/edit/add-shape")
async def edit_pdf_add_shape(
    file: UploadFile = File(...),
    page: int = Form(1),
    x: float = Form(100),
    y: float = Form(100),
    width: float = Form(200),
    height: float = Form(100),
    color: str = Form("blue"),
    fill: bool = Form(False),
    opacity: float = Form(1.0),
):
    """Add rectangle shape to a PDF page."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFEditor.add_rectangle(buffer, page - 1, x, y, width, height, color, fill, opacity)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to add shape.")
    
    headers = {"Content-Disposition": "attachment; filename=edited.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/sign/image")
async def sign_pdf_image(
    file: UploadFile = File(...),
    signature: UploadFile = File(...),
    page: int = Form(-1),  # -1 = last page
    x: float = Form(100),
    y: float = Form(100),
    width: float = Form(200),
    height: float = Form(80),
):
    """Add signature image to a PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    allowed_image_exts = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
    if not any(signature.filename.lower().endswith(ext) for ext in allowed_image_exts):
        raise HTTPException(status_code=400, detail="Signature must be an image file")
    
    try:
        buffer = await file.read()
        signature_buffer = await signature.read()
        result = PDFSigner.add_signature_image(buffer, signature_buffer, page - 1 if page > 0 else page, x, y, width, height)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to add signature.")
    
    headers = {"Content-Disposition": "attachment; filename=signed.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/sign/text")
async def sign_pdf_text(
    file: UploadFile = File(...),
    name: str = Form(...),
    page: int = Form(-1),  # -1 = last page
    x: float = Form(100),
    y: float = Form(100),
    font_size: int = Form(24),
    include_date: bool = Form(True),
):
    """Add text signature to a PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFSigner.add_text_signature(buffer, name, page - 1 if page > 0 else page, x, y, font_size, include_date)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to add signature.")
    
    headers = {"Content-Disposition": "attachment; filename=signed.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/info")
async def pdf_info(file: UploadFile = File(...)):
    """Get information about a PDF file."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        info = get_pdf_info(buffer)
        return JSONResponse(content=info)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# =============================================================================
# Conversions
# =============================================================================

@app.post("/api/convert/pdf-to-jpg")
async def pdf_to_jpg(
    file: UploadFile = File(...),
    dpi: int = Form(150),
):
    """Convert PDF to JPG images (returned as ZIP)."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFToImageConverter.convert_to_zip(buffer, "jpg", dpi)
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Conversion failed.")
    
    headers = {"Content-Disposition": "attachment; filename=images.zip"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/zip",
        headers=headers,
    )


@app.post("/api/convert/pdf-to-png")
async def pdf_to_png(
    file: UploadFile = File(...),
    dpi: int = Form(150),
):
    """Convert PDF to PNG images (returned as ZIP)."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFToImageConverter.convert_to_zip(buffer, "png", dpi)
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Conversion failed.")
    
    headers = {"Content-Disposition": "attachment; filename=images.zip"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/zip",
        headers=headers,
    )


@app.post("/api/convert/jpg-to-pdf")
async def jpg_to_pdf(
    files: List[UploadFile] = File(...),
    page_size: Literal["a4", "letter", "fit"] = Form("a4"),
):
    """Convert JPG/PNG images to PDF."""
    allowed_extensions = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
    
    image_buffers = []
    for upload in files:
        filename = (upload.filename or "").lower()
        if not any(filename.endswith(ext) for ext in allowed_extensions):
            raise HTTPException(status_code=400, detail=f"Unsupported file: {upload.filename}")
        image_buffers.append(await upload.read())
    
    try:
        result = ImageToPDFConverter.convert(image_buffers, page_size)
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Conversion failed.")
    
    headers = {"Content-Disposition": "attachment; filename=images.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/convert/pdf-to-word")
async def pdf_to_word(file: UploadFile = File(...)):
    """Convert PDF to Word document."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFToWordConverter.convert(buffer)
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Conversion failed.")
    
    headers = {"Content-Disposition": "attachment; filename=document.docx"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


@app.post("/api/convert/word-to-pdf")
async def word_to_pdf(file: UploadFile = File(...)):
    """Convert Word document to PDF."""
    filename = (file.filename or "").lower()
    if not filename.endswith((".doc", ".docx")):
        raise HTTPException(status_code=400, detail="File must be a Word document")
    
    try:
        buffer = await file.read()
        result = WordToPDFConverter.convert(buffer)
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Conversion failed.")
    
    headers = {"Content-Disposition": "attachment; filename=document.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/convert/pdf-to-excel")
async def pdf_to_excel(file: UploadFile = File(...)):
    """Convert PDF tables to Excel."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFToExcelConverter.convert(buffer)
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Conversion failed.")
    
    headers = {"Content-Disposition": "attachment; filename=spreadsheet.xlsx"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@app.post("/api/convert/excel-to-pdf")
async def excel_to_pdf(file: UploadFile = File(...)):
    """Convert Excel to PDF."""
    filename = (file.filename or "").lower()
    if not filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="File must be an Excel file")
    
    try:
        buffer = await file.read()
        result = ExcelToPDFConverter.convert(buffer)
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Conversion failed.")
    
    headers = {"Content-Disposition": "attachment; filename=spreadsheet.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/convert/pdf-to-ppt")
async def pdf_to_ppt(
    file: UploadFile = File(...),
    dpi: int = Form(150),
):
    """Convert PDF to PowerPoint."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFToPowerPointConverter.convert(buffer, dpi)
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Conversion failed.")
    
    headers = {"Content-Disposition": "attachment; filename=presentation.pptx"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers=headers,
    )


@app.post("/api/convert/ppt-to-pdf")
async def ppt_to_pdf(file: UploadFile = File(...)):
    """Convert PowerPoint to PDF."""
    filename = (file.filename or "").lower()
    if not filename.endswith((".ppt", ".pptx")):
        raise HTTPException(status_code=400, detail="File must be a PowerPoint file")
    
    try:
        buffer = await file.read()
        result = PowerPointToPDFConverter.convert(buffer)
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Conversion failed.")
    
    headers = {"Content-Disposition": "attachment; filename=presentation.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/convert/html-to-pdf")
async def html_to_pdf(url: str = Form(...)):
    """Convert webpage URL to PDF."""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    
    try:
        result = await HTMLToPDFConverter.convert_url(url)
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Conversion failed.")
    
    headers = {"Content-Disposition": "attachment; filename=webpage.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


# =============================================================================
# OCR
# =============================================================================

@app.post("/api/ocr/extract-text")
async def ocr_extract_text(
    file: UploadFile = File(...),
    language: str = Form("eng"),
):
    """Extract text from scanned PDF using OCR."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        text = PDFOCRProcessor.extract_text(buffer, language)
        return {"text": text}
    except OCRError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="OCR failed.")


@app.post("/api/ocr/make-searchable")
async def ocr_make_searchable(
    file: UploadFile = File(...),
    language: str = Form("eng"),
):
    """Create searchable PDF from scanned PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFOCRProcessor.create_searchable_pdf(buffer, language)
    except OCRError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="OCR failed.")
    
    headers = {"Content-Disposition": "attachment; filename=searchable.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.get("/api/ocr/languages")
async def ocr_languages():
    """Get available OCR languages."""
    return {"languages": get_available_languages()}


# =============================================================================
# Extraction Tools
# =============================================================================

@app.post("/api/extract/text")
async def extract_text(
    file: UploadFile = File(...),
    format: str = Form("txt"),
    preserve_layout: bool = Form(False),
):
    """Extract text from PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = TextExtractor.extract(buffer, format, preserve_layout)
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Extraction failed.")
    
    ext = format if format in ("txt", "md", "html") else "txt"
    mime = {"txt": "text/plain", "md": "text/markdown", "html": "text/html"}.get(ext, "text/plain")
    
    headers = {"Content-Disposition": f"attachment; filename=extracted.{ext}"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type=mime,
        headers=headers,
    )


@app.post("/api/extract/images")
async def extract_images(
    file: UploadFile = File(...),
    format: str = Form("png"),
    min_size: int = Form(50),
):
    """Extract images from PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = ImageExtractor.extract(buffer, format, min_size)
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Extraction failed.")
    
    headers = {"Content-Disposition": "attachment; filename=images.zip"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/zip",
        headers=headers,
    )


@app.post("/api/extract/tables")
async def extract_tables(
    file: UploadFile = File(...),
    format: str = Form("csv"),
    pages: str = Form(""),
):
    """Extract tables from PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = TableExtractor.extract(buffer, format, pages)
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Extraction failed.")
    
    headers = {"Content-Disposition": "attachment; filename=tables.zip"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/zip",
        headers=headers,
    )


@app.post("/api/extract/metadata")
async def extract_metadata(file: UploadFile = File(...)):
    """Extract metadata from PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = MetadataExtractor.extract(buffer)
        return JSONResponse(content=result)
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Extraction failed.")


# =============================================================================
# Advanced PDF Tools
# =============================================================================

@app.post("/api/pdf/compare")
async def compare_pdfs(
    files: List[UploadFile] = File(...),
    mode: str = Form("visual"),
):
    """Compare two PDF files."""
    if len(files) != 2:
        raise HTTPException(status_code=400, detail="Exactly two PDF files required")
    
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"File must be a PDF: {f.filename}")
    
    try:
        pdf1 = await files[0].read()
        pdf2 = await files[1].read()
        result = PDFComparer.compare(pdf1, pdf2, mode)
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Comparison failed.")
    
    headers = {"Content-Disposition": "attachment; filename=comparison.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/redact")
async def redact_pdf(
    file: UploadFile = File(...),
    patterns: str = Form(""),
    redact_emails: bool = Form(True),
    redact_phones: bool = Form(True),
    redact_ssn: bool = Form(True),
):
    """Redact sensitive information from PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFRedactor.redact(buffer, patterns, redact_emails, redact_phones, redact_ssn)
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Redaction failed.")
    
    headers = {"Content-Disposition": "attachment; filename=redacted.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/flatten")
async def flatten_pdf(
    file: UploadFile = File(...),
    flatten_forms: bool = Form(True),
    flatten_annotations: bool = Form(True),
):
    """Flatten PDF forms and annotations."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = PDFFlattener.flatten(buffer, flatten_forms, flatten_annotations)
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Flatten failed.")
    
    headers = {"Content-Disposition": "attachment; filename=flattened.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


@app.post("/api/pdf/remove-pages")
async def remove_pages(
    file: UploadFile = File(...),
    pages: str = Form(...),
):
    """Remove specific pages from PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        
        # Parse pages to remove
        doc = fitz.open(stream=buffer, filetype="pdf")
        total_pages = len(doc)
        
        pages_to_remove = set()
        for part in pages.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                try:
                    start = int(start.strip())
                    end = int(end.strip())
                    pages_to_remove.update(range(start, end + 1))
                except ValueError:
                    continue
            else:
                try:
                    pages_to_remove.add(int(part))
                except ValueError:
                    continue
        
        # Keep pages not in removal list (convert to 0-indexed)
        pages_to_keep = [i for i in range(total_pages) if (i + 1) not in pages_to_remove]
        
        if not pages_to_keep:
            raise HTTPException(status_code=400, detail="Cannot remove all pages")
        
        doc.select(pages_to_keep)
        result = doc.tobytes()
        doc.close()
        
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Page removal failed.")
    
    headers = {"Content-Disposition": "attachment; filename=trimmed.pdf"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="application/pdf",
        headers=headers,
    )


# =============================================================================
# AI Features
# =============================================================================

@app.get("/api/ai/status")
async def ai_status():
    """Check AI system status."""
    return check_ai_status()


@app.post("/api/ai/summarize")
async def ai_summarize(
    file: UploadFile = File(...),
    length: str = Form("medium"),
    style: str = Form("bullets"),
):
    """AI-powered document summarization."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        summary = AISummarizer.summarize(buffer, length, style)
        
        # Return as downloadable text file
        result = summary.encode("utf-8")
    except AIError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Summarization failed.")
    
    headers = {"Content-Disposition": "attachment; filename=summary.txt"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="text/plain",
        headers=headers,
    )


@app.post("/api/ai/chat")
async def ai_chat(
    file: UploadFile = File(...),
    question: str = Form(...),
):
    """AI-powered document Q&A."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        answer = AIChatPDF.ask(buffer, question)
        
        result = answer.encode("utf-8")
    except AIError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Q&A failed.")
    
    headers = {"Content-Disposition": "attachment; filename=answer.txt"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="text/plain",
        headers=headers,
    )


@app.post("/api/ai/translate")
async def ai_translate(
    file: UploadFile = File(...),
    target_language: str = Form("es"),
):
    """AI-powered document translation."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        buffer = await file.read()
        result = AITranslator.translate(buffer, target_language)
    except AIError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Translation failed.")
    
    headers = {"Content-Disposition": "attachment; filename=translated.txt"}
    return StreamingResponse(
        io.BytesIO(result),
        media_type="text/plain",
        headers=headers,
    )
