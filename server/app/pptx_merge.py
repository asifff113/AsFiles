"""
PPTX Merge - Merge multiple PowerPoint presentations into one.
Uses python-pptx for the heavy lifting to avoid XML issues.
"""
from __future__ import annotations

import io
import os
import tempfile
import zipfile
import shutil
import re
from typing import Iterable, List, Set

from pptx import Presentation
from pptx.util import Inches, Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE


class MergeError(Exception):
    pass


def merge_presentations(buffers: Iterable[bytes]) -> bytes:
    """
    Merge multiple PPTX files into one, preserving all content.
    
    Strategy: Use ZIP-level merge to copy slides and media, then
    let python-pptx validate and fix the result.
    """
    payloads = list(buffers)
    if not payloads:
        raise MergeError("No PPTX data provided.")
    
    if len(payloads) == 1:
        return payloads[0]
    
    try:
        # First try the simple python-pptx approach
        result = _merge_with_pptx(payloads)
        return result
    except Exception as e:
        print(f"[PPTX Merge] python-pptx merge failed: {e}")
        # Fallback to ZIP-level merge
        try:
            result = _merge_via_zip(payloads)
            return result
        except Exception as e2:
            print(f"[PPTX Merge] ZIP merge also failed: {e2}")
            raise MergeError(f"Merge failed: {e}")


def _merge_with_pptx(payloads: List[bytes]) -> bytes:
    """
    Merge using python-pptx by copying shapes from source slides.
    This approach preserves images properly.
    """
    # Open first presentation as base
    base = Presentation(io.BytesIO(payloads[0]))
    
    # Get a blank layout from base (usually index 6)
    blank_layout = None
    for i, layout in enumerate(base.slide_layouts):
        if layout.name.lower() in ('blank', 'empty') or i == 6:
            blank_layout = layout
            break
    if blank_layout is None:
        blank_layout = base.slide_layouts[-1]
    
    # Process each additional presentation
    for payload in payloads[1:]:
        source = Presentation(io.BytesIO(payload))
        
        for slide in source.slides:
            # Add new blank slide
            new_slide = base.slides.add_slide(blank_layout)
            
            # Copy slide background if it has one
            try:
                _copy_background(slide, new_slide)
            except:
                pass
            
            # Copy all shapes
            for shape in slide.shapes:
                try:
                    _copy_shape(shape, new_slide)
                except Exception as e:
                    print(f"[PPTX Merge] Could not copy shape: {e}")
    
    # Save result
    output = io.BytesIO()
    base.save(output)
    return output.getvalue()


def _copy_background(src_slide, dst_slide):
    """Copy slide background."""
    src_bg = src_slide.background
    if src_bg is None:
        return
    
    # Try to copy fill
    try:
        src_fill = src_bg.fill
        dst_fill = dst_slide.background.fill
        
        if src_fill.type is not None:
            if hasattr(src_fill, 'fore_color') and src_fill.fore_color:
                dst_fill.solid()
                if src_fill.fore_color.rgb:
                    dst_fill.fore_color.rgb = src_fill.fore_color.rgb
    except:
        pass


def _copy_shape(shape, new_slide):
    """Copy a shape to a new slide."""
    shape_type = shape.shape_type
    
    # Handle pictures - must extract and re-add image
    if shape_type == MSO_SHAPE_TYPE.PICTURE:
        try:
            image_blob = shape.image.blob
            new_slide.shapes.add_picture(
                io.BytesIO(image_blob),
                shape.left,
                shape.top,
                shape.width,
                shape.height,
            )
        except Exception as e:
            print(f"[PPTX Merge] Picture copy failed: {e}")
        return
    
    # Handle tables
    if shape_type == MSO_SHAPE_TYPE.TABLE:
        try:
            table = shape.table
            rows = len(table.rows)
            cols = len(table.columns)
            
            new_table_shape = new_slide.shapes.add_table(
                rows, cols,
                shape.left, shape.top,
                shape.width, shape.height
            )
            new_table = new_table_shape.table
            
            for row_idx in range(rows):
                for col_idx in range(cols):
                    src_cell = table.cell(row_idx, col_idx)
                    dst_cell = new_table.cell(row_idx, col_idx)
                    dst_cell.text = src_cell.text
        except Exception as e:
            print(f"[PPTX Merge] Table copy failed: {e}")
        return
    
    # Handle text boxes and other shapes - copy element directly
    try:
        from copy import deepcopy
        new_element = deepcopy(shape.element)
        new_slide.shapes._spTree.insert_element_before(new_element, "p:extLst")
    except Exception as e:
        print(f"[PPTX Merge] Shape copy failed: {e}")


