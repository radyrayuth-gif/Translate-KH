import streamlit as st
import asyncio
import edge_tts
import srt
import io
from pydub import AudioSegment

st.set_page_config(page_title="Khmer TTS - Natural Smooth", page_icon="🎙️")

async def fetch_audio(text, voice, rate_str):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def generate_natural_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    # បង្កើត Audio Segment ទទេសម្រាប់ចាប់ផ្ដើម
    combined_audio = AudioSegment.empty()
    
    progress_bar = st.progress(0)
    
    for i, sub in enumerate(subs):
        audio_data = await fetch_audio(sub.content, voice, rate_str)
        if audio_data:
            # ១. បំប្លែងទិន្នន័យជា Audio Segment
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            
            # ២. គណនារយៈពេលដែលត្រូវឈប់ (Silence) រវាងឃ្លា
            # យើងយកម៉ោងបញ្ចប់នៃឃ្លាមុន ដកជាមួយម៉ោងចាប់ផ្ដើមនៃឃ្លានេះ
            current_duration_ms = len(combined_audio)
            target_start_ms = int(sub.start.total_seconds() * 1000)
            
            if target_start_ms > current_duration_ms:
                silence_gap = target_start_ms - current_duration_ms
                combined_audio += AudioSegment.silent(duration=silence_gap)
            
            # ៣. បន្ថែមសំឡេងចូល និងប្រើ Crossfade តូចមួយ (50ms) ដើម្បីឱ្យសំឡេងតភ្ជាប់គ្នារលូន
            if len(combined_audio) > 0:
                combined_audio = combined_audio.append(segment, crossfade=50)
            else:
                combined_audio += segment
                
        progress_bar.progress((i + 1) / len(subs))

    # នាំចេញជា MP3 គុណភាពខ្ពស់
    buffer = io.BytesIO()
    combined_audio.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

# --- UI Layout ---
st.title("🎙️ Khmer TTS - កំណែអានរលូនធម្មជាតិ")
st.markdown("""
* **បច្ចេកទេសថ្មី:** ប្រើការតភ្ជាប់ខ្សែសំឡេង (Concatenation) ជំនួសឱ្យការ Overlay។
* **គុណសម្បត្តិ:** សំឡេងមិនដាច់ៗ ឮពិរោះរលូន និងតភ្ជាប់គ្នាបានល្អជាងមុន។
""")

col1, col2 = st.columns(2)
with col1:
    voice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
with col2:
    speed = st.slider("ល្បឿនអាន (%):", -50, 50, 10)

srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=250)

if st.button("🔊 ផលិតសំឡេងរលូន"):
    if srt_text.strip():
        with st.spinner("កំពុងផលិតសំឡេង..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio = loop.run_until_complete(generate_natural_audio(srt_text, voice, speed))
            if audio:
                st.audio(audio)
                st.download_button("📥 ទាញយក MP3", audio, "natural_khmer_audio.mp3")
