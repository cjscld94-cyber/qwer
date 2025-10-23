import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os

# 환경 변수 로드
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY=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"))

# 앱 제목
st.title("💬 GPT-5 Streamlit Chat")

# 사용자 입력
user_input = st.text_area("질문을 입력하세요:")

if st.button("응답 받기"):
    if user_input.strip() == "":
        st.warning("질문을 입력해주세요.")
    else:
        # OpenAI API 호출
        with st.spinner("GPT-5가 생각 중입니다..."):
            response = client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": "너는 친절한 과학 선생님이야."},
                    {"role": "user", "content": user_input}
                ]
            )
            answer = response.choices[0].message.content
            st.success("✅ 답변:")
            st.write(answer)

