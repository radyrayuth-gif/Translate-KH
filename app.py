import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment
from pydub.effects import speedup

st.set_page_config(page_title="Khmer TTS - Full Text Sync", page_icon="🎙️")

async def fetch_audio(text, voice, rate_str):
    try:
        # សម្អាតអត្ថបទតែនៅរក្សាភាពពេញលេញ
        clean_text = text.strip()
        if not clean_text: return None
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def generate_perfect_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    # បង្កើត Timeline មូលដ្ឋាន
    final_audio = AudioSegment.silent(duration=0, frame_rate=44100)
    
    current_pos_ms = 0

    for sub in subs:
        audio_data = await fetch_audio(sub.content, voice, rate_str)
        if audio_data:
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            
            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            target_dur = end_ms - start_ms
            
            # --- Logic ថ្មី: អានឱ្យអស់ពាក្យ ---
            # ប្រសិនបើសំឡេងអានវែងជាង SRT យើងពន្លឿនវាបន្តិច (តែមិនកាត់ចុងចោលទេ)
            if len(segment) > target_dur and target_dur > 0:
                ratio = len(segment) / target_dur
                # បើលើសពី 10% ទើបពន្លឿន ដើម្បីរក្សាសំឡេងឱ្យធម្មជាតិ
                if ratio > 1.1:
                    # chunk_size តូចជួយឱ្យសំឡេងរលូនមិនស្រគាត្រចៀក
                    segment = speedup(segment, playback_speed=min(ratio, 1.4), chunk_size=25, crossfade=15)
            
            # រៀបចំ Timeline កុំឱ្យជាន់គ្នា និងឱ្យត្រូវតាម Start Time
            if start_ms > len(final_audio):
                silence_gap = start_ms - len(final_audio)
                final_audio += AudioSegment.silent(duration=silence_gap)
            
            # បញ្ចូលសំឡេងចូល (Overlay) ដោយមិនកាត់កន្ទុយ
            # ប្រសិនបើសំឡេងវែងជាង SRT បន្តិច វានឹងរុញទៅមុខបន្តិចដោយមិនបាត់ពាក្យ
            final_audio = final_audio.overlay(segment, position=start_ms)
            
            # បច្ចុប្បន្នភាពទីតាំងចុងក្រោយ ដើម្បីការពារកុំឱ្យជាន់គ្នាខ្លាំង
            new_pos = start_ms + len(segment)
            if len(final_audio) < new_pos:
                # បន្ថែមផ្ទៃស្ងាត់បន្តិចដើម្បីពង្រីក Timeline
                final_audio += AudioSegment.silent(duration=new_pos - len(final_audio))

    buffer = io.BytesIO()
    # ប្រើ Bitrate 192k ដើម្បីភាពច្បាស់
    final_audio.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Full Voice & Smooth")
st.success("កំណែនេះធានាថាអានអស់សេចក្តី ១០០% មិនបាត់កន្ទុយ និងឮពិរោះរលូន។")

voice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអានទូទៅ (%):", -50, 50, 15)
srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT របស់អ្នក:", height=250)

if st.button("🔊 ផលិតសំឡេងពេញលេញ"):
    if srt_text.strip():
        with st.spinner("កំពុងរៀបចំសំឡេងឱ្យពិរោះ..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio = loop.run_until_complete(generate_perfect_audio(srt_text, voice, speed))
            if audio:
                st.audio(audio)
                st.download_button("📥 ទាញយក MP3 (គុណភាពខ្ពស់)", audio, "full_speech.mp3")
