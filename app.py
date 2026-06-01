import os
import random
import requests
import urllib.parse
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI
from google import genai
# [추가] Anthropic(Claude) 라이브러리 임포트
import anthropic
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()

app = Flask(__name__)

# 각 AI 클라이언트 초기화
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

gemini_key = os.getenv("GEMINI_API_KEY")
client_gemini = genai.Client(api_key=gemini_key) if gemini_key else None

# [추가] Claude 클라이언트 초기화
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
# [시나리오 1: 질문] AI 선택형 질문 처리 엔드포인트 (Claude 포함)
# =========================================================
@app.route("/ask-ai", methods=["POST"])
def ask_ai():
    data = request.get_json(silent=True) or {}
    action = data.get("action", {})
    params = action.get("params", {})

    ai_type = params.get("ai_type", "ChatGPT").strip()
    user_question = params.get("user_question", "").strip()

    if not user_question:
        return jsonify(kakao_text("질문 내용을 입력해주세요! 용례: 'Claude한테 오늘 급식 맛있어? 라고 물어봐'"))

    # 1. ChatGPT 선택 시
    if "chatgpt" in ai_type.lower() or "gpt" in ai_type.lower():
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

    # 2. Gemini 선택 시
    elif "gemini" in ai_type.lower() or "제미나이" in ai_type:
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
            
    # 3. [추가] Claude 선택 시
    elif "claude" in ai_type.lower() or "클로드" in ai_type:
        if not client_claude:
            return jsonify(kakao_text("CLAUDE_API_KEY 환경변수가 설정되지 않았습니다."))
        try:
            # 비용과 속도가 합리적인 claude-3-5-haiku 모델을 사용합니다.
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
            
    else:
        reply = "지원하지 않는 AI 종류입니다. 'ChatGPT', 'Gemini', 'Claude' 중 하나를 선택해주세요."

    return jsonify(kakao_text(reply))


# 기존 제공해주신 기타 기능들
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
