import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment
from pydub.effects import speedup, normalize

st.set_page_config(page_title="Khmer TTS - Audio Final Fix", page_icon="🎙️")

async def fetch_audio_chunk(text, voice, rate_str, pitch_str):
    try:
        # សម្អាតអត្ថបទឱ្យស្អាតបំផុត
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

    # បង្កើត Timeline ទទេ
    final_combined = AudioSegment.silent(duration=0, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            # អានសំឡេងដែលទាញបាន
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            target_duration = srt_end_ms - srt_start_ms
            
            # ពន្លឿនសំឡេងបើវាវែងជាងម៉ោង SRT (ប្រើ speedup ឮច្បាស់ជាង)
            current_dur = len(segment)
            if current_dur > target_duration and target_duration > 500:
                ratio = current_dur / target_duration
                if ratio > 1.1:
                    segment = speedup(segment, playback_speed=ratio, chunk_size=150, crossfade=25)
            
            # បញ្ចូលក្នុង Timeline
            if srt_start_ms > len(final_combined):
                final_combined += AudioSegment.silent(duration=srt_start_ms - len(final_combined))
            
            final_combined = final_combined.overlay(segment, position=srt_start_ms)
            
            if len(final_combined) < srt_end_ms:
                final_combined += AudioSegment.silent(duration=srt_end_ms - len(final_combined))

    if len(final_combined) == 0: return None

    # ធ្វើឱ្យសំឡេងឮខ្លាំង និងតុល្យភាព (Normalize)
    final_combined = normalize(final_combined)

    # នាំចេញជា MP3 គុណភាពខ្ពស់
    buffer = io.BytesIO()
    final_combined.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Audio Fix")

voice_choice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿន (%):", -50, 100, 20)
srt_input = st.text_area("បញ្ចូល SRT របស់អ្នក:", height=300)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងផលិតសំឡេង..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed, 0))
            if final_audio:
                st.audio(final_audio, format="audio/mp3")
                st.download_button("📥 ទាញយក MP3 ដើម្បីស្ដាប់", final_audio, "khmer_voice.mp3", mime="audio/mp3")
            else:
                st.error("មិនអាចផលិតសំឡេងបានទេ។ សូមពិនិត្យ SRT របស់បង។")
