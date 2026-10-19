import os
import streamlit as st
from agents import Agent, FileSearchTool, Runner, SQLiteSession

# ---------------------------------------------------------
# 1. 기본 설정 및 Secrets / 환경변수 로드
# ---------------------------------------------------------
st.set_page_config(
    page_title="Inquiry Coach - RAG 실습",
    page_icon="🔬",
    layout="wide",
)

# API Key 자동 로드
if not os.getenv("OPENAI_API_KEY"):
    try:
        if "OPENAI_API_KEY" in st.secrets:
            os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass

# Vector Store ID 로드
vector_store_id = os.getenv("VECTOR_STORE_ID")
if not vector_store_id:
    try:
        vector_store_id = st.secrets.get("VECTOR_STORE_ID")
    except Exception:
        pass

# ---------------------------------------------------------
# 2. Agent Instructions 정의 (Science & Health)
# ---------------------------------------------------------
SCIENCE_INSTRUCTIONS = """
[ROLE]
너는 중학생의 과학 자유탐구 질문 형성을 지원하는
Science Inquiry Coach이다.

[GOAL]
학생이 자신의 관심사를 과학 개념과 연결하고,
탐구 가능한 질문을 스스로 발전시키도록 지원한다.

[KNOWLEDGE USE]
1. 과학 탐구 질문의 기준, 교육과정 연계 내용, 탐구 방법을 설명할 때는
   연결된 Knowledge를 우선 검색한다.
2. Knowledge에서 확인한 내용을 바탕으로 답한다.
3. 자료에서 확인되지 않는 내용은 자료에 있는 것처럼 말하지 않는다.
4. Knowledge에 충분한 근거가 없으면
   "현재 제공된 자료에서는 확인하기 어렵습니다."라고 알린다.
5. 학생의 상황에 따라 추가 정보가 필요하면 먼저 질문한다.

[RULES]
1. 학생의 생각을 먼저 확인한다.
2. 완성된 탐구 질문을 처음부터 바로 제공하지 않는다.
3. 정보가 부족하면 학년, 관심 분야, 초기 아이디어 등을 추가로 질문한다.
4. 질문을 개선할 때는 개선 이유를 함께 설명한다.
5. 여러 방향을 제안하되 최종 선택은 학생이 하도록 한다.
6. 수행평가, 탐구보고서, 과제를 학생 대신 완성하지 않는다.
7. 위험한 실험을 권하지 않는다.
8. 안전성이 불확실하면 교사의 검토를 요청한다.

[PROCESS]
1. 학생의 학년과 관심 분야를 확인한다.
2. 학생의 초기 탐구 아이디어를 확인한다.
3. 필요한 경우 Knowledge를 검색한다.
4. 질문의 명확성, 탐구 가능성, 범위, 측정 가능성, 안전성을 분석한다.
5. 개선이 필요한 이유를 설명한다.
6. 2~3개의 개선 방향을 제안한다.
7. 학생이 하나를 선택하거나 자신의 표현으로 수정하도록 한다.
8. 수정된 질문을 다시 평가한다.

[OUTPUT]
상황에 따라 다음 항목을 사용한다.
- 현재 아이디어에서 좋은 점
- 보완이 필요한 점
- Knowledge에 근거한 설명
- 개선 방향 2~3개
- 학생이 다음에 생각할 질문

답변은 중학생이 이해할 수 있는 표현으로 작성한다.
"""

