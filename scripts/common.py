"""Shared by the scripts: step logging, data errors, login. No retries here, by design."""
import functools
import json
import os
import sys
import time

from dotenv import load_dotenv
from playwright.sync_api import Page

load_dotenv()


class ValueNotFound(Exception):
    """An expected value is missing from the page or cannot be parsed."""


class AmbiguousValue(Exception):
    """The page offers more than one candidate and nothing says which is right."""


def _log(event: str, name: str, **extra) -> None:
    print(json.dumps({"event": event, "step": name, "t": round(time.time(), 3), **extra}),
          file=sys.stderr, flush=True)


def step(fn):
    """Log step_start / step_end around a named step so a failure points at the step."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        _log("step_start", fn.__name__)
        try:
            result = fn(*args, **kwargs)
        except Exception as e:
            _log("step_end", fn.__name__, ok=False, error=f"{type(e).__name__}: {e}")
            raise
        _log("step_end", fn.__name__, ok=True)
        return result
    return wrapper


@step
def login(page: Page) -> None:
    page.goto(f"http://localhost:{os.environ['OPENEMR_HTTP_PORT']}/interface/login/login.php?site=default")
    page.get_by_label("Username").fill(os.environ["OE_USER"])
    page.get_by_label("Password").fill(os.environ["OE_PASS"])
    page.get_by_role("button", name="Login").click()
    page.wait_for_url("**/interface/main/tabs/main.php**")
