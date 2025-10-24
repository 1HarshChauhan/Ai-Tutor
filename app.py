import streamlit as st
import google.generativeai as genai
import json
import speech_recognition as sr
from io import BytesIO
import base64

from dotenv import load_dotenv
load_dotenv()
# Configure your API key here
genai.configure(api_key=GEMINI_API_KEY)

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

# Function to convert speech to text
def speech_to_text():
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            st.info("🎤 Listening... Speak now!")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
            st.success("Processing your speech...")
            text = recognizer.recognize_google(audio)
            return text
    except sr.WaitTimeoutError:
        st.warning("No speech detected. Please try again.")
        return None
    except sr.UnknownValueError:
        st.warning("Could not understand the audio. Please try again.")
        return None
    except sr.RequestError as e:
        st.error(f"Could not request results; {e}")
        return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

# Function to generate speech using Edge TTS (better quality, free)
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
    except ImportError:
        st.error("Please install edge-tts: pip install edge-tts")
        return None
    except Exception as e:
        st.error(f"Error in text-to-speech: {str(e)}")
        return None

# Title
st.title("🎓 AI Tutor with Voice Assistant")
st.markdown("Learn any topic with explanations, quizzes, and voice interaction!")
st.markdown("---")

# Topic input
topic = st.text_input("Enter the topic you want to learn about:", placeholder="e.g., Photosynthesis, Machine Learning, French Revolution")

if st.button("Generate Lesson", type="primary"):
    if topic:
        with st.spinner("Generating explanation and quiz..."):
            try:
                # Generate explanation
                explanation_prompt = f"""Explain the topic '{topic}' in a clear, comprehensive, and educational manner. 
                Include key concepts, examples, and make it easy to understand for learners. 
                Use markdown formatting for better readability. Keep it concise but informative (around 300-400 words)."""
                
                explanation_response = model.generate_content(explanation_prompt)
                st.session_state.explanation = explanation_response.text
                st.session_state.current_topic = topic
                
                # Generate MCQs
                mcq_prompt = f"""Based on the topic '{topic}', generate exactly 5 multiple choice questions (MCQs).
                
                Format your response as a JSON array with this exact structure:
                [
                    {{
                        "question": "Question text here?",
                        "options": ["Option A", "Option B", "Option C", "Option D"],
                        "correct_answer": 0,
                        "explanation": "Brief explanation of why this is correct"
                    }}
                ]
                
                Make sure:
                - Questions test understanding, not just memorization
                - All options are plausible
                - correct_answer is the index (0-3) of the correct option
                - Include brief explanations
                
                Return ONLY the JSON array, no additional text."""
                
                mcq_response = model.generate_content(mcq_prompt)
                mcq_text = mcq_response.text.strip()
                
                # Extract JSON from response
                if "```json" in mcq_text:
                    mcq_text = mcq_text.split("```json")[1].split("```")[0].strip()
                elif "```" in mcq_text:
                    mcq_text = mcq_text.split("```")[1].split("```")[0].strip()
                
                st.session_state.mcqs = json.loads(mcq_text)
                st.session_state.submitted = False
                st.session_state.user_answers = {}
                st.session_state.chat_history = []
                
                st.success("Lesson generated successfully!")
                st.rerun()
                
            except Exception as e:
                st.error(f"Error generating content: {str(e)}")
    else:
        st.warning("Please enter a topic first!")

# Display content
if st.session_state.explanation:
    st.markdown("---")
    st.header("📚 Explanation")
    st.markdown(st.session_state.explanation)
    
