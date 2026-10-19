import os
import sys
from pathlib import Path
from openai import OpenAI

# UTF-8 출력 설정
sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------
# setup_knowledge.py
#
# 역할
# 1. knowledge/ 폴더 내 모든 PDF 교과서 및 지침 파일을 찾는다.
# 2. OpenAI Vector Store('Health Inquiry Knowledge')를 생성한다.
# 3. PDF 파일들을 업로드하고 인덱싱(청킹 + 임베딩) 완료까지 대기한다.
# 4. 생성된 VECTOR_STORE_ID를 .streamlit/secrets.toml 에 자동 저장한다.
# ---------------------------------------------------------

KNOWLEDGE_DIR = Path("knowledge")
VECTOR_STORE_NAME = "Health Inquiry Knowledge"
SECRETS_FILE = Path(".streamlit/secrets.toml")


def load_api_key_from_secrets():
    """환경변수 또는 .streamlit/secrets.toml 에서 API 키를 읽어옵니다."""
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
        print(f"\n[알림] secrets.toml 저장 중 메시지: {e}")


def main():
    api_key = load_api_key_from_secrets()
    if not api_key:
        print("⚠️ OPENAI_API_KEY 가 설정되어 있지 않습니다.")
        print("방법 1) .streamlit/secrets.toml 파일에 OPENAI_API_KEY = \"sk-...\" 입력")
        print("방법 2) 터미널에서 환경변수 설정: export OPENAI_API_KEY=\"sk-...\"")
        return

    client = OpenAI(api_key=api_key)

    # -----------------------------------------------------
    # Step 1. Knowledge 폴더의 모든 PDF 파일 탐색 (대소문자 구분 없음)
    # -----------------------------------------------------
    if not KNOWLEDGE_DIR.exists():
        raise FileNotFoundError("knowledge/ 폴더가 존재하지 않습니다.")

    pdf_paths = sorted([
        p for p in KNOWLEDGE_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    ])

    if not pdf_paths:
        raise FileNotFoundError(
            "knowledge/ 폴더에서 PDF 파일을 찾지 못했습니다.\n"
            "교과서 및 지침 PDF 파일을 knowledge/ 폴더에 넣어주세요."
        )

    total_size_mb = sum(p.stat().st_size for p in pdf_paths) / (1024 * 1024)
    print("==========================================================")
    print(f"📚 업로드할 보건교과 Knowledge PDF 목록 (총 {len(pdf_paths)}개 / {total_size_mb:.1f} MB)")
    print("==========================================================")
    for i, path in enumerate(pdf_paths, 1):
        mb = path.stat().st_size / (1024 * 1024)
        print(f"{i:2d}. {path.name} ({mb:.1f} MB)")
    print("==========================================================\n")

    # -----------------------------------------------------
    # Step 2. Vector Store 생성
    # -----------------------------------------------------
    print(f"1) OpenAI Vector Store '{VECTOR_STORE_NAME}' 생성 중...")
    vector_store = client.vector_stores.create(
        name=VECTOR_STORE_NAME
    )
    print(f"   ✓ Vector Store 생성 완료: {vector_store.id}\n")

    # -----------------------------------------------------
    # Step 3. PDF 업로드 + 인덱싱 완료까지 대기 (Batch Upload)
    # -----------------------------------------------------
    print("2) PDF 파일 업로드 및 인덱싱(청킹 + 임베딩) 시작...")
    print("   (용량에 따라 수 분 정도 소요될 수 있으니 완료될 때까지 기다려 주세요)")

    streams = []
    try:
        streams = [open(path, "rb") for path in pdf_paths]
        batch = client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=streams,
        )
    finally:
        for s in streams:
            try:
                s.close()
            except Exception:
                pass

    # -----------------------------------------------------
    # Step 4. 결과 확인 및 secrets.toml 자동 저장
    # -----------------------------------------------------
    print("\n3) Knowledge 인덱싱 결과 확인")
    print(f"   • 최종 상태(status): {batch.status}")
    if hasattr(batch, "file_counts"):
        print(f"   • 처리 파일 현황(file_counts): {batch.file_counts}")

    print("\n----------------------------------------------------------")
    print(f"발급된 VECTOR_STORE_ID: {vector_store.id}")
    print("----------------------------------------------------------")

    save_vector_store_id_to_secrets(vector_store.id)

    print(
        "\n✅ 이제 보건교과 RAG 준비가 완료되었습니다!\n"
        "Streamlit 앱 실행:\n"
        "streamlit run app.py\n"
    )


if __name__ == "__main__":
    main()
