import os
import sys
from pathlib import Path
from agents import Agent, FileSearchTool, Runner, SQLiteSession

# UTF-8 출력 설정
sys.stdout.reconfigure(encoding="utf-8")

SECRETS_FILE = Path(".streamlit/secrets.toml")

def load_secrets():
    api_key = os.getenv("OPENAI_API_KEY")
    vector_store_id = os.getenv("VECTOR_STORE_ID")
    
    if SECRETS_FILE.exists():
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY") and "=" in line and not api_key:
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if k and not k.startswith("sk-여기에"):
                        api_key = k
                        os.environ["OPENAI_API_KEY"] = k
                elif line.startswith("VECTOR_STORE_ID") and "=" in line and not vector_store_id:
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v and not v.startswith("setup_knowledge"):
                        vector_store_id = v
                        os.environ["VECTOR_STORE_ID"] = v
    return api_key, vector_store_id

SCIENCE_INSTRUCTIONS = """
[ROLE] 너는 중학생의 과학 자유탐구 질문 형성을 지원하는 Science Inquiry Coach이다.
[GOAL] 학생이 자신의 관심사를 과학 개념과 연결하고, 탐구 가능한 질문을 스스로 발전시키도록 지원한다.
[KNOWLEDGE USE]
1. 과학 탐구 질문의 기준, 교육과정 연계 내용, 탐구 방법을 설명할 때는 연결된 Knowledge를 우선 검색한다.
2. Knowledge에서 확인한 내용을 바탕으로 답한다.
3. 자료에서 확인되지 않는 내용은 자료에 있는 것처럼 말하지 않는다.
4. Knowledge에 충분한 근거가 없으면 "현재 제공된 자료에서는 확인하기 어렵습니다."라고 알린다.
5. 학생의 상황에 따라 추가 정보가 필요하면 먼저 질문한다.
[RULES]
1. 학생의 생각을 먼저 확인한다.
2. 완성된 탐구 질문을 처음부터 바로 제공하지 않는다.
3. 정보가 부족하면 학년, 관심 분야, 초기 아이디어 등을 추가로 질문한다.
4. 질문을 개선할 때는 개선 이유를 함께 설명한다.
5. 위험한 실험을 권하지 않는다.
"""

HEALTH_INSTRUCTIONS = """
[ROLE] 너는 특성화고 2학년의 보건교과 개념 이해와 탐구·모의실습 설계를 돕는 학습 코치인 Health Inquiry Coach이다.
[GOAL] 학생이 개념을 자기 말로 설명하고, 탐구질문과 사례를 선택한 뒤 간호활동 및 근거를 스스로 수정하도록 돕는다.
[KNOWLEDGE USE]
1. 보건·간호 탐구 질문의 기준, 교육과정 연계 내용, 모의실습 기준을 설명할 때는 연결된 Knowledge를 우선 검색한다.
2. Knowledge에서 확인한 내용을 바탕으로 답한다.
3. 자료에서 확인되지 않는 내용은 자료에 있는 것처럼 말하지 않는다.
4. Knowledge에 충분한 근거가 없으면 "현재 제공된 자료에서는 확인하기 어렵습니다."라고 알린다.
[RULES]
1. 쉬운 용어를 사용하고 학생의 생각을 먼저 확인한다.
2. 완성 답안을 대신 쓰거나 교사의 승인·점수를 만들지 않는다.
3. 실제 건강 문제는 학습 상황과 구분하고 전문 의료진 평가 및 교사 검토를 요청한다.
"""

TEST_CASES = [
    {
        "id": "T01",
        "type": "Known-answer (문서에 답이 있는 정상 질문)",
        "question": "좋은 과학탐구 질문의 핵심 기준은 무엇인가요?",
        "expected": "가이드 문서에 명시된 기준(명확성, 탐구 가능성, 변인 구체성, 범위 적절성, 과학적 관련성, 안전성)을 근거로 제시"
    },
    {
        "id": "T02",
        "type": "Negative (문서에 답이 없는 질문 - 부재 인정 검증)",
        "question": "우주정거장에서 인슐린을 냉장 보관하는 국제우주기구의 세부 안전 기준은 어떻게 되나요?",
        "expected": "자료에 없는 내용이므로 추측하여 지어내지 않고 '현재 제공된 자료에서는 확인하기 어렵습니다'라고 명확히 밝힘"
    }
]

def run_comparison():
    api_key, vector_store_id = load_secrets()
    if not api_key:
        print("⚠️ OPENAI_API_KEY 가 필요합니다. .streamlit/secrets.toml 에 입력해 주세요.")
        return
    if not vector_store_id:
        print("⚠️ VECTOR_STORE_ID 가 필요합니다. 먼저 `python setup_knowledge.py` 를 실행하세요.")
        return

    print("================================================================")
    print("🔬 6주차 RAG 비교 실험: RAG ON vs RAG OFF 검증 테스트")
    print(f"Vector Store ID: {vector_store_id}")
    print("================================================================\n")

    # Agent A: RAG OFF (FileSearchTool 없음)
    agent_off = Agent(
        name="Inquiry Coach (RAG OFF)",
        instructions=SCIENCE_INSTRUCTIONS,
        tools=[]
    )

    # Agent B: RAG ON (FileSearchTool + Vector Store)
    agent_on = Agent(
        name="Inquiry Coach (RAG ON)",
        instructions=SCIENCE_INSTRUCTIONS,
        tools=[
            FileSearchTool(
                vector_store_ids=[vector_store_id],
                max_num_results=3,
            )
        ]
    )

    report_lines = [
        "# 6주차 RAG 비교 실험 결과 보고서 (RAG ON vs RAG OFF)",
        f"- Vector Store ID: `{vector_store_id}`\n"
    ]

    for tc in TEST_CASES:
        t_id = tc["id"]
        t_type = tc["type"]
        q = tc["question"]
        exp = tc["expected"]

        print(f"----------------------------------------------------------------")
        print(f"▶ [{t_id}] {t_type}")
        print(f"질문: {q}")
        print(f"기대 행동: {exp}\n")

        # 1. RAG OFF 실행
        print(">> [Agent A: RAG OFF] 실행 중...")
        res_off = Runner.run_sync(agent_off, q)
        ans_off = res_off.final_output.strip()

        # 2. RAG ON 실행
        print(">> [Agent B: RAG ON] 실행 중...")
        res_on = Runner.run_sync(agent_on, q)
        ans_on = res_on.final_output.strip()

        print("\n--- [Agent A: RAG OFF 답변] ---")
        print(ans_off)
        print("\n--- [Agent B: RAG ON 답변] ---")
        print(ans_on)
        print("----------------------------------------------------------------\n")

        report_lines.append(f"## [{t_id}] {t_type}")
        report_lines.append(f"**질문**: {q}\n")
        report_lines.append(f"**기대 행동**: {exp}\n")
        report_lines.append(f"### ⚪ Agent A (RAG OFF 응답)")
        report_lines.append(f"```markdown\n{ans_off}\n```\n")
        report_lines.append(f"### 🟢 Agent B (RAG ON 응답)")
        report_lines.append(f"```markdown\n{ans_on}\n```\n")
        report_lines.append("---\n")

    report_path = Path("RAG_ON_OFF_비교검증보고서.md")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"🎉 비교 결과가 '{report_path}' 파일로 저장되었습니다.")

if __name__ == "__main__":
    run_comparison()
