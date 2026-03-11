import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment
from pydub.effects import normalize

st.set_page_config(page_title="Khmer TTS - Audio Final Fix", page_icon="🎙️")

async def fetch_audio_chunk(text, voice, rate_str):
    try:
        # សម្អាតអត្ថបទឱ្យស្អាតបំផុត
        clean_text = re.sub(r'[^\u1780-\u17FF\u19E0-\u19FFa-zA-Z0-9\s\.]', '', text)
        if not clean_text.strip(): return None
        
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def generate_audio(srt_content, voice, rate):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{rate:+d}%"
    tasks = [fetch_audio_chunk(sub.content, voice, rate_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # បង្កើត Timeline សំឡេង (WAV format ជួយឱ្យឮច្បាស់គ្រប់ឧបករណ៍)
    final_combined = AudioSegment.silent(duration=0, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            # អានសំឡេងដែលទាញបាន
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            
            # បញ្ចូល Silence ឱ្យចំម៉ោងចាប់ផ្ដើម
            if srt_start_ms > len(final_combined):
                final_combined += AudioSegment.silent(duration=srt_start_ms - len(final_combined), frame_rate=44100)
            
            # បញ្ចូលសំឡេងចូលគ្នា
            final_combined = final_combined.overlay(segment, position=srt_start_ms)
            
            # បង្គ្រប់ម៉ោងឱ្យដល់ End Time
            if len(final_combined) < srt_end_ms:
                final_combined += AudioSegment.silent(duration=srt_end_ms - len(final_combined), frame_rate=44100)

    if len(final_combined) == 0: return None

    # ធ្វើឱ្យសំឡេងឮខ្លាំងច្បាស់
    final_combined = normalize(final_combined)

    # នាំចេញជា WAV (ធានាថាឮ ១០០%)
    buffer = io.BytesIO()
    final_combined.export(buffer, format="wav")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Audio Fix")

voice_choice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿន (%):", -50, 100, 20)
srt_input = st.text_area("បញ្ចូល SRT:", height=300)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងផលិត..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed))
            if final_audio:
                st.audio(final_audio, format="audio/wav")
                st.download_button("📥 ទាញយក WAV (ឮច្បាស់)", final_audio, "khmer_voice.wav", mime="audio/wav")
