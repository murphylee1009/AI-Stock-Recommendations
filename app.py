import streamlit as st
import google.generativeai as genai
from datetime import datetime
import pytz
import json
import re
from duckduckgo_search import DDGS

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="台股 AI 操盤手 (連網加強版)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 初始化 API ---
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ 請設定 GEMINI_API_KEY 在 .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- 3. 強大的免費搜尋函式 (DuckDuckGo) ---
def search_web(keyword):
    """使用 DuckDuckGo 搜尋最新財經資訊"""
    try:
        results = DDGS().text(f"{keyword} 台灣股市 股價 新聞", region='tw-tw', max_results=5)
        search_content = ""
        if results:
            for res in results:
                search_content += f"- 標題: {res['title']}\n  連結: {res['href']}\n  摘要: {res['body']}\n\n"
        return search_content if search_content else "無搜尋結果"
    except Exception as e:
        return f"搜尋發生錯誤: {str(e)}"

# --- 4. 輔助工具 ---
def get_current_time_info():
    taiwan_tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(taiwan_tz)
    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "weekday": ["週一", "週二", "週三", "週四", "週五", "週六", "週日"][now.weekday()],
    }

def extract_stock_code(text):
    if not text: return None
    matches = re.findall(r'\b(\d{4})\b', text)
    for match in matches:
        if 1000 <= int(match) <= 9999: return match
    return None

def clean_json_from_text(text):
    if not text: return ""
    return re.sub(r'\{[\s\n]*"price".*?"code".*?\}', '', text, flags=re.DOTALL).strip()

def get_tradingview_widget(stock_code=None):
    symbol = f"TWSE:{stock_code}" if stock_code else "TWSE:TAIEX"
    return f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {{
      "autosize": true, "symbol": "{symbol}", "interval": "D", "timezone": "Asia/Taipei", "theme": "light", "style": "1", "locale": "zh_TW", "hide_top_toolbar": false, "hide_legend": false, "allow_symbol_change": true, "save_image": false, "calendar": false, "support_host": "https://www.tradingview.com"
    }}
      </script>
    </div>
    """

# --- 5. 介面與邏輯 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("📈 台股 AI 操盤手")
    st.info("✅ 模式：Gemini 穩定版 + 即時連網搜尋")
    
    if st.button("📊 今日大盤分析", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "請搜尋今日台股大盤走勢，分析技術面、外資動向與操作建議。"})
        st.rerun()
    if st.button("🔥 今日熱門股推薦", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "請搜尋今日台股成交量大且強勢的熱門股票，推薦 1-2 檔並分析。"})
        st.rerun()

st.title("📈 台股 AI 操盤手 (連網版)")

# 顯示歷史訊息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.markdown(clean_json_from_text(message["content"]))
        else:
            st.markdown(message["content"])

# 處理輸入
if prompt := st.chat_input("請輸入股票代號或問題 (例如：2330 怎麼看?)..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🔍 AI 正在聯網搜尋最新財經資訊..."):
            try:
                # 1. 先進行網路搜尋
                search_results = search_web(prompt)
                
                # 2. 準備給 AI 的提示詞
                time_info = get_current_time_info()
                system_prompt = f"""
                你是一位專業的台股操盤手。
                目前時間：{time_info['datetime']}
                
                【即時搜尋資料】
                以下是網路上搜尋到的最新資訊，請務必依據這些資料進行分析，不要憑空捏造：
                {search_results}
                
                【回答要求】
                1. 請整合上述搜尋資料與你的技術分析知識回答。
                2. 若有搜尋到具體股價，請在分析中提及。
                3. 請給出明確的「多空判斷」與「操作建議」。
                """
                
                # 3. 呼叫 Gemini 1.5 Flash (最穩定版本)
                model = genai.GenerativeModel("gemini-1.5-flash")
                
                chat_history = []
                for msg in st.session_state.messages[:-1]:
                    role = "model" if msg["role"] == "assistant" else "user"
                    chat_history.append({"role": role, "parts": [msg["content"]]})
                
                chat = model.start_chat(history=chat_history)
                response = chat.send_message(f"{system_prompt}\n\n使用者問題：{prompt}")
                ai_response = response.text
                
                # 4. 顯示結果
                st.markdown(clean_json_from_text(ai_response))
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                
                # 5. 顯示圖表
                stock_code = extract_stock_code(prompt)
                st.components.v1.html(get_tradingview_widget(stock_code), height=600)
            
            except Exception as e:
                st.error(f"❌ 發生錯誤：{str(e)}")