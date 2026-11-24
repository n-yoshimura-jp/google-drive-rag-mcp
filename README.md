# Google Drive RAG MCP Server

Word / Excel / PowerPoint / PDF / テキストファイルを Markdown に変換して Google Drive にアップロードし、その内容について MCP クライアント（Claude Code / Claude Desktop など）から質問できるようにする RAG（Retrieval-Augmented Generation）システムです。

## 構成

処理は 3 つのプログラムに分かれています。

| ファイル | 種類 | 役割 |
|---|---|---|
| `src/convert_to_markdown.py` | CLI | ローカルフォルダのファイルを Markdown (`.md`) に変換する |
| `src/upload_to_drive.py` | CLI | `.md` ファイルを Google Drive のフォルダにアップロードする（同名ファイルは更新） |
| `src/google_drive_rag_mcp_server.py` | MCP サーバー | Drive の `.md` ファイルを検索し、質問に回答する（ツール: `ask_question`） |

```
ローカルの資料 ──(convert_to_markdown.py)──> .md ──(upload_to_drive.py)──> Google Drive
                                                                              │
                                    MCP クライアント ──(ask_question)──> google_drive_rag_mcp_server.py
```

## 対応ファイル形式

Word (`.docx`)、Excel (`.xlsx`、全シート)、PowerPoint (`.pptx`)、PDF (`.pdf`、文字情報のあるもの)、テキスト (`.txt`)

## 主なライブラリ

- **markitdown**: 各種ファイルの Markdown 変換
- **Google Drive API**: ファイルのアップロードと読み込み
- **LangChain**: RAG パイプライン（チャンク分割、ベクトル検索）
- **OpenAI Embeddings** (`text-embedding-3-small`): ドキュメントと質問のベクトル化
- **Claude Haiku 5.5**: 回答生成
- **MCP Python SDK**: MCP サーバーの実装

## セットアップ

詳しい手順は [SETUP_GUIDE.txt](SETUP_GUIDE.txt) を参照してください。

1. 依存関係をインストール:
   ```bash
   uv sync
   ```
2. Google Cloud で Drive API を有効化し、OAuth クライアント ID（デスクトップアプリ）の `credentials.json` を用意
3. `.env` ファイルを作成:
   ```env
   OPENAI_API_KEY=your-openai-api-key
   ANTHROPIC_API_KEY=your-anthropic-api-key
   GOOGLE_DRIVE_FOLDER_ID=your-folder-id
   GOOGLE_DRIVE_CREDENTIALS_PATH=/absolute/path/to/credentials.json
   ```

## 使い方

フォルダはスクリプト先頭の変数で指定します（既定値: 変換元 `data/`、Markdown の保存先 `markdown/`）。アップロード先の Drive フォルダ ID は `.env` の `GOOGLE_DRIVE_FOLDER_ID` から読み込みます。

1. `data/` の資料を Markdown に変換し、`markdown/` に保存:
   ```bash
   uv run python src/convert_to_markdown.py
   ```
2. `markdown/` の `.md` を Google Drive にアップロード（ブラウザで Google 認証）:
   ```bash
   uv run python src/upload_to_drive.py
   ```
3. MCP サーバーを MCP クライアントに登録して、質問する:
   ```bash
   claude mcp add google-drive-rag -- uv run --directory /path/to/google-drive-rag python src/google_drive_rag_mcp_server.py
   ```
   例: 「ビジネスプランの月額は？」

## 仕組み（`ask_question`）

1. 初回の質問時に、Drive フォルダ直下の `.md` ファイルを読み込む
2. Markdown の見出し・段落を区切りにしてチャンク分割（1000 文字、200 文字オーバーラップ）
3. OpenAI Embeddings でベクトル化し、メモリ上のベクトルストアに保存
4. 質問に近いチャンクを 4 件検索し、Claude Haiku 5.5 で回答を生成
5. 回答と参照元（ファイル名と抜粋）を返す

インデックスはメモリ上にのみ保持されます。Drive の資料を更新したら、MCP サーバーを再起動してください。

## 参考リンク

- [markitdown](https://github.com/microsoft/markitdown)
- [LangChain](https://github.com/langchain-ai/langchain)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [OpenAI](https://openai.com/)
- [Claude API](https://platform.claude.com/docs)
