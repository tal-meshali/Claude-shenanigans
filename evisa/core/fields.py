"""Declarative form filling that tolerates unknown or changing markup.

A site profile describes each input as a `Field` with several candidate
locators (label text, name/id guesses, placeholders). The first candidate that
resolves on the page is used, and the one that matched is reported, which makes
calibrating against a live portal a matter of reading the run log. Locators can
be overridden per field from a JSON file without touching code.

Locator mini-language:
    label=Surname           exact accessible label
    label~=Surname          label contains text
    label/=^(Nom|Surname)   label matches a case-insensitive regex (handy for bilingual portals)
    placeholder=Surname     exact placeholder
    role=button:Save        ARIA role + accessible name (substring)
    button/=^(Next|Suivant) a button OR link whose name matches the regex
    text=Save and Continue  visible text (substring)
    anything else           CSS / XPath passed to page.locator()
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence, Union

from playwright.sync_api import Frame, Locator, Page

from .countries import best_option_match, normalize

log = logging.getLogger(__name__)

Scope = Union[Page, Frame, Locator]

_PLACEHOLDER_OPTION = re.compile(r"^(|-+|select|choose|please select|select one|select an option|--.*--|\.\.\.)$", re.I)


class FieldKind(str, Enum):
    TEXT = "text"
    SELECT = "select"
    COMBOBOX = "combobox"  # custom dropdown: click, type, pick
    DATE = "date"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    FILE = "file"


class FormError(RuntimeError):
    pass


class FieldNotFound(FormError):
    def __init__(self, key: str, tried: Sequence[str], url: str):
        super().__init__(f"field {key!r} not found on {url}; tried: {list(tried)}")
        self.key, self.tried, self.url = key, list(tried), url


class OptionNotFound(FormError):
    def __init__(self, key: str, wanted: Sequence[str], available: Sequence[str]):
        preview = ", ".join(available[:25]) + (" ..." if len(available) > 25 else "")
        super().__init__(f"field {key!r}: none of {list(wanted)} matched options [{preview}]")
        self.key, self.wanted, self.available = key, list(wanted), list(available)


ValueFn = Callable[[Any], Any]


@dataclass(frozen=True)
class Field:
    key: str
    kind: FieldKind
    locators: tuple[str, ...]
    value: ValueFn | Any
    required: bool = True
    date_format: str = "%d/%m/%Y"
    # Wait after filling, for portals that reload dependent dropdowns via AJAX.
    settle_ms: int = 0

    def resolve_value(self, ctx: Any) -> Any:
        return self.value(ctx) if callable(self.value) else self.value


@dataclass
class FillRecord:
    key: str
    locator: str
    value: str


@dataclass
class FillReport:
    filled: list[FillRecord] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _page_of(scope: Scope) -> Page:
    if isinstance(scope, Page):
        return scope
    if isinstance(scope, Frame):
        return scope.page
    return scope.page


def locate(scope: Scope, spec: str) -> Locator:
    if spec.startswith("label/="):
        return scope.get_by_label(re.compile(spec[7:], re.I))
    if spec.startswith("button/="):
        rx = re.compile(spec[8:], re.I)
        return scope.get_by_role("button", name=rx).or_(scope.get_by_role("link", name=rx))
    if spec.startswith("label="):
        return scope.get_by_label(spec[6:], exact=True)
    if spec.startswith("label~="):
        return scope.get_by_label(spec[7:], exact=False)
    if spec.startswith("placeholder="):
        return scope.get_by_placeholder(spec[12:], exact=True)
    if spec.startswith("role="):
        role, _, name = spec[5:].partition(":")
        return scope.get_by_role(role, name=name or None)  # type: ignore[arg-type]
    if spec.startswith("text="):
        return scope.get_by_text(spec[5:], exact=False)
    return scope.locator(spec)


USED_MARK = "data-evisa-used"


def find(
    scope: Scope, specs: Iterable[str], *, require_visible: bool = True, timeout_ms: int = 0, skip_used: bool = False,
) -> tuple[Locator, str] | None:
    """First (visible) element matching any spec, polling up to `timeout_ms`.

    `skip_used` ignores elements an earlier field already filled, so two
    fields whose fallback locators overlap cannot overwrite each other.
    """
    specs = list(specs)
    page = _page_of(scope)
    waited = 0
    while True:
        for spec in specs:
            try:
                loc = locate(scope, spec)
                count = loc.count()
            except Exception:  # noqa: BLE001 - invalid selector for this engine, try next
                continue
            for i in range(count):
                candidate = loc.nth(i)
                if skip_used and candidate.get_attribute(USED_MARK) is not None:
                    continue
                if not require_visible or candidate.is_visible():
                    return candidate, spec
        if waited >= timeout_ms:
            return None
        page.wait_for_timeout(250)
        waited += 250


def click(scope: Scope, specs: Iterable[str], *, what: str, timeout_ms: int = 10_000) -> str:
    found = find(scope, specs, timeout_ms=timeout_ms)
    if not found:
        raise FieldNotFound(what, list(specs), _page_of(scope).url)
    loc, spec = found
    loc.click()
    return spec


class Choice(tuple):
    """Candidate groups tried in order: Choice(["Software Engineer"], ["Other"]).

    Within a group the best-ranked match wins (exact beats fuzzy); a later
    group is only consulted when nothing in the earlier ones matched at all.
    """

    def __new__(cls, *groups: Sequence[str]) -> "Choice":
        return super().__new__(cls, tuple(tuple(str(v) for v in g if v not in (None, "")) for g in groups))


def _groups(value: Any) -> list[list[str]]:
    if value is None:
        return []
    if isinstance(value, Choice):
        return [list(g) for g in value if g]
    if isinstance(value, (list, tuple)):
        return [[str(v) for v in value if v not in (None, "")]]
    return [[str(value)]]


def _as_candidates(value: Any) -> list[str]:
    return [c for group in _groups(value) for c in group]


def read_options(select: Locator) -> list[dict[str, Any]]:
    # Portals hide options a person may not pick (e.g. a 90-day visa only some
    # nationalities get); those count as unavailable.
    return select.evaluate(
        """el => Array.from(el.options).map(o => ({value: o.value, label: (o.label || o.text || '').trim(),
            disabled: o.disabled || o.hidden || getComputedStyle(o).display === 'none'}))"""
    )


def choose_option(options: list[dict[str, Any]], candidates: Any) -> dict[str, Any] | None:
    usable = [o for o in options if not o.get("disabled") and not _PLACEHOLDER_OPTION.match(o["label"].strip()) and o["value"] != ""]
    for group in _groups(candidates):
        idx = best_option_match(group, [o["label"] for o in usable])
        if idx is None:
            idx = best_option_match(group, [o["value"] for o in usable])
        if idx is not None:
            return usable[idx]
    return None


def _set_value_js(loc: Locator, value: str) -> None:
    loc.evaluate(
        """(el, v) => {
            el.removeAttribute('readonly');
            const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set;
            setter.call(el, v);
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new Event('blur', {bubbles: true}));
        }""",
        value,
    )


def fill_field(scope: Scope, f: Field, ctx: Any, *, extra_locators: Sequence[str] = (), timeout_ms: int = 3_000) -> FillRecord | None:
    value = f.resolve_value(ctx)
    if value is None or value == "" or value == []:
        if f.required:
            raise FormError(f"field {f.key!r} is required but has no value")
        return None

    specs = [*extra_locators, *f.locators]
    hidden_ok = f.kind in (FieldKind.FILE, FieldKind.SELECT, FieldKind.CHECKBOX, FieldKind.RADIO)
    # Only required fields wait for the page; optional ones get a single look.
    found = find(scope, specs, require_visible=not hidden_ok, timeout_ms=timeout_ms if f.required else 0, skip_used=True)
    if not found:
        if f.required:
            raise FieldNotFound(f.key, specs, _page_of(scope).url)
        log.info("optional field %s not present, skipping", f.key)
        return None
    loc, spec = found

    if f.kind is FieldKind.TEXT:
        shown = str(value)
        loc.fill(shown)
    elif f.kind is FieldKind.DATE:
        if not isinstance(value, date):
            raise FormError(f"field {f.key!r} expects a date")
        input_type = (loc.get_attribute("type") or "").lower()
        shown = value.isoformat() if input_type == "date" else value.strftime(f.date_format)
        if loc.get_attribute("readonly") is not None and input_type != "date":
            _set_value_js(loc, shown)  # datepicker-only inputs refuse typing
        else:
            loc.fill(shown)
            loc.evaluate("el => el.dispatchEvent(new Event('change', {bubbles: true}))")
    elif f.kind is FieldKind.SELECT and loc.evaluate("el => el.tagName") != "SELECT":
        # A "choice" the portal renders as radios or as a free-text input.
        if (loc.get_attribute("type") or "").lower() == "radio":
            group = f'input[type="radio"][name="{loc.get_attribute("name")}"]'
            shown = _choose_radio(scope, f.key, group, value)
        else:
            shown = _as_candidates(value)[0]
            loc.fill(shown)
    elif f.kind is FieldKind.SELECT:
        options = read_options(loc)
        chosen = choose_option(options, value)
        if not chosen:
            raise OptionNotFound(f.key, _as_candidates(value), [o["label"] for o in options if not o.get("disabled")])
        loc.select_option(value=chosen["value"], force=not loc.is_visible())
        shown = chosen["label"]
    elif f.kind is FieldKind.COMBOBOX:
        candidates = _as_candidates(value)
        loc.click()
        if loc.evaluate("el => 'value' in el"):
            loc.fill(candidates[0])
        else:
            loc.page.keyboard.type(candidates[0])
        option = find(_page_of(scope), [f"role=option:{c}" for c in candidates], timeout_ms=3_000)
        if not option:
            raise OptionNotFound(f.key, candidates, [])
        option[0].click()
        shown = candidates[0]
    elif f.kind is FieldKind.CHECKBOX:
        if bool(value):
            loc.check(force=not loc.is_visible())
        else:
            loc.uncheck(force=not loc.is_visible())
        shown = str(bool(value))
    elif f.kind is FieldKind.RADIO:
        shown = _choose_radio(scope, f.key, spec, value)
    elif f.kind is FieldKind.FILE:
        path = Path(value)
        loc.set_input_files(str(path))
        shown = path.name
    else:  # pragma: no cover
        raise FormError(f"unsupported field kind {f.kind}")

    try:
        loc.evaluate(f"el => el.setAttribute('{USED_MARK}', '1')")
    except Exception:  # noqa: BLE001 - element replaced by a re-render; nothing to mark
        pass
    if f.settle_ms:
        _page_of(scope).wait_for_timeout(f.settle_ms)
    return FillRecord(f.key, spec, shown)


def _choose_radio(scope: Scope, key: str, group_spec: str, candidates: Any) -> str:
    """`group_spec` must match every radio in the group (e.g. input[name=gender])."""
    group = locate(scope, group_spec)
    radios = [group.nth(i) for i in range(group.count())]
    labels = [
        r.evaluate(
            """el => {
                if (el.labels && el.labels.length) return el.labels[0].innerText.trim();
                const parent = el.closest('label');
                if (parent) return parent.innerText.trim();
                if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim();
                // Table layouts: "<input type=radio> Yes" with the caption as the next text node.
                let n = el.nextSibling;
                while (n && n.nodeType === 3 && !n.textContent.trim()) n = n.nextSibling;
                if (n && (n.nodeType === 3 || ['SPAN', 'FONT', 'B'].includes(n.tagName))) return n.textContent.trim();
                return (el.value || '').trim();
            }"""
        )
        for r in radios
    ]
    values = [r.get_attribute("value") or "" for r in radios]
    idx = None
    for group in _groups(candidates):
        idx = best_option_match(group, labels)
        if idx is None:
            idx = best_option_match(group, values)
        if idx is not None:
            break
    if idx is None:
        raise OptionNotFound(key, _as_candidates(candidates), labels)
    radios[idx].check(force=not radios[idx].is_visible())
    return labels[idx]


def fill_form(
    scope: Scope,
    fields: Sequence[Field],
    ctx: Any,
    *,
    overrides: dict[str, list[str]] | None = None,
    timeout_ms: int = 3_000,
) -> FillReport:
    report = FillReport()
    overrides = overrides or {}
    for f in fields:
        record = fill_field(scope, f, ctx, extra_locators=overrides.get(f.key, ()), timeout_ms=timeout_ms)
        if record:
            log.debug("filled %-24s via %-40s = %s", record.key, record.locator, record.value)
            report.filled.append(record)
        else:
            report.skipped.append(f.key)
    return report


def page_text_match(page: Page, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(page.inner_text("body"))
    return match.group(1) if match else None


def normalized_equals(a: str, b: str) -> bool:
    return normalize(a) == normalize(b)


VALIDATION_ERROR_SELECTORS = (
    ".field-validation-error", ".validation-summary-errors li", ".invalid-feedback", ".alert-danger",
    ".error-message", ".errorMessage", "#errorMsg", ".error", "[role='alert']",
)


def visible_errors(scope: Scope) -> list[str]:
    messages: list[str] = []
    for sel in VALIDATION_ERROR_SELECTORS:
        loc = scope.locator(sel)
        for i in range(loc.count()):
            item = loc.nth(i)
            if item.is_visible():
                text = item.inner_text().strip()
                # Skip required-field asterisks and other decoration.
                if len(re.sub(r"\W", "", text)) >= 3 and text not in messages:
                    messages.append(text)
    return messages


_NAV_FLAG = "__evisaBeforeSubmit"


def submit_and_verify(
    page: Page,
    buttons: Sequence[str],
    *,
    what: str,
    arrived: Callable[[], bool] | None = None,
    timeout_ms: int = 20_000,
) -> None:
    """Click a step's submit button and make sure the portal accepted it.

    Success is `arrived()` if given, otherwise "a new document loaded and it
    shows no validation errors". Validation messages on the page are raised
    as a FormError so the run log says exactly what the portal disliked.
    """
    page.evaluate(f"window.{_NAV_FLAG} = true")
    alerts: list[str] = []

    def on_dialog(dialog) -> None:
        # Portals that validate in JavaScript report problems with alert();
        # confirm() prompts ("are you sure?") are accepted.
        if dialog.type == "confirm":
            dialog.accept()
        else:
            alerts.append(dialog.message.strip())
            dialog.dismiss()

    def navigated() -> bool:
        return not page.evaluate(f"!!window.{_NAV_FLAG}")

    page.on("dialog", on_dialog)
    try:
        _submit_wait(page, buttons, what, arrived, navigated, alerts, timeout_ms)
    finally:
        page.remove_listener("dialog", on_dialog)


def _submit_wait(
    page: Page, buttons: Sequence[str], what: str, arrived: Callable[[], bool] | None,
    navigated: Callable[[], bool], alerts: list[str], timeout_ms: int,
) -> None:
    click(page, buttons, what=f"{what} submit button")
    waited = 0
    while waited < timeout_ms:
        if alerts:
            raise FormError(f"{what}: portal said: " + " | ".join(alerts))
        try:
            if arrived is not None and arrived():
                return
            if arrived is None and navigated():
                page.wait_for_load_state()
                errors = visible_errors(page)
                if errors:
                    raise FormError(f"{what}: portal rejected the form: " + " | ".join(errors))
                return
        except FormError:
            raise
        except Exception:  # noqa: BLE001 - page mid-navigation
            pass
        page.wait_for_timeout(250)
        waited += 250
        if waited % 1000 == 0:
            try:
                errors = visible_errors(page)
            except Exception:  # noqa: BLE001
                errors = []
            if errors:
                raise FormError(f"{what}: portal rejected the form: " + " | ".join(errors))
    errors = visible_errors(page)
    raise FormError(f"{what}: did not advance after submitting" + (": " + " | ".join(errors) if errors else f" (still on {page.url})"))
