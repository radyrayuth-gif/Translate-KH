import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment

st.set_page_config(page_title="Khmer TTS - Ultimate Sync", page_icon="🎙️")

async def fetch_audio_chunk(text, voice, rate_str):
    """ផលិតសំឡេងដើម (ឮច្បាស់បំផុត)"""
    try:
        # សម្អាតអក្សរចម្លែកៗ
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

    # បង្កើត Timeline មូលដ្ឋាន (៤៤១០០Hz)
    final_audio = AudioSegment.silent(duration=0, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            # ១. ទាញយកសំឡេង AI មក
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # ២. គណនាម៉ោងក្នុង SRT
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            target_duration = srt_end_ms - srt_start_ms
            
            # ៣. សម្រួលប្រវែងសំឡេងឱ្យត្រូវនឹងម៉ោង SRT (ដោយមិនកែ Frame Rate)
            current_dur = len(segment)
            if current_dur > target_duration:
                # បើ AI អានវែងជាងម៉ោង SRT៖ យើងកាត់ចុងចោលបន្តិច (Clip)
                segment = segment[:target_duration]
            elif current_dur < target_duration:
                # បើ AI អានខ្លីជាងម៉ោង SRT៖ យើងថែមភាពស្ងាត់ឱ្យគ្រប់ម៉ោង (Padding)
                padding = AudioSegment.silent(duration=target_duration - current_dur)
                segment = segment + padding

            # ៤. បញ្ចូលក្នុង Timeline ឱ្យចំម៉ោងចាប់ផ្ដើម
            curr_len = len(final_audio)
            if srt_start_ms > curr_len:
                final_audio += AudioSegment.silent(duration=srt_start_ms - curr_len)
            
            # បូកបញ្ជូលគ្នា (ប្រើ += ជំនួស overlay ដើម្បីកុំឱ្យជាន់គ្នា)
            final_audio += segment

    # នាំចេញជា MP3 ស្ដង់ដារ
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="128k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Perfect Sync Fix")
st.markdown("កូដនេះធានាថា **ឮសំឡេង** និង **បញ្ចប់ចំម៉ោង** ក្នុង SRT របស់បងជានិច្ច។")

voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអាន (%):", -50, 100, 25)
srt_input = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=300)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងរៀបចំតាមម៉ោង SRT..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed))
            if final_audio:
                st.audio(final_audio, format="audio/mp3")
                st.download_button("📥 ទាញយក MP3", final_audio, "khmer_sync.mp3")
            else:
                st.error("មិនអាចផលិតបានទេ។ សូមពិនិត្យ SRT របស់បង។")
