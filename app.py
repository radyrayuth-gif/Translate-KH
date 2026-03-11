import streamlit as st
import asyncio
import edge_tts
import re
import io
from pydub import AudioSegment

# --- កំណត់ទំព័រ ---
st.set_page_config(page_title="Khmer TTS Pro - Sync & Clear", page_icon="🎙️")

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
            "start_ms": int(to_ms(match[1])),
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
    except Exception as e:
        print(f"Error fetching chunk: {e}")
        return None

async def generate_audio(srt_text, voice, rate, pitch):
    subs = parse_srt(srt_text)
    if not subs: return None
    
    # កំណត់ទម្រង់ល្បឿន និងកម្រិតសំឡេង
    # ចំណាំ៖ ក្នុង edge-tts ការប្រើ +10% គឺលឿនល្មម បើប្រើ +100% គឺស្តាប់មិនបានទេ
    rate_str = f"{rate:+d}%"
    pitch_str = f"{pitch:+d}Hz"

    # ១. ទាញយកសំឡេងគ្រប់បន្ទាត់ក្នុងពេលតែមួយ (Concurrency) ដើម្បីល្បឿន
    tasks = [fetch_audio_chunk(sub['text'], voice, rate_str, pitch_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # ២. បង្កើត Timeline សំឡេង
    final_combined = AudioSegment.empty()
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            # បំប្លែង chunk ទៅជា AudioSegment
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # រយៈពេលបច្ចុប្បន្ននៃ Audio ដែលបានផលិតរួច (ms)
            current_duration = len(final_combined)
            
            # គណនាចន្លោះដែលត្រូវបន្ថែម Silence (ភាពស្ងាត់) ដើម្បីឱ្យចំ Start Time ក្នុង SRT
            wait_time = sub['start_ms'] - current_duration
            
            if wait_time > 0:
                # បន្ថែមភាពស្ងាត់បើ Start Time មិនទាន់ដល់
                final_combined += AudioSegment.silent(duration=wait_time)
                final_combined += segment
            else:
                # បើ Audio មុនវែងពេក រហូតដល់ហួស Start Time ថ្មី យើងប្រើ Overlay ដើម្បីកុំឱ្យបាត់ Sync
                final_combined = final_combined.overlay(segment, position=sub['start_ms'])

    # នាំចេញជា MP3
    buffer = io.BytesIO()
    final_combined.export(buffer, format="mp3")
    return buffer.getvalue()

# --- ចំណុចប្រទាក់អ្នកប្រើ (UI) ---
st.title("🎙️ Khmer TTS - Sync & Clear")
st.markdown("""
<style>
    .stTextArea textarea { font-family: 'Kantumruy Pro', sans-serif; }
</style>
""", unsafe_allow_html=True)

st.info("💡 **ដំបូន្មាន:** ដើម្បីឱ្យសំឡេងអានបានពីរោះ និងច្បាស់ សូមប្រើល្បឿនចន្លោះពី **+0%** ដល់ **+20%**។")

col1, col2 = st.columns(2)
with col1:
    voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
    # ប្តូរលំនាំដើមមក 10% វិញដើម្បីឱ្យអានច្បាស់
    speed = st.slider("ល្បឿនអាន (%):", -50, 100, 10, 5)
with col2:
    pitch = st.slider("កម្រិតសំឡេង (Hz):", -20, 20, 0, 1)

srt_input = st.text_area("បញ្ចូលអត្ថបទ SRT របស់អ្នកនៅទីនេះ:", height=250, placeholder="1\n00:00:01,000 --> 00:00:03,000\nសួស្តីបងប្អូនទាំងអស់គ្នា!")

if st.button("🔊 ផលិតសំឡេង"):
    if srt_input.strip():
        with st.spinner("កំពុងផលិតសំឡេង... សូមរង់ចាំ"):
            try:
                final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed, pitch))
                if final_audio:
                    st.audio(final_audio)
                    st.download_button("📥 ទាញយក MP3", final_audio, "khmer_tts_sync.mp3")
                else:
                    st.error("មិនអាចផលិតសំឡេងបានទេ! សូមពិនិត្យទម្រង់ SRT ឡើងវិញ។")
            except Exception as e:
                st.error(f"បញ្ហា៖ {e}")
    else:
        st.warning("សូមបញ្ចូលអត្ថបទ SRT ជាមុនសិន!")
