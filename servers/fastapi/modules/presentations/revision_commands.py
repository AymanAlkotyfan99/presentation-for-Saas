"""Deterministic server-side interpreter for the canonical editor command contract."""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from typing import Any, Callable

from modules.presentations.domain import validate_presentation_document


COMMAND_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MAX_COMMANDS = 500
MAX_BATCH_DEPTH = 8
ELEMENT_COMMANDS = {
    "DELETE_ELEMENTS", "DUPLICATE_ELEMENTS", "UPDATE_ELEMENT", "MOVE_ELEMENTS",
    "RESIZE_ELEMENTS", "ROTATE_ELEMENTS", "REORDER_ELEMENTS", "GROUP_ELEMENTS",
    "UNGROUP_ELEMENTS", "LOCK_ELEMENTS", "UNLOCK_ELEMENTS", "HIDE_ELEMENTS",
    "SHOW_ELEMENTS", "ALIGN_ELEMENTS", "DISTRIBUTE_ELEMENTS", "UPDATE_TEXT",
    "UPDATE_STYLE", "REPLACE_ASSET",
}
LOCK_BYPASS = {"LOCK_ELEMENTS", "UNLOCK_ELEMENTS", "HIDE_ELEMENTS", "SHOW_ELEMENTS"}


@dataclass(slots=True)
class RevisionCommandError(ValueError):
    code: str
    detail: str
    target_id: str | None = None

    def __init__(self, code: str, detail: str, target_id: str | None = None):
        ValueError.__init__(self, detail)
        self.code = code
        self.detail = detail
        self.target_id = target_id


def flatten_command_count(commands: list[dict[str, Any]], depth: int = 0) -> int:
    if depth > MAX_BATCH_DEPTH:
        raise RevisionCommandError("EDITOR_COMMAND_BATCH_DEPTH_EXCEEDED", "Nested batch depth is excessive")
    total = 0
    command_ids: set[str] = set()
    for command in commands:
        command_id = command.get("commandId") if isinstance(command, dict) else None
        if command_id in command_ids:
            raise RevisionCommandError("EDITOR_COMMAND_ID_DUPLICATE", "Command IDs must be unique within a batch", command_id)
        if isinstance(command_id, str):
            command_ids.add(command_id)
        total += 1
        if command.get("type") == "BATCH":
            nested = command.get("payload", {}).get("commands")
            if not isinstance(nested, list) or not nested:
                raise RevisionCommandError("EDITOR_COMMAND_BATCH_EMPTY", "Batch commands cannot be empty")
            total += flatten_command_count(nested, depth + 1)
        if total > MAX_COMMANDS:
            raise RevisionCommandError("EDITOR_COMMAND_LIMIT_EXCEEDED", "Command request exceeds the supported limit")
    return total


