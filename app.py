import streamlit as st
import asyncio
import edge_tts
import srt
import io
from pydub import AudioSegment, effects

st.set_page_config(page_title="Khmer TTS - No Gap", page_icon="🎙️")

async def fetch_audio(text, voice, rate_str):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def generate_no_gap_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    # បង្កើតផ្ទៃសំឡេងទទេ
    total_ms = int(subs[-1].end.total_seconds() * 1000) + 500
    final_audio = AudioSegment.silent(duration=total_ms, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        audio_data = await fetch_audio(sub.content, voice, rate_str)
        if audio_data:
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            
            # ១. កាត់ផ្នែកស្ងាត់ចេញឱ្យអស់ពីដើម និងខាងចុងនៃ Clip នីមួយៗ
            segment = effects.strip_silence(segment, silence_thresh=-50, padding=0)

            start_ms = int(sub.start.total_seconds() * 1000)
            
            # រកម៉ោងត្រូវចាប់ផ្ដើមលេខរៀងបន្ទាប់ (ដកចន្លោះស្ងាត់ចេញទាំងស្រុង)
            if i + 1 < len(subs):
                next_start_ms = int(subs[i+1].start.total_seconds() * 1000)
                allowed_duration = next_start_ms - start_ms
                
                current_duration = len(segment)

                # ២. បង្ខំពន្លឿនឱ្យចប់ត្រឹមម៉ោងចាប់ផ្ដើមនៃ Subtitle បន្ទាប់តែម្ដង
                if current_duration > allowed_duration and allowed_duration > 0:
                    ratio = current_duration / allowed_duration
                    segment = effects.speedup(segment, playback_speed=min(ratio, 2.0), chunk_size=50, crossfade=15)
                    segment = segment[:allowed_duration] # តម្រឹមឱ្យហាប់បំផុត

            # ដាក់សំឡេងចូលតាមទីតាំង Start Time
            final_audio = final_audio.overlay(segment, position=start_ms)

    # ធ្វើឱ្យកម្រិតសំឡេងស្មើគ្នា
    final_audio = effects.normalize(final_audio)
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - កំណែអានជាប់គ្នា (No Gap)")
st.info("កូដនេះនឹងដកចន្លោះស្ងាត់ចេញទាំងស្រុង។ សំឡេងលេខរៀងបន្ទាប់នឹងចាប់ផ្ដើមភ្លាមៗ។")

voice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអានទូទៅ (%):", -50, 50, 15)
srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=250)

if st.button("🔊 ផលិតសំឡេងជាប់គ្នា"):
    if srt_text.strip():
        with st.spinner("កំពុងផលិតសំឡេង..."):
            audio = asyncio.run(generate_no_gap_audio(srt_text, voice, speed))
            if audio:
                st.audio(audio)
                st.download_button("📥 ទាញយក MP3", audio, "no_gap_khmer.mp3")
