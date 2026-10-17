from __future__ import annotations

import pytest
from web_fakes import Demo, make_demo


@pytest.fixture
def demo() -> Demo:
    return make_demo()
