import os
import sys
import io
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from pypdf import PdfReader
from docx import Document as DocxDocument

# Windows環境でのcp932（Shift-JIS）のエラー対策 (UTF-8に変更。Windowsの場合のみ実行)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(override=True)

SCOPES = ["https://www.googleapis.com/auth/drive"]

# グローバル変数
qa_chain = None
vector_store = None
drive_service = None
retriever_global = None

mcp = FastMCP("Google Drive RAG")

def get_drive_service():
    """
    Google Drive APIサービスインスタンスを取得します。
    
    初回呼び出し時にOAuth2.0認証フローを実行し、ユーザーの認証を求めます。
    認証後はセッション中はグローバル変数に保持され、再認証は不要です。
    
    Returns:
        googleapiclient.discovery.Resource: Google Drive API v3のサービスインスタンス
    
    Raises:
        Exception: GOOGLE_DRIVE_CREDENTIALS_PATH環境変数が設定されていない場合
    
    Note:
        - 認証情報はセッション中のみ保持され、永続化されません
        - credentials.jsonファイルのパスは環境変数GOOGLE_DRIVE_CREDENTIALS_PATHで指定
        - 初回実行時はブラウザが開き、Googleアカウントでの認証が必要です
    """
    global drive_service
    
    if drive_service:
        return drive_service
    
    creds_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH")
    if not creds_path:
        raise Exception("GOOGLE_DRIVE_CREDENTIALS_PATH環境変数が設定されていません")
    
    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=0)
    
    drive_service = build("drive", "v3", credentials=creds)
    return drive_service


def _initialize_index():
    """
    Google DriveフォルダからドキュメントをダウンロードしてRAGインデックスを構築します。
    
    以下の処理を実行します：
    1. 環境変数GOOGLE_DRIVE_FOLDER_IDで指定されたフォルダ内のファイルを取得
    2. 対応形式（Googleドキュメント、スプレッドシート、テキストファイル、PDF、DOCX）をダウンロード
    3. テキストをチャンクに分割（1000文字、200文字オーバーラップ）
    4. OpenAI Embeddingsでベクトル化しFAISSインデックスに保存
    5. LangChainのQAチェーンを構築（gpt-4o-mini使用）
    
    グローバル変数を更新：
        qa_chain: 質問応答用のLangChainチェーン
        vector_store: FAISSベクトルストア
        retriever_global: ドキュメント検索用レトリーバー
    
    Raises:
        Exception: 必要な環境変数が未設定の場合
        Exception: フォルダ内に有効なドキュメントが見つからない場合
    
    Note:
        - 対応ファイル形式：Googleドキュメント、Googleスプレッドシート、テキストファイル、PDF、DOCX
        - 空のファイルやエラーが発生したファイルはスキップされます
        - 処理状況は標準出力に表示されます
    """
    global qa_chain, vector_store, retriever_global
    
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        raise Exception("GOOGLE_DRIVE_FOLDER_ID環境変数が設定されていません")
    
    if not os.getenv("OPENAI_API_KEY"):
        raise Exception("OPENAI_API_KEY環境変数が設定されていません")
    
    print(f"フォルダID {folder_id} からドキュメントを読み込み中...")
    
    service = get_drive_service()
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType)"
    ).execute()
    
    files = results.get("files", [])
    documents = []
    
    for file in files:
        try:
            content = None
            
            if file["mimeType"] == "application/vnd.google-apps.document":
                content = service.files().export_media(
                    fileId=file["id"], 
                    mimeType="text/plain"
                ).execute().decode("utf-8", errors='replace')
                
            elif file["mimeType"] == "application/vnd.google-apps.spreadsheet":
                content = service.files().export_media(
                    fileId=file["id"], 
                    mimeType="text/csv"
                ).execute().decode("utf-8", errors='replace')
                
            elif file["mimeType"] == "text/plain":
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, service.files().get_media(fileId=file["id"]))
                while not downloader.next_chunk()[1]:
                    pass
                content = fh.getvalue().decode("utf-8", errors="ignore")
            
            # PDF処理
            elif file["mimeType"] == "application/pdf":
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, service.files().get_media(fileId=file["id"]))
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                fh.seek(0)
                
                pdf_reader = PdfReader(fh)
                content = "\n".join([page.extract_text() or "" for page in pdf_reader.pages])
            
            # DOCX処理
            elif file["mimeType"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, service.files().get_media(fileId=file["id"]))
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                fh.seek(0)
                
                doc = DocxDocument(fh)
                content = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
            
            if content and content.strip():
                documents.append(Document(
                    page_content=content,
                    metadata={"source": file['name'], "file_id": file['id']}
                ))
                print(f"✓ {file['name']}")
            else:
                print(f"⚠ {file['name']}: 空のコンテンツ")
        except Exception as e:
            print(f"✗ {file['name']}: {e}")
    
    if not documents:
        raise Exception(f"フォルダID '{folder_id}' に有効なドキュメントが見つかりませんでした")
    
    splits = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(documents)
    vector_store = FAISS.from_documents(splits, OpenAIEmbeddings())
    retriever_global = vector_store.as_retriever()
    
    prompt = ChatPromptTemplate.from_template(
        "以下のコンテキストを使用して質問に答えてください。\n\nコンテキスト: {context}\n\n質問: {input}\n\n回答:"
    )
    
    qa_chain = {
        "context": retriever_global | (lambda docs: "\n\n".join(doc.page_content for doc in docs)),
        "input": RunnablePassthrough(),
    } | prompt | ChatOpenAI(model_name="gpt-5-mini", temperature=0) | StrOutputParser()
    
    print(f"完了: {len(documents)}ドキュメント、{len(splits)}チャンク")


