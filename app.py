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

# =========================================================
# AI 클라이언트 초기화
# =========================================================
openai_key = os.getenv("OPENAI_API_KEY")
client_openai = OpenAI(api_key=openai_key) if openai_key else None

gemini_key = os.getenv("GEMINI_API_KEY")
client_gemini = genai.Client(api_key=gemini_key) if gemini_key else None

claude_key = os.getenv("CLAUDE_API_KEY")
client_claude = anthropic.Anthropic(api_key=claude_key) if claude_key else None

# 나이스 API 설정
NEIS_API_KEY = os.getenv("NEIS_API_KEY", "")
ATPT_CODE = "B10"
SCHUL_CODE = "7010537"

# =========================================================
# 서버 메모리 저장소 (재시작 시 초기화됨)
# =========================================================

# 운세 사용 기록: { "유저ID_날짜": True }
luck_used_log = {}

# 퀴즈 진행 상태: { "유저ID": { quiz 정보 } }
quiz_sessions = {}

# =========================================================
# 퀴즈 문제 데이터베이스
# =========================================================
QUIZ_DATA = [
    # 사자성어 — 앞 2글자 공개, 뒤 2글자를 맞추는 방식
    # display: 문제에 표시할 텍스트 / answer: 뒤 2글자
    {"type": "사자성어", "display": "고진___ (苦盡甘來)\n뜻: 고생 끝에 즐거움이 온다", "question": "고진▢▢ (苦盡甘來)", "answer": "감래", "hints": ["'달 감(甘)' 자로 시작해", "달콤함이 온다는 뜻이야", "甘(달 감), 來(올 래)", "감으로 시작하는 두 글자", "감_ (마지막 글자 힌트: 올 래)"]},
    {"type": "사자성어", "display": "일석___ (一石二鳥)\n뜻: 돌 하나로 새 두 마리를 잡는다", "question": "일석▢▢ (一石二鳥)", "answer": "이조", "hints": ["'둘 이(二)' 자로 시작해", "새를 뜻하는 한자가 마지막에 와", "二(둘 이), 鳥(새 조)", "이로 시작하는 두 글자", "이_ (마지막 글자 힌트: 새 조)"]},
    {"type": "사자성어", "display": "오리___ (五里霧中)\n뜻: 상황을 전혀 파악하지 못하는 상태", "question": "오리▢▢ (五里霧中)", "answer": "무중", "hints": ["'안개 무(霧)' 자로 시작해", "안개 속을 뜻하는 표현이야", "霧(안개 무), 中(가운데 중)", "무로 시작하는 두 글자", "무_ (마지막 글자 힌트: 가운데 중)"]},
    {"type": "사자성어", "display": "전화___ (轉禍爲福)\n뜻: 재앙이 바뀌어 오히려 복이 된다", "question": "전화▢▢ (轉禍爲福)", "answer": "위복", "hints": ["'될 위(爲)' 자로 시작해", "복을 뜻하는 한자가 마지막에 와", "爲(될 위), 福(복 복)", "위로 시작하는 두 글자", "위_ (마지막 글자 힌트: 복 복)"]},
    {"type": "사자성어", "display": "청출___ (靑出於藍)\n뜻: 제자가 스승보다 더 뛰어남", "question": "청출▢▢ (靑出於藍)", "answer": "어람", "hints": ["'어조사 어(於)' 자로 시작해", "쪽(藍)을 뜻하는 한자가 마지막에 와", "於(어조사 어), 藍(쪽 람)", "어로 시작하는 두 글자", "어_ (마지막 글자 힌트: 쪽 람)"]},
    {"type": "사자성어", "display": "마이___ (馬耳東風)\n뜻: 남의 말을 전혀 귀담아듣지 않음", "question": "마이▢▢ (馬耳東風)", "answer": "동풍", "hints": ["'동녘 동(東)' 자로 시작해", "바람을 뜻하는 한자가 마지막에 와", "東(동녘 동), 風(바람 풍)", "동으로 시작하는 두 글자", "동_ (마지막 글자 힌트: 바람 풍)"]},
    {"type": "사자성어", "display": "금상___ (錦上添花)\n뜻: 좋은 것 위에 더 좋은 것이 더해짐", "question": "금상▢▢ (錦上添花)", "answer": "첨화", "hints": ["'더할 첨(添)' 자로 시작해", "꽃을 뜻하는 한자가 마지막에 와", "添(더할 첨), 花(꽃 화)", "첨으로 시작하는 두 글자", "첨_ (마지막 글자 힌트: 꽃 화)"]},
    # 속담
    {"type": "속담", "question": "가는 말이 고와야 ___이/가 곱다", "answer": "오는 말", "hints": ["상대방을 대하는 태도에 관한 속담", "말하는 것과 관련된 표현이야", "상호 관계를 뜻하는 속담", "내가 잘 해야 상대도 잘 한다는 의미", "가는 것과 반대되는 것은?"]},
    {"type": "속담", "question": "공든 탑이 ___", "answer": "무너지랴", "hints": ["정성껏 쌓은 것은 쉽게 무너지지 않는다는 속담", "노력의 결과는 사라지지 않는다는 의미", "탑과 관련된 표현이야", "공들인 것의 결과에 관한 속담", "탑이 어떻게 될까? (부정형)"]},
    {"type": "속담", "question": "원숭이도 나무에서 ___", "answer": "떨어진다", "hints": ["아무리 뛰어난 사람도 실수할 수 있다는 뜻", "원숭이가 나무에서 하는 행동", "잘하는 사람도 실수한다는 의미", "나무에서 내려오는 것과 다른 표현", "중력과 관련된 동사야"]},
    {"type": "속담", "question": "세 살 버릇 ___까지 간다", "answer": "여든", "hints": ["어릴 때 습관이 평생 간다는 속담", "나이와 관련된 표현이야", "인생의 끝 무렵을 나타내는 나이", "60보다 크고 90보다 작은 숫자", "팔십이라고도 불러"]},
    {"type": "속담", "question": "백지장도 맞들면 낫다", "answer": "백지장도 맞들면 낫다", "hints": ["협동과 협력에 관한 속담", "종이와 관련된 표현이야", "혼자보다 둘이 낫다는 의미", "白紙張(흰 종이)을 함께 드는 것", "전체 속담을 그대로 입력해봐"]},
    {"type": "속담", "question": "하늘이 무너져도 솟아날 ___이/가 있다", "answer": "구멍", "hints": ["아무리 어려운 상황도 살 길이 있다는 뜻", "빠져나갈 수 있는 통로", "뚫려 있는 공간을 뜻하는 단어", "도넛 가운데 있는 것", "구_ (한 글자 힌트)"]},
    # 인물/캐릭터 퀴즈
    {"type": "캐릭터 퀴즈", "question": "저는 초록색 옷을 입고 공주를 구하러 다니며, 삼각형 모양의 유물을 모으는 게임의 주인공입니다. 저는 누구일까요?", "answer": "링크", "hints": ["닌텐도 게임의 캐릭터야", "젤다 시리즈의 주인공", "초록색 모자와 귀가 뾰족한 특징", "이름이 두 글자야", "ㄹ으로 시작하는 이름"]},
    {"type": "캐릭터 퀴즈", "question": "저는 빨간 모자와 파란 멜빵바지를 입고 버섯을 먹으면 커지며, 쿠파를 물리치는 게임의 주인공입니다. 저는 누구일까요?", "answer": "마리오", "hints": ["닌텐도의 대표 캐릭터", "이탈리아 출신 배관공", "쌍둥이 동생의 이름은 루이지", "이름이 세 글자야", "ㅁ으로 시작하는 이름"]},
    {"type": "캐릭터 퀴즈", "question": "저는 노란색 전기 쥐로 볼에 빨간 동그라미가 있고 '피카피카'라고 말합니다. 저는 누구일까요?", "answer": "피카츄", "hints": ["포켓몬의 마스코트 캐릭터", "전기 타입 포켓몬", "지우의 파트너 포켓몬", "이름이 세 글자야", "ㅍ으로 시작하는 이름"]},
    {"type": "캐릭터 퀴즈", "question": "저는 영국의 유명한 탐정으로 베이커가 221B에 살며 파이프 담배와 돋보기가 트레이드마크입니다. 저는 누구일까요?", "answer": "셜록 홈즈", "hints": ["아서 코난 도일이 만든 캐릭터", "왓슨 박사가 조수야", "추리 소설의 전설적인 탐정", "이름이 네 글자야 (성+이름)", "ㅅ으로 시작하는 이름"]},
    {"type": "캐릭터 퀴즈", "question": "저는 거미에 물린 후 초능력을 얻은 고등학생 히어로로 '친애하는 이웃'이라는 별명이 있습니다. 저는 누구일까요?", "answer": "스파이더맨", "hints": ["마블 코믹스의 히어로", "거미줄을 쏘는 능력이 있어", "피터 파커가 본명이야", "이름이 다섯 글자야", "ㅅ으로 시작하는 이름"]},
    # 상식 퀴즈
    {"type": "상식 퀴즈", "question": "대한민국의 수도는 어디일까요?", "answer": "서울", "hints": ["한강이 흐르는 도시야", "경복궁이 있는 곳", "가장 인구가 많은 도시", "두 글자야", "ㅅ으로 시작해"]},
    {"type": "상식 퀴즈", "question": "태양계에서 가장 큰 행성은 무엇일까요?", "answer": "목성", "hints": ["가스로 이루어진 행성이야", "태양계 행성 중 제일 커", "대적반이라는 거대한 폭풍이 있어", "두 글자야", "ㅁ으로 시작해"]},
    {"type": "상식 퀴즈", "question": "세계에서 가장 긴 강은 무엇일까요?", "answer": "나일강", "hints": ["아프리카에 있는 강이야", "이집트 문명의 발상지", "세 글자야 (강 포함)", "ㄴ으로 시작해", "나_ 강 (빈칸 채우기)"]},
    {"type": "상식 퀴즈", "question": "물의 화학식은 무엇일까요?", "answer": "H2O", "hints": ["수소와 산소로 이루어져 있어", "수소 2개, 산소 1개", "알파벳과 숫자 조합이야", "세 자리 표현이야", "H_O (빈칸 채우기)"]},
    {"type": "상식 퀴즈", "question": "1년은 몇 일일까요?", "answer": "365", "hints": ["윤년에는 하루가 더 많아", "52주보다 하루 많아", "세 자리 숫자야", "300보다 크고 400보다 작아", "36_ (빈칸 채우기)"]},
]