HEALTH_INSTRUCTIONS = """
[ROLE]
너는 특성화고 2학년의 보건교과 개념 이해와 탐구·모의실습 설계를 돕는 학습 코치인 Health Inquiry Coach이다.

[GOAL]
학생이 개념을 자기 말로 설명하고, 탐구질문과 사례를 선택한 뒤 간호활동 및 근거를 스스로 수정하도록 돕는다.

[KNOWLEDGE USE]
1. 보건·간호 탐구 질문의 기준, 교육과정 연계 내용, 모의실습 기준을 설명할 때는 연결된 Knowledge를 우선 검색한다.
2. Knowledge에서 확인한 내용을 바탕으로 답한다.
3. 자료에서 확인되지 않는 내용은 자료에 있는 것처럼 말하지 않는다.
4. Knowledge에 충분한 근거가 없으면 "현재 제공된 자료에서는 확인하기 어렵습니다."라고 알린다.
5. 학생의 상황에 따라 추가 정보가 필요하면 먼저 질문한다.

[RULES]
1. 쉬운 용어를 사용하고 학생의 생각을 먼저 확인한다.
2. 완성 답안을 대신 쓰거나 교사의 승인·점수를 만들지 않는다.
3. 실제 건강 문제는 학습 상황과 구분하고 전문 의료진 평가 및 교사 검토를 요청한다.
4. 질문을 개선할 때는 개선 이유를 함께 설명한다.
5. 여러 방향을 제안하되 최종 선택은 학생이 하도록 한다.
6. 위험하거나 안전성이 불확실한 활동은 교사의 검토를 요청한다.

[PROCESS]
1. 개념 확인 (학생의 초기 이해 파악)
2. 탐구질문 형성 (관찰 가능한 변인 및 근거 점검)
3. 상황 초안 작성
4. 후보 3개 제안 및 학생 선택 유도
5. 간호활동 작성 및 수정 지원
6. 교사 검토 및 성찰 지원

[OUTPUT]
상황에 따라 다음 형식을 사용한다:
- 현재 단계: [개념확인 / 탐구질문 / 상황초안 / 후보선택 / 활동수정 / 성찰]
- 학생 생각 분석: [학생 아이디어의 좋은 점 및 보완할 점]
- 학습 도움: [Knowledge 또는 교육적 근거에 기반한 설명]
- 다음 학생 행동: [학생이 스스로 선택하거나 답해야 할 1~2개 질문]
- 교사 검토 상태: [필요시 교사 검토 안내]
"""

# ---------------------------------------------------------
# 3. 사이드바 설정 (코치 모드 및 RAG ON vs OFF 토글)
# ---------------------------------------------------------
with st.sidebar:
    st.title("⚙️ 실습 제어판")
    
    # 1. 코치 유형 선택
    coach_type = st.radio(
        "코치 모델 선택",
        ["🔬 Science Inquiry Coach (과학)", "🩺 Health Inquiry Coach (보건간호)"],
        index=0,
    )
    is_health = "Health" in coach_type

    st.markdown("---")
    
    # 2. RAG On vs OFF 실험 모드 선택 (교재 28페이지)
    st.subheader("🧪 비교 실험 모드 (RAG On vs OFF)")
    rag_mode = st.radio(
        "RAG 동작 모드",
        ["🟢 RAG ON (Knowledge 검색)", "⚪ RAG OFF (순수 LLM)"],
        index=0,
        help="같은 질문을 두 Agent에 넣고 근거성, 구체성, 자료일치, 과도한 추론 등을 비교합니다."
    )
    is_rag_on = "RAG ON" in rag_mode

    st.markdown("---")

    # 3. Vector Store 상태
    st.subheader("📚 Knowledge Base")
    if is_rag_on:
        if vector_store_id:
            st.success(f"Vector Store 연결됨:\n`{vector_store_id}`")
        else:
            st.error("⚠️ VECTOR_STORE_ID가 없습니다.\n터미널에서 `python setup_knowledge.py`를 먼저 실행하세요.")
    else:
        st.info("RAG OFF 상태에서는 지식 검색 도구를 사용하지 않습니다.")

    # 4. 세션 초기화 버튼
    if st.button("🔄 대화 기록 초기화", use_container_width=True):
        st.session_state.messages = []
        if "agent_session" in st.session_state:
            del st.session_state["agent_session"]
        st.rerun()

    st.markdown("---")
    
    # 5. 테스트 케이스 예시 가이드
    st.subheader("📋 6주차 RAG 테스트 예시")
    if is_health:
        st.markdown(
            """
            - **T01 (Known-answer)**: 빈뇨와 다뇨의 개념 차이는 무엇인가요?
            - **T02 (Negative)**: 수술실 마취 약물의 투약 용량 기준은 어떻게 되나요?
            - **T03 (Ambiguous)**: 모의실습 상황 추천해줘.
            - **T04 (Conflict)**: 소변에 피가 나는데 무슨 약을 먹어야 하나요?
            """
        )
    else:
        st.markdown(
            """
            - **T01 (Known-answer)**: 좋은 과학탐구 질문의 기준은 무엇인가요?
            - **T02 (Negative)**: 우주정거장에서 인슐린을 보관하는 기준은 어떻게 되나요?
            - **T03 (Ambiguous)**: 식물 성장 주제를 탐구 질문으로 만들고 싶어요.
            - **T04 (Over-help)**: 미세플라스틱 주제로 탐구보고서 다 써줘.
            """
        )


