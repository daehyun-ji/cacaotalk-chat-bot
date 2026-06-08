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

# .env 파일에서 환경변수 로드 (로컬 테스트용, Render 배포 시에는 시스템 환경변수 참조)
load_dotenv()

app = Flask(__name__)

# 각 AI 클라이언트 초기화 (Render에 등록한 환경변수를 자동으로 가져옵니다)
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

gemini_key = os.getenv("GEMINI_API_KEY")
client_gemini = genai.Client(api_key=gemini_key) if gemini_key else None

claude_key = os.getenv("CLAUDE_API_KEY")
client_claude = anthropic.Anthropic(api_key=claude_key) if claude_key else None

# 나이스 API 설정 (Render Environment에 등록하여 사용하세요)
NEIS_API_KEY = os.getenv("NEIS_API_KEY", "")
ATPT_CODE = "B10"       # 예시: 서울특별시교육청 (학교에 맞게 수정 가능)
SCHUL_CODE = "7010537"  # 예시: 학교 행정표준코드 (학교에 맞게 수정 가능)


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
    return "Server is running."


# =========================================================
# 1. 질문 기능 - AI 엔진별 개별 엔드포인트 (/gpt, /gemini, /claude)
# =========================================================

# [ChatGPT 질문 처리]
@app.route("/gpt", methods=["POST"])
def ask_gpt():
    data = request.get_json(silent=True) or {}
    tt = data.get("action", {}).get("params", {}).get("파라미터", "").strip()

    if not tt:
        return jsonify(kakao_text("질문 내용을 입력해주세요!"))

    if not os.getenv("OPENAI_API_KEY"):
        return jsonify(kakao_text("OPENAI_API_KEY 환경변수가 설정되지 않았습니다."))

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


# [Gemini 질문 처리]
@app.route("/gemini", methods=["POST"])
def ask_gemini():
    data = request.get_json(silent=True) or {}
    tt = data.get("action", {}).get("params", {}).get("파라미터", "").strip()

    if not tt:
        return jsonify(kakao_text("질문 내용을 입력해주세요!"))

    if not client_gemini:
        return jsonify(kakao_text("GEMINI_API_KEY 환경변수가 설정되지 않았습니다."))

    try:
        response = client_gemini.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"당신은 유능하고 친절한 학교 생활 도우미 챗봇입니다. 답변은 간결하고 명확하게 하세요. 질문: {tt}",
        )
        result_text = f"✨ [Gemini 답변]\n\n{response.text.strip()}"
    except Exception as e:
        result_text = f"Gemini 호출 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(result_text))


# [Claude 질문 처리]
@app.route("/claude", methods=["POST"])
def ask_claude():
    data = request.get_json(silent=True) or {}
    tt = data.get("action", {}).get("params", {}).get("파라미터", "").strip()

    if not tt:
        return jsonify(kakao_text("질문 내용을 입력해주세요!"))

    if not client_claude:
        return jsonify(kakao_text("CLAUDE_API_KEY 환경변수가 설정되지 않았습니다."))

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
# 2. 도움 기능 - 기능별 개별 엔드포인트 (/meal, /dinner, /timetable)
# =========================================================

# [오늘의 급식 조회]
@app.route("/meal", methods=["POST"])
def school_meal():
    meal_result = get_neis_meal()
    reply_text = f"🍱 오늘의 학교 급식 (중식):\n\n{meal_result}"
    return jsonify(kakao_text(reply_text))


# [저녁 메뉴 추천 (급식 연동)]
@app.route("/dinner", methods=["POST"])
def dinner_recommend():
    meal_result = get_neis_meal()

    # 급식 정보 파싱 성공 시 겹치지 않게 추천 설계
    if "오류" not in meal_result and "없습니다" not in meal_result:
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


# [학교 시간표 조회]
@app.route("/timetable", methods=["POST"])
def school_timetable():
    today = datetime.today().strftime("%Y%m%d")
    data = request.get_json(silent=True) or {}
    params = data.get("action", {}).get("params", {})

    # 오픈빌더 파라미터 매핑 (없을 시 기본값 1학년 1반 처리)
    grade = params.get("학년", "1").replace("학년", "").strip()
    room = params.get("반", "1").replace("반", "").strip()

    if not NEIS_API_KEY:
        return jsonify(kakao_text("NEIS_API_KEY 환경변수가 설정되지 않았습니다."))

    url = "https://open.neis.go.kr/hub/hisTimetable"  # 고교 기준 (중등: misTimetable, 초등: elsTimetable)
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
                
                # [수정 포인트] ITM_NM이 없으면 SBJT_NM을 가져오도록 안전장치 마련
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
# 기존 레거시 기능들 (테스트 및 샘플용 유지)
# =========================================================
@app.route("/text", methods=["GET", "POST"])
def text_skill():
    return jsonify(kakao_text(str(random.randint(1, 10))))

@app.route("/image", methods=["GET", "POST"])
def image_skill():
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{
                "simpleImage": {
                    "imageUrl": "https://t1.daumcdn.net/friends/prod/category/M001_friends_ryan2.jpg",
                    "altText": "hello I'm Ryan"
                }
            }]
        }
    })

@app.route("/echo", methods=["POST"])
def echo_skill():
    data = request.get_json(silent=True) or {}
    user_input = data.get("userRequest", {}).get("utterance", "입력값이 없습니다.")
    return jsonify(kakao_text(user_input))

@app.route("/google-news", methods=["POST"])
def google_news():
    data = request.get_json(silent=True) or {}
    y = data.get("action", {}).get("params", {}).get("파라미터", "").strip()
    if not y: return jsonify(kakao_text("파라미터 값이 없습니다."))
    query = urllib.parse.quote(y)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")
        titles = [item.title.text for item in items[:5] if item.title.text]
        if titles: result = f"['{y}'] 뉴스 검색 결과:\n\n" + "\n\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
        else: result = f"['{y}']에 대한 검색 결과를 찾지 못했습니다."
    except Exception as e: result = f"뉴스 조회 중 오류 발생: {str(e)}"
    return jsonify(kakao_text(result))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
