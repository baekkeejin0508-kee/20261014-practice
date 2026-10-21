import os
import sys
import re
import subprocess
import shutil
from pathlib import Path

# UTF-8 출력 설정
sys.stdout.reconfigure(encoding="utf-8")

MD_FILE = Path("RAG_ON_OFF_비교검증보고서.md")
HTML_FILE = Path("RAG_ON_OFF_비교검증보고서.html")
PDF_FILE = Path("RAG_ON_OFF_비교검증보고서.pdf")
DOWNLOADS_DIR = Path("C:/Users/user/Downloads")

def markdown_to_styled_html(md_text: str) -> str:
    # 텍스트 내 볼드, 코드, 줄바꿈 등을 안전하게 변환
    def inline_fmt(text: str) -> str:
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        return text

    lines = md_text.splitlines()
    html_parts = []
    
    in_code_block = False
    code_block_lines = []
    code_block_type = ""
    
    in_table = False
    table_lines = []

    def flush_table():
        nonlocal in_table, table_lines
        if not in_table or not table_lines:
            return ""
        t_html = ['<div class="table-container"><table>']
        # 헤더
        header_cells = [c.strip() for c in table_lines[0].split('|')[1:-1]]
        t_html.append('<thead><tr>')
        for h in header_cells:
            t_html.append(f'<th>{inline_fmt(h)}</th>')
        t_html.append('</tr></thead><tbody>')
        # 바디 (인덱스 2부터)
        for r in table_lines[2:]:
            cells = [c.strip() for c in r.split('|')[1:-1]]
            t_html.append('<tr>')
            for c in cells:
                t_html.append(f'<td>{inline_fmt(c)}</td>')
            t_html.append('</tr>')
        t_html.append('</tbody></table></div>')
        in_table = False
        table_lines = []
        return "".join(t_html)

    i = 0
    while i < len(lines):
        line = lines[i]

        # 코드 블록 처리
        if line.startswith("```"):
            if in_code_block:
                in_code_block = False
                code_content = "\n".join(code_block_lines)
                badge_class = "rag-on-box" if "🟢" in code_block_type or "RAG ON" in code_block_type else "rag-off-box"
                html_parts.append(f'<div class="response-card {badge_class}"><pre><code>{code_content}</code></pre></div>')
                code_block_lines = []
            else:
                if in_table:
                    html_parts.append(flush_table())
                in_code_block = True
                code_block_lines = []
                code_block_type = lines[i-1] if i > 0 else ""
            i += 1
            continue

        if in_code_block:
            code_block_lines.append(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            i += 1
            continue

        # 테이블 처리
        if line.startswith("|") and line.endswith("|"):
            in_table = True
            table_lines.append(line)
            i += 1
            continue
        elif in_table:
            html_parts.append(flush_table())

        # 빈 줄
        if not line.strip():
            i += 1
            continue

        # 구분선
        if line.strip() == "---":
            html_parts.append('<hr class="section-divider"/>')
            i += 1
            continue

        # 메인 타이틀 (# )
        if line.startswith("# "):
            title_text = line[2:].strip()
            html_parts.append(f'<header class="report-header"><div class="badge-tag">특성화고 보건간호 RAG 지식 에이전트</div><h1 class="main-title">{title_text}</h1></header>')
            i += 1
            continue

        # 대제목 (## )
        if line.startswith("## "):
            h2_text = line[3:].strip()
            html_parts.append(f'<h2 class="section-h2">{h2_text}</h2>')
            i += 1
            continue

        # 중제목 (### [Tx] ...)
        if line.startswith("### "):
            h3_text = line[4:].strip()
            html_parts.append(f'<div class="test-case-wrapper"><h3 class="test-h3"><span class="test-pill">시나리오</span> {h3_text}</h3>')
            # 다음 구분선이나 h3이 나올 때까지 닫는 태그는 나중에 처리하거나 플래그
            i += 1
            continue

        # 소제목 (#### ⚪ / #### 🟢 / #### 🔍)
        if line.startswith("#### "):
            h4_text = line[5:].strip()
            if "Agent A" in h4_text or "RAG OFF" in h4_text:
                html_parts.append(f'<div class="agent-title agent-off-title"><span class="agent-icon">⚪</span> {inline_fmt(h4_text)}</div>')
            elif "Agent B" in h4_text or "RAG ON" in h4_text:
                html_parts.append(f'<div class="agent-title agent-on-title"><span class="agent-icon">🟢</span> {inline_fmt(h4_text)}</div>')
            else:
                html_parts.append(f'<h4 class="analysis-h4">{inline_fmt(h4_text)}</h4>')
            i += 1
            continue

        # 질문 및 기대 행동 리스트
        if line.startswith("- **질문**:"):
            q_text = line.replace("- **질문**:", "").strip()
            html_parts.append(f'<div class="question-box"><strong>질문:</strong> {inline_fmt(q_text)}</div>')
            i += 1
            continue

        if line.startswith("- **검증 목표 및 기대 행동**:") or line.startswith("- **기대 행동**:"):
            exp_text = re.sub(r'^- \*\*(검증 목표 및 )?기대 행동\*\*:', '', line).strip()
            html_parts.append(f'<div class="expected-box"><strong>기대 행동:</strong> {inline_fmt(exp_text)}</div>')
            i += 1
            continue

        # 일반 리스트 항목
        if line.startswith("- "):
            item_text = line[2:].strip()
            html_parts.append(f'<div class="bullet-item"><span class="bullet-dot">•</span> {inline_fmt(item_text)}</div>')
            i += 1
            continue

        # 번호 리스트 (1. 2. 3.)
        m_num = re.match(r'^(\d+)\.\s+(.*)', line)
        if m_num:
            num = m_num.group(1)
            item_text = m_num.group(2)
            html_parts.append(f'<div class="num-item"><span class="num-badge">{num}</span> {inline_fmt(item_text)}</div>')
            i += 1
            continue

        # 일반 문단
        html_parts.append(f'<p class="general-p">{inline_fmt(line)}</p>')
        i += 1

    if in_table:
        html_parts.append(flush_table())

    body_html = "\n".join(html_parts)

    full_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Health Inquiry Coach - RAG ON vs RAG OFF 종합 비교 검증 보고서</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;500;600;700;800&display=swap');

  @page {{
    size: A4;
    margin: 14mm 14mm 14mm 14mm;
    @bottom-right {{
      content: counter(page) " / " counter(pages);
      font-size: 9pt;
      color: #94a3b8;
    }}
  }}

  * {{
    box-sizing: border-box;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }}

  body {{
    font-family: 'Pretendard', 'Malgun Gothic', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #1e293b;
    background-color: #ffffff;
    line-height: 1.6;
    font-size: 10pt;
    margin: 0;
    padding: 0;
  }}

  .report-header {{
    text-align: center;
    border-bottom: 2.5px solid #0284c7;
    padding-bottom: 16px;
    margin-bottom: 22px;
  }}

  .badge-tag {{
    display: inline-block;
    background: #e0f2fe;
    color: #0369a1;
    font-size: 8.5pt;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 9999px;
    margin-bottom: 8px;
    letter-spacing: 0.5px;
    border: 1px solid #bae6fd;
  }}

  .main-title {{
    font-size: 17pt;
    font-weight: 800;
    color: #0f172a;
    margin: 4px 0 0 0;
    line-height: 1.35;
  }}

  .section-h2 {{
    font-size: 13pt;
    font-weight: 700;
    color: #0f172a;
    background: #f1f5f9;
    padding: 7px 14px;
    border-left: 5px solid #0284c7;
    border-radius: 4px;
    margin-top: 24px;
    margin-bottom: 14px;
  }}

  .test-case-wrapper {{
    page-break-inside: avoid;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
  }}

  .test-h3 {{
    font-size: 11.5pt;
    font-weight: 700;
    color: #1e293b;
    margin: 0 0 10px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid #e2e8f0;
  }}

  .test-pill {{
    background: #0284c7;
    color: #ffffff;
    font-size: 7.5pt;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 4px;
    vertical-align: middle;
    margin-right: 6px;
  }}

  .question-box {{
    background: #eff6ff;
    border-left: 4px solid #3b82f6;
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 9.5pt;
    color: #1e3a8a;
    margin-bottom: 8px;
  }}

  .expected-box {{
    background: #f8fafc;
    border-left: 4px solid #94a3b8;
    padding: 7px 12px;
    border-radius: 4px;
    font-size: 9pt;
    color: #475569;
    margin-bottom: 12px;
  }}

  .agent-title {{
    font-size: 9.5pt;
    font-weight: 700;
    margin-top: 10px;
    margin-bottom: 4px;
    padding: 3px 8px;
    border-radius: 4px;
    display: inline-block;
  }}

  .agent-off-title {{
    background: #f1f5f9;
    color: #475569;
    border: 1px solid #cbd5e1;
  }}

  .agent-on-title {{
    background: #ecfdf5;
    color: #065f46;
    border: 1px solid #a7f3d0;
  }}

  .response-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 10px;
  }}

  .rag-off-box {{
    border-left: 4px solid #94a3b8;
  }}

  .rag-on-box {{
    border-left: 4px solid #10b981;
    background: #f0fdf4;
  }}

  .response-card pre {{
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
    font-size: 8.8pt;
    line-height: 1.55;
    color: #1e293b;
  }}

  .analysis-h4 {{
    font-size: 9.5pt;
    font-weight: 700;
    color: #0369a1;
    margin: 12px 0 6px 0;
  }}

  .table-container {{
    margin: 8px 0 12px 0;
    overflow-x: auto;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 8.5pt;
    text-align: left;
    border: 1px solid #cbd5e1;
  }}

  th {{
    background: #f8fafc;
    color: #334155;
    font-weight: 700;
    padding: 6px 10px;
    border: 1px solid #cbd5e1;
  }}

  td {{
    padding: 6px 10px;
    border: 1px solid #e2e8f0;
    vertical-align: top;
    line-height: 1.45;
  }}

  tr:nth-child(even) {{
    background-color: #f8fafc;
  }}

  .section-divider {{
    border: 0;
    border-top: 1px dashed #cbd5e1;
    margin: 16px 0;
  }}

  .bullet-item {{
    font-size: 9.2pt;
    margin: 3px 0;
    color: #334155;
  }}

  .bullet-dot {{
    color: #0284c7;
    font-weight: bold;
    margin-right: 4px;
  }}

  .num-item {{
    font-size: 9.2pt;
    margin: 6px 0;
    color: #1e293b;
    padding-left: 4px;
  }}

  .num-badge {{
    display: inline-block;
    background: #0284c7;
    color: white;
    font-size: 7.5pt;
    font-weight: bold;
    width: 16px;
    height: 16px;
    text-align: center;
    line-height: 16px;
    border-radius: 50%;
    margin-right: 6px;
  }}

  code {{
    background: #f1f5f9;
    padding: 1px 5px;
    border-radius: 3px;
    font-family: Consolas, monospace;
    font-size: 8.5pt;
    color: #0f172a;
    border: 1px solid #e2e8f0;
  }}

  strong {{
    font-weight: 700;
    color: #0f172a;
  }}
