"""MARKDOWN_DIR 内の Markdown ファイルを、Google Drive のフォルダ（FOLDER_ID）にアップロードする。

アップロード先に同じ名前のファイルがあれば内容を更新し、なければ新しく作成する。
実行するとブラウザが開くので、Google アカウントで認証する。

使い方:
    uv run python src/upload_to_drive.py
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv(override=True)

# プロジェクトのルートフォルダ（このファイルの 1 つ上の階層）
BASE_DIR = Path(__file__).resolve().parent.parent
# アップロードする Markdown ファイルが入っているフォルダ
MARKDOWN_DIR = BASE_DIR / "markdown"

# アップロード先の Drive フォルダ ID と、OAuth クライアントの credentials.json のパス（.env から読み込む）
FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
CREDENTIALS_PATH = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH")

# アップロード先の既存ファイルを探して更新するため、Drive の読み書き権限を使う
SCOPES = ["https://www.googleapis.com/auth/drive"]

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_drive_service(credentials_path: str):
    """ブラウザで OAuth 認証を行い、Google Drive API v3 のサービスを返す。"""
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    creds = flow.run_local_server(port=0)
    return build("drive", "v3", credentials=creds)


def escape(value: str) -> str:
    """Drive の検索クエリに埋め込む文字列の \\ と ' をエスケープする。"""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def find_file_id(service, folder_id: str, name: str) -> str | None:
    """フォルダ内にある同じ名前のファイルの ID を返す。なければ None を返す。"""
    query = f"name = '{escape(name)}' and '{escape(folder_id)}' in parents and trashed = false"
    files = service.files().list(q=query, fields="files(id)").execute().get("files", [])
    return files[0]["id"] if files else None


def upload_file(service, folder_id: str, path: Path) -> None:
    media = MediaFileUpload(path, mimetype="text/markdown")
    file_id = find_file_id(service, folder_id, path.name)

    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
        logger.info("更新: %s", path.name)
    else:
        metadata = {"name": path.name, "parents": [folder_id]}
        service.files().create(body=metadata, media_body=media).execute()
        logger.info("新規作成: %s", path.name)


def main() -> None:
    if not FOLDER_ID:
        sys.exit("環境変数 GOOGLE_DRIVE_FOLDER_ID が設定されていません")
    if not CREDENTIALS_PATH:
        sys.exit("環境変数 GOOGLE_DRIVE_CREDENTIALS_PATH が設定されていません")

    paths = sorted(MARKDOWN_DIR.glob("*.md"))
    if not paths:
        sys.exit(f".md ファイルが見つかりません: {MARKDOWN_DIR}")

    service = get_drive_service(CREDENTIALS_PATH)
    for path in paths:
        upload_file(service, FOLDER_ID, path)


if __name__ == "__main__":
    main()
