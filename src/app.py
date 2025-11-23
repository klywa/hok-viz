import streamlit as st
import os
import io
import base64
import streamlit.components.v1 as components
from PIL import Image
from parser import MatchParser
from renderer import MatchRenderer

st.set_page_config(layout="wide", page_title="HOK-Viz: 王者荣耀对局可视化", page_icon="🎮")

def main():
    st.title("🎮 王者荣耀对局可视化工具")
    
    # Initialize
    if 'parser' not in st.session_state:
        st.session_state.parser = MatchParser()
    if 'renderer' not in st.session_state:
        # Determine assets directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        assets_dir = os.path.join(project_root, "assets")
        st.session_state.renderer = MatchRenderer(assets_dir=assets_dir)
    if 'generated_image' not in st.session_state:
        st.session_state.generated_image = None
        
    # Initialize session state for text input
    if 'match_text_input' not in st.session_state:
        st.session_state.match_text_input = ""

    # Callback for file upload
    def on_file_upload():
        if st.session_state.file_uploader:
            content = st.session_state.file_uploader.getvalue().decode("utf-8")
            if st.session_state.file_uploader.name.endswith('.jsonl'):
                import json
                try:
                    line = content.split('\n')[0]
                    data = json.loads(line)
                    text = data.get('content') or data.get('match_info') or ""
                    st.session_state.match_text_input = text
                except:
                    st.session_state.match_text_input = content
            else:
                st.session_state.match_text_input = content

    # Callback for clear
    def on_clear():
        st.session_state.match_text_input = ""
        st.session_state.generated_image = None

    # Layout
    col_main, col_side = st.columns([2, 1])
    
    with col_side:
        st.header("📝 对局信息输入")
        
        # Quality Settings
        scale_options = {1.0: "标准 (1080p)", 2.0: "高清 (4K)", 3.0: "超清 (6K)"}
        selected_scale = st.select_slider(
            "画质设置",
            options=[1.0, 2.0, 3.0],
            value=2.0,
            format_func=lambda x: scale_options[x]
        )
        
        # Update renderer if scale changed
        if getattr(st.session_state, 'last_scale', None) != selected_scale:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(script_dir)
            assets_dir = os.path.join(project_root, "assets")
            st.session_state.renderer = MatchRenderer(assets_dir=assets_dir, scale_factor=selected_scale)
            st.session_state.last_scale = selected_scale

        # File Uploader
        st.file_uploader(
            "上传文件 (JSONL/TXT)", 
            type=['jsonl', 'txt'], 
            key="file_uploader",
            on_change=on_file_upload
        )
        
        match_text = st.text_area(
            "或是直接粘贴对局描述文本", 
            key="match_text_input",
            height=400,
            placeholder="[整体情况]\n当前时间：..."
        )
        
        col_btn1, col_btn2 = st.columns(2)
        should_generate = False
        with col_btn1:
            if st.button("🎨 生成战报图片", type="primary", use_container_width=True):
                should_generate = True
        with col_btn2:
            st.button("🗑️ 清空内容", use_container_width=True, on_click=on_clear)
        
        # Actions Placeholder (Download/Copy)
        actions_placeholder = st.empty()

    with col_main:
        st.header("🖼️ 可视化战报")
        
        if should_generate and match_text:
            try:
                with st.spinner("正在生成图片..."):
                    # Parse
                    match_state = st.session_state.parser.parse(match_text)
                    
                    # Render
                    img = st.session_state.renderer.render(match_state)
                    
                    # Store in session state
                    st.session_state.generated_image = img
            except Exception as e:
                st.error(f"生成失败: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
        
        # Display Image if available
        if st.session_state.generated_image:
            img = st.session_state.generated_image
            st.image(img, caption="对局战报可视化", use_container_width=True, output_format="PNG")
            
            # Convert to bytes for download/copy
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            byte_im = buf.getvalue()
            
            # Render buttons in sidebar
            with actions_placeholder.container():
                st.markdown("---")
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button(
                        label="💾 保存高清PNG",
                        data=byte_im,
                        file_name="hok_viz_output.png",
                        mime="image/png",
                        type="primary",
                        use_container_width=True
                    )
                with col_dl2:
                    # Clipboard Button via HTML/JS injection
                    # Convert to base64
                    b64_img = base64.b64encode(byte_im).decode()
                    
                    components.html(
                        f"""
                        <script>
                        async function copyImage() {{
                            try {{
                                const response = await fetch("data:image/png;base64,{b64_img}");
                                const blob = await response.blob();
                                await navigator.clipboard.write([
                                    new ClipboardItem({{ "image/png": blob }})
                                ]);
                                document.getElementById("status").innerText = "✅";
                                setTimeout(() => {{ document.getElementById("status").innerText = ""; }}, 2000);
                            }} catch (err) {{
                                console.error(err);
                                document.getElementById("status").innerText = "❌";
                            }}
                        }}
                        </script>
                        <style>
                            button:hover {{ border-color: #ff4b4b !important; color: #ff4b4b !important; }}
                            button:active {{ background-color: #1e1e1e !important; }}
                        </style>
                        <div style="display: flex; align-items: center; gap: 5px; height: 100%; justify-content: center;">
                            <button onclick="copyImage()" style="
                                background-color: #ffffff; 
                                color: #262730; 
                                border: 1px solid rgba(49, 51, 63, 0.2); 
                                padding: 0.25rem 0.5rem; 
                                border-radius: 0.25rem; 
                                cursor: pointer;
                                font-family: 'Source Sans Pro', sans-serif;
                                font-weight: 400;
                                font-size: 1rem;
                                line-height: 1.6;
                                width: 100%;
                                transition: border-color 0.2s, color 0.2s;
                            ">📋 复制到剪贴板</button>
                            <span id="status" style="color: green; font-family: sans-serif; position: absolute; right: 5px; font-size: 0.8rem;"></span>
                        </div>
                        """,
                        height=50
                    )

        elif not should_generate:
             # Initial state or empty
             if not match_text:
                st.info("👈 请在左侧输入对局信息并点击生成")
                
                # Show sample if empty
                if st.button("加载示例数据"):
                    sample_path = os.path.join("data", "sample.txt")
                    if os.path.exists(sample_path):
                        with open(sample_path, 'r') as f:
                            st.code(f.read(), language=None)
                            st.warning("请复制上方文本到左侧输入框")

if __name__ == "__main__":
    main()

