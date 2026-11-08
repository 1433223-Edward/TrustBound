"""Small local .env loader; injected process settings always take precedence."""
import os
from pathlib import Path

ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
LOCAL_KEYS = {"VULTR_INFERENCE_API_KEY", "VULTR_MODEL", "TRUSTBOUND_ENABLE_LIVE",
              "TRUSTBOUND_ENABLE_RECOVERY_LIVE", "TRUSTBOUND_ENABLE_WORKSPACE_LIVE"}


def load_local_env(path=ROOT_ENV, environ=None):
    """Read only backend settings, without expansion, execution or secret logging.

    Set TRUSTBOUND_LOAD_DOTENV=0 in production to disable local files entirely.
    Existing variables, including explicitly empty values, override the local file.
    """
    target = os.environ if environ is None else environ
    if target.get("TRUSTBOUND_LOAD_DOTENV", "1") == "0" or not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].strip()
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or key not in LOCAL_KEYS:
            continue
        if value.startswith(("'", '"')):
            quote = value[0]
            end = value.find(quote, 1)
            if end < 0 or (value[end + 1:].strip() and not value[end + 1:].strip().startswith("#")):
                continue
            value = value[1:end]
        else:
            value = value.split(" #", 1)[0].rstrip()
        target.setdefault(key, value)
