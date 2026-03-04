import streamlit as st
import whisper
import os
from googletrans import Translator
from moviepy.editor import VideoFileClip

st.set_page_config(page_title="បកប្រែវីដេអូចិន-ខ្មែរ", page_icon="🇨🇳")

st.title("🎥 កម្មវិធីបកប្រែវីដេអូចិន មកជាភាសាខ្មែរ")
st.markdown("បង្ហោះវីដេអូចិនរបស់អ្នក ដើម្បីបម្លែងជាអក្សរខ្មែរដោយស្វ័យប្រវត្តិ")

# Load Whisper Model
@st.cache_resource
def load_model():
    return whisper.load_model("base")

model = load_model()
translator = Translator()

uploaded_file = st.file_uploader("ជ្រើសរើសវីដេអូ (MP4, MOV, AVI)", type=["mp4", "mov", "avi"])

if uploaded_file is not None:
    # បង្ហាញវីដេអូដែលបាន Upload
    st.video(uploaded_file)
    
    if st.button("ចាប់ផ្ដើមបកប្រែ"):
        with st.spinner('កំពុងដំណើរការ... សូមរង់ចាំបន្តិច (វាអាចប្រើពេលតាមទំហំវីដេអូ)'):
            # ១. រក្សាទុកឯកសារបណ្ដោះអាសន្ន
            with open("temp_video.mp4", "wb") as f:
                f.write(uploaded_file.getbuffer())

            # ២. បម្លែងសំឡេងទៅជាអក្សរ (Transcription)
            result = model.transcribe("temp_video.mp4")
            chinese_text = result['text']

            # ៣. បកប្រែមកជាភាសាខ្មែរ
            translation = translator.translate(chinese_text, src='zh-cn', dest='km')
            khmer_text = translation.text

            # ៤. បង្ហាញលទ្ធផល
            st.success("ការបកប្រែរួចរាល់!")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("អក្សរចិន (Original)")
                st.write(chinese_text)
            
            with col2:
                st.subheader("អក្សរខ្មែរ (Translated)")
                st.write(khmer_text)

            # លុបឯកសារចោលវិញ
            os.remove("temp_video.mp4")
          
