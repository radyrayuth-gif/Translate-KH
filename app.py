import streamlit as st
import asyncio
import edge_tts
import re
import io
from pydub import AudioSegment

# --- កំណត់ទំព័រ ---
st.set_page_config(page_title="Khmer TTS Pro - Sync & Clear", page_icon="🎙️")

def parse_srt(srt_text):
    """បំប្លែង SRT ឱ្យកាន់តែសុក្រិត"""
    # Regex ថ្មីសម្រាប់ចាប់យក Start Time និង Text ឱ្យបានគ្រប់កាលៈទេសៈ
    pattern = r"\d+\s+(\d{2}:\d{2}:\d{2},\d{3}) --> \d{2}:\d{2}:\d{2},\d{3}\s+(.*?)(?=\n\d+\s+\d{2}:\d{2}:\d{2},\d{3} -->|$)"
    matches = re.findall(pattern, srt_text, re.DOTALL)
    
    subtitles = []
    def to_ms(time_str):
        h, m, s = time_str.replace(',', '.').split(':')
        return int(float(h)*3600000 + float(m)*60000 + float(s)*1000)
        
    for match in matches:
        subtitles.append({
            "start_ms": to_ms(match[0]),
            "text": match[1].strip()
        })
    return subtitles

async def fetch_audio_chunk(text, voice, rate_str, pitch_str):
    """ទាញយកសំឡេងពី Microsoft Edge TTS"""
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except:
        return None

async def generate_audio(srt_text, voice, rate, pitch):
    subs = parse_srt(srt_text)
    if not subs: return None
    
    rate_str = f"{rate:+d}%"
    pitch_str = f"{pitch:+d}Hz"

    tasks = [fetch_audio_chunk(sub['text'], voice, rate_str, pitch_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # បង្កើត Timeline សំឡេង
    final_combined = AudioSegment.empty()
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            current_duration = len(final_combined)
            wait_time = sub['start_ms'] - current_duration
            
            if wait_time > 0:
                final_combined += AudioSegment.silent(duration=wait_time)
                final_combined += segment
            else:
                final_combined = final_combined.overlay(segment, position=sub['start_ms'])

    buffer = io.BytesIO()
    final_combined.export(buffer, format="mp3")
    return buffer.getvalue()

# --- ចំណុចប្រទាក់អ្នកប្រើ (UI) ---
st.title("🎙️ Khmer TTS - Sync & Clear")
st.info("💡 កំណែថ្មី៖ កែសម្រួលការចាប់អត្ថបទ SRT ឱ្យកាន់តែសុក្រិត។")

col1, col2 = st.columns(2)
with col1:
    voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
    speed = st.slider("ល្បឿនអាន (%):", -50, 100, 10, 5)
with col2:
    pitch = st.slider("កម្រិតសំឡេង (Hz):", -20, 20, 0, 1)

srt_input = st.text_area("បញ្ចូលអត្ថបទ SRT របស់អ្នកនៅទីនេះ:", height=250)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងផលិតសំឡេង..."):
            try:
                final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed, pitch))
                if final_audio and len(final_audio) > 100: # ពិនិត្យថាមាន Data សំឡេងពិតមែន
                    st.audio(final_audio)
                    st.download_button("📥 ទាញយក MP3", final_audio, "khmer_tts_pro.mp3")
                else:
                    st.error("មិនអាចចាប់យកអត្ថបទពី SRT បានទេ! សូមពិនិត្យទម្រង់ SRT របស់អ្នកឡើងវិញ។")
            except Exception as e:
                st.error(f"បញ្ហា៖ {e}")
    else:
        st.warning("សូមបញ្ចូលអត្ថបទ SRT ជាមុនសិន!")
