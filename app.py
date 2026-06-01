import os
import random
import requests
import urllib.parse
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI
from google import genai
import anthropic
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()

app = Flask(__name__)

# 각 AI 클라이언트 초기화
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

gemini_key = os.getenv("GEMINI_API_KEY")
client_gemini = genai.Client(api_key=gemini_key) if gemini_key else None

claude_key = os.getenv("CLAUDE_API_KEY")
client_claude = anthropic.Anthropic(api_key=claude_key) if claude_key else None

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

@app.route("/", methods=["GET"])
def home():
    return "Server is running."


# =========================================================
# [시나리오 1: 질문] AI별 전용 엔드포인트 분리
# =========================================================

# 1. ChatGPT 전용 주소 (/gpt)
@app.route("/gpt", methods=["POST"])
def ask_gpt():
    data = request.get_json(silent=True) or {}
    action = data.get("action", {})
    params = action.get("params", {})
    
    # 오픈빌더에서 설정한 질문 파라미터 추출
    user_question = params.get("user_question", "").strip()

    if not user_question:
        return jsonify(kakao_text("질문 내용을 입력해주세요!"))

    if not os.getenv("OPENAI_API_KEY"):
        return jsonify(kakao_text("OPENAI_API_KEY 환경변수가 설정되지 않았습니다."))
    
    try:
        response = client_openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 친절한 학교 생활 도우미 챗봇입니다. 학생의 질문에 상냥하고 간결하게 답해주세요."},
                {"role": "user", "content": user_question}
            ],
            temperature=0.7,
            max_tokens=400
        )
        reply = f"🤖 [ChatGPT 답변]\n\n{response.choices[0].message.content.strip()}"
    except Exception as e:
        reply = f"ChatGPT 호출 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(reply))


# 2. Gemini 전용 주소 (/gemini)
@app.route("/gemini", methods=["POST"])
def ask_gemini():
    data = request.get_json(silent=True) or {}
    action = data.get("action", {})
    params = action.get("params", {})
    
    user_question = params.get("user_question", "").strip()

    if not user_question:
        return jsonify(kakao_text("질문 내용을 입력해주세요!"))

    if not client_gemini:
        return jsonify(kakao_text("GEMINI_API_KEY 환경변수가 설정되지 않았습니다."))
    
    try:
        response = client_gemini.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"당신은 친절한 학교 생활 도우미 챗봇입니다. 상냥하고 간결하게 답해주세요. 질문: {user_question}",
        )
        reply = f"✨ [Gemini 답변]\n\n{response.text.strip()}"
    except Exception as e:
        reply = f"Gemini 호출 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(reply))


# 3. Claude 전용 주소 (/claude)
@app.route("/claude", methods=["POST"])
def ask_claude():
    data = request.get_json(silent=True) or {}
    action = data.get("action", {})
    params = action.get("params", {})
    
    user_question = params.get("user_question", "").strip()

    if not user_question:
        return jsonify(kakao_text("질문 내용을 입력해주세요!"))

    if not client_claude:
        return jsonify(kakao_text("CLAUDE_API_KEY 환경변수가 설정되지 않았습니다."))
    
    try:
        response = client_claude.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=400,
            system="당신은 친절한 학교 생활 도우미 챗봇입니다. 학생의 질문에 상냥하고 간결하게 답해주세요.",
            messages=[
                {"role": "user", "content": user_question}
            ]
        )
        reply = f"🦅 [Claude 답변]\n\n{response.content[0].text.strip()}"
    except Exception as e:
        reply = f"Claude 호출 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(reply))


# =========================================================
# 기존 제공해주신 기타 기능들 (유지)
# =========================================================
@app.route("/text", methods=["GET", "POST"])
def text_skill():
    return jsonify(kakao_text(str(random.randint(1, 10))))

@app.route("/echo", methods=["POST"])
def echo_skill():
    data = request.get_json(silent=True) or {}
    user_input = data.get("userRequest", {}).get("utterance", "입력값이 없습니다.")
    return jsonify(kakao_text(user_input))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
