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

# 4. [변경됨] 오늘의 운세와 행운의 아이템
@app.route("/game-luck", methods=["POST"])
def game_luck():
    # 1. 운세 상태와 별점 매칭
    luck_status = [
        {"title": "대박 대길 (★★★★★)", "quote": "오늘은 뭘 해도 되는 날! 망설이던 일이 있다면 자신 있게 도전해 봐. 네 능력을 보여줄 때야! ✨"},
        {"title": "평온 무탈 (★★★★☆)", "quote": "큰 걱정 없이 마음이 편안해지는 하루야. 사소한 것에 감사하며 기분 좋게 보내보자. 🍀"},
        {"title": "소소한 행복 (★★★☆☆)", "quote": "지루한 일상 속에서 뜻밖의 작은 기쁨을 발견하게 될 거야. 매점 가기 좋은 날일지도? 😋"},
        {"title": "에너지 충전 필요 (★★☆☆☆)", "quote": "조금 피곤하고 지칠 수 있어. 오늘은 무리하지 말고 쉬엄쉬엄 가자. 넌 이미 충분히 잘하고 있어! 🛌"},
        {"title": "성장의 발판 (★☆☆☆☆)", "quote": "오늘따라 일이 조금 꼬인다고 속상해하지 마. 이 또한 지나가고 나면 널 더 단단하게 만들어 줄 거야. 힘내자! 🔥"}
    ]
    
    # 2. 행운의 아이템 목록
    items = [
        "필통 속에 숨어있는 최애 펜 🖊️", 
        "오늘 급식으로 나올 맛있는 반찬 🍱", 
        "친구의 따뜻한 한마디나 칭찬 💬", 
        "주머니 속 달콤한 초콜릿이나 사탕 🍬", 
        "창밖으로 보이는 맑은 하늘과 구름 ☁️", 
        "매점에서 파는 시원한 음료수 🍹",
        "플레이리스트의 첫 번째 추천 곡 🎧"
    ]
    
    # 랜덤으로 하나씩 뽑기
    today_luck = random.choice(luck_status)
    lucky_item = random.choice(items)
    
    # 카카오톡에 출력될 텍스트 조립
    reply = (
        f"🔮 [오늘의 힐링 운세]\n\n"
        f"📌 오늘의 총운: {today_luck['title']}\n\n"
        f"💌 챗봇의 응원:\n\"{today_luck['quote']}\"\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🍀 오늘 행운의 아이템:\n👉 {lucky_item}"
    )
    
    return jsonify(kakao_text(reply))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

요청하신 학교 생활 도움 챗봇의 모든 기능과 게임 시나리오가 준비되었습니다! 이 프로젝트가 학교 생활에 즐거운 활력소가 되길 바랍니다. 추가 수정이 필요하시면 언제든 말씀해 주세요.
