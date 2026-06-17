import copy
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "sample_rpc.json"


@pytest.fixture
def sample_raw():
    """A fresh copy of the captured ``{command: response}`` RPC dict."""
    return copy.deepcopy(json.loads(FIXTURE.read_text()))
