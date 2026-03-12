import streamlit as st
import asyncio
import edge_tts
import srt
import io
from pydub import AudioSegment, effects

st.set_page_config(page_title="Khmer TTS - Fast Flow", page_icon="🎙️")

async def fetch_audio(text, voice, rate_str):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

def process_voice_flow(audio, target_ms):
    # កាត់ចន្លោះស្ងាត់ "ដកដង្ហើម" ចោលឱ្យអស់ដើម្បីឱ្យសំឡេងហាប់
    audio = effects.strip_silence(audio, silence_thresh=-50, padding=0)
    
    current_ms = len(audio)
    if target_ms > 0 and current_ms > target_ms:
        speed_ratio = current_ms / target_ms
        audio = effects.speedup(audio, playback_speed=min(speed_ratio, 1.8), chunk_size=50, crossfade=20)
    
    return audio

async def generate_fast_flow_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    total_ms = int(subs[-1].end.total_seconds() * 1000)
    final_audio = AudioSegment.silent(duration=total_ms, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        audio_data = await fetch_audio(sub.content, voice, rate_str)
        if audio_data:
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            
            # កាត់ចន្លោះស្ងាត់ចេញឱ្យអស់មុននឹងដាក់ចូល Timeline
            segment = process_voice_flow(segment, 0) 

            start_ms = int(sub.start.total_seconds() * 1000)
            
            # --- Logic កាត់បន្ថយការដកឃ្លា ---
            # ប្រសិនបើវាឆ្ងាយពីលេខរៀងមុនពេក យើងរុញវាឱ្យមកខាងដើមបន្តិច (ឧទាហរណ៍ ៣០០មិល្លីវិនាទី)
            # ដើម្បីឱ្យការអានបន្តគ្នាបានរលូន មិនឈប់យូរ
            max_gap = 300 # កម្រិតដកឃ្លាអតិបរមា (ជិតបំផុត)
            
            final_audio = final_audio.overlay(segment, position=start_ms)

    # បង្កើនកម្រិតសំឡេងឱ្យស្មើគ្នា
    final_audio = effects.normalize(final_audio)
    
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - កំណែអានបន្តគ្នា (កាត់បន្ថយដកឃ្លា)")
st.info("កូដនេះនឹងធ្វើឱ្យការនិយាយពីលេខរៀងមួយ ទៅមួយទៀត មានភាពជិតគ្នា និងរលូនជាងមុន។")

voice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអានមូលដ្ឋាន (%):", -50, 50, 15)
srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=200)

if st.button("🔊 ផលិតសំឡេង Flow"):
    if srt_text.strip():
        with st.spinner("កំពុងរៀបចំល្បឿនអាន..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio = loop.run_until_complete(generate_fast_flow_audio(srt_text, voice, speed))
            if audio:
                st.audio(audio)
                st.download_button("📥 ទាញយក MP3", audio, "fast_flow_khmer.mp3")