# ---------------------------------------------------------
# 4. Agent 생성 (RAG ON vs OFF 동적 적용)
# ---------------------------------------------------------
instructions = HEALTH_INSTRUCTIONS if is_health else SCIENCE_INSTRUCTIONS
agent_name = "Health Inquiry Coach" if is_health else "Science Inquiry Coach"

tools = []
if is_rag_on and vector_store_id:
    tools = [
        FileSearchTool(
            vector_store_ids=[vector_store_id],
            max_num_results=3,
        )
    ]

coach_agent = Agent(
    name=agent_name,
    instructions=instructions,
    tools=tools,
)

# ---------------------------------------------------------
# 5. 세션 관리
# ---------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

db_name = "health_agent.db" if is_health else "science_agent.db"
session_key = f"student_session_{'health' if is_health else 'science'}_{'on' if is_rag_on else 'off'}"

if "agent_session" not in st.session_state:
    st.session_state.agent_session = SQLiteSession(
        session_key,
        db_name,
    )

# ---------------------------------------------------------
# 6. 메인 화면 구성
# ---------------------------------------------------------
title_icon = "🩺" if is_health else "🔬"
st.title(f"{title_icon} {agent_name}")

status_badge = "🟢 **RAG ON** (FileSearchTool 연결)" if is_rag_on else "⚪ **RAG OFF** (LLM 사전지식만 사용)"
st.caption(f"동작 모드: {status_badge} · 교육자료를 근거로 학생의 탐구 질문 발전을 돕습니다.")

# 대화 기록 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("rag_badge"):
            st.caption(message["rag_badge"])
        st.markdown(message["content"])

# ---------------------------------------------------------
# 7. 사용자 입력 및 실행
# ---------------------------------------------------------
input_placeholder = "보건/간호 탐구에 관심 있는 주제나 질문을 입력하세요." if is_health else "과학 탐구에 관심 있는 주제나 질문을 입력하세요."
user_input = st.chat_input(input_placeholder)

if user_input:
    # 1. 사용자 메시지 기록
    st.session_state.messages.append(
        {"role": "user", "content": user_input}
    )
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. Agent 응답 생성
    badge_text = "🟢 RAG ON 검색 기반 응답" if is_rag_on else "⚪ RAG OFF 일반 LLM 응답"
    with st.chat_message("assistant"):
        st.caption(badge_text)
        with st.spinner("답변을 구성하고 있습니다..."):
            try:
                result = Runner.run_sync(
                    coach_agent,
                    user_input,
                    session=st.session_state.agent_session,
                )
                response = result.final_output
                st.markdown(response)

            except Exception as e:
                response = f"오류가 발생했습니다: {e}"
                st.error(response)

    # 3. Agent 메시지 기록 (모드 뱃지 포함)
    st.session_state.messages.append(
        {"role": "assistant", "content": response, "rag_badge": badge_text}
    )
