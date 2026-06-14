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

# 로컬 환경 변수 로드 (Render 배포 시에는 시스템 환경변수를 우선 참조합니다)
load_dotenv()

app = Flask(__name__)

# 각 AI 클라이언트 초기화 (Render 환경변수에 값이 있을 때만 안전하게 빌드되도록 설정)
openai_key = os.getenv("OPENAI_API_KEY")
client_openai = OpenAI(api_key=openai_key) if openai_key else None

gemini_key = os.getenv("GEMINI_API_KEY")
client_gemini = genai.Client(api_key=gemini_key) if gemini_key else None

claude_key = os.getenv("CLAUDE_API_KEY")
client_claude = anthropic.Anthropic(api_key=claude_key) if claude_key else None

# 나이스 API 설정 (Render Environment 탭에 등록 필요)
NEIS_API_KEY = os.getenv("NEIS_API_KEY", "")
ATPT_CODE = "B10"       # 기본값: 서울특별시교육청 (학교에 맞게 Render에서 수정 가능)
SCHUL_CODE = "7010537"  # 기본값: 학교 행정표준코드 (학교에 맞게 Render에서 수정 가능)


def kakao_text(text):
    """카카오톡 텍스트 응답 규격 생성 (1000자 제한 안전장치)"""
    safe_text = text[:950] + "..." if len(text) > 950 else text
    return {
        "version": "2.0",
        "template": {
            "outputs": [{
                "simpleText": {
                    "text": safe_text
                }
            }]
        }
    }


def get_neis_meal():
    """나이스 API로부터 오늘 급식을 가져오는 내부 공통 함수"""
    if not NEIS_API_KEY:
        return "NEIS_API_KEY 환경변수가 설정되지 않았습니다."
        
    today = datetime.today().strftime("%Y%m%d")
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": NEIS_API_KEY,
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": ATPT_CODE,
        "SD_SCHUL_CODE": SCHUL_CODE,
        "MLSV_YMD": today,
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        res_data = response.json()
        
        if "mealServiceDietInfo" in res_data:
            meal_info = res_data["mealServiceDietInfo"][1]["row"][0]
            pure_meal = meal_info["DDISH_NM"].replace("<br/>", "\n")
            pure_meal = re.sub(r'\([0-9.]+\)', '', pure_meal)  # 알레르기 번호 제거
            return pure_meal
        else:
            return "오늘 등록된 급식 정보가 없습니다."
    except Exception as e:
        return f"급식 조회 중 오류 발생: {str(e)}"


@app.route("/", methods=["GET"])
def home():
    return "School Bot Server is Running Perfectly."


# =========================================================
# 시나리오 1: 질문 기능 (엔진별 주소 분리)
# =========================================================

@app.route("/gpt", methods=["POST"])
def ask_gpt():
    data = request.get_json(silent=True) or {}
    tt = data.get("action", {}).get("params", {}).get("파라미터", "").strip()

    if not tt: return jsonify(kakao_text("질문 내용을 입력해주세요!"))
    if not client_openai: return jsonify(kakao_text("OPENAI_API_KEY가 설정되지 않았습니다."))

    try:
        response = client_openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 유능하고 친절한 학교 생활 도우미 챗봇입니다. 답변은 간결하고 명확하게 하세요."},
                {"role": "user", "content": tt}
            ],
            temperature=0.7,
            max_tokens=400
        )
        result_text = f"🤖 [ChatGPT 답변]\n\n{response.choices[0].message.content.strip()}"
    except Exception as e:
        result_text = f"ChatGPT 호출 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(result_text))


@app.route("/gemini", methods=["POST"])
def ask_gemini():
    data = request.get_json(silent=True) or {}
    tt = data.get("action", {}).get("params", {}).get("파라미터", "").strip()

    if not tt: return jsonify(kakao_text("질문 내용을 입력해주세요!"))
    if not client_gemini: return jsonify(kakao_text("GEMINI_API_KEY가 설정되지 않았습니다."))

    try:
        response = client_gemini.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"당신은 유능하고 친절한 학교 생활 도우미 챗봇입니다. 답변은 간결하고 명확하게 하세요. 질문: {tt}",
        )
        result_text = f"✨ [Gemini 답변]\n\n{response.text.strip()}"
    except Exception as e:
        result_text = f"Gemini 호출 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(result_text))


@app.route("/claude", methods=["POST"])
def ask_claude():
    data = request.get_json(silent=True) or {}
    tt = data.get("action", {}).get("params", {}).get("파라미터", "").strip()

    if not tt: return jsonify(kakao_text("질문 내용을 입력해주세요!"))
    if not client_claude: return jsonify(kakao_text("CLAUDE_API_KEY가 설정되지 않았습니다."))

    try:
        response = client_claude.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=400,
            system="당신은 유능하고 친절한 학교 생활 도우미 챗봇입니다. 답변은 간결하고 명확하게 하세요.",
            messages=[{"role": "user", "content": tt}]
        )
        result_text = f"🦅 [Claude 답변]\n\n{response.content[0].text.strip()}"
    except Exception as e:
        result_text = f"Claude 호출 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(result_text))