def kakao_text(text):
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
            pure_meal = re.sub(r'\([0-9.]+\)', '', pure_meal)
            return pure_meal
        else:
            return "오늘 등록된 급식 정보가 없습니다."
    except Exception as e:
        return f"급식 조회 중 오류 발생: {str(e)}"


def get_kakao_user_id(data):
    """카카오톡 요청에서 사용자 ID 추출"""
    try:
        return data.get("userRequest", {}).get("user", {}).get("id", "unknown")
    except Exception:
        return "unknown"


@app.route("/", methods=["GET"])
def home():
    return "School Bot Server is Running Perfectly."


# =========================================================
# 시나리오 1: 질문 기능
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
# 시나리오 2: 도움 기능
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
# 시나리오 3: 게임 기능
# =========================================================

# ── 1. 퀴즈 게임 (/game-quiz: 문제 출제, /game-quiz-answer: 정답 입력) ──

@app.route("/game-quiz", methods=["POST"])
def game_quiz_start():
    """새 퀴즈 문제를 출제하고 세션을 시작합니다."""
    data = request.get_json(silent=True) or {}
    user_id = get_kakao_user_id(data)

    # 이미 진행 중인 세션이 있으면 현재 문제를 다시 보여줌
    if user_id in quiz_sessions:
        session = quiz_sessions[user_id]
        q = session["quiz"]
        display = q.get("display", q["question"])
        tries_left = 5 - session["tries"]
        hint_count = session["tries"]
        hint_text = ""
        if hint_count > 0:
            shown_hints = q["hints"][:hint_count]
            hint_text = "\n" + "\n".join([f"💡 힌트{i+1}: {h}" for i, h in enumerate(shown_hints)])

        # 사자성어는 뒤 2글자를 맞추는 것임을 안내
        if q["type"] == "사자성어":
            guide = "✏️ 빈칸(▢▢)에 들어갈 2글자를 입력하세요!"
        else:
            guide = "✏️ !정답을 채팅창에 입력 후 정답을 이야기해주세요!"

        reply = (
            f"🎯 [{q['type']}] 진행 중인 퀴즈가 있어요!\n\n"
            f"❓ {display}\n"
            f"{hint_text}\n\n"
            f"남은 기회: {tries_left}번 🎲\n"
            f"{guide}"
        )
        return jsonify(kakao_text(reply))

    # 새 문제 출제
    q = random.choice(QUIZ_DATA)
    quiz_sessions[user_id] = {
        "quiz": q,
        "tries": 0,
        "solved": False
    }

    display = q.get("display", q["question"])

    # 사자성어는 뒤 2글자를 맞추는 것임을 안내
    if q["type"] == "사자성어":
        guide = "✏️ 빈칸(▢▢)에 들어갈 뒤 2글자를 입력하세요!\n예) 감래, 이조, 동풍 등"
    else:
        guide = "✏️ !정답을 채팅창에 입력 후 정답을 이야기해주세요!"

    reply = (
        f"🎯 [{q['type']}] 퀴즈 시작!\n\n"
        f"❓ {display}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{guide}\n"
        f"🎲 기회: 5번  💡 틀릴 때마다 힌트 제공\n"
        f"🔄 포기하려면 '포기'를 입력하세요"
    )
    return jsonify(kakao_text(reply))


