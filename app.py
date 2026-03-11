import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment

# --- កំណត់ទំព័រ ---
st.set_page_config(page_title="Khmer TTS Pro - Full Sync", page_icon="🎙️")

async def fetch_audio_chunk(text, voice, rate_str, pitch_str):
    """ទាញយកសំឡេងពី Microsoft Edge TTS"""
    try:
        # បំបាត់សញ្ញាពិសេសដែល AI មិនអាចអានបាន
        clean_text = re.sub(r'[^\u1780-\u17FF\u19E0-\u19FFa-zA-Z0-9\s\.\?\!]', '', text)
        if not clean_text.strip(): 
            return None
            
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
        # បំប្លែង SRT ឱ្យទៅជា List នៃ Subtitles
        subs = list(srt.parse(srt_content))
    except Exception as e:
        st.error(f"ទម្រង់ SRT មានបញ្ហា៖ {e}")
        return None

    if not subs: return None
    
    rate_str = f"{rate:+d}%"
    pitch_str = f"{pitch:+d}Hz"

    # ១. ទាញយកសំឡេងគ្រប់ឃ្លាទាំងអស់ក្នុងពេលតែមួយ
    with st.status("កំពុងផលិតសំឡេងតាមឃ្លានីមួយៗ...", expanded=False) as status:
        tasks = [fetch_audio_chunk(sub.content, voice, rate_str, pitch_str) for sub in subs]
        audio_chunks = await asyncio.gather(*tasks)
        status.update(label="ផលិតសំឡេងរួចរាល់! កំពុងបញ្ចូលគ្នា...", state="complete")

    # ២. បញ្ចូលសំឡេងចូលគ្នាដោយរក្សាលំនឹងម៉ោង (Synchronization)
    final_combined = AudioSegment.empty()
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # ម៉ោងចាប់ផ្ដើមក្នុង SRT (ms)
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            
            # រយៈពេលនៃ Audio ដែលបានបញ្ចូលរួចមកហើយ
            current_duration = len(final_combined)
            
            if srt_start_ms > current_duration:
                # ករណីម៉ោង SRT មកដល់ក្រោយ៖ ថែម Silence ចន្លោះកណ្តាល
                silence_gap = srt_start_ms - current_duration
                final_combined += AudioSegment.silent(duration=silence_gap)
                final_combined += segment
            else:
                # ករណី Audio ចាស់វែងជាងម៉ោង SRT ថ្មី៖ 
                # បន្ថែម Silence បន្តិច (៥០ms) រួចឱ្យវាអានបន្តកន្ទុយគ្នាភ្លាម ដើម្បីកុំឱ្យបាត់សំឡេង
                final_combined += AudioSegment.silent(duration=50)
                final_combined += segment

    # នាំចេញជា MP3
    buffer = io.BytesIO()
    final_combined.export(buffer, format="mp3")
    return buffer.getvalue()

# --- ចំណុចប្រទាក់អ្នកប្រើ (UI) ---
st.title("🎙️ Khmer TTS - Full Sync Pro")
st.markdown("កម្មវិធីផលិតសំឡេងខ្មែរពី SRT ដោយរក្សាម៉ោងឱ្យត្រូវជាមួយវីដេអូ")

with st.sidebar:
    st.header("⚙️ ការកំណត់សំឡេង")
    voice_choice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
    speed = st.slider("ល្បឿនអាន (%):", -50, 100, 20, 5)
    pitch = st.slider("កម្រិតសំឡេង (Hz):", -20, 20, 0, 1)
    st.divider()
    st.info("ណែនាំ៖ ប្រើល្បឿន +20% សម្រាប់វីដេអូទូទៅ។")

srt_input = st.text_area("បញ្ចូលអត្ថបទ SRT របស់អ្នកនៅទីនេះ:", height=400, placeholder="1\n00:00:01,000 --> 00:00:03,000\nសួស្តីបងប្អូនទាំងអស់គ្នា!")

if st.button("🔊 ចាប់ផ្ដើមផលិតសំឡេង", use_container_width=True):
    if srt_input.strip():
        try:
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed, pitch))
            if final_audio:
                st.success("ផលិតជោគជ័យ!")
                st.audio(final_audio)
                st.download_button(
                    label="📥 ទាញយកឯកសារ MP3",
                    data=final_audio,
                    file_name="khmer_tts_final.mp3",
                    mime="audio/mp3",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"កើតមានបញ្ហាបច្ចេកទេស៖ {e}")
    else:
        st.warning("សូមបញ្ចូលអត្ថបទ SRT ជាមុនសិន!")
