from __future__ import annotations

import io
from copy import deepcopy
from typing import Iterable

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


class MergeError(Exception):
    pass


def merge_presentations(buffers: Iterable[bytes]) -> bytes:
    payloads = list(buffers)
    if not payloads:
        raise MergeError("No PPTX data provided.")

    base = Presentation(io.BytesIO(payloads[0]))
    for payload in payloads[1:]:
        source = Presentation(io.BytesIO(payload))
        for slide in source.slides:
            _append_slide(base, slide)

    output = io.BytesIO()
    base.save(output)
    return output.getvalue()


def _append_slide(target: Presentation, slide) -> None:
    layout = _blank_layout(target)
    new_slide = target.slides.add_slide(layout)

    for shape in slide.shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            _copy_picture(shape, new_slide)
            continue

        new_element = deepcopy(shape.element)
        new_slide.shapes._spTree.insert_element_before(new_element, "p:extLst")


def _blank_layout(prs: Presentation):
    if len(prs.slide_layouts) > 6:
        return prs.slide_layouts[6]
    return prs.slide_layouts[-1]


def _copy_picture(shape, new_slide) -> None:
    try:
        image_blob = shape.image.blob
    except Exception:
        return

    new_slide.shapes.add_picture(
        io.BytesIO(image_blob),
        shape.left,
        shape.top,
        shape.width,
        shape.height,
    )
