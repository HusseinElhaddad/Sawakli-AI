import runpy
from pathlib import Path

import pytest

CHECK = runpy.run_path(str(Path(__file__).resolve().parents[4] / "scripts/check_ai_security.py"))


@pytest.mark.parametrize(
    "source",
    [
        "import requests as r",
        "from httpx import Client as C",
        "from urllib import request as r",
        "import socket",
        "from sawakli.connectors.oauth import repository",
        "from sawakli.db.models.user import User as Account",
        "from sawakli.db.tables import connector_tokens_table as t",
        "query = tables.users.select()",
        "q = 'SELECT * FROM users'",
        "q = 'SELECT * FROM public.users'",
        'q = \'SELECT * FROM "public"."connector_tokens"\'',
        "q = 'SELECT * FROM campaigns JOIN oauth_connections ON true'",
    ],
)
def test_forbidden_source_is_detected(source):
    assert CHECK["inspect_source"](source)


@pytest.mark.parametrize(
    "source",
    [
        "# import requests\nimport csv",
        "from pathlib import Path",
        "from sawakli.db.models.jobs import Job",
        "from sawakli.db.tables import campaigns_table",
        "from sawakli.db.session import SessionLocal",
        "q = 'SELECT * FROM campaigns WHERE organization_id=:org'",
    ],
)
def test_legitimate_source_is_allowed(source):
    assert CHECK["inspect_source"](source) == []
