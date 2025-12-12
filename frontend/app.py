import streamlit as st
import requests
import base64
import json
import streamlit.components.v1 as components
import pandas as pd
import time

import io
import zipfile

st.set_page_config(page_title="Whisper & Gemini POC", layout="wide")

# --- Helper Functions ---
def get_backend_url():
    return "http://localhost:8000"

def generate_vtt(segments):
    if not segments:
        return "WEBVTT\n\n"
    vtt_content = "WEBVTT\n\n"
    for seg in segments:
        start = seg['start']
        end = seg['end']
        text = seg['text']
        speaker = seg.get('speaker', '')
        
        # Format time: HH:MM:SS.mmm
        def format_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours:02}:{minutes:02}:{secs:06.3f}"
        
        start_str = format_time(start)
        end_str = format_time(end)
        
        if speaker:
            text = f"[{speaker}] {text}"
            
        vtt_content += f"{start_str} --> {end_str}\n{text}\n\n"
    return vtt_content

def convert_summary_to_vtt(summary_text):
    """
    Converts summary text with timestamps [start -> end] to VTT format.
    """
    if not summary_text:
        return "WEBVTT\n\n"
        
    vtt_content = "WEBVTT\n\n"
    import re
    
    # Regex to find timestamps: [0.00s -> 5.00s] or [0.00 -> 5.00]
    pattern = re.compile(r'\[\s*(\d+\.?\d*)\s*s?\s*->\s*(\d+\.?\d*)\s*s?\s*\]\s*(.*)')
    
    lines = summary_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        
        match = pattern.match(line)
        if match:
            start_sec = float(match.group(1))
            end_sec = float(match.group(2))
            text = match.group(3).strip()
            
            # Format time: HH:MM:SS.mmm
            def format_time(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = seconds % 60
                return f"{hours:02}:{minutes:02}:{secs:06.3f}"
            
            start_str = format_time(start_sec)
            end_str = format_time(end_sec)
            
            vtt_content += f"{start_str} --> {end_str}\n{text}\n\n"
        else:
            # If line doesn't match timestamp format, maybe just append it as a note or skip
            # For VTT, we need timestamps. If no timestamp, we can't really place it.
            # But we could append it to the previous cue if we wanted, or just ignore.
            # Let's try to be safe: if it looks like text, maybe give it a dummy timestamp or skip.
            # For now, we only convert lines with timestamps.
            pass
            
    return vtt_content

def add_task_to_zip(zip_file, task, folder_prefix=""):
    """
    Adds task files to an open ZipFile object.
    """
    # 1. Transcription
    transcription = task.get('corrected_transcription') or task.get('raw_transcription') or ""
    zip_file.writestr(f"{folder_prefix}transcription.txt", transcription)
    
    # 2. Subtitles
    segs = task.get('corrected_segments') or task.get('raw_segments')
    subtitles_vtt = generate_vtt(segs)
    zip_file.writestr(f"{folder_prefix}subtitles.vtt", subtitles_vtt)
    
    # 3. Summary
    summary = task.get('summary') or ""
    summary_vtt = convert_summary_to_vtt(summary)
    zip_file.writestr(f"{folder_prefix}summary.vtt", summary_vtt)

def create_task_zip(task):
    """
    Creates an in-memory ZIP file for a single task.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        add_task_to_zip(zip_file, task)
    return zip_buffer.getvalue()

def render_unified_player(audio_url, transcription_corrected, subtitles_corrected, segments_corrected, summary_text):
    # Prepare data for JS
    # Ensure segments is a list
    if segments_corrected is None:
        segments_corrected = []
    if not isinstance(segments_corrected, list):
        segments_corrected = []
        
    # Ensure summary is a string
    if summary_text is None:
        summary_text = ""
    summary_text = str(summary_text)
    
    html_code = f"""
    <html>
    <head>
        <style>
            body {{ font-family: sans-serif; margin: 0; padding: 0; color: #333; }}
            .container {{ display: flex; flex-direction: column; gap: 20px; }}
            .section {{ border: 1px solid #ddd; border-radius: 5px; padding: 15px; background: #fff; }}
            .section-title {{ margin-top: 0; margin-bottom: 10px; font-size: 1.1em; font-weight: bold; color: #444; }}
            
            .row {{ display: flex; gap: 20px; }}
            .col {{ flex: 1; min-width: 0; }}
            @media (max-width: 768px) {{ .row {{ flex-direction: column; }} }}
            
            .box {{ 
                border: 1px solid #ddd; 
                border-radius: 5px; 
                padding: 10px; 
                overflow-y: auto; 
                background: #f0f2f6; /* Streamlit style */
                font-family: monospace;
                white-space: pre-wrap;
            }}
            
            .scroll-box {{ height: 400px; }}
            .text-box {{ height: 400px; }}
            
            /* Audio Player */
            audio {{ width: 100%; margin-bottom: 10px; position: sticky; top: 0; z-index: 100; }}
            
            /* Subtitles */
            .segment {{
                padding: 5px;
                margin-bottom: 5px;
                border-radius: 3px;
                cursor: pointer;
                transition: background-color 0.2s;
                font-size: 14px;
                font-family: sans-serif;
            }}
            .segment:hover {{ background-color: #e0e2e6; }}
            .segment.active {{ background-color: #ffe082; font-weight: bold; }}
            .timestamp {{ color: #888; font-size: 0.8em; margin-right: 5px; }}
            
            /* Summary */
            .summary-text {{ line-height: 1.6; font-size: 14px; font-family: sans-serif; }}
            .summary-timestamp {{
                color: #0066cc;
                cursor: pointer;
                text-decoration: underline;
                font-weight: bold;
            }}
            .summary-timestamp:hover {{ color: #004488; }}
        </style>
    </head>
    <body>
        <audio id="audio-player" controls>
            <source src="{audio_url}" type="audio/mp3">
            Your browser does not support the audio element.
        </audio>
        
        <div class="container">
            <div class="row">
                <!-- 1. Dynamic Subtitles (Corrected) -->
                <div class="section col">
                    <div class="section-title">🎬 Dynamic Subtitles (Corrected)</div>
                    <div id="subtitles-corrected" class="box scroll-box"></div>
                </div>
                
                <!-- 3. AI Summary -->
                <div class="section col">
                    <div class="section-title">🤖 AI Summary (Click time to seek)</div>
                    <div id="summary-container" class="box text-box summary-text"></div>
                </div>
            </div>
            
            <!-- 2. Transcription (Corrected) -->
            <div class="section">
                <div class="section-title">📝 Transcription (Corrected)</div>
                <div class="box text-box">{transcription_corrected}</div>
            </div>
        </div>

        <script>
            const segmentsCorrected = {json.dumps(segments_corrected, default=str)};
            const summaryText = {json.dumps(summary_text, default=str)};
            
            const audio = document.getElementById('audio-player');
            const subCorrContainer = document.getElementById('subtitles-corrected');
            const sumContainer = document.getElementById('summary-container');
            
            // --- Helper: Render Segments ---
            function renderSegments(segments, container, prefix) {{
                if (!segments) return;
                segments.forEach((seg, index) => {{
                    const div = document.createElement('div');
                    div.className = 'segment';
                    div.id = prefix + '-' + index;
                    div.innerHTML = `<span class="timestamp">[${{seg.start.toFixed(2)}}s]</span> ${{seg.speaker ? '<strong>[' + seg.speaker + ']</strong> ' : ''}}${{seg.text}}`;
                    
                    div.onclick = () => {{
                        audio.currentTime = seg.start;
                        audio.play();
                    }};
                    
                    container.appendChild(div);
                }});
            }}
            
            renderSegments(segmentsCorrected, subCorrContainer, 'corr');

            // --- Render Summary ---
            function formatSummary(text) {{
                if (!text) return "";
                const pattern = /\[(\d+\.?\d*)\s*s?\s*->\s*(\d+\.?\d*)\s*s?\]/g;
                return text.replace(pattern, (match, start, end) => {{
                    return `<span class="summary-timestamp" onclick="seekTo(${{start}})">${{match}}</span>`;
                }}).replace(/\\n/g, '<br>');
            }}
            sumContainer.innerHTML = formatSummary(summaryText);
            
            window.seekTo = (time) => {{
                audio.currentTime = time;
                audio.play();
            }};

            // --- Sync Logic ---
            audio.ontimeupdate = () => {{
                const currentTime = audio.currentTime;
                
                // Update Corrected
                if (segmentsCorrected) {{
                    updateHighlight(segmentsCorrected, 'corr');
                }}
            }};
            
            function updateHighlight(segments, prefix) {{
                const currentTime = audio.currentTime;
                segments.forEach((seg, index) => {{
                    const div = document.getElementById(prefix + '-' + index);
                    if (div && currentTime >= seg.start && currentTime <= seg.end) {{
                        if (!div.classList.contains('active')) {{
                            const container = document.getElementById('subtitles-corrected');
                            container.querySelectorAll('.segment').forEach(el => el.classList.remove('active'));
                            
                            div.classList.add('active');
                            // div.scrollIntoView({{ behavior: 'smooth', block: 'center' }}); // Disabled auto-scroll
                        }}
                    }}
                }});
            }}
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=800, scrolling=True)

def render_home_page():
    st.title("🎙️ AI Audio Transcription & Summarization")
    st.markdown("本系統利用先進的 AI 模型來轉錄、區分說話者、校正和摘要您的音檔。")

    st.header("🔄 系統流程")
    st.markdown("下圖展示了您的音檔是如何被處理的：")
    
    mermaid_code = """
    graph LR
        A[音檔] --> B(Whisper 模型);
        A --> C(Pyannote Audio);
        B --> D[原始逐字稿];
        C --> E[說話者區分];
        D & E --> F{合併與格式化};
        F --> G[原始字幕];
        G --> H(Gemini AI);
        H --> I[校正後字幕];
        I --> J(Gemini AI);
        J --> K[AI 摘要];
    """
    
    # Render Mermaid using HTML component
    components.html(
        f"""
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true }});
        </script>
        <div class="mermaid">
            {mermaid_code}
        </div>
        """,
        height=300,
    )
    
    st.header("📖 使用指南")
    
    with st.expander("1. 設定與配置", expanded=True):
        st.markdown("""
        - **Google Gemini API Key**：用於**校正**和**摘要**。請在側邊欄輸入。
        - **Hugging Face Token**：用於**說話者區分**。請在側邊欄輸入。
        - **說話者人數**：可選。如果您知道確切的人數，輸入它可以提高區分準確度。
        """)
        
    with st.expander("2. 處理新任務", expanded=True):
        st.markdown("""
        - 前往 **New Task** 頁面。
        - 上傳一個或多個音檔 (MP3, WAV, M4A, MP4)。
        - 點擊 **Start Processing**。
        - 系統將按順序處理文件。您可以即時監控狀態。
        """)
        
    with st.expander("3. 審閱與編輯", expanded=True):
        st.markdown("""
        - 前往 **History** 頁面查看過去的任務。
        - 選擇一個任務以加載詳細信息。
        - **播放器**：聆聽音檔並跟隨互動字幕。
        - **編輯**：展開 **✏️ Edit Corrected Content** 區塊以：
            - **重命名說話者**：將 `SPEAKER_00` 映射到真實姓名 (例如 `Alice`)。
            - **編輯文本**：修正字幕中的錯字或調整摘要。
            - **重新生成摘要**：勾選此框以讓 AI 根據您的編輯重新撰寫摘要。
        """)

# --- Session State for User ---
if 'user' not in st.session_state:
    st.session_state.user = None

# --- Auth UI ---
if not st.session_state.user:
    st.title("🔐 Login / Register")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                try:
                    response = requests.post(f"{get_backend_url()}/login", json={"email": email, "password": password})
                    if response.status_code == 200:
                        st.session_state.user = response.json()
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error(f"Login failed: {response.json().get('detail')}")
                except Exception as e:
                    st.error(f"Connection error: {str(e)}")

    with tab2:
        with st.form("register_form"):
            new_email = st.text_input("Email")
            new_password = st.text_input("Password", type="password")
            submit_reg = st.form_submit_button("Register")
            
            if submit_reg:
                try:
                    response = requests.post(f"{get_backend_url()}/register", json={"email": new_email, "password": new_password})
                    if response.status_code == 200:
                        st.success("Registration successful! Please login.")
                    else:
                        st.error(f"Registration failed: {response.json().get('detail')}")
                except Exception as e:
                    st.error(f"Connection error: {str(e)}")
    
                    st.error(f"Connection error: {str(e)}")
    
    st.divider()
    render_home_page()
    st.stop() # Stop execution if not logged in

# --- Sidebar Navigation ---
st.sidebar.title("Navigation")
st.sidebar.write(f"👤 **{st.session_state.user['username']}** ({'Admin' if st.session_state.user['is_admin'] else 'User'})")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

st.sidebar.divider()

page = st.sidebar.radio("Go to", ["Home", "API Doc", "New Task", "History"])

st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Google Gemini API Key", type="password", help="Enter your Google Generative AI API Key here.")
hf_token = st.sidebar.text_input("Hugging Face Token (Optional)", type="password", help="Required for Speaker Diarization (Pyannote).")
num_speakers_input = st.sidebar.text_input("Number of Speakers (Optional)", value="", help="Leave empty to let the model detect speakers automatically. Enter a number (1-10) to force a specific count.")
num_speakers = None
if num_speakers_input.strip():
    try:
        val = int(num_speakers_input.strip())
        if 1 <= val <= 10:
            num_speakers = val
        else:
            st.sidebar.error("Number of speakers must be between 1 and 10.")
    except ValueError:
        st.sidebar.error("Please enter a valid number.")
st.sidebar.markdown("[Get your API Key here](https://aistudio.google.com/api-keys)")

# --- Page: Home ---
if page == "Home":
    render_home_page()
    # ... (rest of Home page)

# --- Page: API Doc ---
elif page == "API Doc":
    st.title("🔌 API 介接文件")
    st.markdown("本系統提供 RESTful API，供外部系統整合使用。以下是詳細的介接指引。")
    
    st.info(f"**Base URL**: `{get_backend_url()}`")
    
    st.warning("⚠️ **Authentication**: 本系統目前使用 `user_id` (UUID) 進行用戶識別與資料隔離。請確保在請求中包含正確的 `user_id`。")
    
    st.header("1. 上傳與處理 (Upload & Process)")
    st.markdown("**Endpoint**: `POST /process`")
    st.markdown("上傳音檔並開始背景處理任務。")
    
    st.subheader("請求參數 (Request Parameters)")
    st.markdown("""
    - `file`: (File, Required) 要處理的音頻文件 (mp3, wav, m4a, mp4)。
    - `user_id`: (String, Required) 用戶的 UUID (從 Supabase Auth 獲取)。
    - `api_key`: (String, Required) Google Gemini API Key。
    - `hf_token`: (String, Optional) Hugging Face Token (用於說話者區分)。
    - `num_speakers`: (Integer, Optional) 指定說話者人數。
    """)
    
    st.code("""
import requests

url = "http://localhost:8000/process"
files = {'file': open('audio.mp3', 'rb')}
data = {
    'user_id': 'YOUR_USER_UUID', # Required
    'api_key': 'YOUR_GEMINI_API_KEY',
    'hf_token': 'YOUR_HF_TOKEN', # Optional
    'num_speakers': 2 # Optional
}

response = requests.post(url, files=files, data=data)
print(response.json())
# Output: {'task_id': 1, 'message': 'Processing started in background'}
    """, language="python")

    st.divider()

    st.header("2. 獲取任務列表 (Get Tasks)")
    st.markdown("**Endpoint**: `GET /tasks`")
    st.markdown("獲取指定用戶的所有任務列表。")
    
    st.subheader("請求參數 (Query Parameters)")
    st.markdown("""
    - `user_id`: (String, Required) 用戶的 UUID。
    - `skip`: (Integer, Default=0) 跳過的筆數。
    - `limit`: (Integer, Default=100) 返回的筆數限制。
    """)
    
    st.code("""
user_id = "YOUR_USER_UUID"
response = requests.get(f"http://localhost:8000/tasks?user_id={user_id}&limit=5")
print(response.json())
    """, language="python")

    st.divider()

    st.header("3. 獲取任務詳情 (Get Task Details)")
    st.markdown("**Endpoint**: `GET /tasks/{task_id}`")
    st.markdown("獲取指定任務的詳細資訊，包括轉錄結果、字幕和摘要。")
    
    st.code("""
task_id = 1
response = requests.get(f"http://localhost:8000/tasks/{task_id}")
task = response.json()

print(f"Status: {task['status']}")
print(f"Transcription: {task['corrected_transcription']}")
print(f"Summary: {task['summary']}")
    """, language="python")

    st.divider()

    st.header("4. 更新任務 (Update Task)")
    st.markdown("**Endpoint**: `PUT /tasks/{task_id}`")
    st.markdown("更新任務的字幕、摘要或重命名說話者。")
    
    st.subheader("請求主體 (JSON Body)")
    st.markdown("""
    - `corrected_subtitles`: (String, Optional) 修正後的字幕文本。
    - `summary`: (String, Optional) 修正後的摘要。
    - `speaker_map`: (Dictionary, Optional) 說話者映射，例如 `{"SPEAKER_00": "Alice"}`。
    - `regenerate_summary`: (Boolean, Optional) 是否重新生成摘要 (需提供 `api_key`)。
    - `api_key`: (String, Optional) 用於重新生成的 API Key。
    """)
    
    st.code("""
url = f"http://localhost:8000/tasks/{task_id}"
payload = {
    "speaker_map": {"SPEAKER_00": "Alice"},
    "regenerate_summary": True,
    "api_key": "YOUR_GEMINI_API_KEY"
}
response = requests.put(url, json=payload)
print(response.json())
    """, language="python")



# --- Page: New Task ---
if page == "New Task":
    st.title("🎙️ AI Audio Transcription & Summarization")
    
    # Check if we have active batch tasks
    if st.session_state.get('batch_tasks'):
        batch_tasks = st.session_state.batch_tasks
        
        # Button to reset
        if st.button("Start New Batch"):
            st.session_state.batch_tasks = []
            st.session_state.processing_done = False
            st.rerun()
            
        st.divider()
        
        # Layout: List (Left) vs Detail (Right)
        col_list, col_detail = st.columns([1, 2])
        
        # Containers for dynamic updates
        with col_list:
            st.subheader("Batch Status")
            list_container = st.empty()
            
        with col_detail:
            detail_header = st.empty()
            detail_container = st.empty()
            
            # Debug Info Placeholders (Collapsible)
            with st.expander("Debug Information", expanded=False):
                debug_area_1 = st.empty() # Corrected Transcription
                debug_area_2 = st.empty() # Corrected Subtitles
                debug_area_3 = st.empty() # Raw Transcription
                debug_area_4 = st.empty() # Raw Subtitles
                debug_area_5 = st.empty() # Summary

        # Polling Loop
        try:
            while True:
                # 1. Fetch all task statuses
                current_batch_data = []
                active_task = None
                all_completed = True
                
                for tid in batch_tasks:
                    try:
                        resp = requests.get(f"{get_backend_url()}/tasks/{tid}")
                        if resp.status_code == 200:
                            t_data = resp.json()
                            current_batch_data.append(t_data)
                            
                            # Determine Active Task Logic
                            # Priority: Processing > Pending > Completed
                            status = t_data['status']
                            if status in ['transcribing', 'correcting', 'summarizing']:
                                if active_task is None or active_task['status'] not in ['transcribing', 'correcting', 'summarizing']:
                                    active_task = t_data
                            elif status == 'pending':
                                if active_task is None:
                                    active_task = t_data
                            
                            if status not in ['completed', 'failed']:
                                all_completed = False
                    except:
                        pass
                
                # Fallback: If no active task found (e.g. all completed), show the last one
                if active_task is None and current_batch_data:
                    active_task = current_batch_data[-1]

                # 2. Update List View
                if current_batch_data:
                    df_batch = pd.DataFrame(current_batch_data)
                    df_batch = df_batch[['filename', 'status']]
                    list_container.dataframe(df_batch, width="stretch", hide_index=True)

                # 3. Update Detail View (Active Task)
                if active_task:
                    detail_header.subheader(f"Now Monitoring: {active_task['filename']}")
                    
                    # Update Debug Info
                    if active_task.get("raw_transcription"):
                        debug_area_3.markdown(f"**3. 逐字稿 (Raw)**\n```text\n{active_task.get('raw_transcription')}\n```")
                    if active_task.get("raw_subtitles"):
                        debug_area_4.markdown(f"**4. 字幕 (Raw)**\n```text\n{active_task.get('raw_subtitles')}\n```")
                    if active_task.get("corrected_transcription"):
                        debug_area_1.markdown(f"**1. 逐字稿 (Corrected)**\n```text\n{active_task.get('corrected_transcription')}\n```")
                    if active_task.get("corrected_subtitles"):
                        debug_area_2.markdown(f"**2. 字幕 (Corrected)**\n```text\n{active_task.get('corrected_subtitles')}\n```")
                    if active_task.get("summary"):
                        debug_area_5.markdown(f"**5. 摘要**\n```text\n{active_task.get('summary')}\n```")

                    # Render Player
                    audio_url = f"{get_backend_url()}/{active_task['audio_path']}"
                    with detail_container:
                        render_unified_player(
                            audio_url,
                            active_task.get('corrected_transcription') or active_task.get('raw_transcription'),
                            active_task.get('corrected_subtitles') or active_task.get('raw_subtitles'),
                            active_task.get('corrected_segments') or active_task.get('raw_segments'),
                            active_task.get('summary')
                        )

                if all_completed:
                    st.success("All tasks in batch completed!")
                    break
                
                time.sleep(2)
                
        except Exception as e:
            st.error(f"Polling Error: {str(e)}")

    else:
        # Upload View
        st.markdown("Upload audio files to transcribe using **Whisper** and summarize using **Google Gemini**.")
        uploaded_files = st.file_uploader("Choose audio files...", type=["mp3", "wav", "m4a", "mp4"], accept_multiple_files=True)

        if uploaded_files:
            st.write(f"Selected {len(uploaded_files)} files.")
            
            if st.button("Start Processing"):
                if not api_key:
                    st.error("Please enter your Google Gemini API Key in the sidebar.")
                else:
                    try:
                        batch_ids = []
                        progress_bar = st.progress(0)
                        
                        for i, uploaded_file in enumerate(uploaded_files):
                            files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                            data = {
                                "api_key": api_key, 
                                "hf_token": hf_token,
                                "user_id": st.session_state.user['id'],
                                "username": st.session_state.user['username']
                            }
                            if num_speakers:
                                data["num_speakers"] = num_speakers
                            uploaded_file.seek(0)
                            
                            response = requests.post(f"{get_backend_url()}/process", files=files, data=data)
                            
                            if response.status_code == 200:
                                task_data = response.json()
                                batch_ids.append(task_data.get("task_id"))
                            else:
                                st.error(f"Failed to upload {uploaded_file.name}: {response.text}")
                            
                            progress_bar.progress((i + 1) / len(uploaded_files))
                        
                        if batch_ids:
                            st.session_state.batch_tasks = batch_ids
                            st.rerun()
                                
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")

# --- Page: History ---
elif page == "History":
    st.title("📜 Transcription History")
    
    try:
        # Pass user_id and is_admin flag
        user_id = st.session_state.user['id']
        is_admin = st.session_state.user.get('is_admin', False)
        
        response = requests.get(f"{get_backend_url()}/tasks", params={"user_id": user_id, "is_admin": is_admin})
        
        if response.status_code == 200:
            tasks = response.json()
            
            if not tasks:
                st.info("No history found.")
            else:
                # Create a DataFrame for the list
                df = pd.DataFrame(tasks)
                df['created_at'] = pd.to_datetime(df['created_at'])
                
                # Columns to display
                cols = ['id', 'filename', 'status', 'created_at']
                if is_admin:
                    cols.insert(1, 'username') # Show username for admin
                    
                df = df[cols]
                
                # Display list
                st.dataframe(df, width="stretch", hide_index=True)
                
                # Selection & Download
                col1, col2 = st.columns([1, 1])
                with col1:
                    task_id = st.selectbox("Select a Task ID to view/download:", df['id'])
                
                with col2:
                    st.write("") # Spacer
                    st.write("") # Spacer
                    
                    # Prepare ZIP data
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for t in tasks:
                            segs = t.get('corrected_segments') or t.get('raw_segments')
                            if segs:
                                vtt_data = generate_vtt(segs)
                                fname = f"{t['id']}_{t['filename']}.vtt"
                                zip_file.writestr(fname, vtt_data)
                    
                    # Nested columns for side-by-side buttons
                    btn_col1, btn_col2 = st.columns([1, 1])
                    
                    with btn_col1:
                        # Download Single Selected
                        selected_task_data = next((t for t in tasks if t['id'] == task_id), None)
                        if selected_task_data:
                            zip_data = create_task_zip(selected_task_data)
                            st.download_button(
                                label=f"📥 Download Single (.zip)",
                                data=zip_data,
                                file_name=f"{selected_task_data['id']}_{selected_task_data['filename']}.zip",
                                mime="application/zip",
                                help=f"Download ZIP containing transcription, subtitles, and summary for {selected_task_data['filename']}",
                                use_container_width=True
                            )


                    with btn_col2:
                        # Prepare ZIP data for ALL tasks
                        zip_buffer_all = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer_all, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for t in tasks:
                                # Create a folder name: {id}_{filename}/
                                folder_name = f"{t['id']}_{t['filename']}/"
                                add_task_to_zip(zip_file, t, folder_prefix=folder_name)
                        
                        st.download_button(
                            label="📥 Download All (.zip)",
                            data=zip_buffer_all.getvalue(),
                            file_name="all_tasks_export.zip",
                            mime="application/zip",
                            help="Download ZIP containing folders for all tasks, each with transcription, subtitles, and summary.",
                            use_container_width=True
                        )

                    
                if st.button("Load Task Details"):
                    st.session_state.history_active_task_id = task_id
                
                if st.session_state.get("history_active_task_id"):
                    # Ensure the selected task matches the session state (optional, but good for consistency)
                    # If user changes selectbox but doesn't click Load, we might still show old one or reset.
                    # For now, let's just use the session state ID.
                    active_id = st.session_state.history_active_task_id
                    
                    with st.spinner("Loading details..."):
                        detail_response = requests.get(f"{get_backend_url()}/tasks/{active_id}")
                        if detail_response.status_code == 200:
                            task = detail_response.json()
                            
                            st.header(f"Details: {task['filename']}")
                            st.caption(f"Status: {task['status']} | Created: {task['created_at']}")
                            
                            if task['status'] == 'failed':
                                if st.button("🔄 Retry Task"):
                                    if not api_key:
                                        st.error("Please enter your Google Gemini API Key in the sidebar to retry.")
                                    else:
                                        try:
                                            retry_payload = {
                                                "api_key": api_key,
                                                "hf_token": hf_token,
                                                "num_speakers": num_speakers
                                            }
                                            retry_resp = requests.post(f"{get_backend_url()}/tasks/{active_id}/retry", json=retry_payload)
                                            if retry_resp.status_code == 200:
                                                st.success("Retry started! Reloading...")
                                                time.sleep(1)
                                                st.rerun()
                                            else:
                                                st.error(f"Retry failed: {retry_resp.text}")
                                        except Exception as e:
                                            st.error(f"Error triggering retry: {str(e)}")
                            
                            audio_url = f"{get_backend_url()}/{task['audio_path']}"
                            
                            render_unified_player(
                                audio_url,
                                task.get('corrected_transcription') or task.get('raw_transcription'),
                                task.get('corrected_subtitles') or task.get('raw_subtitles'),
                                task.get('corrected_segments') or task.get('raw_segments'),
                                task.get('summary')
                            )

                            st.divider()
                            
                            # --- Edit Mode ---
                            with st.expander("✏️ Edit Corrected Content", expanded=False):
                                with st.form(key=f"edit_form_{active_id}"):
                                    st.info("ℹ️ Note: Editing the **Corrected Subtitles** will automatically update the **Transcription** view above upon saving.")
                                    
                                    # --- Speaker Renaming ---
                                    st.subheader("Rename Speakers")
                                    current_segments = task.get('corrected_segments') or task.get('raw_segments') or []
                                    # Extract unique speakers
                                    unique_speakers = sorted(list(set(s.get('speaker') for s in current_segments if s.get('speaker'))))
                                    
                                    speaker_map = {}
                                    if unique_speakers:
                                        cols = st.columns(2)
                                        for i, spk in enumerate(unique_speakers):
                                            with cols[i % 2]:
                                                new_name = st.text_input(f"Name for {spk}", value=spk, key=f"spk_{active_id}_{spk}")
                                                if new_name != spk:
                                                    speaker_map[spk] = new_name
                                    else:
                                        st.caption("No speakers detected.")

                                    st.subheader("Edit Text")
                                    new_subtitles = st.text_area("Corrected Subtitles", value=task.get('corrected_subtitles') or task.get('raw_subtitles') or "", height=300)
                                    
                                    # Regeneration Checkbox
                                    regenerate_summary = st.checkbox("🔄 Regenerate AI Summary based on new content", help="If checked, the AI will re-summarize the text after you save. This requires your API Key.")
                                    
                                    if regenerate_summary:
                                        st.info("Summary will be regenerated. Manual edits to the summary below will be ignored.")
                                        new_summary = "" # Ignored
                                    else:
                                        new_summary = st.text_area("Summary", value=task.get('summary') or "", height=150)
                                    
                                    submit_button = st.form_submit_button(label="Save Changes")
                                    
                                    if submit_button:
                                        update_payload = {
                                            "corrected_subtitles": new_subtitles,
                                            "summary": new_summary,
                                            "regenerate_summary": regenerate_summary,
                                            "api_key": api_key # From sidebar
                                        }
                                        if speaker_map:
                                            update_payload["speaker_map"] = speaker_map
                                            
                                        try:
                                            update_resp = requests.put(f"{get_backend_url()}/tasks/{active_id}", json=update_payload)
                                            if update_resp.status_code == 200:
                                                st.success("Changes saved successfully! Reloading...")
                                                time.sleep(1)
                                                st.rerun()
                                            else:
                                                st.error(f"Failed to save changes: {update_resp.text}")
                                        except Exception as e:
                                            st.error(f"Error saving changes: {str(e)}")

                            
                            with st.expander("Debug Information (Raw Data)"):
                                st.text_area("Raw Transcription", task.get('raw_transcription', ''), height=100)
                                st.text_area("Raw Subtitles", task.get('raw_subtitles', ''), height=100)
                                st.json(task.get('raw_segments', []))
                        else:
                            st.error("Failed to load task details.")
        else:
            st.error("Failed to fetch task list.")
            
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the backend. Is it running? (http://localhost:8000)")