</style>
</head>
<body>
{body_html}
</body>
</html>
"""
    return full_html


def generate_pdf():
    if not MD_FILE.exists():
        print(f"오류: {MD_FILE} 파일이 없습니다.")
        return False

    print("1. Markdown 문서를 세련된 고품질 인쇄용 HTML로 변환 중...")
    md_text = MD_FILE.read_text(encoding="utf-8")
    html_content = markdown_to_styled_html(md_text)
    HTML_FILE.write_text(html_content, encoding="utf-8")
    print(f"   -> HTML 생성 완료: {HTML_FILE}")

    # 브라우저 실행 파일 경로 탐색
    browser_exe = None
    chrome_path = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
    edge_path = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    if chrome_path.exists():
        browser_exe = str(chrome_path)
    elif edge_path.exists():
        browser_exe = str(edge_path)
    else:
        print("오류: Chrome 또는 Edge 브라우저를 찾을 수 없습니다.")
        return False

    print(f"2. 헤드리스 브라우저({Path(browser_exe).stem})를 통해 PDF 렌더링 중...")
    abs_html = HTML_FILE.resolve().as_uri()
    cmd = [
        browser_exe,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={PDF_FILE.resolve()}",
        "--no-pdf-header-footer",
        abs_html
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0 and PDF_FILE.exists():
        print(f"   🎉 PDF 파일 생성 완료: {PDF_FILE} ({PDF_FILE.stat().st_size} bytes)")
    else:
        err_msg = res.stderr.decode('utf-8', errors='ignore')
        print(f"PDF 생성 실패: {err_msg}")
        return False

    # 3. Downloads 폴더로 복사
    if DOWNLOADS_DIR.exists():
        target_path = DOWNLOADS_DIR / PDF_FILE.name
        shutil.copy(PDF_FILE, target_path)
        print(f"   📁 사용자 다운로드 폴더로 복사 완료: {target_path}")

    return True

if __name__ == "__main__":
    generate_pdf()
