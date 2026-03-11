import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment
from pydub.effects import speedup

st.set_page_config(page_title="Khmer TTS - Audio Sync Fix", page_icon="🎙️")

async def fetch_audio_chunk(text, voice, rate_str, pitch_str):
    try:
        # សម្អាតអត្ថបទ (AI អានបានតែអក្សរ និងលេខ)
        clean_text = re.sub(r'[^\u1780-\u17FF\u19E0-\u19FFa-zA-Z0-9\s\.\,\?\!\-]', '', text)
        if not clean_text.strip(): return None
        
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate_str, pitch=pitch_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def generate_audio(srt_content, voice, rate, pitch):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{rate:+d}%"
    pitch_str = f"{pitch:+d}Hz"

    tasks = [fetch_audio_chunk(sub.content, voice, rate_str, pitch_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # បង្កើត Timeline ទទេ (Stereo, 44.1kHz)
    final_combined = AudioSegment.silent(duration=0, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            target_duration = srt_end_ms - srt_start_ms
            
            # --- បច្ចេកទេស Adjust ល្បឿនឱ្យត្រូវម៉ោង ---
            current_dur = len(segment)
            if current_dur > target_duration and target_duration > 500:
                ratio = current_dur / target_duration
                # បើ AI អានវែងជាងម៉ោង SRT យើងពន្លឿនវាដោយប្រើ speedup (ឮច្បាស់ជាង)
                if ratio > 1.1:
                    segment = speedup(segment, playback_speed=ratio)
            
            # បង្គ្រប់ Silence ឱ្យដល់ម៉ោង Start
            if srt_start_ms > len(final_combined):
                gap = srt_start_ms - len(final_combined)
                final_combined += AudioSegment.silent(duration=gap, frame_rate=44100)
            
            # បញ្ចូលសំឡេងចូលគ្នា
            final_combined = final_combined.overlay(segment, position=srt_start_ms)
            
            # បង្គ្រប់ម៉ោងឱ្យដល់ End Time ក្នុង SRT
            if len(final_combined) < srt_end_ms:
                final_combined += AudioSegment.silent(duration=srt_end_ms - len(final_combined), frame_rate=44100)

    if len(final_combined) == 0: return None

    # នាំចេញជា MP3 ជាមួយ Bitrate ខ្ពស់ដើម្បីឱ្យឮច្បាស់គ្រប់ឧបករណ៍
    buffer = io.BytesIO()
    final_combined.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Sync Fix")

voice_choice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿន (%):", -50, 100, 20)
srt_input = st.text_area("បញ្ចូល SRT:", height=300)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងដំណើរការផលិត..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed, 0))
            if final_audio:
                st.audio(final_audio, format="audio/mp3")
                st.download_button("📥 ទាញយក MP3", final_audio, "khmer_voice.mp3")
            else:
                st.error("មិនអាចផលិតសំឡេងបានទេ។ សូមពិនិត្យ SRT របស់បង។")
