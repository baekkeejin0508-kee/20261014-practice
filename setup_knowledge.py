import os
from pathlib import Path
from openai import OpenAI

# ---------------------------------------------------------
# setup_knowledge.py
#
# 역할
# 1. knowledge/ 폴더의 PDF 파일을 찾는다.
# 2. OpenAI Vector Store를 한 번 생성한다.
# 3. PDF를 업로드하고 인덱싱이 끝날 때까지 기다린다.
# 4. 생성된 VECTOR_STORE_ID를 출력하고 .streamlit/secrets.toml에 자동 반영한다.
#
# 주의
# 이 파일은 Streamlit 앱을 실행할 때마다 실행하는 파일이 아니다.
# Knowledge Base를 처음 만들거나 다시 만들 때만 실행한다.
# ---------------------------------------------------------

KNOWLEDGE_DIR = Path("knowledge")
VECTOR_STORE_NAME = "Science Inquiry Knowledge"
SECRETS_FILE = Path(".streamlit/secrets.toml")


def load_api_key_from_secrets():
    """환경변수에 키가 없을 경우 .streamlit/secrets.toml 에서 읽어옵니다."""
    if os.getenv("OPENAI_API_KEY"):
        return os.getenv("OPENAI_API_KEY")

    if SECRETS_FILE.exists():
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY") and "=" in line:
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key and not key.startswith("sk-여기에"):
                        os.environ["OPENAI_API_KEY"] = key
                        return key
    return None


def save_vector_store_id_to_secrets(vs_id: str):
    """생성된 Vector Store ID를 .streamlit/secrets.toml 에 자동 기록합니다."""
    try:
        SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        updated = False
        if SECRETS_FILE.exists():
            with open(SECRETS_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for i, line in enumerate(lines):
                if line.strip().startswith("VECTOR_STORE_ID"):
                    lines[i] = f'VECTOR_STORE_ID = "{vs_id}"\n'
                    updated = True
                    break

        if not updated:
            lines.append(f'\nVECTOR_STORE_ID = "{vs_id}"\n')

        with open(SECRETS_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"\n[성공] .streamlit/secrets.toml 에 VECTOR_STORE_ID 가 자동 저장되었습니다.")
    except Exception as e:
        print(f"\n[참고] secrets.toml 저장 중 알림: {e}")


def main():
    api_key = load_api_key_from_secrets()
    if not api_key:
        print("⚠️ OPENAI_API_KEY 가 설정되어 있지 않습니다.")
        print("방법 1) .streamlit/secrets.toml 파일에 OPENAI_API_KEY = \"sk-...\" 입력")
        print("방법 2) 터미널에서 환경변수 설정: export OPENAI_API_KEY=\"sk-...\"")
        return

    client = OpenAI(api_key=api_key)

    # -----------------------------------------------------
    # Step 1. Knowledge PDF 확인
    # -----------------------------------------------------
    pdf_paths = sorted(KNOWLEDGE_DIR.glob("*.pdf"))

    if not pdf_paths:
        raise FileNotFoundError(
            "knowledge/ 폴더에서 PDF 파일을 찾지 못했습니다.\n"
            "예: knowledge/curriculum.pdf, knowledge/inquiry_design_guide.pdf"
        )

    print("=== 업로드할 Knowledge 파일 목록 ===")
    for path in pdf_paths:
        print(f" - {path} ({path.stat().st_size:,} bytes)")

    # -----------------------------------------------------
    # Step 2. Vector Store 생성
    # -----------------------------------------------------
    print(f"\nOpenAI Vector Store '{VECTOR_STORE_NAME}' 생성 중...")
    vector_store = client.vector_stores.create(
        name=VECTOR_STORE_NAME
    )

    print(f"Vector Store 생성 완료: {vector_store.id}")

    # -----------------------------------------------------
    # Step 3. PDF 업로드 + 인덱싱 완료까지 대기
    # -----------------------------------------------------
    print("PDF 파일 업로드 및 인덱싱(Chunking + Embedding) 진행 중...")
    streams = [open(path, "rb") for path in pdf_paths]

    try:
        batch = client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=streams,
        )
    finally:
        for stream in streams:
            stream.close()

    # -----------------------------------------------------
    # Step 4. 결과 확인 및 저장
    # -----------------------------------------------------
    print("\n=== Knowledge 인덱싱 결과 ===")
    print(f"상태(status): {batch.status}")

    if hasattr(batch, "file_counts"):
        print(f"처리 파일 수(file_counts): {batch.file_counts}")

    print("\n--------------------------------------------")
    print(f"VECTOR_STORE_ID: {vector_store.id}")
    print("--------------------------------------------")

    save_vector_store_id_to_secrets(vector_store.id)

    print(
        "\n이제 Streamlit 앱을 실행할 수 있습니다:\n"
        "streamlit run app.py"
    )


if __name__ == "__main__":
    main()
