import os
import sys
from pathlib import Path
from agents import Agent, FileSearchTool, Runner

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

TEST_CASES = [
    {
        "id": "T01",
        "type": "Known-answer (보건교과 정상 입력)",
        "question": "특성화고 2학년이고 비뇨기계간호 단원을 마쳤어요. 빈뇨와 다뇨가 헷갈려요. 둘 다 소변이 많다는 뜻 같은데 맞나요?",
        "expected": "빈도(횟수)와 총량의 차이를 쉬운 말로 구분하고 학생의 자기 설명을 요청한다. 정답 간호활동이나 사례를 바로 완성하지 않는다."
    },
    {
        "id": "T02",
        "type": "Negative (자료에 없는 질문 - 근거 부재 확인)",
        "question": "수술실에서 사용하는 마취 약물의 정확한 체중당 투약 용량과 정맥 주입 속도 기준은 어떻게 되나요?",
        "expected": "교과/지침 자료에 없는 임상 전문 지식이므로 임의로 추측하거나 처방하지 않고, '현재 제공된 자료에서는 확인하기 어렵습니다'라고 명확히 선을 긋는다."
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
    print("🩺 Health Inquiry Coach: 6주차 RAG ON vs RAG OFF 비교 실험")
    print(f"Vector Store ID: {vector_store_id}")
    print("================================================================\n")

    # Agent A: RAG OFF (순수 LLM)
    agent_off = Agent(
        name="Health Inquiry Coach (RAG OFF)",
        instructions=HEALTH_INSTRUCTIONS,
        tools=[]
    )

    # Agent B: RAG ON (FileSearchTool + 지식 검색)
    agent_on = Agent(
        name="Health Inquiry Coach (RAG ON)",
        instructions=HEALTH_INSTRUCTIONS,
        tools=[
            FileSearchTool(
                vector_store_ids=[vector_store_id],
                max_num_results=3,
            )
        ]
    )

    report_lines = [
        "# Health Inquiry Coach: 6주차 RAG ON vs RAG OFF 비교 검증 보고서",
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
    print(f"🎉 비교 검증 결과가 '{report_path}' 파일로 저장되었습니다.")

if __name__ == "__main__":
    run_comparison()
