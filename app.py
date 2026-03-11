import streamlit as st
import asyncio
import edge_tts
import srt
import io
from pydub import AudioSegment

st.set_page_config(page_title="Khmer TTS - Standard Audio Fix", page_icon="🎙️")

async def fetch_audio_chunk(text, voice, rate_str):
    """ប្រើវិធីផលិតសំឡេងដែលធ្លាប់ឮច្បាស់បំផុត"""
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
    
    # ១. ទាញយកសំឡេង (ប្រើបច្ចេកទេសដើមដែលឮច្បាស់)
    tasks = [fetch_audio_chunk(sub.content, voice, rate_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # ២. បង្កើត Timeline ស្ងាត់ (Silent) ជាមូលដ្ឋាន
    # យកម៉ោងបញ្ចប់នៃ SRT ចុងក្រោយបូកថែម ២ វិនាទី
    last_end_ms = int(subs[-1].end.total_seconds() * 1000) + 2000
    final_audio = AudioSegment.silent(duration=last_end_ms, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            # បំប្លែង chunk ទៅជា AudioSegment (មិនកែ Frame Rate ដើម្បីកុំឱ្យបាត់សំឡេង)
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # កំណត់ម៉ោងចាប់ផ្ដើមក្នុង SRT (ms)
            start_ms = int(sub.start.total_seconds() * 1000)
            
            # ប្រើ overlay ដើម្បីដាក់សំឡេងឱ្យចំម៉ោងចាប់ផ្ដើម
            # វិធីនេះធានាថាឮ ១០០% ហើយចាប់ផ្ដើមចំម៉ោងជានិច្ច
            final_audio = final_audio.overlay(segment, position=start_ms)

    # នាំចេញជា MP3 ក្នុងទម្រង់ Standard បំផុត
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="128k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Sync Fix")
st.info("💡 កូដនេះប្រើវិធីសាស្ត្រ Overlay ៖ ធានាថាឮសំឡេងច្បាស់ និងចាប់ផ្ដើមអានចំម៉ោង SRT។")

voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអាន (%):", -50, 100, 20)
srt_input = st.text_area("បញ្ចូលអក្សរ SRT របស់អ្នក:", height=300)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងផលិត..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed))
            if final_audio:
                st.audio(final_audio, format="audio/mp3")
                st.download_button("📥 ទាញយក MP3", final_audio, "khmer_sync_audio.mp3")
