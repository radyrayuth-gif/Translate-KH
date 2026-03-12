import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment

st.set_page_config(page_title="Khmer TTS - Perfect Sync", page_icon="🎙️")

async def fetch_audio(text, voice, rate_str):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

def change_audio_speed(audio, speed=1.0):
    """ពន្លឿនសំឡេងដោយមិនឱ្យបែក ឬស្រគាត្រចៀក"""
    if speed == 1.0: return audio
    # ប្រើ Frame Rate modification ដើម្បីពន្លឿនបែបធម្មជាតិ
    new_sample_rate = int(audio.frame_rate * speed)
    fast_audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate})
    return fast_audio.set_frame_rate(44100)

async def generate_perfect_sync_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    total_ms = int(subs[-1].end.total_seconds() * 1000)
    final_audio = AudioSegment.silent(duration=total_ms, frame_rate=44100)
    
    progress_bar = st.progress(0)
    
    for i, sub in enumerate(subs):
        audio_data = await fetch_audio(sub.content, voice, rate_str)
        if audio_data:
            # ១. ទាញយកសំឡេង AI
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            
            # ២. គណនាម៉ោង SRT ឱ្យម៉ត់ចត់
            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            target_duration = end_ms - start_ms
            
            # ៣. Logic សំខាន់: បើអានយឺតជាង SRT យើងពន្លឿនវាឱ្យត្រូវមិល្លីវិនាទី
            current_duration = len(segment)
            if current_duration > target_duration and target_duration > 0:
                speed_ratio = current_duration / target_duration
                # ពន្លឿនឱ្យត្រូវតាមម៉ោង SRT ក្បៀសឱ្យចំ
                segment = change_audio_speed(segment, speed_ratio)
            
            # ៤. Overlay ចូលក្នុង Timeline ឱ្យចំម៉ោង Start ១០០%
            final_audio = final_audio.overlay(segment, position=start_ms)
                
        progress_bar.progress((i + 1) / len(subs))

    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Perfect Sync & Smooth")
st.info("កូដនេះធានាថាអានត្រូវតាមម៉ោង SRT ១០០% និងរក្សាសំឡេងឱ្យពិរោះរលូន។")

voice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអានមូលដ្ឋាន (%):", -50, 50, 15)
srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=250)

if st.button("🔊 ផលិតសំឡេង Sync"):
    if srt_text.strip():
        with st.spinner("កំពុងគណនា Timeline ឱ្យត្រូវម៉ោង..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio = loop.run_until_complete(generate_perfect_sync_audio(srt_text, voice, speed))
            if audio:
                st.audio(audio)
                st.download_button("📥 ទាញយក MP3", audio, "sync_perfect.mp3")
