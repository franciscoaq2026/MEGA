import uuid
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def sessao():
    """Header de uma sessão válida, criada direto no banco — gravar resultado
    exige login. O import fica aqui dentro porque cada arquivo de teste
    define o MEGASENA_DB_PATH antes de importar o app."""
    from app import db

    db.init_db()
    sid = uuid.uuid4().hex
    agora = datetime.now(timezone.utc)
    db.create_session(
        sid, "teste@example.com", "owner", agora.isoformat(), (agora + timedelta(hours=1)).isoformat()
    )
    return {"X-Session-Id": sid}
