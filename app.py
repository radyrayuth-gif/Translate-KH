import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment
from pydub.effects import speedup

st.set_page_config(page_title="Khmer TTS HD - Sync", page_icon="🎙️")

async def fetch_audio(text, voice, rate_str):
    """ទាញយកសំឡេងដើមដែលមានគុណភាពខ្ពស់បំផុត"""
    try:
        # បន្ថែមពាក្យបញ្ជា '--write-subtitles' មិនចាំបាច់ទេ តែយើងបង្កើន Quality តាមរយៈ Communicate
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

def perfect_speed_sync(audio, target_ms):
    """ពន្លឿនសំឡេងឱ្យត្រូវម៉ោងដោយរក្សាសំឡេងឱ្យនៅច្បាស់ (High Fidelity)"""
    current_ms = len(audio)
    if target_ms <= 0 or current_ms <= target_ms:
        return audio
    
    # គណនាល្បឿនដែលត្រូវបង្កើន
    playback_speed = current_ms / target_ms
    
    # កម្រិតល្បឿនត្រឹម ២ដង ដើម្បីកុំឱ្យបែកសំឡេង
    if playback_speed > 2.0: playback_speed = 2.0
    
    # ប្រើ speedup ជាមួយ chunk_size ធំល្មម (60ms) ដើម្បីឱ្យសំឡេងថ្លា មិនស្រគាត្រចៀក
    # crossfade ជួយឱ្យការតភ្ជាប់រលកសំឡេងរលូន
    sync_audio = speedup(audio, playback_speed=playback_speed, chunk_size=60, crossfade=25)
    
    # កាត់តម្រឹមឱ្យចំម៉ោង SRT បន្ទាប់ពី Speedup រួច
    return sync_audio[:target_ms]

async def generate_hd_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    total_duration = int(subs[-1].end.total_seconds() * 1000)
    # បង្កើត Background ស្ងាត់ដែលមាន High Sample Rate (48kHz)
    final_audio = AudioSegment.silent(duration=total_duration, frame_rate=48000)
    
    progress_bar = st.progress(0)
    for i, sub in enumerate(subs):
        audio_data = await fetch_audio(sub.content, voice, rate_str)
        if audio_data:
            # អាន MP3 ឱ្យទៅជា Segment
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            
            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            target_ms = end_ms - start_ms
            
            # ធ្វើឱ្យសំឡេងត្រូវម៉ោង និងច្បាស់
            processed_segment = perfect_speed_sync(segment, target_ms)
            
            # Overlay ចូល Timeline
            final_audio = final_audio.overlay(processed_segment, position=start_ms)
            
        progress_bar.progress((i + 1) / len(subs))

    # Export ជា MP3 ជាមួយ Bitrate ខ្ពស់បំផុត (320kbps)
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="320k")
    return buffer.getvalue()

# --- UI Layout ---
st.title("🎙️ Khmer TTS HD & Sync")
st.success("កំណែថ្មី៖ បង្កើនកម្រិតសំឡេងឱ្យច្បាស់ (320kbps) និងប្រើបច្ចេកទេស Sync មិនឱ្យបែកសំឡេង។")

voice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអានមូលដ្ឋាន (%):", -50, 50, 0) # ដាក់ ០ ដើម្បីឱ្យច្បាស់បំផុត
srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=200)

if st.button("🔊 ផលិតសំឡេងកម្រិតច្បាស់"):
    if srt_text.strip():
        with st.spinner("កំពុងផលិតសំឡេងកម្រិត HD..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio = loop.run_until_complete(generate_hd_audio(srt_text, voice, speed))
            if audio:
                st.audio(audio)
                st.download_button("📥 ទាញយក MP3 (320kbps)", audio, "khmer_hd_sync.mp3")
