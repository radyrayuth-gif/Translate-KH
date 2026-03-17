import streamlit as st
import asyncio
import edge_tts
import srt
import io
from pydub import AudioSegment, effects

st.set_page_config(page_title="Khmer TTS - CapCut Style", page_icon="🎙️")

async def fetch_audio(text, voice, rate_str):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def generate_no_gap_audio(srt_content, voice, multiplier):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    # បំប្លែងពី multiplier (1.0x) ទៅជាភាគរយសម្រាប់ edge-tts
    # រូបមន្ត៖ (multiplier - 1) * 100
    percentage = int((multiplier - 1) * 100)
    rate_str = f"{percentage:+d}%"
    
    total_ms = int(subs[-1].end.total_seconds() * 1000) + 500
    final_audio = AudioSegment.silent(duration=total_ms, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        audio_data = await fetch_audio(sub.content, voice, rate_str)
        if audio_data:
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            segment = effects.strip_silence(segment, silence_thresh=-50, padding=0)

            start_ms = int(sub.start.total_seconds() * 1000)
            
            if i + 1 < len(subs):
                next_start_ms = int(subs[i+1].start.total_seconds() * 1000)
                allowed_duration = next_start_ms - start_ms
                current_duration = len(segment)

                if current_duration > allowed_duration and allowed_duration > 0:
                    ratio = current_duration / allowed_duration
                    segment = effects.speedup(segment, playback_speed=min(ratio, 2.0), chunk_size=50, crossfade=15)
                    segment = segment[:allowed_duration]

            final_audio = final_audio.overlay(segment, position=start_ms)

    final_audio = effects.normalize(final_audio)
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - CapCut Style")

col1, col2 = st.columns([2, 1])
with col1:
    voice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
with col2:
    # កំណត់ Slider ឱ្យដូច CapCut (ពី 0.5x ដល់ 2.0x)
    speed_multiplier = st.slider("ល្បឿនអាន (Speed):", 0.5, 2.0, 1.2, step=0.1, format="%.1fx")

srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=250)

if st.button("🔊 ផលិតសំឡេង (No Gap)", use_container_width=True):
    if srt_text.strip():
        with st.spinner(f"កំពុងផលិតក្នុងល្បឿន {speed_multiplier}x..."):
            audio = asyncio.run(generate_no_gap_audio(srt_text, voice, speed_multiplier))
            if audio:
                st.audio(audio)
                st.download_button("📥 ទាញយក MP3", audio, "capcut_style_khmer.mp3")
