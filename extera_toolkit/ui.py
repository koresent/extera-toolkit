import re
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .adb import AdbController, AdbError

BOUNDS_REGEX = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def parse_bounds(bounds_str: str) -> Optional[Tuple[int, int, int, int]]:
    """Parses '[x1,y1][x2,y2]' bounds string into (x1, y1, x2, y2)."""
    match = BOUNDS_REGEX.match(bounds_str)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))


def parse_ui_hierarchy(xml_content: str) -> List[Dict[str, Any]]:
    """Parses Android uiautomator XML into a flattened list of meaningful UI elements."""
    if not xml_content.strip():
        return []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise ValueError(f"Failed to parse UI hierarchy XML: {exc}") from exc

    elements: List[Dict[str, Any]] = []

    for node in root.iter("node"):
        attrib = node.attrib
        text = attrib.get("text", "").strip()
        resource_id = attrib.get("resource-id", "").strip()
        content_desc = attrib.get("content-desc", "").strip()
        cls_name = attrib.get("class", "").strip()
        clickable = attrib.get("clickable", "false").lower() == "true"
        enabled = attrib.get("enabled", "true").lower() == "true"
        bounds_str = attrib.get("bounds", "")

        # Skip invisible or irrelevant layout wrappers with no identifying traits
        if not (text or resource_id or content_desc or clickable):
            continue

        bounds = parse_bounds(bounds_str)
        if not bounds:
            continue

        x1, y1, x2, y2 = bounds
        # Skip zero-sized elements
        if x2 <= x1 or y2 <= y1:
            continue

        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2

        # Simplify class name (e.g. android.widget.TextView -> TextView)
        short_cls = cls_name.split(".")[-1] if cls_name else ""

        elem_data: Dict[str, Any] = {
            "type": short_cls,
            "center": [center_x, center_y],
            "bounds": [x1, y1, x2, y2],
        }
        if text:
            elem_data["text"] = text
        if resource_id:
            # Strip package prefix if common
            short_id = resource_id.split("/")[-1] if "/" in resource_id else resource_id
            elem_data["id"] = short_id
        if content_desc:
            elem_data["desc"] = content_desc
        if clickable:
            elem_data["clickable"] = True
        if not enabled:
            elem_data["disabled"] = True

        elements.append(elem_data)

    return elements


class UIInspector:
    """Provides UI inspection, element search, click automation, and visual verification."""

    def __init__(self, adb_controller: Optional[AdbController] = None):
        self.adb = adb_controller or AdbController()

    def dump(
        self,
        filter_text: Optional[str] = None,
        clickable_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Dumps current on-screen UI elements."""
        xml_data = self.adb.dump_window_hierarchy()
        elements = parse_ui_hierarchy(xml_data)

        if clickable_only:
            elements = [e for e in elements if e.get("clickable")]

        if filter_text:
            query = filter_text.lower()
            elements = [
                e for e in elements
                if (
                    query in e.get("text", "").lower()
                    or query in e.get("desc", "").lower()
                    or query in e.get("id", "").lower()
                )
            ]
        return elements

    def find_elements(self, query: str) -> List[Dict[str, Any]]:
        """Finds elements matching text, id, or content description."""
        return self.dump(filter_text=query)

    def click(self, query: str, index: int = 0) -> Dict[str, Any]:
        """Finds an element by query and taps its center."""
        matches = self.find_elements(query)
        if not matches:
            return {
                "success": False,
                "error": f"Element matching '{query}' not found on screen.",
                "total_matches": 0,
            }

        if index >= len(matches):
            return {
                "success": False,
                "error": f"Match index {index} out of range (found {len(matches)} matches).",
                "total_matches": len(matches),
            }

        target = matches[index]
        cx, cy = target["center"]
        self.adb.input_tap(cx, cy)

        return {
            "success": True,
            "clicked": target,
            "total_matches": len(matches),
            "index": index,
        }

    def screenshot(
        self,
        output_path: Optional[str] = None,
        crop_bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> Dict[str, Any]:
        """Takes a screenshot and optionally crops it."""
        pulled_path = self.adb.screencap(local_path=output_path)
        if crop_bounds:
            try:
                from PIL import Image
                img = Image.open(pulled_path)
                cropped = img.crop(crop_bounds)
                cropped.save(pulled_path)
            except ImportError:
                pass

        return {
            "success": True,
            "path": pulled_path,
            "crop": list(crop_bounds) if crop_bounds else None,
        }
