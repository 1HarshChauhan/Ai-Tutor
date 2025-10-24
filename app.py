import streamlit as st
import google.generativeai as genai
import json
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import tempfile
import scipy.io.wavfile as wav
from io import BytesIO
import base64
import os

# Configure your API key securely using Streamlit Secrets
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Initialize the model
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Page config
st.set_page_config(page_title="AI Tutor", page_icon="🎓", layout="wide")

# Initialize session state
if 'explanation' not in st.session_state:
    st.session_state.explanation = None
if 'mcqs' not in st.session_state:
    st.session_state.mcqs = None
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'current_topic' not in st.session_state:
    st.session_state.current_topic = None
if 'audio_autoplay' not in st.session_state:
    st.session_state.audio_autoplay = None


# 🎤 Function to record voice using sounddevice
def record_audio(duration=5, fs=44100):
    try:
        st.info("🎙️ Recording... Speak now!")
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()
        st.success("✅ Recording complete!")
        return fs, recording
    except Exception as e:
        st.error(f"Error recording audio: {str(e)}")
        return None, None


# 🎧 Function to convert speech to text using SpeechRecognition
def speech_to_text():
    fs, audio_data = record_audio(duration=5)
    if audio_data is None:
        return None

    try:
        # Save recorded audio temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
            wav.write(tmpfile.name, fs, audio_data)
            tmp_path = tmpfile.name

        recognizer = sr.Recognizer()
        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio)
            os.remove(tmp_path)
            return text
    except sr.UnknownValueError:
        st.warning("Could not understand the audio. Please try again.")
    except sr.RequestError as e:
        st.error(f"Speech recognition service error: {e}")
    except Exception as e:
        st.error(f"Error in speech recognition: {str(e)}")
    return None


# 🗣️ Function to generate speech using Edge TTS
def text_to_speech_edge(text):
    try:
        import edge_tts
        import asyncio

        async def generate_speech():
            communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
            audio_data = BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.write(chunk["data"])
            return audio_data.getvalue()

        audio_bytes = asyncio.run(generate_speech())
        audio_base64 = base64.b64encode(audio_bytes).decode()
        audio_html = f'<audio autoplay><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>'
        return audio_html
    except Exception as e:
        st.error(f"Error in text-to-speech: {str(e)}")
        return None


# 🎓 UI
st.title("🎓 AI Tutor with Voice Assistant")
st.markdown("Learn any topic with explanations, quizzes, and voice interaction!")
st.markdown("---")

topic = st.text_input("Enter the topic you want to learn about:", placeholder="e.g., Photosynthesis, Machine Learning, French Revolution")

