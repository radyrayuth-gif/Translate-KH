import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment

st.set_page_config(page_title="Khmer TTS - Perfect Timing", page_icon="⏱️")

async def fetch_audio_chunk(text, voice, rate_str):
    try:
        # សម្អាតអត្ថបទ កុំឱ្យមានសញ្ញាដែលធ្វើឱ្យ AI គាំង
        clean_text = re.sub(r'[^\u1780-\u17FF\u19E0-\u19FFa-zA-Z0-9\s\.\!\?]', '', text)
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
            # ១. បង្កើត segment សំឡេងពី AI
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # ២. គណនាម៉ោងក្នុង SRT
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            target_duration = srt_end_ms - srt_start_ms
            
            # ៣. បច្ចេកទេសបង្រួម ឬពង្រីកសំឡេងឱ្យត្រូវនឹងម៉ោង (Time Stretching)
            current_dur = len(segment)
            if target_duration > 100: # ការពារករណីម៉ោង SRT ខ្លីពេក
                # គណនា Ratio ដើម្បីឱ្យសំឡេងចប់ចំម៉ោង SRT
                speed_ratio = current_dur / target_duration
                # បង្ខំឱ្យ Frame Rate ប្រែប្រួលតាម Ratio (ល្បឿននឹងប្រែប្រួលតាមម៉ោង SRT)
                segment = segment._spawn(segment.raw_data, overrides={
                    "frame_rate": int(segment.frame_rate * speed_ratio)
                }).set_frame_rate(segment.frame_rate)

            # ៤. បញ្ចូលក្នុង Timeline ឱ្យចំម៉ោងចាប់ផ្ដើម
            curr_len = len(final_audio)
            if srt_start_ms > curr_len:
                final_audio += AudioSegment.silent(duration=srt_start_ms - curr_len)
            
            # ប្រើ overlay ដើម្បីធានាថាវាចាប់ផ្ដើមចំម៉ោង start បេះបិទ
            final_audio = final_audio.overlay(segment, position=srt_start_ms)
            
            # បង្គ្រប់ Silence ឱ្យដល់ម៉ោងបញ្ចប់ ដើម្បីឱ្យ Timeline បន្តទៅមុខត្រឹមត្រូវ
            if len(final_audio) < srt_end_ms:
                final_audio += AudioSegment.silent(duration=srt_end_ms - len(final_audio))

    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="128k")
    return buffer.getvalue()

# --- UI ---
st.title("⏱️ Khmer TTS - Perfect Timing")
st.markdown("សំឡេងនឹងត្រូវបាន **ពន្លឿន ឬបន្ថយ** ដោយស្វ័យប្រវត្តិឱ្យចប់ចំម៉ោងបញ្ចប់ក្នុង SRT។")

voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
base_speed = st.slider("ល្បឿនមូលដ្ឋាន (%):", -50, 100, 10)
srt_input = st.text_area("បញ្ចូល SRT របស់អ្នក:", height=300)

if st.button("🔊 ផលិតសំឡេងឱ្យត្រូវម៉ោង"):
    if srt_input.strip():
        with st.spinner("កំពុងគណនាម៉ោងឱ្យត្រូវនឹង SRT..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, base_speed))
            if final_audio:
                st.audio(final_audio, format="audio/mp3")
                st.download_button("📥 ទាញយក MP3", final_audio, "perfect_sync.mp3")
