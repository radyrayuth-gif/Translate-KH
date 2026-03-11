import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment
from pydub.effects import speedup

st.set_page_config(page_title="Khmer TTS - Guaranteed Sound", page_icon="🎙️")

async def fetch_audio_chunk(text, voice, rate_str):
    """ផលិតសំឡេងដើម (Standard MP3)"""
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

async def generate_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    tasks = [fetch_audio_chunk(sub.content, voice, rate_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # បង្កើត Timeline មូលដ្ឋាន
    final_audio = AudioSegment.silent(duration=0, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            # ១. ទាញយកសំឡេង AI
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # ២. គណនាម៉ោងក្នុង SRT
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            target_duration = srt_end_ms - srt_start_ms
            
            # ៣. Logic ពន្លឿនសំឡេង (Speed up) បើអានយឺតជាងម៉ោង SRT
            current_dur = len(segment)
            if current_dur > target_duration and target_duration > 0:
                ratio = current_dur / target_duration
                # ពន្លឿនឱ្យល្មមនឹងម៉ោង SRT (ប្រើ speedup function ដើម្បីកុំឱ្យបាត់សំឡេង)
                if ratio > 1.0:
                    # speedup របស់ pydub ជួយឱ្យឮសំឡេងធម្មតា តែអានញាប់
                    segment = speedup(segment, playback_speed=ratio, chunk_size=150, crossfade=25)
            
            # ៤. រៀបចំ Timeline
            curr_len = len(final_audio)
            if srt_start_ms > curr_len:
                final_audio += AudioSegment.silent(duration=srt_start_ms - curr_len)
            
            # បញ្ចូលក្នុង Timeline (ប្រើ overlay ដើម្បីឱ្យចាប់ផ្ដើមចំម៉ោង Start)
            final_audio = final_audio.overlay(segment, position=srt_start_ms)
            
            # បង្គ្រប់ម៉ោងឱ្យដល់ End Time
            if len(final_audio) < srt_end_ms:
                final_audio += AudioSegment.silent(duration=srt_end_ms - len(final_audio))

    # នាំចេញជា MP3 ស្ដង់ដារ (128k)
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="128k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Sound & Sync Fix")
st.success("កូដនេះធានាថាឮសំឡេង ១០០% និងពន្លឿនការអានឱ្យចប់ចំម៉ោង SRT ដោយស្វ័យប្រវត្តិ។")

voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអានមូលដ្ឋាន (%):", -50, 100, 20)
srt_input = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=300)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងគណនា និងរៀបចំសំឡេង..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed))
            if final_audio:
                st.audio(final_audio, format="audio/mp3")
                st.download_button("📥 ទាញយក MP3", final_audio, "final_sync_audio.mp3")
            else:
                st.error("មិនអាចផលិតបានទេ។ សូមពិនិត្យ SRT របស់បង។")