if st.button("Generate Lesson", type="primary"):
    if topic:
        with st.spinner("Generating explanation and quiz..."):
            try:
                # Generate explanation
                explanation_prompt = f"""Explain the topic '{topic}' clearly and comprehensively for learners.
                Include examples and keep it around 300-400 words, using markdown formatting."""

                explanation_response = model.generate_content(explanation_prompt)
                st.session_state.explanation = explanation_response.text
                st.session_state.current_topic = topic

                # Generate MCQs
                mcq_prompt = f"""
                Based on the topic '{topic}', generate exactly 5 multiple choice questions (MCQs).
                Return only a JSON array in this format:
                [
                    {{
                        "question": "Question text here?",
                        "options": ["A", "B", "C", "D"],
                        "correct_answer": 0,
                        "explanation": "Reason for correctness"
                    }}
                ]
                """

                mcq_response = model.generate_content(mcq_prompt)
                mcq_text = mcq_response.text.strip()

                if "```json" in mcq_text:
                    mcq_text = mcq_text.split("```json")[1].split("```")[0].strip()
                elif "```" in mcq_text:
                    mcq_text = mcq_text.split("```")[1].split("```")[0].strip()

                st.session_state.mcqs = json.loads(mcq_text)
                st.session_state.submitted = False
                st.session_state.user_answers = {}
                st.session_state.chat_history = []

                st.success("✅ Lesson generated successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"Error generating content: {str(e)}")
    else:
        st.warning("Please enter a topic first!")


# 📚 Display explanation
if st.session_state.explanation:
    st.markdown("---")
    st.header("📘 Explanation")
    st.markdown(st.session_state.explanation)

# 📝 Quiz Section
if st.session_state.mcqs:
    st.markdown("---")
    st.header("🧠 Quiz Time!")
    for idx, mcq in enumerate(st.session_state.mcqs):
        st.subheader(f"Question {idx + 1}")
        st.write(mcq['question'])
        answer = st.radio(
            f"Choose your answer:",
            options=range(len(mcq['options'])),
            format_func=lambda x: mcq['options'][x],
            key=f"q_{idx}",
            disabled=st.session_state.submitted
        )
        st.session_state.user_answers[idx] = answer

        if st.session_state.submitted:
            if answer == mcq['correct_answer']:
                st.success("✅ Correct!")
            else:
                st.error(f"❌ Correct answer: {mcq['options'][mcq['correct_answer']]}")
            st.info(f"💡 {mcq['explanation']}")

        st.markdown("---")

    if not st.session_state.submitted:
        if st.button("Submit Quiz", type="primary"):
            st.session_state.submitted = True
            st.rerun()
    else:
        score = sum(1 for i, a in st.session_state.user_answers.items()
                    if a == st.session_state.mcqs[i]['correct_answer'])
        st.success(f"🎯 Your Score: {score}/{len(st.session_state.mcqs)}")


# 🎤 Voice Chat Section
if st.session_state.mcqs:
    st.markdown("---")
    st.header("💬 Ask Questions with Voice")

    if st.session_state.chat_history:
        st.subheader("🗂️ Chat History")
        for msg in st.session_state.chat_history:
            role = "🧑 You" if msg["role"] == "user" else "🤖 Tutor"
            st.markdown(f"**{role}:** {msg['content']}")

    col1, col2 = st.columns([3, 1])
    with col1:
        text_question = st.text_input("Type your question:", key="text_question", placeholder="Ask anything...")
    with col2:
        use_voice = st.button("🎙️ Use Voice", key="voice_button")

    if use_voice:
        voice_question = speech_to_text()
        if voice_question:
            st.success(f"✅ Recognized: {voice_question}")
            text_question = voice_question

    if st.button("Ask Tutor", type="primary") or (use_voice and text_question):
        question = text_question.strip() if text_question else None
        if question:
            st.session_state.chat_history.append({'role': 'user', 'content': question})

            with st.spinner("🤔 Thinking..."):
                try:
                    context = f"You are an AI tutor. Topic: {st.session_state.current_topic}.\n\n"
                    context += f"Explanation:\n{st.session_state.explanation}\n\n"
                    for msg in st.session_state.chat_history[-6:-1]:
                        context += f"{msg['role']}: {msg['content']}\n"
                    prompt = context + f"\nStudent's question: {question}\nGive a clear, helpful answer."

                    response = model.generate_content(prompt)
                    answer = response.text

                    st.session_state.chat_history.append({'role': 'assistant', 'content': answer})
                    st.session_state.audio_autoplay = text_to_speech_edge(answer)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating response: {str(e)}")
        else:
            st.warning("Please type or speak your question!")

    if st.session_state.audio_autoplay:
        st.markdown(st.session_state.audio_autoplay, unsafe_allow_html=True)
        st.session_state.audio_autoplay = None

    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()

# 🔄 Reset button
if st.session_state.explanation:
    st.markdown("---")
    if st.button("🔁 Try Another Topic"):
        for key in ['explanation', 'mcqs', 'submitted', 'user_answers', 'current_topic', 'chat_history']:
            st.session_state[key] = None
        st.rerun()
