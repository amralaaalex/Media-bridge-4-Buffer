import base64
import os
import tempfile

# Must be set before app modules import settings / create the engine.
os.environ.update(
    SESSION_SECRET="test-session-secret",
    TOKEN_ENCRYPTION_KEY=base64.urlsafe_b64encode(b"0" * 32).decode(),
    BUFFER_CLIENT_ID="test-client",
    BUFFER_CLIENT_SECRET="test-secret",
    DATABASE_URL=f"sqlite:///{tempfile.mkdtemp()}/test.db",
    CLEANUP_WORKER_ENABLED="false",
)
