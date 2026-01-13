import streamlit as st
import google.generativeai as genai
import sys

st.title("系統底層診斷模式")

# 1. 檢查 Python 與套件版本
st.subheader("1. 環境版本檢查")
st.write(f"Python Version: {sys.version}")
try:
    import google.generativeai
    st.write(f"Google GenAI Library Version: **{google.generativeai.__version__}**")
    
    # 判斷版本是否過舊
    ver_parts = google.generativeai.__version__.split('.')
    if int(ver_parts[0]) == 0 and int(ver_parts[1]) < 7:
        st.error("❌ 版本過舊！Gemini 1.5 Flash 至少需要 0.7.0 以上。")
    else:
        st.success("✅ 版本符合需求。")
except ImportError:
    st.error("❌ 找不到 google.generativeai 套件，requirements.txt 安裝失敗。")

# 2. 檢查 API Key 與模型清單
st.subheader("2. 帳號可用模型清單")
if "GEMINI_API_KEY" not in st.secrets:
    st.error("❌ 未檢測到 API Key")
else:
    st.success("✅ API Key 已設定")
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    try:
        st.write("正在向 Google 查詢可用模型...")
        models = genai.list_models()
        found_flash = False
        
        model_list = []
        for m in models:
            model_list.append(f"- {m.name}")
            if "gemini-1.5-flash" in m.name:
                found_flash = True
        
        st.code("\n".join(model_list))
        
        if found_flash:
            st.success("✅ 檢測到 gemini-1.5-flash 可用！")
        else:
            st.error("❌ 你的 API Key 權限中找不到 gemini-1.5-flash。")
            
    except Exception as e:
        st.error(f"連線查詢失敗: {str(e)}")