@app.route("/game-quiz-answer", methods=["POST"])
def game_quiz_answer():
    """사용자가 입력한 정답을 채점합니다."""
    data = request.get_json(silent=True) or {}
    user_id = get_kakao_user_id(data)
    user_input = data.get("action", {}).get("params", {}).get("파라미터", "").strip()

    # 세션 없는 경우
    if user_id not in quiz_sessions:
        return jsonify(kakao_text("❗ 진행 중인 퀴즈가 없어요!\n퀴즈 시작 버튼을 눌러주세요. 🎯"))

    session = quiz_sessions[user_id]
    q = session["quiz"]

    # 포기 처리
    if user_input in ["포기", "skip", "그만", "취소"]:
        answer = q["answer"]
        full_q = q.get("question", q.get("display", ""))
        del quiz_sessions[user_id]
        return jsonify(kakao_text(
            f"😢 퀴즈를 포기했습니다.\n\n"
            f"❓ {full_q}\n"
            f"정답은 👉 【{answer}】 이었어요!\n\n"
            f"다음엔 꼭 맞춰보세요! 💪"
        ))

    # 정답 비교 (공백·대소문자 무시)
    correct = q["answer"].replace(" ", "").lower()
    given = user_input.replace(" ", "").lower()

    display = q.get("display", q["question"])

    if given == correct:
        tries = session["tries"] + 1
        del quiz_sessions[user_id]
        emoji = "🏆" if tries == 1 else "🎉" if tries <= 3 else "😅"
        return jsonify(kakao_text(
            f"{emoji} 정답입니다!\n\n"
            f"❓ {display}\n"
            f"✅ 정답: 【{q['answer']}】\n\n"
            f"도전 횟수: {tries}번 만에 성공!\n"
            f"🎯 새 퀴즈를 시작하려면 !퀴즈를 입력해주세요!"
        ))

    # 오답 처리
    session["tries"] += 1
    tries_used = session["tries"]
    tries_left = 5 - tries_used

    if tries_left <= 0:
        answer = q["answer"]
        display = q.get("display", q["question"])
        del quiz_sessions[user_id]
        return jsonify(kakao_text(
            f"💀 아쉽게도 기회를 모두 소진했어요!\n\n"
            f"❓ {display}\n"
            f"✅ 정답: 【{answer}】\n\n"
            f"🔄 새 퀴즈를 시작하려면 !퀴즈를 입력해주세요!"
        ))

    # 힌트 제공
    hint = q["hints"][tries_used - 1]
    all_hints = "\n".join([f"💡 힌트{i+1}: {h}" for i, h in enumerate(q["hints"][:tries_used])])
    display = q.get("display", q["question"])

    if q["type"] == "사자성어":
        guide = "▢▢에 들어갈 2글자를 입력해주세요!"
    else:
        guide = "정답을 입력해주세요!"

    return jsonify(kakao_text(
        f"❌ 틀렸어요! 다시 도전해보세요.\n\n"
        f"❓ {display}\n\n"
        f"{all_hints}\n\n"
        f"남은 기회: {tries_left}번 🎲  {guide}\n"
        f"포기하려면 '포기'를 입력하세요"
    ))


