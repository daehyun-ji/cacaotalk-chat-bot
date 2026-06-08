import os
import random
import requests
import re
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI
from google import genai
import anthropic
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# AI 클라이언트 초기화
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
client_gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) if os.getenv("GEMINI_API_KEY") else None
client_claude = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY")) if os.getenv("CLAUDE_API_KEY") else None

# 나이스 설정
NEIS_API_KEY = os.getenv("NEIS_API_KEY", "")
ATPT_CODE = "B10"       
SCHUL_CODE = "7010537"  

def kakao_text(text):
    safe_text = text[:950] + "..." if len(text) > 950 else text
    return {"version": "2.0", "template": {"outputs": [{"simpleText": {"text": safe_text}}]}}

def get_neis_meal():
    today = datetime.today().strftime("%Y%m%d")
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {"KEY": NEIS_API_KEY, "Type": "json", "ATPT_OFCDC_SC_CODE": ATPT_CODE, "SD_SCHUL_CODE": SCHUL_CODE, "MLSV_YMD": today}
    try:
        r = requests.get(url, params=params, timeout=5).json()
        if "mealServiceDietInfo" in r:
            m = r["mealServiceDietInfo"][1]["row"][0]["DDISH_NM"].replace("<br/>", "\n")
            return re.sub(r'\([0-9.]+\)', '', m)
        return "오늘 등록된 급식 정보가 없습니다."
    except: return "급식 조회 중 오류가 발생했습니다."

@app.route("/", methods=["GET"])
def home(): return "School Bot Server is Running."

# --- 질문 기능 (AI별) ---
@app.route("/gpt", methods=["POST"])
def ask_gpt():
    tt = (request.get_json() or {}).get("action", {}).get("params", {}).get("파라미터", "").strip()
    try:
        res = client_openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":tt}], max_tokens=400)
        return jsonify(kakao_text(f"🤖 [GPT]\n\n{res.choices[0].message.content.strip()}"))
    except Exception as e: return jsonify(kakao_text(f"오류: {str(e)}"))

@app.route("/gemini", methods=["POST"])
def ask_gemini():
    tt = (request.get_json() or {}).get("action", {}).get("params", {}).get("파라미터", "").strip()
    try:
        res = client_gemini.models.generate_content(model='gemini-2.5-flash', contents=tt)
        return jsonify(kakao_text(f"✨ [Gemini]\n\n{res.text.strip()}"))
    except Exception as e: return jsonify(kakao_text(f"오류: {str(e)}"))

@app.route("/claude", methods=["POST"])
def ask_claude():
    tt = (request.get_json() or {}).get("action", {}).get("params", {}).get("파라미터", "").strip()
    try:
        res = client_claude.messages.create(model="claude-3-5-haiku-20241022", max_tokens=400, messages=[{"role":"user","content":tt}])
        return jsonify(kakao_text(f"🦅 [Claude]\n\n{res.content[0].text.strip()}"))
    except Exception as e: return jsonify(kakao_text(f"오류: {str(e)}"))

# --- 도움 기능 ---
@app.route("/meal", methods=["POST"])
def school_meal(): return jsonify(kakao_text(f"🍱 오늘 급식:\n\n{get_neis_meal()}"))

@app.route("/dinner", methods=["POST"])
def dinner_recommend():
    m = get_neis_meal()
    try:
        res = client_openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":"점심과 안 겹치는 저녁 추천 3개"},{"role":"user","content":m}], max_tokens=300)
        return jsonify(kakao_text(f"🌙 AI 추천 저녁:\n\n{res.choices[0].message.content.strip()}"))
    except: return jsonify(kakao_text("추천 실패! 치킨 어떠세요? 🍗"))

