import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment
from pydub.effects import speedup

# ១. កំណត់ការបង្ហាញទំព័រ
st.set_page_config(page_title="Khmer TTS Sync Pro", page_icon="🎙️")

# ២. Function ជំនួយសម្រាប់កែសម្រួលសំឡេង
def trim_audio_silence(audio, threshold=-50.0):
    start_trim = 0
    while start_trim < len(audio) and audio[start_trim:start_trim+10].dBFS < threshold:
        start_trim += 10
    end_trim = 0
    while end_trim < len(audio) and audio[len(audio)-end_trim-10:len(audio)-end_trim].dBFS < threshold:
        end_trim += 10
    return audio[start_trim:len(audio)-end_trim]

async def fetch_audio_chunk(text, voice, rate_str):
    try:
        clean_text = re.sub(r'[^\u1780-\u17FF\u19E0-\u19FFa-zA-Z0-9\s\.\?\!]', '', text)
        if not clean_text.strip(): return None
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def process_sync_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except:
        st.error("ទម្រង់ SRT មិនត្រឹមត្រូវ!")
        return None

    rate_str = f"{base_speed:+d}%"
    total_ms = int(subs[-1].end.total_seconds() * 1000) + 1000
    final_audio = AudioSegment.silent(duration=total_ms, frame_rate=44100)

    progress_bar = st.progress(0)
    for i, sub in enumerate(subs):
        audio_data = await fetch_audio_chunk(sub.content, voice, rate_str)
        if audio_data:
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            segment = trim_audio_silence(segment)
            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            target_dur = end_ms - start_ms
            
            if len(segment) > target_dur and target_dur > 0:
                ratio = len(segment) / target_dur
                segment = speedup(segment, playback_speed=min(ratio, 2.2), chunk_size=50, crossfade=15)
                segment = segment[:target_dur]
            
            final_audio = final_audio.overlay(segment, position=start_ms)
        progress_bar.progress((i + 1) / len(subs))

    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="128k")
    return buffer.getvalue()

# ៣. ផ្នែក UI
st.title("🎙️ Khmer TTS Sync Pro")
voice_choice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿន (%):", -50, 100, 25)
srt_input = st.text_area("បញ្ចូល SRT:", height=250)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        # ប្រើ loop ដើម្បីចៀសវាងការគាំងលើ Cloud
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        final_mp3 = loop.run_until_complete(process_sync_audio(srt_input, voice_choice, speed))
        
        if final_mp3:
            st.audio(final_mp3)
            st.download_button("📥 ទាញយក MP3", final_mp3, "audio.mp3")