# ── 2. 업다운 게임 (/game-updown) ──

@app.route("/game-updown", methods=["POST"])
def game_updown():
    data = request.get_json(silent=True) or {}
    user_val = data.get("action", {}).get("params", {}).get("파라미터", "").strip()
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


# ── 3. 가위바위보 (/game-rps) ──

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


# ── 4. 오늘의 운세 (/game-luck) — 사용자 ID 기준 하루 1회 제한 ──

@app.route("/game-luck", methods=["POST"])
def game_luck():
    data = request.get_json(silent=True) or {}
    user_id = get_kakao_user_id(data)
    today_str = datetime.today().strftime("%Y%m%d")
    log_key = f"{user_id}_{today_str}"

    # 하루 1회 제한 체크
    if log_key in luck_used_log:
        return jsonify(kakao_text(
            "🔮 오늘의 운세는 이미 확인하셨어요!\n\n"
            "운세는 하루에 한 번만 볼 수 있답니다. ✨\n"
            "내일 자정이 지나면 다시 확인할 수 있어요. 🌙\n\n"
            "오늘 하루도 화이팅! 💪"
        ))

    luck_used_log[log_key] = True

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
        f"🍀 오늘 행운의 아이템:\n👉 {lucky_item}\n\n"
        f"✅ 오늘의 운세 확인 완료! (하루 1회)"
    )
    return jsonify(kakao_text(reply))


# ── 레거시 엔드포인트 ──
@app.route("/text", methods=["GET", "POST"])
def text_skill(): return jsonify(kakao_text(str(random.randint(1, 10))))

@app.route("/echo", methods=["POST"])
def echo_skill():
    data = request.get_json(silent=True) or {}
    user_input = data.get("userRequest", {}).get("utterance", "입력값이 없습니다.")
    return jsonify(kakao_text(user_input))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
