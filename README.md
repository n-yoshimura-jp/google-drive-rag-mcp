# Google Drive RAG MCP Server

Google DriveのドキュメントにRAG（Retrieval-Augmented Generation）機能を提供するMCP（Model Context Protocol）サーバーです。Google Drive内のドキュメント（PDF、DOCX、Googleドキュメントなど）を検索し、AIによる質問応答を実現します。

## 特徴

- **RAGベースの質問応答**: Google Drive内のドキュメントに対して自然言語で質問できます
- **多様なファイル形式に対応**: PDF、DOCX、Googleドキュメント、スプレッドシート、テキストファイル
- **ベクトル検索**: FAISSを使用した高速な類似度検索
- **MCPサーバー実装**: 標準的なMCPプロトコルに準拠
- **簡単な統合**: LangChainとOpenAI GPTを活用した柔軟なアーキテクチャ

## 主要機能

### 1. ドキュメント検索と質問応答 (`ask_question`)
Google Driveフォルダ内のドキュメントを検索し、質問に対する回答を生成します。

**使用例:**
- 「料金プランについて教えて」
- 「エンタープライズプランの機能は？」
- 「サービスの利用規約を教えて」

### 2. ファイル一覧表示 (`list_files`)
指定したフォルダ内のファイル一覧を取得します。

### 3. ファイルアップロード (`upload_file`)
ローカルファイルをGoogle Driveにアップロードします。

## 主なライブラリ

- **Python 3.13+**
- **LangChain**: RAGパイプラインの構築
- **OpenAI GPT**: 自然言語処理と回答生成
- **FAISS**: ベクトル類似度検索
- **Google Drive API**: ドキュメントの取得と管理
- **FastMCP**: MCPサーバーの実装
- **PyPDF & python-docx**: ファイル形式の解析

## インストール

### 前提条件

- Python 3.13以上
- OpenAI APIキー
- Google Cloud Projectとサービスアカウント
- Google Drive APIの有効化

### セットアップ

1. リポジトリをクローン:
```bash
git clone <repository-url>
cd google-drive-rag
```

2. 依存関係をインストール:
```bash
pip install -r requirements.txt
```

または`uv`を使用:
```bash
uv sync
```

3. 環境変数を設定（`.env`ファイルを作成）:
```env
OPENAI_API_KEY=your-openai-api-key
GOOGLE_DRIVE_FOLDER_ID=your-folder-id
GOOGLE_DRIVE_CREDENTIALS_PATH=path/to/credentials.json
```

### Google Drive APIの設定

1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクトを作成
2. Google Drive APIを有効化
3. OAuth 2.0クライアントIDを作成（デスクトップアプリケーション）
4. `credentials.json`をダウンロードし、プロジェクトディレクトリに配置
5. 環境変数`GOOGLE_DRIVE_CREDENTIALS_PATH`にパスを設定

## 使用方法

### MCPサーバーとして起動

```bash
python src/google_drive_rag_mcp_server.py
```

### ツールの使用例

#### 質問応答
```python
# MCPクライアントから
ask_question("料金プランについて教えてください")
```

#### ファイル一覧
```python
list_files(max_results=10)
```

#### ファイルアップロード
```python
upload_file("/path/to/document.pdf")
```

## 仕組み

1. **初期化フェーズ**:
   - 指定されたGoogle Driveフォルダからドキュメントをダウンロード
   - テキストを抽出し、チャンク分割（1000文字、200文字オーバーラップ）
   - OpenAI Embeddingsでベクトル化
   - FAISSインデックスを構築

2. **検索フェーズ**:
   - ユーザーの質問をベクトル化
   - FAISSで関連ドキュメントを検索
   - 上位3件のドキュメントを取得

3. **生成フェーズ**:
   - 検索結果をコンテキストとして使用
   - OpenAI GPTで回答を生成
   - 参照元情報と共に返答

## 対応ファイル形式

- Googleドキュメント (`.gdoc`)
- PDFファイル (`.pdf`)
- Wordファイル (`.docx`)
- テキストファイル (`.txt`)

## 参考リンク

- [LangChain](https://github.com/langchain-ai/langchain)
- [FastMCP](https://github.com/jlowin/fastmcp)
- [OpenAI](https://openai.com/)
- [FAISS](https://github.com/facebookresearch/faiss)