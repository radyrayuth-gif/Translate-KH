import streamlit as st
import asyncio
import edge_tts
import re
import io
from pydub import AudioSegment

# --- កំណត់ទំព័រ ---
st.set_page_config(page_title="Khmer TTS - High Speed Start Sync", page_icon="🎙️")

def parse_srt(srt_text):
    """បំប្លែង SRT ដើម្បីយកតែ Start Time និង អត្ថបទ"""
    # Regex សម្រាប់ចាប់យកលំដាប់ ម៉ោង និងអត្ថបទ
    pattern = r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\n$|$)"
    matches = re.findall(pattern, srt_text, re.DOTALL)
    subtitles = []
    
    def to_ms(time_str):
        h, m, s = time_str.replace(',', '.').split(':')
        return int(h)*3600000 + int(m)*60000 + float(s)*1000
        
    for match in matches:
        subtitles.append({
            "start_ms": to_ms(match[1]),
            "text": match[3].strip()
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
    except Exception:
        return None

async def generate_audio(srt_text, voice, rate, pitch):
    subs = parse_srt(srt_text)
    if not subs: return None
    
    # កំណត់ទម្រង់ល្បឿន និងកម្រិតសំឡេង
    rate_str = f"{rate:+d}%"
    pitch_str = f"{pitch:+d}Hz"

    # ១. ទាញយកសំឡេងគ្រប់បន្ទាត់ក្នុងពេលតែមួយ (Concurrency)
    tasks = [fetch_audio_chunk(sub['text'], voice, rate_str, pitch_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # ២. បង្កើត Timeline ស្ងាត់ (Buffer 30s សម្រាប់ការពារការដាច់)
    max_duration = subs[-1]['start_ms'] + 30000 
    final_combined = AudioSegment.silent(duration=max_duration)
    
    last_end_point = 0
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # ដាក់សំឡេងឱ្យចំ Start Time ក្នុង SRT (អានតាមល្បឿនធម្មជាតិរបស់ AI)
            final_combined = final_combined.overlay(segment, position=sub['start_ms'])
            
            # ចំណាំចំណុចបញ្ចប់ចុងក្រោយបង្អស់
            end_at = sub['start_ms'] + len(segment)
            if end_at > last_end_point:
                last_end_point = end_at

    # ៣. កាត់តម្រឹម File ឱ្យនៅត្រឹមសំឡេងបញ្ចប់ពិតប្រាកដ
    final_combined = final_combined[:last_end_point + 1000]

    buffer = io.BytesIO()
    final_combined.export(buffer, format="mp3")
    return buffer.getvalue()

# --- ចំណុចប្រទាក់អ្នកប្រើ (UI) ---
st.title("🎙️ Khmer TTS - High Speed Sync")
st.info("💡 កំណែថ្មី៖ ល្បឿនអានត្រូវបានដំឡើង និងអានចំតែនាទីចាប់ផ្ដើម (Start Time) ដើម្បីរក្សាគុណភាពសំឡេង។")

col1, col2 = st.columns(2)
with col1:
    voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
    # កំណត់ Default ល្បឿនទៅ 100 តាមការចង់បានរបស់អ្នក
    speed = st.slider("ល្បឿនអានទូទៅ (%):", 0, 100, 100, 5)
with col2:
    pitch = st.slider("កម្រិតសំឡេង (Hz):", -20, 20, 0, 1)

srt_input = st.text_area("បញ្ចូលអត្ថបទ SRT របស់អ្នកនៅទីនេះ:", height=250)

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងផលិតសំឡេងល្បឿនលឿន..."):
            try:
                final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed, pitch))
                if final_audio:
                    st.audio(final_audio)
                    st.download_button("📥 ទាញយក MP3", final_audio, "high_speed_sync.mp3")
            except Exception as e:
                st.error(f"បញ្ហា៖ {e}")
    else:
        st.warning("សូមបញ្ចូលអត្ថបទ SRT ជាមុនសិន!")