# =========================================================
# 시나리오 2: 도움 기능 (급식 / 저녁추천 / 시간표)
# =========================================================

@app.route("/meal", methods=["POST"])
def school_meal():
    meal_result = get_neis_meal()
    reply_text = f"🍱 오늘의 학교 급식 (중식):\n\n{meal_result}"
    return jsonify(kakao_text(reply_text))


@app.route("/dinner", methods=["POST"])
def dinner_recommend():
    meal_result = get_neis_meal()

    if "오류" not in meal_result and "없습니다" not in meal_result and client_openai:
        try:
            response = client_openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 영양사 출신의 친절한 학교 챗봇입니다. 제공된 점심 급식 메뉴와 전혀 겹치지 않으면서 학생들이 선호할 만한 맛있는 저녁 메뉴 3가지를 추천하고 그 이유를 한 줄로 요약하세요."},
                    {"role": "user", "content": f"오늘 학교 점심 메뉴야:\n{meal_result}\n\n이것과 겹치지 않는 저녁 메뉴를 추천해줘."}
                ],
                temperature=0.7,
                max_tokens=400
            )
            recommendation = response.choices[0].message.content.strip()
        except Exception as e:
            recommendation = f"AI 저녁 추천 중 오류가 발생했습니다: {str(e)}"
    else:
        recommendation = "오늘 급식 데이터가 존재하지 않아 맞춤 추천이 어렵습니다. 삼겹살이나 따뜻한 부대찌개는 어떠신가요? 🥩"

    reply_text = f"🌙 AI 추천 저녁 메뉴:\n\n{recommendation}"
    return jsonify(kakao_text(reply_text))


@app.route("/timetable", methods=["POST"])
def school_timetable():
    today = datetime.today().strftime("%Y%m%d")
    data = request.get_json(silent=True) or {}
    params = data.get("action", {}).get("params", {})

    # 학년/반 파라미터 매핑 보안 처리
    raw_grade = params.get("학년") or params.get("파라미터") or "1"
    raw_room = params.get("반") or params.get("파라미터2") or "1"

    grade_match = re.search(r'\d+', str(raw_grade))
    room_match = re.search(r'\d+', str(raw_room))

    grade = grade_match.group() if grade_match else "1"
    room = room_match.group() if room_match else "1"

    url = "https://open.neis.go.kr/hub/hisTimetable"
    api_params = {
        "KEY": NEIS_API_KEY,
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": ATPT_CODE,
        "SD_SCHUL_CODE": SCHUL_CODE,
        "ALL_TI_YMD": today,
        "GRADE": grade,
        "CLASS_NM": room
    }

    try:
        response = requests.get(url, params=api_params, timeout=5)
        res_data = response.json()

        if "hisTimetable" in res_data:
            timetable_rows = res_data["hisTimetable"][1]["row"]
            lines = []
            for row in timetable_rows:
                period = row.get("PERIO", "?")
                subject = row.get("ITM_NM") or row.get("SBJT_NM", "자율/공백")
                lines.append(f"⏱️ {period}교시 : {subject}")
                
            timetable_text = "\n".join(lines)
            reply_text = f"📅 오늘 ({grade}학년 {room}반) 시간표:\n\n{timetable_text}"
        else:
            reply_text = f"오늘 {grade}학년 {room}반의 시간표가 없거나 주말/공휴일입니다. 🏖️"
    except Exception as e:
        reply_text = f"시간표를 가져오는 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(reply_text))


# =========================================================
# 시나리오 3: 스트레스 타파 게임 기능 (4종)
# =========================================================

# 1. 스트레스 격파 게임 (/game-smash)
@app.route("/game-smash", methods=["POST"])
def game_smash():
    targets = ["기말고사", "수학 숙제", "월요병", "0교시 등교", "빽빽이 야자", "수행평가 폭탄"]
    target = random.choice(targets)
    dmg = random.randint(500, 9999)
    msgs = ["크리티컬 히트! 스트레스가 한 방에 날아갑니다!", "통쾌하게 찌부러뜨렸습니다!", "완전 뼈를 때리는 격파였습니다!", "강력한 일격을 꽂아 넣었습니다!"]
    reply = f"👊 [타파! 스트레스 격파]\n\n대상: 【{target}】\n타격 데미지: {dmg}pt 💥\n\n{random.choice(msgs)}"
    return jsonify(kakao_text(reply))


