from __future__ import annotations

import io
import os
import tempfile
import zipfile
import shutil
import re
from copy import deepcopy
from typing import Iterable, List, Dict, Set
from lxml import etree as ET

from pptx import Presentation
from pptx.util import Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE


class MergeError(Exception):
    pass


# XML namespaces used in PPTX
NAMESPACES = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'ct': 'http://schemas.openxmlformats.org/package/2006/content-types',
    'pr': 'http://schemas.openxmlformats.org/package/2006/relationships',
}


def merge_presentations(buffers: Iterable[bytes]) -> bytes:
    """
    Merge multiple PPTX files into one, preserving all content.
    
    Uses a clean ZIP-level merge with proper relationship handling.
    """
    payloads = list(buffers)
    if not payloads:
        raise MergeError("No PPTX data provided.")
    
    if len(payloads) == 1:
        return payloads[0]
    
    try:
        result = _merge_pptx_clean(payloads)
        # Validate and repair the result
        result = _validate_and_repair_pptx(result)
        return result
    except Exception as e:
        print(f"[PPTX Merge] Clean merge failed: {e}")
        raise MergeError(f"Merge failed: {e}")


def _merge_pptx_clean(payloads: List[bytes]) -> bytes:
    """
    Clean PPTX merge that properly handles all relationships.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extract base presentation
        base_dir = os.path.join(tmpdir, 'base')
        with zipfile.ZipFile(io.BytesIO(payloads[0]), 'r') as zf:
            zf.extractall(base_dir)
        
        # Track what we have in base
        base_media = _get_media_files(base_dir)
        base_slide_count = _count_slides(base_dir)
        
        # Get max IDs from base
        max_slide_id, max_rid = _get_max_ids(base_dir)
        
        print(f"[PPTX Merge] Base has {base_slide_count} slides, max_slide_id={max_slide_id}, max_rid={max_rid}")
        
        next_slide_num = base_slide_count + 1
        
        # Process each additional presentation
        for pptx_idx, payload in enumerate(payloads[1:], start=2):
            src_dir = os.path.join(tmpdir, f'src_{pptx_idx}')
            with zipfile.ZipFile(io.BytesIO(payload), 'r') as zf:
                zf.extractall(src_dir)
            
            src_slides = _get_slide_files(src_dir)
            print(f"[PPTX Merge] Adding {len(src_slides)} slides from presentation {pptx_idx}")
            
            for src_slide_name in src_slides:
                # Map old media references to new ones
                media_map = {}
                
                # Copy slide's media files first
                src_slide_rels = _get_slide_relationships(src_dir, src_slide_name)
                for rel_id, rel_info in src_slide_rels.items():
                    if rel_info['type'] == 'image' or rel_info['type'] == 'media':
                        src_media_path = os.path.join(src_dir, 'ppt', 'slides', rel_info['target'].lstrip('../'))
                        if not os.path.exists(src_media_path):
                            src_media_path = os.path.join(src_dir, 'ppt', rel_info['target'].lstrip('../'))
                        
                        if os.path.exists(src_media_path):
                            media_filename = os.path.basename(src_media_path)
                            new_media_name = _copy_media_file(src_media_path, base_dir, base_media, pptx_idx, next_slide_num)
                            media_map[rel_info['target']] = f'../media/{new_media_name}'
                            base_media.add(new_media_name)
                
                # Copy and update slide XML
                new_slide_name = f'slide{next_slide_num}.xml'
                _copy_slide(src_dir, base_dir, src_slide_name, new_slide_name, media_map)
                
                # Copy and update slide relationships
                _copy_slide_rels(src_dir, base_dir, src_slide_name, new_slide_name, media_map)
                
                # Add slide to presentation.xml and relationships
                max_slide_id += 1
                max_rid += 1
                _add_slide_to_presentation(base_dir, new_slide_name, max_slide_id, max_rid)
                
                # Update Content_Types.xml
                _add_slide_content_type(base_dir, new_slide_name)
                
                next_slide_num += 1
        
        # Repack as PPTX
        return _repack_pptx(base_dir)


def _get_media_files(base_dir: str) -> Set[str]:
    """Get set of media filenames in the presentation."""
    media_dir = os.path.join(base_dir, 'ppt', 'media')
    if not os.path.exists(media_dir):
        return set()
    return set(os.listdir(media_dir))


def _count_slides(base_dir: str) -> int:
    """Count slides in the presentation."""
    slides_dir = os.path.join(base_dir, 'ppt', 'slides')
    if not os.path.exists(slides_dir):
        return 0
    return len([f for f in os.listdir(slides_dir) if f.startswith('slide') and f.endswith('.xml')])


def _get_slide_files(src_dir: str) -> List[str]:
    """Get sorted list of slide filenames."""
    slides_dir = os.path.join(src_dir, 'ppt', 'slides')
    if not os.path.exists(slides_dir):
        return []
    slides = [f for f in os.listdir(slides_dir) if f.startswith('slide') and f.endswith('.xml')]
    # Sort by slide number
    slides.sort(key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0)
    return slides


def _get_max_ids(base_dir: str) -> tuple:
    """Get maximum slide ID and relationship ID from base presentation."""
    max_slide_id = 255
    max_rid = 0
    
    # Parse presentation.xml for slide IDs
    pres_path = os.path.join(base_dir, 'ppt', 'presentation.xml')
    if os.path.exists(pres_path):
        try:
            tree = ET.parse(pres_path)
            for sld_id in tree.findall('.//p:sldId', NAMESPACES):
                sid = sld_id.get('id')
                if sid:
                    max_slide_id = max(max_slide_id, int(sid))
        except:
            pass
    
    # Parse relationships for rIds
    rels_path = os.path.join(base_dir, 'ppt', '_rels', 'presentation.xml.rels')
    if os.path.exists(rels_path):
        try:
            tree = ET.parse(rels_path)
            for rel in tree.findall('.//pr:Relationship', NAMESPACES):
                rid = rel.get('Id', '')
                if rid.startswith('rId'):
                    try:
                        max_rid = max(max_rid, int(rid[3:]))
                    except:
                        pass
        except:
            pass
    
    return max_slide_id, max_rid


def _get_slide_relationships(src_dir: str, slide_name: str) -> Dict:
    """Get relationships for a slide."""
    rels = {}
    rels_path = os.path.join(src_dir, 'ppt', 'slides', '_rels', f'{slide_name}.rels')
    
    if not os.path.exists(rels_path):
        return rels
    
    try:
        tree = ET.parse(rels_path)
        for rel in tree.findall('.//pr:Relationship', NAMESPACES):
            rel_id = rel.get('Id')
            rel_type = rel.get('Type', '')
            target = rel.get('Target', '')
            
            # Categorize relationship type
            if 'image' in rel_type or '/media/' in target:
                type_cat = 'image'
            elif 'slideLayout' in rel_type:
                type_cat = 'layout'
            elif 'media' in rel_type:
                type_cat = 'media'
            else:
                type_cat = 'other'
            
            rels[rel_id] = {
                'type': type_cat,
                'full_type': rel_type,
                'target': target
            }
    except:
        pass
    
    return rels


def _copy_media_file(src_path: str, base_dir: str, existing_media: Set[str], pptx_idx: int, slide_num: int) -> str:
    """Copy media file to base, handling name collisions."""
    media_dir = os.path.join(base_dir, 'ppt', 'media')
    os.makedirs(media_dir, exist_ok=True)
    
    filename = os.path.basename(src_path)
    base_name, ext = os.path.splitext(filename)
    
    # If file exists, create unique name
    new_name = filename
    if filename in existing_media:
        new_name = f'{base_name}_p{pptx_idx}_s{slide_num}{ext}'
    
    dst_path = os.path.join(media_dir, new_name)
    shutil.copy2(src_path, dst_path)
    
    # Update Content_Types if needed
    _ensure_media_content_type(base_dir, ext.lower().lstrip('.'))
    
    return new_name


def _copy_slide(src_dir: str, base_dir: str, src_slide_name: str, new_slide_name: str, media_map: Dict) -> None:
    """Copy slide XML, updating media references."""
    src_path = os.path.join(src_dir, 'ppt', 'slides', src_slide_name)
    dst_path = os.path.join(base_dir, 'ppt', 'slides', new_slide_name)
    
    # Just copy the file - relationships handle the media refs
    shutil.copy2(src_path, dst_path)


def _copy_slide_rels(src_dir: str, base_dir: str, src_slide_name: str, new_slide_name: str, media_map: Dict) -> None:
    """Copy slide relationships, updating media references."""
    src_rels_path = os.path.join(src_dir, 'ppt', 'slides', '_rels', f'{src_slide_name}.rels')
    dst_rels_dir = os.path.join(base_dir, 'ppt', 'slides', '_rels')
    os.makedirs(dst_rels_dir, exist_ok=True)
    dst_rels_path = os.path.join(dst_rels_dir, f'{new_slide_name}.rels')
    
    if not os.path.exists(src_rels_path):
        # Create minimal rels file pointing to first layout
        _create_minimal_slide_rels(base_dir, dst_rels_path)
        return
    
    try:
        tree = ET.parse(src_rels_path)
        root = tree.getroot()
        
        for rel in root.findall('.//pr:Relationship', NAMESPACES):
            target = rel.get('Target', '')
            rel_type = rel.get('Type', '')
            
            # Update media references
            if target in media_map:
                rel.set('Target', media_map[target])
            
            # Update slideLayout references to use base layout
            if 'slideLayout' in rel_type:
                # Point to layout1 in base (usually blank or basic)
                rel.set('Target', '../slideLayouts/slideLayout1.xml')
        
        tree.write(dst_rels_path, xml_declaration=True, encoding='UTF-8', standalone=True)
    except Exception as e:
        print(f"[PPTX Merge] Error copying rels: {e}")
        shutil.copy2(src_rels_path, dst_rels_path)


def _create_minimal_slide_rels(base_dir: str, rels_path: str) -> None:
    """Create minimal slide relationships file."""
    content = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>'''
    with open(rels_path, 'w', encoding='utf-8') as f:
        f.write(content)


def _add_slide_to_presentation(base_dir: str, slide_name: str, slide_id: int, rid: int) -> None:
    """Add slide reference to presentation.xml and relationships."""
    # Update presentation.xml
    pres_path = os.path.join(base_dir, 'ppt', 'presentation.xml')
    
    # Parse with lxml, preserving namespaces
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(pres_path, parser)
    root = tree.getroot()
    
    # Define namespace map from root
    nsmap = root.nsmap.copy()
    if None in nsmap:
        nsmap['p'] = nsmap.pop(None)
    
    # Find or create sldIdLst
    sld_id_lst = root.find('.//p:sldIdLst', nsmap)
    if sld_id_lst is None:
        # Find the position to insert (after sldMasterIdLst)
        sld_master_lst = root.find('.//p:sldMasterIdLst', nsmap)
        if sld_master_lst is not None:
            idx = list(root).index(sld_master_lst) + 1
            sld_id_lst = ET.Element('{http://schemas.openxmlformats.org/presentationml/2006/main}sldIdLst')
            root.insert(idx, sld_id_lst)
        else:
            sld_id_lst = ET.SubElement(root, '{http://schemas.openxmlformats.org/presentationml/2006/main}sldIdLst')
    
    # Add slide ID element
    sld_id = ET.SubElement(sld_id_lst, '{http://schemas.openxmlformats.org/presentationml/2006/main}sldId')
    sld_id.set('id', str(slide_id))
    sld_id.set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id', f'rId{rid}')
    
    # Write back
    tree.write(pres_path, xml_declaration=True, encoding='UTF-8', standalone=True)
    
    # Update relationships
    rels_path = os.path.join(base_dir, 'ppt', '_rels', 'presentation.xml.rels')
    rels_tree = ET.parse(rels_path, parser)
    rels_root = rels_tree.getroot()
    
    rel = ET.SubElement(rels_root, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')
    rel.set('Id', f'rId{rid}')
    rel.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide')
    rel.set('Target', f'slides/{slide_name}')
    
    rels_tree.write(rels_path, xml_declaration=True, encoding='UTF-8', standalone=True)


def _add_slide_content_type(base_dir: str, slide_name: str) -> None:
    """Add slide to [Content_Types].xml."""
    ct_path = os.path.join(base_dir, '[Content_Types].xml')
    
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(ct_path, parser)
    root = tree.getroot()
    
    # Check if already exists
    part_name = f'/ppt/slides/{slide_name}'
    for override in root.findall('.//ct:Override', NAMESPACES):
        if override.get('PartName') == part_name:
            return  # Already exists
    
    # Also check without namespace prefix
    for override in root.iter():
        if 'Override' in override.tag and override.get('PartName') == part_name:
            return
    
    override = ET.SubElement(root, '{http://schemas.openxmlformats.org/package/2006/content-types}Override')
    override.set('PartName', part_name)
    override.set('ContentType', 'application/vnd.openxmlformats-officedocument.presentationml.slide+xml')
    
    tree.write(ct_path, xml_declaration=True, encoding='UTF-8', standalone=True)


def _ensure_media_content_type(base_dir: str, ext: str) -> None:
    """Ensure media extension is in Content_Types.xml."""
    ct_path = os.path.join(base_dir, '[Content_Types].xml')
    
    ext_map = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
        'tiff': 'image/tiff',
        'tif': 'image/tiff',
        'wmf': 'image/x-wmf',
        'emf': 'image/x-emf',
        'svg': 'image/svg+xml',
    }
    
    if ext not in ext_map:
        return
    
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(ct_path, parser)
    root = tree.getroot()
    
    # Check if extension already registered
    for default in root.iter():
        if 'Default' in default.tag and default.get('Extension', '').lower() == ext:
            return
    
    default = ET.SubElement(root, '{http://schemas.openxmlformats.org/package/2006/content-types}Default')
    default.set('Extension', ext)
    default.set('ContentType', ext_map[ext])
    
    tree.write(ct_path, xml_declaration=True, encoding='UTF-8', standalone=True)


def _repack_pptx(base_dir: str) -> bytes:
    """Repack directory as PPTX file."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arc_name = os.path.relpath(file_path, base_dir)
                zf.write(file_path, arc_name)
    return output.getvalue()


def _validate_and_repair_pptx(pptx_bytes: bytes) -> bytes:
    """
    Validate and repair PPTX using python-pptx.
    Opening and saving with python-pptx often fixes minor XML issues.
    """
    try:
        # Open with python-pptx - this validates and normalizes the file
        prs = Presentation(io.BytesIO(pptx_bytes))
        
        # Save back - python-pptx will write clean XML
        output = io.BytesIO()
        prs.save(output)
        
        print("[PPTX Merge] Validation/repair completed successfully")
        return output.getvalue()
    except Exception as e:
        print(f"[PPTX Merge] Validation failed: {e}, returning original")
        return pptx_bytes
