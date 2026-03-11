import streamlit as st
import asyncio
import edge_tts
import srt
import io
from pydub import AudioSegment

st.set_page_config(page_title="Khmer TTS - Standard Fix", page_icon="🎙️")

async def fetch_audio_chunk(text, voice, rate_str):
    """ប្រើ Logic ផលិតសំឡេងពីកូដដំបូង (ឮច្បាស់)"""
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except:
        return None

async def generate_audio(srt_content, voice, speed_val):
    try:
        subs = list(srt.parse(srt_content))
    except:
        return None

    rate_str = f"{speed_val:+d}%"
    
    # ១. ទាញយកសំឡេង (ប្រើបច្ចេកទេសដើម)
    tasks = [fetch_audio_chunk(sub.content, voice, rate_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # ២. រៀបចំ Timeline (ប្រើ overlay បែបសាមញ្ញបំផុតដើម្បីការពារការបាត់សំឡេង)
    # បង្កើត Silence ជាមូលដ្ឋានដែលមានប្រវែងវែងជាង SRT បន្តិច
    max_duration_ms = int(subs[-1].end.total_seconds() * 1000) + 1000
    final_audio = AudioSegment.silent(duration=max_duration_ms, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            # បំប្លែង chunk ទៅជា AudioSegment ដោយមិនកែ Speed (ដើម្បីកុំឱ្យខូចសំឡេង)
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # កំណត់ម៉ោងចាប់ផ្ដើមតាម SRT
            start_ms = int(sub.start.total_seconds() * 1000)
            
            # បញ្ចូលសំឡេងទៅក្នុង Timeline (Overlay ជួយឱ្យឮគ្រប់ឃ្លា ទោះអានលើសម៉ោងក៏ដោយ)
            final_audio = final_audio.overlay(segment, position=start_ms)

    # នាំចេញជា MP3 Standard
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="128k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Combined Version")
st.markdown("កូដនេះបូកបញ្ចូលគ្នា៖ សំឡេងច្បាស់ពី Version ដើម + ការតម្រៀបម៉ោងឱ្យ Sync ជាមួយវីដេអូ")

voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអាន (%):", -50, 100, 20)

srt_input = st.text_area("បញ្ចូលអក្សរ SRT របស់អ្នក:", height=300)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងផលិតសំឡេង..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed))
            if final_audio:
                st.audio(final_audio, format="audio/mp3")
                st.download_button("📥 ទាញយក MP3", final_audio, "khmer_voice.mp3")
            else:
                st.error("បញ្ហា៖ មិនអាចផលិតសំឡេងបានទេ។ សូមឆែក SRT របស់បង។")