# 2. 숫자 업다운 게임 (/game-updown)
@app.route("/game-updown", methods=["POST"])
def game_updown():
    data = request.get_json(silent=True) or {}
    user_val = data.get("action", {}).get("params", {}).get("파라미터", "").strip()
    
    # 세션 유지 대신 현재 '분'을 기반으로 동적 정답 생성 (유사 타겟팅)
    target = (datetime.now().minute % 100) + 1
    
    try:
        val_match = re.search(r'\d+', user_val)
        if val_match:
            val = int(val_match.group())
            if val > target: res = f"⬇️ DOWN! 입력하신 {val}보다 낮습니다."
            elif val < target: res = f"⬆️ UP! 입력하신 {val}보다 높습니다."
            else: res = f"🎊 정답입니다! 축하합니다. 정답은 {val}이었습니다!"
        else:
            res = "숫자를 포함해서 말해주세요! (예: 50)"
    except Exception:
        res = "숫자 판정 중 오류가 발생했습니다. 숫자로 다시 입력해주세요!"
        
    return jsonify(kakao_text(f"🔢 [업다운 숫자맞추기]\n\n{res}"))


# 3. 가위바위보 게임 (/game-rps)
@app.route("/game-rps", methods=["POST"])
def game_rps():
    data = request.get_json(silent=True) or {}
    user = data.get("action", {}).get("params", {}).get("파라미터", "").strip()
    ai = random.choice(["가위", "바위", "보"])
    
    if user not in ["가위", "바위", "보"]:
        return jsonify(kakao_text("📢 '가위', '바위', '보' 중 하나만 정확하게 입력해 주세요!"))
        
    if user == ai:
        res = "🤝 비겼습니다! 호적수를 만났군요. 한 번 더?"
    elif (user == "가위" and ai == "보") or (user == "바위" and ai == "가위") or (user == "보" and ai == "바위"):
        res = "🏆 이겼습니다! 역시 오늘 운이 따라주는 날이네요!"
    else:
        res = "💀 졌습니다... 인공지능의 벽은 높군요. 복수하러 고?"
        
    reply = f"✌️ [가위바위보 한판 승부]\n\n나: {user}\nAI: {ai}\n\n{res}"
    return jsonify(kakao_text(reply))


# 4. 오늘의 운세와 행운의 아이템 (/game-luck)
@app.route("/game-luck", methods=["POST"])
def game_luck():
    luck_status = [
        {"title": "대박 대길 (★★★★★)", "quote": "오늘은 뭘 해도 되는 날! 망설이던 일이 있다면 자신 있게 도전해 봐. 네 능력을 보여줄 때야! ✨"},
        {"title": "평온 무탈 (★★★★☆)", "quote": "큰 걱정 없이 마음이 편안해지는 하루야. 사소한 것에 감사하며 기분 좋게 보내보자. 🍀"},
        {"title": "소소한 행복 (★★★☆☆)", "quote": "지루한 일상 속에서 뜻밖의 작은 기쁨을 발견하게 될 거야. 매점 가기 좋은 날일지도? 😋"},
        {"title": "에너지 충전 필요 (★★☆☆☆)", "quote": "조금 피곤하고 지칠 수 있어. 오늘은 무리하지 말고 쉬엄쉬엄 가자. 넌 이미 충분히 잘하고 있어! 🛌"},
        {"title": "성장의 발판 (★☆☆☆☆)", "quote": "오늘따라 일이 조금 꼬인다고 속상해하지 마. 이 또한 지나가고 나면 널 더 단단하게 만들어 줄 거야. 힘내자! 🔥"}
    ]
    
    items = [
        "필통 속에 숨어있는 최애 펜 🖊️", 
        "오늘 급식으로 나올 가장 맛있는 반찬 🍱", 
        "친구의 따뜻한 한마디나 예상치 못한 칭찬 💬", 
        "주머니 속 숨겨둔 달콤한 초콜릿이나 사탕 🍬", 
        "창밖으로 잠시 보이는 맑은 하늘과 구름 ☁️", 
        "매점에서 파는 아주 시원한 탄산음료 🍹",
        "내 플레이리스트의 첫 번째 추천 곡 🎧"
    ]
    
    today_luck = random.choice(luck_status)
    lucky_item = random.choice(items)
    
    reply = (
        f"🔮 [오늘의 힐링 운세]\n\n"
        f"📌 오늘의 총운: {today_luck['title']}\n\n"
        f"💌 챗봇의 응원:\n\"{today_luck['quote']}\"\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🍀 오늘 행운의 아이템:\n👉 {lucky_item}"
    )
    return jsonify(kakao_text(reply))


# --- 기존 레거시 기능 백업 ---
@app.route("/text", methods=["GET", "POST"])
def text_skill(): return jsonify(kakao_text(str(random.randint(1, 10))))

@app.route("/echo", methods=["POST"])
def echo_skill():
    data = request.get_json(silent=True) or {}
    user_input = data.get("userRequest", {}).get("utterance", "입력값이 없습니다.")
    return jsonify(kakao_text(user_input))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
