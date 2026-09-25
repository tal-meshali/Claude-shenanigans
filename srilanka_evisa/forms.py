"""Profile-driven element location and form filling on top of Playwright."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from playwright.sync_api import Frame, Locator, Page

from .countries import country_candidates


class FieldNotFound(RuntimeError):
    pass


class OptionNotFound(RuntimeError):
    pass


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip().lower()


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


def _scopes(page: Page, all_frames: bool) -> Iterable[Page | Frame]:
    yield page
    if all_frames:
        for frame in page.frames:
            if frame is not page.main_frame:
                yield frame


def locate(page: Page, spec: dict[str, Any], *, all_frames: bool = False) -> Locator | None:
    """Return the first visible element matching the spec, or None."""
    for scope in _scopes(page, all_frames):
        candidates: list[Locator] = [scope.locator(css) for css in spec.get("selectors", [])]
        candidates += [scope.get_by_label(_rx(lbl)) for lbl in spec.get("labels", [])]
        for text in spec.get("texts", []):
            candidates += [
                scope.get_by_role("button", name=_rx(text)),
                scope.get_by_role("link", name=_rx(text)),
            ]
        for loc in candidates:
            try:
                for i in range(loc.count()):
                    item = loc.nth(i)
                    if item.is_visible() or _is_hidden_file_input(item):
                        return item
            except Exception:  # detached frames, invalid selectors on some engines...
                continue
    return None


def _is_hidden_file_input(loc: Locator) -> bool:
    # Upload widgets often hide the real <input type=file> behind a styled button.
    return loc.evaluate("e => e.tagName === 'INPUT' && e.type === 'file'")


def click(page: Page, spec: dict[str, Any], what: str, *, all_frames: bool = False) -> None:
    loc = locate(page, spec, all_frames=all_frames)
    if loc is None:
        raise FieldNotFound(f"could not find the '{what}' button/link on {page.url}")
    loc.click()


def _value_candidates(value: Any, spec: dict[str, Any]) -> list[str]:
    value_map = spec.get("value_map")
    if value_map == "countries":
        return country_candidates(str(value))
    if isinstance(value_map, dict) and value in value_map:
        return [str(v) for v in value_map[value]]
    return [str(value)]


def _choose_option(loc: Locator, candidates: list[str]) -> None:
    options: list[dict[str, str]] = loc.evaluate(
        "e => [...e.options].map(o => ({value: o.value, text: o.textContent}))"
    )
    options = [o for o in options if o["value"] != ""]
    wanted = [_norm(c) for c in candidates]
    # exact value, exact text, then text starting with / containing the candidate
    for test in (
        lambda o, w: _norm(o["value"]) == w,
        lambda o, w: _norm(o["text"]) == w,
        lambda o, w: _norm(o["text"]).startswith(w),
        lambda o, w: len(w) > 3 and w in _norm(o["text"]),
    ):
        for w in wanted:
            for o in options:
                if test(o, w):
                    loc.select_option(value=o["value"])
                    return
    sample = ", ".join(o["text"].strip() for o in options[:15])
    raise OptionNotFound(f"none of {candidates} in dropdown (options: {sample}...)")


def fill_value(page: Page, loc: Locator, value: Any, spec: dict[str, Any], date_format: str) -> None:
    info = loc.evaluate(
        "e => ({tag: e.tagName.toLowerCase(), type: (e.type || '').toLowerCase()})"
    )
    kind = spec.get("kind") or {
        "select": "select", "textarea": "text"
    }.get(info["tag"]) or {
        "checkbox": "checkbox", "radio": "radio", "file": "file", "date": "date"
    }.get(info["type"], "text")

    if kind == "select":
        _choose_option(loc, _value_candidates(value, spec))
    elif kind == "checkbox":
        loc.set_checked(bool(value))
    elif kind == "radio":
        loc.check()
    elif kind == "file":
        loc.set_input_files(str(Path(value)))
    elif isinstance(value, date):
        text = value.isoformat() if info["type"] == "date" else value.strftime(date_format)
        loc.fill(text)
        # Date pickers often keep a popup open that covers the next field.
        loc.press("Tab")
    else:
        candidates = _value_candidates(value, spec)
        loc.fill(candidates[0] if spec.get("value_map") else str(value))


def fill_field(page: Page, name: str, spec: dict[str, Any], value: Any, date_format: str,
               *, all_frames: bool = False) -> bool:
    """Fill one logical field. Returns False if an optional field is absent."""
    if value is None or value == "":
        return False
    required = spec.get("required", True)

    if spec.get("kind") == "radio" and "options" in spec:
        option_spec = spec["options"].get(value)
        loc = locate(page, option_spec, all_frames=all_frames) if option_spec else None
        if loc is None:
            if required:
                raise FieldNotFound(f"radio option '{value}' for '{name}' not found on {page.url}")
            return False
        loc.check()
        return True

    loc = locate(page, spec, all_frames=all_frames)
    if loc is None:
        if required:
            raise FieldNotFound(f"required field '{name}' not found on {page.url}")
        return False
    fill_value(page, loc, value, spec, date_format)
    return True


def fill_fields(page: Page, specs: dict[str, dict[str, Any]], values: dict[str, Any], date_format: str,
                *, all_frames: bool = False) -> list[str]:
    """Fill every field of a step that has a value; returns the names filled."""
    filled = []
    for name, spec in specs.items():
        if fill_field(page, name, spec, values.get(name), date_format, all_frames=all_frames):
            filled.append(name)
    return filled