@mcp.tool()
def ask_question(question: str) -> str:
    """
    Google Driveフォルダ内のドキュメント（料金プラン、製品情報、社内ドキュメントなど）の内容について質問します。
    
    このツールは、環境変数で指定されたGoogle Driveフォルダ内のすべてのドキュメントを検索し、
    質問に関連する情報を見つけて回答を生成します。
    
    【対応ファイル形式】
    - Googleドキュメント、Googleスプレッドシート
    - テキストファイル (.txt)
    - PDFファイル (.pdf) ※PyPDF2が必要
    - Wordファイル (.docx) ※python-docxが必要
    
    【使用場面】
    - 「料金プランについて教えて」「価格表を見せて」
    - 「製品の特徴は？」「サービス内容を説明して」
    - 「ドキュメントに書かれている○○について教えて」
    - 「この資料によると〜」といった情報検索
    
    【重要】初回実行時は自動的にドキュメントのインデックス構築を行うため、
    数秒から数十秒かかります。2回目以降は高速に応答します。
    
    Args:
        question: ドキュメントの内容に関する質問（日本語推奨）
                 例: "料金プラン一覧を表示して"
                     "スタンダードプランの価格は？"
                     "サービスの利用規約を教えて"
    
    Returns:
        質問に対する回答と、情報源となったドキュメントの抜粋
        
    Examples:
        ask_question("料金プランを教えてください")
        ask_question("エンタープライズプランにはどんな機能が含まれていますか？")
        ask_question("解約方法について書かれていますか？")
    """
    global qa_chain, retriever_global
    
    try:
        if qa_chain is None:
            _initialize_index()
        
        answer = qa_chain.invoke(question)
        source_docs = retriever_global.invoke(question)[:3]
        sources = "\n\n参照元:\n" + "\n".join([f"- {doc.page_content[:100]}..." for doc in source_docs])
        
        return f"{answer}{sources}"
    except Exception as e:
        return f"エラー: {e}"


@mcp.tool()
def list_files(folder_id: Optional[str] = None, max_results: int = 20) -> str:
    """
    Google Driveのフォルダ内にあるファイルとドキュメントの一覧を表示します。
    
    【使用場面】
    - 「Google Driveのファイル一覧を見せて」
    - 「フォルダの中身を表示して」
    - 「どんなドキュメントがありますか？」
    - 「ドライブにあるファイルをリストアップして」
    
    このツールは、指定されたGoogle Driveフォルダ（または環境変数で設定されたフォルダ）内の
    ファイル名、サイズ、更新日時などを一覧表示します。
    
    Args:
        folder_id: 表示したいフォルダのID（省略時は環境変数のフォルダを使用）
        max_results: 表示する最大ファイル数（デフォルト20件）
    
    Returns:
        ファイル一覧（ファイル名、ID、サイズ、更新日時を含む）
        
    Examples:
        list_files()  # デフォルトフォルダの一覧
        list_files(max_results=10)  # 最大10件まで表示
        list_files(folder_id="abc123xyz")  # 特定フォルダの一覧
    """
    try:
        service = get_drive_service()
        folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        query = f"'{folder_id}' in parents and trashed=false" if folder_id else "'root' in parents and trashed=false"
        
        files = service.files().list(q=query, pageSize=max_results, fields="files(id, name, mimeType, modifiedTime, size)").execute().get("files", [])
        
        if not files:
            return "ファイルが見つかりませんでした"
        
        output = f"ファイル一覧 ({len(files)}件):\n\n"
        for file in files:
            size = f"{int(file.get('size', 0)) / 1024:.1f}KB" if "size" in file else "-"
            output += f"{file['name']}\n   ID: {file['id']}\n   サイズ: {size}\n   更新日: {file['modifiedTime']}\n\n"
        
        return output
    except Exception as e:
        return f"エラー: {e}"


@mcp.tool()
def upload_file(file_path: str, folder_id: Optional[str] = None, file_name: Optional[str] = None) -> str:
    """
    ローカルのファイルをGoogle Driveにアップロードします。
    
    【使用場面】
    - 「このファイルをGoogle Driveにアップロードして」
    - 「〜をドライブに保存して」
    - 「レポートをGoogle Driveに上げて」
    
    コンピュータ上のファイルを指定されたGoogle Driveフォルダにアップロードし、
    アクセス用のURLを返します。
    
    Args:
        file_path: アップロードするファイルのパス（例: "/Users/name/document.pdf"）
        folder_id: アップロード先フォルダのID（省略時は環境変数のフォルダ）
        file_name: Drive上でのファイル名（省略時は元のファイル名を使用）
    
    Returns:
        アップロード成功時: ファイル名、ID、WebリンクURL
        エラー時: エラーメッセージ
        
    Examples:
        upload_file("/path/to/report.pdf")
        upload_file("/path/to/doc.txt", folder_id="xyz789")
    """
    try:
        if not os.path.exists(file_path):
            return f"エラー: ファイルが見つかりません: {file_path}"
        
        service = get_drive_service()
        name = file_name or os.path.basename(file_path)
        folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        
        file_metadata = {"name": name}
        if folder_id:
            file_metadata["parents"] = [folder_id]
        
        file = service.files().create(
            body=file_metadata,
            media_body=MediaFileUpload(file_path, resumable=True),
            fields="id, name, webViewLink"
        ).execute()
        
        return f"成功: {file['name']}\nID: {file['id']}\nURL: {file['webViewLink']}"
    except Exception as e:
        return f"エラー: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")