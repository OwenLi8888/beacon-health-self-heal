# Live UI (stack up, make reset first): patients without an A1c must raise, never return a value.
import pytest
from playwright.sync_api import sync_playwright

from scripts.common import ValueNotFound
from scripts.read_a1c import read_a1c


@pytest.mark.parametrize("first, last, dob", [
    ("Grace", "Whitfield", "1952-08-17"),   # BH005: glucose only
    ("Thomas", "Whitfield", "1949-05-09"),  # BH006: no labs at all
])
def test_no_a1c_raises(first, last, dob):
    with sync_playwright() as p:
        with pytest.raises(ValueNotFound):
            read_a1c(p.chromium.launch().new_page(), first, last, dob)