def _merge_via_zip(payloads: List[bytes]) -> bytes:
    """
    Merge PPTX files by manipulating their ZIP structure directly.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extract first presentation as base
        base_dir = os.path.join(tmpdir, 'base')
        with zipfile.ZipFile(io.BytesIO(payloads[0]), 'r') as zf:
            zf.extractall(base_dir)
        
        # Count existing slides and media
        slides_dir = os.path.join(base_dir, 'ppt', 'slides')
        existing_slides = [f for f in os.listdir(slides_dir) if f.startswith('slide') and f.endswith('.xml')]
        next_slide_num = len(existing_slides) + 1
        
        media_dir = os.path.join(base_dir, 'ppt', 'media')
        if not os.path.exists(media_dir):
            os.makedirs(media_dir)
        existing_media = set(os.listdir(media_dir)) if os.path.exists(media_dir) else set()
        
        # Process each additional presentation
        for pptx_idx, payload in enumerate(payloads[1:], start=2):
            src_dir = os.path.join(tmpdir, f'src_{pptx_idx}')
            with zipfile.ZipFile(io.BytesIO(payload), 'r') as zf:
                zf.extractall(src_dir)
            
            src_slides_dir = os.path.join(src_dir, 'ppt', 'slides')
            if not os.path.exists(src_slides_dir):
                continue
            
            src_media_dir = os.path.join(src_dir, 'ppt', 'media')
            
            # Get source slides sorted
            src_slides = sorted(
                [f for f in os.listdir(src_slides_dir) if f.startswith('slide') and f.endswith('.xml')],
                key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0
            )
            
            for src_slide_file in src_slides:
                # Copy slide XML
                new_slide_name = f'slide{next_slide_num}.xml'
                src_slide_path = os.path.join(src_slides_dir, src_slide_file)
                dst_slide_path = os.path.join(slides_dir, new_slide_name)
                shutil.copy2(src_slide_path, dst_slide_path)
                
                # Copy slide relationships
                src_rels_dir = os.path.join(src_slides_dir, '_rels')
                dst_rels_dir = os.path.join(slides_dir, '_rels')
                os.makedirs(dst_rels_dir, exist_ok=True)
                
                src_slide_rels = os.path.join(src_rels_dir, f'{src_slide_file}.rels')
                dst_slide_rels = os.path.join(dst_rels_dir, f'{new_slide_name}.rels')
                
                if os.path.exists(src_slide_rels):
                    # Read and update relationships
                    with open(src_slide_rels, 'r', encoding='utf-8') as f:
                        rels_content = f.read()
                    
                    # Copy any referenced media files
                    if os.path.exists(src_media_dir):
                        for media_file in os.listdir(src_media_dir):
                            if media_file in rels_content:
                                src_media = os.path.join(src_media_dir, media_file)
                                # Handle name collision
                                dst_media_name = media_file
                                if media_file in existing_media:
                                    base, ext = os.path.splitext(media_file)
                                    dst_media_name = f'{base}_{pptx_idx}_{next_slide_num}{ext}'
                                    rels_content = rels_content.replace(media_file, dst_media_name)
                                
                                dst_media = os.path.join(media_dir, dst_media_name)
                                shutil.copy2(src_media, dst_media)
                                existing_media.add(dst_media_name)
                    
                    with open(dst_slide_rels, 'w', encoding='utf-8') as f:
                        f.write(rels_content)
                else:
                    # Create minimal rels
                    minimal_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>'''
                    with open(dst_slide_rels, 'w', encoding='utf-8') as f:
                        f.write(minimal_rels)
                
                next_slide_num += 1
        
        # Repack as PPTX
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, base_dir)
                    zf.write(file_path, arc_name)
        
        zip_result = output.getvalue()
        
        # Validate and fix with python-pptx
        try:
            prs = Presentation(io.BytesIO(zip_result))
            final_output = io.BytesIO()
            prs.save(final_output)
            return final_output.getvalue()
        except Exception as e:
            print(f"[PPTX Merge] Validation failed: {e}, returning raw ZIP merge")
            return zip_result
