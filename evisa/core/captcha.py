"""CAPTCHA handling.

Real portals' CAPTCHAs are completed by a person in the headed browser; the
automation only detects when that is done. `LoopbackCheckboxCaptcha` ticks the
stand-in checkbox of the local mock portals and refuses to run anywhere else.
"""

from __future__ import annotations

from typing import Callable, Protocol

from playwright.sync_api import Page

from .browser import is_loopback, wait_for_human

RECAPTCHA_MARKERS = "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], .g-recaptcha, .h-captcha, [name='g-recaptcha-response']"


class CaptchaHandler(Protocol):
    def __call__(self, page: Page) -> None: ...


def captcha_present(page: Page) -> bool:
    return page.locator(RECAPTCHA_MARKERS).count() > 0


def captcha_token(page: Page) -> str:
    return page.evaluate(
        """() => {
            const el = document.querySelector("[name='g-recaptcha-response'], [name='h-captcha-response']");
            return el ? el.value : '';
        }"""
    )


class ManualCaptcha:
    """Waits for the person to solve the CAPTCHA in the visible browser window."""

    def __init__(self, *, headless: bool, timeout_s: int = 600, notify: Callable[[str], None] = print):
        self.headless, self.timeout_s, self.notify = headless, timeout_s, notify

    def __call__(self, page: Page) -> None:
        if not captcha_present(page):
            return
        wait_for_human(
            page,
            'tick "I\'m not a robot" (and solve any picture challenge)',
            lambda: bool(captcha_token(page)),
            headless=self.headless,
            timeout_s=self.timeout_s,
            notify=self.notify,
        )


class LoopbackCheckboxCaptcha:
    """For the bundled mock portals only: ticks their stand-in CAPTCHA checkbox."""

    def __call__(self, page: Page) -> None:
        if not is_loopback(page.url):
            raise PermissionError("LoopbackCheckboxCaptcha only runs against local mock portals")
        box = page.locator("#mock-captcha")
        if box.count():
            box.check()
