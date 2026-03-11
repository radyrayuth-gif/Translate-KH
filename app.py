import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment

# --- កំណត់ទំព័រ ---
st.set_page_config(page_title="Khmer TTS - Fixed Audio", page_icon="🎙️")

async def fetch_audio_chunk(text, voice, rate_str, pitch_str):
    """ទាញយកសំឡេងពី Microsoft Edge TTS"""
    try:
        # លុបសញ្ញាដែលអាចធ្វើឱ្យ AI គាំង
        clean_text = re.sub(r'[^\u1780-\u17FF\u19E0-\u19FFa-zA-Z0-9\s]', '', text)
        if not clean_text.strip(): return None
        
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate_str, pitch=pitch_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except Exception as e:
        return None

async def generate_audio(srt_content, voice, rate, pitch):
    try:
        subs = list(srt.parse(srt_content))
    except Exception as e:
        st.error(f"ទម្រង់ SRT មិនត្រឹមត្រូវ៖ {e}")
        return None

    if not subs:
        st.warning("រកមិនឃើញអត្ថបទក្នុង SRT ទេ។")
        return None
    
    rate_str = f"{rate:+d}%"
    pitch_str = f"{pitch:+d}Hz"

    # ១. ទាញយកសំឡេង
    tasks = [fetch_audio_chunk(sub.content, voice, rate_str, pitch_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # ២. បញ្ចូលសំឡេង (Perfect Sync Logic)
    final_combined = AudioSegment.silent(duration=0)
    found_audio = False
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            found_audio = True
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # កំណត់ម៉ោង
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            
            current_len = len(final_combined)
            if srt_start_ms > current_len:
                final_combined += AudioSegment.silent(duration=srt_start_ms - current_len)
            
            final_combined = final_combined.overlay(segment, position=srt_start_ms)
            
            # ពង្រីក Duration ឱ្យដល់ម៉ោងបញ្ចប់ក្នុង SRT
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            if len(final_combined) < srt_end_ms:
                final_combined += AudioSegment.silent(duration=srt_end_ms - len(final_combined))

    if not found_audio:
        return None

    buffer = io.BytesIO()
    final_combined.export(buffer, format="mp3")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Sync Fix")

with st.sidebar:
    voice_choice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
    speed = st.slider("ល្បឿន (%):", -50, 100, 20)
    pitch = st.slider("កម្រិតសំឡេង (Hz):", -20, 20, 0)

srt_input = st.text_area("បញ្ចូល SRT របស់អ្នកនៅទីនេះ:", height=300)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងទាញយកសំឡេងពី Server..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed, pitch))
            if final_audio and len(final_audio) > 500: # ត្រូវមានទិន្នន័យលើសពី 500 bytes
                st.success("ផលិតបានជោគជ័យ!")
                st.audio(final_audio)
                st.download_button("📥 ទាញយក MP3", final_audio, "khmer_audio.mp3")
            else:
                st.error("⚠️ អត់ឮសំឡេង៖ ម៉ាស៊ីនមិនអាចទាញយកសំឡេងបានទេ។ សូមឆែកអត្ថបទ SRT ឬអ៊ីនធឺណិតរបស់អ្នក។")
    else:
        st.warning("សូមបញ្ចូលអក្សរ SRT សិន!")
