import streamlit as st
import asyncio
import edge_tts
import srt
import io
from pydub import AudioSegment, effects

st.set_page_config(page_title="Khmer TTS - Minimal Gap", page_icon="🎙️")

async def fetch_audio(text, voice, rate_str):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def generate_minimal_gap_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    total_ms = int(subs[-1].end.total_seconds() * 1000) + 500
    final_audio = AudioSegment.silent(duration=total_ms, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        audio_data = await fetch_audio(sub.content, voice, rate_str)
        if audio_data:
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            
            # ១. កាត់ចន្លោះស្ងាត់ក្បាលកន្ទុយឱ្យអស់ពីសំឡេង AI
            segment = effects.strip_silence(segment, silence_thresh=-50, padding=0)

            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            
            # រកមើលម៉ោងចាប់ផ្ដើមលេខរៀងបន្ទាប់
            next_start_ms = int(subs[i+1].start.total_seconds() * 1000) if i + 1 < len(subs) else end_ms
            
            # ២. កំណត់ចន្លោះសម្រាកថេរ (Gap) ត្រឹមតែ 150ms (០.១៥ វិនាទី)
            fixed_gap = 150 
            allowed_duration = (next_start_ms - start_ms) - fixed_gap
            
            current_duration = len(segment)

            # ៣. បង្ខំពន្លឿនឱ្យចប់មុនពេលកំណត់ ដើម្បីសល់ចន្លោះស្ងាត់ខ្លី
            if current_duration > allowed_duration and allowed_duration > 0:
                ratio = current_duration / allowed_duration
                segment = effects.speedup(segment, playback_speed=min(ratio, 2.0), chunk_size=50, crossfade=15)
                segment = segment[:allowed_duration] # កាត់តម្រឹមឱ្យហាប់ណែន

            # Overlay ឱ្យចំម៉ោង Start
            final_audio = final_audio.overlay(segment, position=start_ms)

    final_audio = effects.normalize(final_audio)
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - កំណែដកឃ្លាខ្លីបំផុត")
st.success("កូដនេះបានកាត់បន្ថយចន្លោះស្ងាត់រវាងលេខរៀង មកនៅត្រឹមតែ ០.១៥ វិនាទីប៉ុណ្ណោះ។")

voice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអានទូទៅ (%):", -50, 50, 15)
srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=250)

if st.button("🔊 ផលិតសំឡេង Flow"):
    if srt_text.strip():
        with st.spinner("កំពុងផលិតសំឡេង..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio = loop.run_until_complete(generate_minimal_gap_audio(srt_text, voice, speed))
            if audio:
                st.audio(audio)
                st.download_button("📥 ទាញយក MP3", audio, "minimal_gap_khmer.mp3")
