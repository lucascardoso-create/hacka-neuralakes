from __future__ import annotations

import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
ROOT = Path(__file__).resolve().parents[1]
CREDENTIALS_FILE = Path(os.getenv("GOOGLE_CREDENTIALS_FILE", str(ROOT / "credentials.json")))
TOKEN_FILE = Path(os.getenv("GOOGLE_TOKEN_FILE", str(ROOT / "token.json")))


def main() -> None:
    if not CREDENTIALS_FILE.is_file():
        raise SystemExit(f"credentials.json não encontrado: {CREDENTIALS_FILE}")
    if TOKEN_FILE.exists():
        raise SystemExit(
            f"token já existe: {TOKEN_FILE}. Remova-o apenas se precisar refazer a autorização."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    credentials = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    TOKEN_FILE.chmod(0o600)
    print(f"Token salvo em: {TOKEN_FILE}")


if __name__ == "__main__":
    main()
