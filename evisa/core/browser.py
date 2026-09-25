"""Playwright session management and human-in-the-loop helpers."""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

log = logging.getLogger(__name__)


class HumanActionRequired(RuntimeError):
    """A step needs a person (CAPTCHA, 3-D Secure) but the browser is headless."""


@dataclass
class BrowserOptions:
    headless: bool = True
    slow_mo_ms: int = 0
    timeout_ms: int = 20_000
    navigation_timeout_ms: int = 60_000
    executable_path: str | None = field(default_factory=lambda: os.environ.get("EVISA_CHROMIUM") or None)
    locale: str = "en-US"
    viewport: tuple[int, int] = (1366, 900)
    # Seconds to wait for a person to finish a CAPTCHA / 3-D Secure challenge.
    human_timeout_s: int = 600


class BrowserSession:
    """One Chromium process; one isolated context per application."""

    def __init__(self, options: BrowserOptions, artifacts_dir: Path):
        self.options = options
        self.artifacts_dir = Path(artifacts_dir)
        self._pw: Playwright | None = None
        self._browser: Browser | None = None

    def __enter__(self) -> "BrowserSession":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.options.headless,
            slow_mo=self.options.slow_mo_ms,
            executable_path=self.options.executable_path,
        )
        return self

    def __exit__(self, *exc) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def new_context(self) -> BrowserContext:
        assert self._browser, "BrowserSession not started"
        ctx = self._browser.new_context(
            locale=self.options.locale,
            viewport={"width": self.options.viewport[0], "height": self.options.viewport[1]},
            accept_downloads=True,
        )
        ctx.set_default_timeout(self.options.timeout_ms)
        ctx.set_default_navigation_timeout(self.options.navigation_timeout_ms)
        return ctx

    def screenshot(self, page: Page, folder: str, name: str) -> Path:
        dest = self.artifacts_dir / folder / f"{re.sub(r'[^a-zA-Z0-9_-]+', '-', name)}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(dest), full_page=True)
        return dest


def wait_for_human(
    page: Page,
    message: str,
    done: Callable[[], bool],
    *,
    headless: bool,
    timeout_s: int,
    notify: Callable[[str], None] = print,
    poll_s: float = 1.0,
) -> None:
    """Hand the browser to a person until `done()` holds.

    Nothing reads stdin here on purpose: a pending `input()` would swallow the
    next prompt (e.g. the card-details prompt). The person acts in the browser
    window and the automation resumes as soon as the page shows it is done.
    """
    if done():
        return
    if headless:
        raise HumanActionRequired(f"{message} -- rerun with --headed so you can complete it")
    try:
        page.bring_to_front()
    except Exception:  # noqa: BLE001 - cosmetic only
        pass
    notify(f"\n>>> ACTION NEEDED in the browser window: {message}\n    (waiting up to {timeout_s // 60} min; the run continues automatically)")
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if done():
                notify(">>> Thanks - continuing.")
                return
        except Exception:  # page may be mid-navigation
            pass
        page.wait_for_timeout(int(poll_s * 1000))
    raise TimeoutError(f"timed out waiting for: {message}")


def is_loopback(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in ("localhost", "127.0.0.1", "::1") or host.startswith("127.")


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()