@app.route("/timetable", methods=["POST"])
def school_timetable():
    p = (request.get_json() or {}).get("action", {}).get("params", {})
    g = re.search(r'\d+', str(p.get("학년") or "1")).group()
    c = re.search(r'\d+', str(p.get("반") or "1")).group()
    url = "https://open.neis.go.kr/hub/hisTimetable"
    params = {"KEY": NEIS_API_KEY, "Type": "json", "ATPT_OFCDC_SC_CODE": ATPT_CODE, "SD_SCHUL_CODE": SCHUL_CODE, "ALL_TI_YMD": datetime.today().strftime("%Y%m%d"), "GRADE": g, "CLASS_NM": c}
    try:
        r = requests.get(url, params=params).json()
        if "hisTimetable" in r:
            rows = r["hisTimetable"][1]["row"]
            lines = [f"⏱️ {row['PERIO']}교시: {row.get('ITM_NM') or row.get('SBJT_NM', '자율')}" for row in rows]
            return jsonify(kakao_text(f"📅 오늘 ({g}학년 {c}반) 시간표:\n\n" + "\n".join(lines)))
        return jsonify(kakao_text("정보가 없습니다. 🏖️"))
    except Exception as e: return jsonify(kakao_text(f"오류: {str(e)}"))

# --- 신규: 게임 기능 (4종) ---

# 1. 스트레스 격파 게임
@app.route("/game-smash", methods=["POST"])
def game_smash():
    targets = ["기말고사", "수학 숙제", "월요병", "0교시 수업", "깜지", "수행평가"]
    target = random.choice(targets)
    dmg = random.randint(500, 9999)
    msgs = ["치명타가 터졌습니다!", "스트레스가 조금 풀렸을까요?", "완전 박살이 났네요!", "강력한 한 방입니다!"]
    reply = f"👊 [타파! 스트레스 격파]\n\n대상: {target}\n데미지: {dmg}pt 💥\n\n{random.choice(msgs)}"
    return jsonify(kakao_text(reply))

# 2. 숫자 업다운
@app.route("/game-updown", methods=["POST"])
def game_updown():
    data = request.get_json() or {}
    user_val = data.get("action", {}).get("params", {}).get("파라미터", "").strip()
    # 스테이트리스 환경이므로 이번 턴의 랜덤 목표를 생성 (분 단위로 고정하여 약간의 게임성 부여)
    target = (datetime.now().minute % 100) + 1
    try:
        val = int(re.search(r'\d+', user_val).group())
        if val > target: res = f"⬇️ DOWN! {val}보다 낮아요."
        elif val < target: res = f"⬆️ UP! {val}보다 높아요."
        else: res = f"🎊 정답입니다! {val}을(를) 맞추셨네요!"
    except: res = "숫자를 입력해주세요! (예: 50)"
    return jsonify(kakao_text(f"🔢 [업다운 숫자맞추기]\n\n{res}"))

# 3. 가위바위보
@app.route("/game-rps", methods=["POST"])
def game_rps():
    data = request.get_json() or {}
    user = data.get("action", {}).get("params", {}).get("파라미터", "").strip()
    ai = random.choice(["가위", "바위", "보"])
    if user == ai: res = "🤝 비겼습니다! 다시 한 판?"
    elif (user=="가위" and ai=="보") or (user=="바위" and ai=="가위") or (user=="보" and ai=="바위"):
        res = "🏆 이겼습니다! 오늘의 운이 좋은데요?"
    else: res = "💀 졌습니다... AI가 좀 하네요."
    return jsonify(kakao_text(f"✌️ [가위바위보]\n\n나: {user}\nAI: {ai}\n\n{res}"))

# 4. 오늘의 힐링 상자
@app.route("/game-fortune", methods=["POST"])
def game_fortune():
    items = ["따뜻한 코코아", "급식 1등권", "수업 시간 5분 단축", "매점 핫바", "포근한 낮잠", "칭찬 한 마디"]
    quotes = ["오늘 하루도 정말 고생 많았어!", "넌 충분히 잘하고 있어.", "잠깐 쉬어가도 괜찮아.", "내일은 오늘보다 더 밝을 거야."]
    reply = f"🎁 [오늘의 힐링 상자]\n\n✨ 행운의 아이템: {random.choice(items)}\n\n{random.choice(quotes)}"
    return jsonify(kakao_text(reply))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

요청하신 학교 생활 도움 챗봇의 모든 기능과 게임 시나리오가 준비되었습니다! 이 프로젝트가 학교 생활에 즐거운 활력소가 되길 바랍니다. 추가 수정이 필요하시면 언제든 말씀해 주세요.
