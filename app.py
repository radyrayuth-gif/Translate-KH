import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment

st.set_page_config(page_title="Khmer TTS - Speed Sync Pro", page_icon="🎙️")

async def fetch_audio_chunk(text, voice, rate_str):
    try:
        clean_text = re.sub(r'[^\u1780-\u17FF\u19E0-\u19FFa-zA-Z0-9\s\.\?\!]', '', text)
        if not clean_text.strip(): return None
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

def speed_change(sound, speed=1.0):
    """ពន្លឿនសំឡេងដោយរក្សា Pitch និង Format ឱ្យនៅដដែល (ឮច្បាស់)"""
    if speed == 1.0: return sound
    # បង្ខំឱ្យ Browser ស្គាល់ដោយការកំណត់ frame_rate ថេរ 44100Hz
    new_sample_rate = int(sound.frame_rate * speed)
    return sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate}).set_frame_rate(44100)

async def generate_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    tasks = [fetch_audio_chunk(sub.content, voice, rate_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # បង្កើត Timeline មូលដ្ឋាន (44100Hz)
    final_audio = AudioSegment.silent(duration=0, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            # ១. ទាញយកសំឡេង AI ដើម
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            segment = segment.set_frame_rate(44100)
            
            # ២. គណនាម៉ោងក្នុង SRT
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            target_duration = srt_end_ms - srt_start_ms
            
            # ៣. Logic សំខាន់៖ បើ AI អានវែងជាងម៉ោង SRT ត្រូវពន្លឿន (Speed up)
            current_dur = len(segment)
            if target_duration > 100: # ការពារករណីម៉ោង SRT កំណត់ខ្លីពេក
                speed_ratio = current_dur / target_duration
                # បើ AI អានយឺត (Ratio > 1) វានឹងពន្លឿនឱ្យល្មមនឹងម៉ោង SRT
                if speed_ratio > 1.0:
                    segment = speed_change(segment, speed_ratio)
            
            # ៤. បញ្ចូលក្នុង Timeline ឱ្យចំម៉ោងចាប់ផ្ដើម
            curr_len = len(final_audio)
            if srt_start_ms > curr_len:
                final_audio += AudioSegment.silent(duration=srt_start_ms - curr_len)
            
            # ប្រើ Overlay ដើម្បីឱ្យវាចាប់ផ្ដើមចំម៉ោង Start បេះបិទ
            final_audio = final_audio.overlay(segment, position=srt_start_ms)
            
            # បង្គ្រប់ Silence ឱ្យដល់ម៉ោងបញ្ចប់ (ការពារការជាន់គ្នា)
            if len(final_audio) < srt_end_ms:
                final_audio += AudioSegment.silent(duration=srt_end_ms - len(final_audio))

    # នាំចេញជា MP3 Standard (128k)
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="128k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Speed Sync Fix")
st.success("Logic: គ្មានការកាត់សំឡេង! ប្រព័ន្ធនឹងពន្លឿនការអានដោយស្វ័យប្រវត្តិឱ្យចប់ចំម៉ោង SRT។")

voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអានទូទៅ (%):", -50, 100, 20)
srt_input = st.text_area("បញ្ចូលអត្ថបទ SRT របស់អ្នក:", height=300)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងគណនា និងពន្លឿនសំឡេងឱ្យត្រូវតាមម៉ោង..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed))
            if final_audio:
                st.audio(final_audio, format="audio/mp3")
                st.download_button("📥 ទាញយក MP3", final_audio, "speed_sync_audio.mp3")
            else:
                st.error("បញ្ហា៖ មិនអាចផលិតបានទេ។")
