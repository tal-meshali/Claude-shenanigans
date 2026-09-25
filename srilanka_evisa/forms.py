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


class FieldRejected(RuntimeError):
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
    options = [o for o in options if o["value"] not in ("", "0X")]  # "0X" = "[Select ...]" on eta.gov.lk
    wanted = [_norm(c) for c in candidates]
    # exact value (also the "CODE" of "CODE|Label" values), exact text,
    # then text starting with / containing the candidate
    for test in (
        lambda o, w: _norm(o["value"]) == w,
        lambda o, w: _norm(o["value"].split("|")[0]) == w,
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


_SET_VALUE_JS = """(e, v) => {
    e.value = v;
    for (const t of ['input', 'change', 'blur']) e.dispatchEvent(new Event(t, {bubbles: true}));
}"""


def _set_text(loc: Locator, text: str, readonly: bool) -> None:
    if readonly:
        # Calendar widgets (e.g. eta.gov.lk's scw.js) make date boxes read-only
        # and only accept clicks in a popup; set the value like the widget does.
        loc.evaluate(_SET_VALUE_JS, text)
        return
    # Type key by key: eta.gov.lk reverts any input that grows by more than one
    # character at once (anti-paste), which is what fill() would do. Then blur
    # so the site's onchange checks (e.g. the passport lookup) run.
    loc.fill("")
    loc.press_sequentially(text)
    loc.evaluate("e => e.blur()")


def _date_part_candidates(part: str, d: date) -> list[str]:
    if part == "year":
        return [str(d.year)]
    if part == "day":
        return [f"{d.day:02d}", str(d.day)]
    return [f"{d.month:02d}", str(d.month), d.strftime("%b"), d.strftime("%B")]


def fill_date_parts(page: Page, parts: dict[str, dict[str, Any]], value: date, *, all_frames: bool = False) -> bool:
    """Fill a date split into year / month / day boxes. False if they are absent."""
    located = {name: locate(page, spec, all_frames=all_frames) for name, spec in parts.items()}
    if any(loc is None for loc in located.values()):
        return False
    for name, loc in located.items():
        candidates = _date_part_candidates(name, value)
        if loc.evaluate("e => e.tagName") == "SELECT":
            _choose_option(loc, candidates)
        else:
            _set_text(loc, candidates[0], loc.evaluate("e => e.readOnly"))
    return True


def fill_value(page: Page, loc: Locator, value: Any, spec: dict[str, Any], date_format: str) -> None:
    info = loc.evaluate(
        "e => ({tag: e.tagName.toLowerCase(), type: (e.type || '').toLowerCase(), readonly: !!e.readOnly})"
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
        _set_text(loc, text, info["readonly"])
        if not info["readonly"]:
            loc.press("Tab")  # date pickers often keep a popup open over the next field
    else:
        candidates = _value_candidates(value, spec)
        _set_text(loc, candidates[0] if spec.get("value_map") else str(value), info["readonly"])


def fill_field(page: Page, name: str, spec: dict[str, Any], value: Any, date_format: str,
               *, all_frames: bool = False) -> bool:
    """Fill one logical field. Returns False if an optional field is absent."""
    if value is None or value == "":
        return False
    required = spec.get("required", True)

    if isinstance(value, date) and "parts" in spec:
        if fill_date_parts(page, spec["parts"], value, all_frames=all_frames):
            return True
        # otherwise fall through to a single date box located by label

    if spec.get("kind") == "radio" and "options" in spec:
        key = {True: "yes", False: "no"}.get(value, value) if isinstance(value, bool) else value
        option_spec = spec["options"].get(key)
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
    if spec.get("wait_for"):
        # e.g. a server-side check that flips a hidden flag once the value is accepted
        try:
            page.wait_for_selector(spec["wait_for"], state="attached", timeout=spec.get("wait_ms", 20_000))
        except Exception as exc:
            raise FieldRejected(f"the site did not accept '{name}' (waited for {spec['wait_for']})") from exc
    return True


def fill_fields(page: Page, specs: dict[str, dict[str, Any]], values: dict[str, Any], date_format: str,
                *, all_frames: bool = False) -> list[str]:
    """Fill every field of a step that has a value; returns the names filled."""
    filled = []
    for name, spec in specs.items():
        if fill_field(page, name, spec, values.get(name), date_format, all_frames=all_frames):
            filled.append(name)
    return filled
