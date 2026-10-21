"""지정한 웹 URL의 정적 본문을 수집하여 OpenAI Vector Store에 등록하는 RAG 지식 구축 스크립트.
교수님 [6-1. RAG-URL로 데이터 가져오기] 교안 준수.
"""
import os
import sys
import hashlib
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# Windows 콘솔 유니코드 이모지 인코딩 지원
if sys.stdout:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr:
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# -------------------------------------------------------------
# 1. 수집할 웹페이지 URL 목록 (보건/간호/교육 전문 공공 지식)
# -------------------------------------------------------------
URLS = [
    # 유네스코 AI 교사 역량 프레임워크 (교수님 공통 지침 URL)
    "https://www.unesco.org/en/articles/ai-competency-framework-teachers",
    # 비뇨계 (배뇨 생리, 신장 및 방광 질환, 빈뇨/다뇨)
    "https://ko.wikipedia.org/wiki/%EB%B9%84%EB%87%A8%EA%B3%84",
    # 간호 (기본간호 및 사정, 환자 안전)
    "https://ko.wikipedia.org/wiki/%EA%B0%84%ED%98%B8",
    # 응급처치 (학교보건 및 일상 응급상황 대처)
    "https://ko.wikipedia.org/wiki/%EC%9D%91%EA%B8%89%EC%B2%98%EC%B9%98",
]

OUT_DIR = Path("knowledge_web")


def extract_page(url: str) -> str:
    """웹페이지를 요청하고 불필요한 태그를 제거한 순수 본문 텍스트를 추출합니다."""
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise ValueError(f"올바른 HTTP(S) URL이 아닙니다: {url}")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) EducationRAGDemo/1.0"}
    response = requests.get(url, timeout=20, headers=headers)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" not in content_type:
        raise ValueError(f"HTML 페이지가 아닙니다 (Content-Type: {content_type}).")

    soup = BeautifulSoup(response.text, "html.parser")
    # 네비게이션, 푸터, 스크립트, 스타일 등 잡음 요소 제거 (교안 표준)
    for tag in soup(["script", "style", "nav", "footer", "header", "form", "noscript"]):
        tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.find("div", id="content") or soup.body or soup
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    lines = [x.strip() for x in root.get_text("\n", strip=True).splitlines()]
    body = "\n".join(x for x in lines if x)

    if len(body) < 200:
        raise ValueError("추출된 본문이 너무 짧습니다. 동적 페이지 또는 접근 제한 여부를 확인하세요.")

    return f"제목: {title}\n출처 URL: {url}\n\n{body}\n"


def load_openai_key():
    """환경변수 또는 .streamlit/secrets.toml에서 API Key를 로드합니다."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        secrets_path = Path(".streamlit/secrets.toml")
        if secrets_path.exists():
            import tomllib
            with open(secrets_path, "rb") as f:
                secrets = tomllib.load(f)
                api_key = secrets.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. .streamlit/secrets.toml을 확인하세요.")
    return api_key


def update_secrets_with_vector_store(vs_id: str):
    """secrets.toml 파일에 새로 생성된 VECTOR_STORE_URL_ID 및 기본 VECTOR_STORE_ID를 등록합니다."""
    secrets_path = Path(".streamlit/secrets.toml")
    lines = []
    if secrets_path.exists():
        lines = secrets_path.read_text(encoding="utf-8").splitlines()

    new_lines = []
    has_vs = False
    has_vs_url = False

    for line in lines:
        if line.startswith("VECTOR_STORE_URL_ID"):
            new_lines.append(f'VECTOR_STORE_URL_ID = "{vs_id}"')
            has_vs_url = True
        elif line.startswith("VECTOR_STORE_ID"):
            new_lines.append(f'VECTOR_STORE_ID = "{vs_id}"')
            has_vs = True
        else:
            new_lines.append(line)

    if not has_vs_url:
        new_lines.append(f'VECTOR_STORE_URL_ID = "{vs_id}"')
    if not has_vs:
        new_lines.append(f'VECTOR_STORE_ID = "{vs_id}"')

    secrets_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"✅ .streamlit/secrets.toml 에 VECTOR_STORE_ID = '{vs_id}' 등록 완료")


def main():
    api_key = load_openai_key()
    client = OpenAI(api_key=api_key)

    OUT_DIR.mkdir(exist_ok=True)
    paths = []

    print("===============================================================")
    print("🌐 [6-1. RAG-URL로 데이터 가져오기] 웹페이지 수집 시작")
    print("===============================================================")

    for url in URLS:
        try:
            print(f">> 수집 중: {url}")
            text = extract_page(url)
            file_name = hashlib.sha256(url.encode()).hexdigest()[:12] + ".txt"
            path = OUT_DIR / file_name
            path.write_text(text, encoding="utf-8")
            paths.append(path)
            print(f"   ✓ 수집 완료: {path.name} ({len(text):,}자)")
        except Exception as exc:
            print(f"   ✗ 수집 실패: {url} - {exc}")

    if not paths:
        raise RuntimeError("수집된 웹페이지가 없습니다. URL과 네트워크 상태를 확인하세요.")

    print(f"\n총 {len(paths)}개 웹페이지 텍스트 추출 완료. OpenAI Vector Store 등록 시작...")

    store = client.vector_stores.create(name="Health Coach Inquiry Web Knowledge (6-1 URL RAG)")
    print(f"생성된 Vector Store ID: {store.id}")

    streams = [p.open("rb") for p in paths]
    try:
        batch = client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=store.id,
            files=streams
        )
    finally:
        for s in streams:
            s.close()

    print(f"인덱싱 상태: {batch.status}")
    print(f"처리 파일 현황: {batch.file_counts}")

    if batch.status != "completed":
        raise RuntimeError(f"인덱싱이 완료되지 않았습니다. 상태: {batch.status}")

    update_secrets_with_vector_store(store.id)
    print("\n🎉 URL RAG Knowledge 구축 성공!")


if __name__ == "__main__":
    main()
