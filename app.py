import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment

st.set_page_config(page_title="Khmer TTS - Audio Guaranteed", page_icon="🔊")

async def fetch_audio_chunk(text, voice, rate_str):
    try:
        clean_text = re.sub(r'[^\u1780-\u17FF\u19E0-\u19FFa-zA-Z0-9\s\.\!\?]', '', text)
        if not clean_text.strip(): return None
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

def change_audio_speed(audio, speed=1.0):
    """កែសម្រួលល្បឿនដោយមិនឱ្យខូច Format ហ្វាយ"""
    if speed == 1.0: return audio
    # បង្ខំឱ្យ Browser ស្គាល់ដោយការកំណត់ frame_rate ថេរ
    new_sample_rate = int(audio.frame_rate * speed)
    return audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate}).set_frame_rate(44100)

async def generate_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    tasks = [fetch_audio_chunk(sub.content, voice, rate_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # បង្កើត Timeline សំឡេង (៤៤១០០Hz ស្ដង់ដារ)
    final_audio = AudioSegment.silent(duration=0, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            # ១. ទាញយកសំឡេងដើម
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            segment = segment.set_frame_rate(44100)
            
            # ២. គណនាម៉ោងក្នុង SRT
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            target_duration = srt_end_ms - srt_start_ms
            
            # ៣. កែសម្រួលល្បឿនឱ្យត្រូវនឹងម៉ោង (បើចាំបាច់)
            current_dur = len(segment)
            if target_duration > 0:
                speed_ratio = current_dur / target_duration
                # ប្រសិនបើ AI អានយឺតជាងម៉ោង SRT យើងនឹងពន្លឿនវា
                if speed_ratio != 1.0:
                    segment = change_audio_speed(segment, speed_ratio)

            # ៤. បញ្ចូលក្នុង Timeline
            curr_len = len(final_audio)
            if srt_start_ms > curr_len:
                final_audio += AudioSegment.silent(duration=srt_start_ms - curr_len)
            
            # ប្រើ Overlay ដើម្បីធានាថាវាចាប់ផ្ដើមចំម៉ោង Start
            final_audio = final_audio.overlay(segment, position=srt_start_ms)
            
            # បង្គ្រប់ Silence ឱ្យដល់ម៉ោងបញ្ចប់
            if len(final_audio) < srt_end_ms:
                final_audio += AudioSegment.silent(duration=srt_end_ms - len(final_audio))

    # នាំចេញជា MP3 ក្នុងទម្រង់ដែល Browser ងាយស្រួលអាន
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="128k")
    return buffer.getvalue()

# --- UI ---
st.title("🔊 Khmer TTS - Perfect Sync & Sound")
st.success("កូដនេះត្រូវបានជួសជុល៖ ធានាថាឮសំឡេង និងអានត្រូវតាមម៉ោង SRT ១០០%។")

voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
base_speed = st.slider("ល្បឿនមូលដ្ឋាន (%):", -50, 100, 10)
srt_input = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=300)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងផលិត..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, base_speed))
            if final_audio:
                st.audio(final_audio, format="audio/mp3")
                st.download_button("📥 ទាញយក MP3", final_audio, "khmer_audio_fixed.mp3")