if st.session_state.mcqs:
    st.markdown("---")
    st.header("📝 Quiz Time!")
    st.write("Test your understanding with these questions:")
    
    # Display MCQs
    for idx, mcq in enumerate(st.session_state.mcqs):
        st.subheader(f"Question {idx + 1}")
        st.write(mcq['question'])
        
        # Radio button for options
        answer = st.radio(
            f"Select your answer:",
            options=range(len(mcq['options'])),
            format_func=lambda x: mcq['options'][x],
            key=f"q_{idx}",
            disabled=st.session_state.submitted
        )
        
        st.session_state.user_answers[idx] = answer
        
        # Show result if submitted
        if st.session_state.submitted:
            if answer == mcq['correct_answer']:
                st.success("✅ Correct!")
            else:
                st.error(f"❌ Incorrect. The correct answer is: {mcq['options'][mcq['correct_answer']]}")
            st.info(f"💡 Explanation: {mcq['explanation']}")
        
        st.markdown("---")
    
    # Submit button
    if not st.session_state.submitted:
        if st.button("Submit Quiz", type="primary"):
            st.session_state.submitted = True
            st.rerun()
    else:
        # Calculate score
        score = sum(1 for idx, answer in st.session_state.user_answers.items() 
                   if answer == st.session_state.mcqs[idx]['correct_answer'])
        st.success(f"🎯 Your Score: {score}/{len(st.session_state.mcqs)}")

# Voice Chat Section (appears after quiz is generated)
if st.session_state.mcqs:
    st.markdown("---")
    st.header("💬 Ask Questions with Voice")
    st.write("Have doubts? Ask me anything about the topic!")
    
    # Display chat history
    if st.session_state.chat_history:
        st.subheader("📜 Conversation History")
        for message in st.session_state.chat_history:
            if message['role'] == 'user':
                st.markdown(f"**🧑 You:** {message['content']}")
            else:
                st.markdown(f"**🤖 Tutor:** {message['content']}")
            st.markdown("")
        st.markdown("---")
    
    # Input section
    col1, col2 = st.columns([3, 1])
    
    with col1:
        text_question = st.text_input("Type your question:", key="text_question", placeholder="Ask anything about the topic...")
    
    with col2:
        st.write("")
        use_voice = st.button("🎤 Use Voice", key="voice_button")
    
    # Handle voice input
    if use_voice:
        voice_question = speech_to_text()
        if voice_question:
            st.success(f"✅ Recognized: {voice_question}")
            text_question = voice_question
    
    # Process question
    if st.button("Ask Tutor", type="primary") or (use_voice and voice_question):
        question = text_question if text_question else (voice_question if use_voice else None)
        
        if question:
            # Add user question to chat
            st.session_state.chat_history.append({
                'role': 'user',
                'content': question
            })
            
            # Generate response
            with st.spinner("🤔 Thinking..."):
                try:
                    context = f"You are a helpful AI tutor. The student is learning about: {st.session_state.current_topic}.\n\n"
                    context += f"The explanation provided was:\n{st.session_state.explanation}\n\n"
                    context += "Previous conversation:\n"
                    for msg in st.session_state.chat_history[-6:-1]:
                        context += f"{msg['role']}: {msg['content']}\n"
                    
                    prompt = context + f"\nStudent's question: {question}\n\nProvide a clear, concise, and helpful answer (2-3 sentences unless more detail is needed)."
                    
                    response = model.generate_content(prompt)
                    answer = response.text
                    
                    # Add tutor response to chat
                    st.session_state.chat_history.append({
                        'role': 'assistant',
                        'content': answer
                    })
                    
                    # Generate audio for the response
                    st.session_state.audio_autoplay = text_to_speech_edge(answer)
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating response: {str(e)}")
        else:
            st.warning("Please type or speak your question!")
    
    # Auto-play audio if available
    if st.session_state.audio_autoplay:
        st.markdown(st.session_state.audio_autoplay, unsafe_allow_html=True)
        st.session_state.audio_autoplay = None
    
    # Clear chat button
    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()

# Try another topic button
if st.session_state.explanation:
    st.markdown("---")
    if st.button("🔄 Try Another Topic"):
        st.session_state.explanation = None
        st.session_state.mcqs = None
        st.session_state.submitted = False
        st.session_state.user_answers = {}
        st.session_state.current_topic = None
        st.session_state.chat_history = []
        st.rerun()