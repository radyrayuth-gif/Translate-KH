import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment

st.set_page_config(page_title="Khmer TTS - Perfect Sync", page_icon="⏱️")

async def fetch_audio_chunk(text, voice, rate_str):
    try:
        # សម្អាតអក្សរ កុំឱ្យមានសញ្ញាដែលធ្វើឱ្យ AI គាំង
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

    # បង្កើត Timeline មូលដ្ឋាន (ប្រើ Frame Rate 44100)
    final_audio = AudioSegment.silent(duration=0, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            # ១. បង្កើត segment សំឡេងពី AI
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # ២. គណនាម៉ោងក្នុង SRT (Target Duration)
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            target_duration = srt_end_ms - srt_start_ms
            
            # ៣. បច្ចេកទេសបង្ខំល្បឿនឱ្យត្រូវនឹងម៉ោង (Perfect Sync Logic)
            current_dur = len(segment)
            if target_duration > 100: # ការពារករណីម៉ោងក្នុង SRT ខ្លីពេក
                # គណនាផលធៀបល្បឿន
                speed_ratio = current_dur / target_duration
                # បង្ខំកែ Frame Rate ដើម្បីឱ្យវាបញ្ចប់ចំម៉ោង (Time Stretching)
                segment = segment._spawn(segment.raw_data, overrides={
                    "frame_rate": int(segment.frame_rate * speed_ratio)
                }).set_frame_rate(segment.frame_rate)

            # ៤. បញ្ចូលក្នុង Timeline ឱ្យចំម៉ោងចាប់ផ្ដើម
            curr_len = len(final_audio)
            if srt_start_ms > curr_len:
                # ថែមចន្លោះស្ងាត់បើមិនទាន់ដល់ម៉ោងអាន
                final_audio += AudioSegment.silent(duration=srt_start_ms - curr_len)
            
            # ប្រើ overlay ដើម្បីធានាថាវាចាប់ផ្ដើមចំម៉ោង Start បេះបិទ
            # ដោយសារយើងបាន Stretch សំឡេងឱ្យត្រូវ Target Duration រួចហើយ វានឹងមិនជាន់គ្នាទេ
            final_audio = final_audio.overlay(segment, position=srt_start_ms)
            
            # បង្គ្រប់ Silence ឱ្យដល់ម៉ោងបញ្ចប់ ដើម្បីឱ្យ Timeline បន្តទៅមុខត្រឹមត្រូវ
            if len(final_audio) < srt_end_ms:
                final_audio += AudioSegment.silent(duration=srt_end_ms - len(final_audio))

    # នាំចេញជា MP3 Standard
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="128k")
    return buffer.getvalue()

# --- UI ---
st.title("⏱️ Khmer TTS - Perfect Timing")
st.success("កូដនេះនឹងបង្ខំ AI ឱ្យអានចប់ចំម៉ោងបញ្ចប់ក្នុង SRT បេះបិទ (ទោះអានញាប់ក៏ដោយ)។")

voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
base_speed = st.slider("ល្បឿនមូលដ្ឋាន (%):", -50, 100, 10)
srt_input = st.text_area("បញ្ចូលអត្ថបទ SRT របស់អ្នក:", height=300)

if st.button("🔊 ផលិតសំឡេង Sync ១០០%"):
    if srt_input.strip():
        with st.spinner("កំពុងគណនា និងច្របាច់សំឡេងឱ្យត្រូវម៉ោង..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, base_speed))
            if final_audio:
                st.audio(final_audio, format="audio/mp3")
                st.download_button("📥 ទាញយក MP3", final_audio, "perfect_timing_audio.mp3")
            else:
                st.error("បញ្ហា៖ មិនអាចផលិតសំឡេងបានទេ។")