def apply_commands(document: dict[str, Any], commands: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply commands and validate every boundary just like the client engine."""
    if not isinstance(commands, list) or not commands:
        raise RevisionCommandError("EDITOR_COMMANDS_REQUIRED", "At least one editor command is required")
    flatten_command_count(commands)
    current = validate_presentation_document(document).model_dump(mode="json", by_alias=True, exclude_none=True)
    for command in commands:
        current = _apply(current, command)
    return current


def _apply(document: dict[str, Any], command: dict[str, Any]) -> dict[str, Any]:
    _validate_shape(command)
    if command["type"] == "BATCH":
        current = document
        for nested in command["payload"]["commands"]:
            current = _apply(current, nested)
        return current
    result = copy.deepcopy(document)
    _apply_single(result, command)
    try:
        return validate_presentation_document(result).model_dump(mode="json", by_alias=True, exclude_none=True)
    except Exception as exc:
        if isinstance(exc, RevisionCommandError):
            raise
        raise RevisionCommandError("EDITOR_COMMAND_RESULT_INVALID", "Command produced an invalid canonical document") from exc


def _validate_shape(command: dict[str, Any]) -> None:
    if not isinstance(command, dict):
        raise RevisionCommandError("EDITOR_COMMAND_INVALID", "Command must be an object")
    command_id = command.get("commandId")
    if not isinstance(command_id, str) or not COMMAND_ID.fullmatch(command_id):
        raise RevisionCommandError("EDITOR_COMMAND_ID_INVALID", "Command ID is invalid")
    targets = command.get("targetIds")
    if not isinstance(targets, list) or any(not isinstance(value, str) for value in targets):
        raise RevisionCommandError("EDITOR_COMMAND_TARGETS_INVALID", "targetIds must be a string array")
    if len(set(targets)) != len(targets):
        raise RevisionCommandError("EDITOR_COMMAND_DUPLICATE_TARGET", "Command targets must be unique")
    if not isinstance(command.get("payload"), dict):
        raise RevisionCommandError("EDITOR_COMMAND_PAYLOAD_INVALID", "Command payload must be an object")


def _element_index(document: dict[str, Any]) -> dict[str, tuple[str, str | None, dict[str, Any], list[dict[str, Any]]]]:
    result: dict[str, tuple[str, str | None, dict[str, Any], list[dict[str, Any]]]] = {}
    for slide in document["slides"]:
        def walk(elements: list[dict[str, Any]], parent: str | None = None) -> None:
            for element in elements:
                result[element["id"]] = (slide["id"], parent, element, elements)
                if element["type"] in {"group", "container"}:
                    walk(element["children"], element["id"])
        walk(slide["elements"])
    return result


def _slide(document: dict[str, Any], slide_id: str) -> dict[str, Any]:
    for slide in document["slides"]:
        if slide["id"] == slide_id:
            return slide
    raise RevisionCommandError("EDITOR_SLIDE_NOT_FOUND", "Slide was not found", slide_id)


def _targets(document: dict[str, Any], command: dict[str, Any], *, allow_locked: bool = False):
    index = _element_index(document)
    slide_id = command["payload"].get("slideId")
    found = []
    for target_id in command["targetIds"]:
        path = index.get(target_id)
        if not path:
            raise RevisionCommandError("EDITOR_ELEMENT_NOT_FOUND", "Element was not found", target_id)
        if slide_id and path[0] != slide_id:
            raise RevisionCommandError("EDITOR_TARGET_SLIDE_MISMATCH", "Element belongs to another slide", target_id)
        if not allow_locked and _first_locked(path[2]):
            raise RevisionCommandError("EDITOR_ELEMENT_LOCKED", "A locked element cannot be changed", target_id)
        found.append(path)
    return found


def _first_locked(element: dict[str, Any]) -> bool:
    if element.get("locked"):
        return True
    return any(_first_locked(child) for child in element.get("children", []))


def _normalize_elements(elements: list[dict[str, Any]]) -> None:
    elements.sort(key=lambda value: (value["zOrder"], value["id"]))
    for order, element in enumerate(elements):
        element["zOrder"] = order
        if element["type"] in {"group", "container"}:
            _normalize_elements(element["children"])


def _normalize_slides(document: dict[str, Any]) -> None:
    for order, slide in enumerate(document["slides"]):
        slide["order"] = order


def _children(document: dict[str, Any], slide_id: str, parent_id: str | None) -> list[dict[str, Any]]:
    slide = _slide(document, slide_id)
    if not parent_id:
        return slide["elements"]
    parent = _element_index(document).get(parent_id)
    if not parent:
        raise RevisionCommandError("EDITOR_PARENT_NOT_FOUND", "Parent was not found", parent_id)
    if parent[0] != slide_id:
        raise RevisionCommandError("EDITOR_TARGET_SLIDE_MISMATCH", "Parent belongs to another slide", parent_id)
    if parent[2]["type"] not in {"group", "container"}:
        raise RevisionCommandError("EDITOR_PARENT_TYPE_INVALID", "Parent cannot contain children", parent_id)
    return parent[2]["children"]


def _update(document: dict[str, Any], command: dict[str, Any], updater: Callable[[dict[str, Any]], None], *, allow_locked: bool = False) -> None:
    for _slide_id, _parent_id, element, _siblings in _targets(document, command, allow_locked=allow_locked):
        updater(element)
    _normalize_elements(_slide(document, command["payload"]["slideId"])["elements"])


def _apply_single(document: dict[str, Any], command: dict[str, Any]) -> None:
    kind = command["type"]
    payload = command["payload"]
    targets = command["targetIds"]
    if kind == "ADD_ELEMENT":
        element = payload.get("element")
        if not isinstance(element, dict) or targets != [element.get("id")]:
            raise RevisionCommandError("EDITOR_COMMAND_TARGET_MISMATCH", "Added element must match the command target")
        if element["id"] in _element_index(document):
            raise RevisionCommandError("EDITOR_DUPLICATE_ID", "Element ID already exists", element["id"])
        children = _children(document, payload["slideId"], payload.get("parentId"))
        children.append(copy.deepcopy(element))
        _normalize_elements(_slide(document, payload["slideId"])["elements"])
        return
    if kind in ELEMENT_COMMANDS:
        paths = _targets(document, command, allow_locked=kind in LOCK_BYPASS)
    else:
        paths = []
    if kind == "DELETE_ELEMENTS":
        for _sid, _pid, element, siblings in paths:
            if element in siblings:
                siblings.remove(element)
        _normalize_elements(_slide(document, payload["slideId"])["elements"])
    elif kind == "DUPLICATE_ELEMENTS":
        copies = payload.get("copies", [])
        if len(copies) != len(targets) or {item.get("sourceId") for item in copies} != set(targets):
            raise RevisionCommandError("EDITOR_COMMAND_TARGET_MISMATCH", "Copies must match source targets")
        existing = set(_element_index(document))
        for item in copies:
            clone = copy.deepcopy(item["element"])
            clone_ids = _collect_ids(clone)
            if existing.intersection(clone_ids) or len(clone_ids) != len(set(clone_ids)):
                raise RevisionCommandError("EDITOR_DUPLICATE_ID", "Copied element IDs must be unique")
            _children(document, payload["slideId"], item.get("parentId")).append(clone)
            existing.update(clone_ids)
        _normalize_elements(_slide(document, payload["slideId"])["elements"])
    elif kind == "UPDATE_ELEMENT":
        allowed = {"geometry", "transform", "style", "locked", "hidden", "zOrder"}
        changes = payload.get("changes", {})
        if set(changes) - allowed:
            raise RevisionCommandError("EDITOR_COMMAND_PAYLOAD_INVALID", "Element change includes immutable fields")
        _update(document, command, lambda element: element.update(copy.deepcopy(changes)))
    elif kind == "MOVE_ELEMENTS":
        dx, dy = _finite(payload.get("deltaX")), _finite(payload.get("deltaY"))
        _update(document, command, lambda element: element["geometry"].update(x=element["geometry"]["x"] + dx, y=element["geometry"]["y"] + dy))
    elif kind == "RESIZE_ELEMENTS":
        geometries = payload.get("geometryById", {})
        _update(document, command, lambda element: element.update(geometry=copy.deepcopy(geometries.get(element["id"], element["geometry"]))))
    elif kind == "ROTATE_ELEMENTS":
        rotations = payload.get("rotationById", {})
        def rotate(element: dict[str, Any]) -> None:
            transform = element.setdefault("transform", {})
            transform["rotation"] = rotations.get(element["id"], transform.get("rotation", 0))
        _update(document, command, rotate)
    elif kind == "REORDER_ELEMENTS":
        children = _children(document, payload["slideId"], payload.get("parentId"))
        ordered_ids = payload.get("orderedIds", [])
        if len(ordered_ids) != len(children) or set(ordered_ids) != {item["id"] for item in children}:
            raise RevisionCommandError("EDITOR_ELEMENT_ORDER_INVALID", "Element order must contain every sibling exactly once")
        previous = sorted(children, key=lambda item: (item["zOrder"], item["id"]))
        for index, element in enumerate(previous):
            if element.get("locked") and ordered_ids.index(element["id"]) != index:
                raise RevisionCommandError("EDITOR_ELEMENT_LOCKED", "Locked element cannot be reordered", element["id"])
        by_id = {item["id"]: item for item in children}
        children[:] = [by_id[item_id] for item_id in ordered_ids]
        for order, element in enumerate(children): element["zOrder"] = order
    elif kind == "GROUP_ELEMENTS":
        if len(targets) < 2 or len({path[1] for path in paths}) != 1:
            raise RevisionCommandError("EDITOR_GROUP_REQUIRES_MULTIPLE", "Grouping requires sibling elements")
        group = copy.deepcopy(payload.get("group"))
        if not isinstance(group, dict) or group.get("id") in _element_index(document) or group.get("children"):
            raise RevisionCommandError("EDITOR_GROUP_PAYLOAD_INVALID", "Group must have a new ID and no children")
        if paths[0][1] != payload.get("parentId"):
            raise RevisionCommandError("EDITOR_TARGET_PARENT_MISMATCH", "Group targets and destination must share a parent")
        siblings = paths[0][3]
        first_index = min(siblings.index(path[2]) for path in paths)
        selected = [item for item in siblings if item["id"] in set(targets)]
        for item in selected:
            item["geometry"]["x"] -= group["geometry"]["x"]
            item["geometry"]["y"] -= group["geometry"]["y"]
        group["children"] = selected
        siblings[:] = [item for item in siblings if item["id"] not in set(targets)]
        siblings.insert(first_index, group)
        _normalize_elements(_slide(document, payload["slideId"])["elements"])
    elif kind == "UNGROUP_ELEMENTS":
        for _sid, _pid, group, siblings in list(paths):
            if group["type"] != "group":
                raise RevisionCommandError("EDITOR_UNGROUP_TARGET_INVALID", "Only groups can be ungrouped", group["id"])
            index = siblings.index(group)
            children = group["children"]
            rotation = group.get("transform", {}).get("rotation", 0)
            for child in children:
                child["geometry"]["x"] += group["geometry"]["x"]
                child["geometry"]["y"] += group["geometry"]["y"]
                if rotation:
                    child.setdefault("transform", {})["rotation"] = child.get("transform", {}).get("rotation", 0) + rotation
            siblings[index:index + 1] = children
        _normalize_elements(_slide(document, payload["slideId"])["elements"])
    elif kind in {"LOCK_ELEMENTS", "UNLOCK_ELEMENTS", "HIDE_ELEMENTS", "SHOW_ELEMENTS"}:
        key = "locked" if "LOCK" in kind else "hidden"
        value = kind in {"LOCK_ELEMENTS", "HIDE_ELEMENTS"}
        _update(document, command, lambda element: element.update({key: value}), allow_locked=True)
    elif kind in {"ALIGN_ELEMENTS", "DISTRIBUTE_ELEMENTS"}:
        minimum = 2 if kind == "ALIGN_ELEMENTS" else 3
        if len(paths) < minimum or len({path[1] for path in paths}) != 1:
            raise RevisionCommandError("EDITOR_ALIGNMENT_TARGETS_INVALID", "Operation requires sibling elements")
        _position_elements(paths, payload, distribute=kind == "DISTRIBUTE_ELEMENTS")
        _normalize_elements(_slide(document, payload["slideId"])["elements"])
    elif kind == "UPDATE_TEXT":
        if any(path[2]["type"] != "text" for path in paths):
            raise RevisionCommandError("EDITOR_TEXT_TARGET_INVALID", "Only text elements can receive paragraphs")
        _update(document, command, lambda element: element.update(paragraphs=copy.deepcopy(payload["paragraphs"])))
    elif kind == "UPDATE_STYLE":
        style = payload.get("style", {})
        _update(document, command, lambda element: element.update(style={**element.get("style", {}), **copy.deepcopy(style)}))
    elif kind == "REPLACE_ASSET":
        asset_id = payload.get("assetId")
        if asset_id not in {asset["assetId"] for asset in document["assets"]}:
            raise RevisionCommandError("EDITOR_ASSET_NOT_FOUND", "Asset is not part of the document", asset_id)
        if any(path[2]["type"] not in {"image", "icon"} for path in paths):
            raise RevisionCommandError("EDITOR_ASSET_TARGET_INVALID", "Only image and icon elements can replace assets")
        _update(document, command, lambda element: element.update(assetId=asset_id))
    elif kind == "ADD_SLIDE":
        slide = copy.deepcopy(payload.get("slide"))
        if not isinstance(slide, dict) or slide.get("id") in {item["id"] for item in document["slides"]}:
            raise RevisionCommandError("EDITOR_DUPLICATE_ID", "Slide ID already exists")
        document["slides"].append(slide); _normalize_slides(document)
    elif kind == "DELETE_SLIDE":
        existing = {item["id"] for item in document["slides"]}
        if not set(targets).issubset(existing):
            raise RevisionCommandError("EDITOR_SLIDE_NOT_FOUND", "Slide was not found")
        document["slides"] = [item for item in document["slides"] if item["id"] not in set(targets)]; _normalize_slides(document)
    elif kind == "DUPLICATE_SLIDE":
        existing = {item["id"] for item in document["slides"]}
        copies = payload.get("copies", [])
        if ({item.get("sourceId") for item in copies} != set(targets) or len(copies) != len(targets)
                or any(item.get("sourceId") not in existing or item.get("slide", {}).get("id") in existing for item in copies)):
            raise RevisionCommandError("EDITOR_DUPLICATE_SLIDE_INVALID", "Slide copy is invalid")
        document["slides"].extend(copy.deepcopy(item["slide"]) for item in copies); _normalize_slides(document)
    elif kind == "REORDER_SLIDES":
        ordered = payload.get("orderedSlideIds", [])
        if len(ordered) != len(document["slides"]) or set(ordered) != {item["id"] for item in document["slides"]}:
            raise RevisionCommandError("EDITOR_SLIDE_ORDER_INVALID", "Slide order must contain every slide exactly once")
        by_id = {item["id"]: item for item in document["slides"]}
        document["slides"] = [by_id[item_id] for item_id in ordered]; _normalize_slides(document)
    elif kind == "UPDATE_SLIDE":
        allowed = {"title", "semanticRole", "background", "layoutIntent", "speakerNotes", "locale", "direction", "transitionHint", "exportCapabilities", "compatibility"}
        changes = payload.get("changes", {})
        if set(changes) - allowed:
            raise RevisionCommandError("EDITOR_COMMAND_PAYLOAD_INVALID", "Slide change includes immutable fields")
        existing_slides = {slide["id"] for slide in document["slides"]}
        if not set(targets).issubset(existing_slides):
            raise RevisionCommandError("EDITOR_SLIDE_NOT_FOUND", "Slide was not found")
        found = False
        for slide in document["slides"]:
            if slide["id"] in targets:
                slide.update(copy.deepcopy(changes)); found = True
        if not found:
            raise RevisionCommandError("EDITOR_SLIDE_NOT_FOUND", "Slide was not found")
    else:
        raise RevisionCommandError("EDITOR_COMMAND_TYPE_UNSUPPORTED", "Editor command type is unsupported")


def _collect_ids(element: dict[str, Any]) -> list[str]:
    return [element["id"], *[nested for child in element.get("children", []) for nested in _collect_ids(child)]]


def _finite(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RevisionCommandError("EDITOR_NONFINITE_NUMBER", "Numeric command values must be finite")
    return value


def _box(element: dict[str, Any]) -> dict[str, float]:
    geometry = element["geometry"]
    rotation = element.get("transform", {}).get("rotation", 0)
    radians = rotation * math.pi / 180
    width = geometry["width"] * abs(math.cos(radians)) + geometry["height"] * abs(math.sin(radians))
    height = geometry["width"] * abs(math.sin(radians)) + geometry["height"] * abs(math.cos(radians))
    center_x, center_y = geometry["x"] + geometry["width"] / 2, geometry["y"] + geometry["height"] / 2
    return {"left": center_x - width / 2, "right": center_x + width / 2, "top": center_y - height / 2, "bottom": center_y + height / 2}


def _rounded(value: float) -> float:
    return math.floor(value * 1_000_000 + 0.5) / 1_000_000


def _position_elements(paths, payload: dict[str, Any], *, distribute: bool) -> None:
    entries = [(path[2], _box(path[2])) for path in paths]
    if distribute:
        axis = payload.get("axis")
        if axis not in {"horizontal", "vertical"}:
            raise RevisionCommandError("EDITOR_COMMAND_PAYLOAD_INVALID", "Distribution axis is invalid")
        low, high = ("left", "right") if axis == "horizontal" else ("top", "bottom")
        entries.sort(key=lambda item: item[1][low])
        span = entries[-1][1][high] - entries[0][1][low]
        total = sum(box[high] - box[low] for _, box in entries)
        gap, cursor = (span - total) / (len(entries) - 1), entries[0][1][low]
        for element, box in entries:
            delta = cursor - box[low]
            key = "x" if axis == "horizontal" else "y"
            element["geometry"][key] = _rounded(element["geometry"][key] + delta)
            cursor += box[high] - box[low] + gap
        return
    alignment = payload.get("alignment")
    if alignment not in {"start", "center-horizontal", "end", "top", "center-vertical", "bottom"}:
        raise RevisionCommandError("EDITOR_COMMAND_PAYLOAD_INVALID", "Alignment is invalid")
    union = {
        "left": min(box["left"] for _, box in entries), "right": max(box["right"] for _, box in entries),
        "top": min(box["top"] for _, box in entries), "bottom": max(box["bottom"] for _, box in entries),
    }
    for element, box in entries:
        dx = dy = 0.0
        if alignment == "start": dx = union["left"] - box["left"]
        if alignment == "center-horizontal": dx = (union["left"] + union["right"] - box["left"] - box["right"]) / 2
        if alignment == "end": dx = union["right"] - box["right"]
        if alignment == "top": dy = union["top"] - box["top"]
        if alignment == "center-vertical": dy = (union["top"] + union["bottom"] - box["top"] - box["bottom"]) / 2
        if alignment == "bottom": dy = union["bottom"] - box["bottom"]
        element["geometry"]["x"] = _rounded(element["geometry"]["x"] + dx)
        element["geometry"]["y"] = _rounded(element["geometry"]["y"] + dy)
