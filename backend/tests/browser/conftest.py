"""Browser-test configuration.

When the sandbox ships a pre-installed Chromium whose build differs from the one the installed
Playwright expects, launch that binary instead (override with PW_CHROMIUM_PATH). No-op elsewhere.
"""
import os

import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    path = os.environ.get("PW_CHROMIUM_PATH") or (
        "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
    if path:
        return {**browser_type_launch_args, "executable_path": path, "args": ["--no-sandbox"]}
    return browser_type_launch_args
