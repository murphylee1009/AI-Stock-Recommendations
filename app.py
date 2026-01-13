import streamlit as st
import google.generativeai as genai
from datetime import datetime
import re
import pytz
import json

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="台股 AI 操盤手 (Google原生版)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 初始化 API ---
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ 請設定 GEMINI_API_KEY 在 .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- 3. 輔助工具函式 ---
def get_current_time_info():
    """取得當前時間資訊"""
    taiwan_tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(taiwan_tz)
    
    weekday = now.weekday()
    # 判斷盤中盤後邏輯
    is_trading_day = weekday < 5
    hour = now.hour
    minute = now.minute
    trading_status = "休市"
    if is_trading_day:
        if 9 <= hour < 13: trading_status = "盤中"
        elif hour == 13 and minute <= 30: trading_status = "盤中"
        elif hour < 9: trading_status = "盤前"
        else: trading_status = "盤後"

    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": ["週一", "週二", "週三", "週四", "週五", "週六", "週日"][weekday],
        "trading_status": trading_status
    }

def extract_stock_code(text):
    if not text: return None
    matches = re.findall(r'\b(\d{4})\b', text)
    for match in matches:
        if 1000 <= int(match) <= 9999: return match
    return None

def parse_stock_data_from_response(response_text):
    if not response_text: return None
    try:
        lines = response_text.split('\n')
        for line in lines[:15]: 
            if '{' in line and '}' in line and '"price"' in line:
                try:
                    json_str = line[line.find('{'):line.rfind('}')+1]
                    data = json.loads(json_str)
                    if isinstance(data, dict) and "price" in data:
                        return data
                except: continue
    except: pass
    return None

def clean_json_from_text(text):
    if not text: return ""
    text = re.sub(r'```json\s*\{.*?\}\s*```', '', text, flags=re.DOTALL)
    text = re.sub(r'\{[\s\n]*"price".*?"code".*?\}', '', text, flags=re.DOTALL)
    return text.strip()

def get_tradingview_widget(stock_code=None):
    symbol = f"TWSE:{stock_code}" if stock_code else "TWSE:TAIEX"
    return f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {{
      "autosize": true, "symbol": "{symbol}", "interval": "D", "timezone": "Asia/Taipei", "theme": "light", "style": "1", "locale": "zh_TW", "backgroundColor": "rgba(255, 255, 255, 1)", "gridColor": "rgba(0, 0, 0, 0.06)", "width": "100%", "height": "600", "hide_top_toolbar": false, "hide_legend": false, "allow_symbol_change": true, "save_image": false, "calendar": false, "support_host": "https://www.tradingview.com"
    }}
      </script>
    </div>
    """

# --- 4. 系統提示詞 ---
def get_system_prompt(time_info):
    return f"""
    角色：你是一位擁有 20 年經驗的台股操盤手。
    時間：{time_info['datetime']} ({time_info['weekday']}) | 狀態：{time_info['trading_status']}
    
    【核心指令：Google Search】
    請務必使用你的內建搜尋工具，針對使用者問題進行聯網搜尋最新財經資訊。
    
    【回答格式】
    1. 第一行請輸出 JSON (若有股價)：{{"price": "123.4", "change": "+1.5", "code": "xxxx"}}
    2. 若無法取得股價，請填 "N/A"。
    3. 分析內容請包含搜尋到的最新新聞、技術面與操作建議。
    """

# --- 5. 介面與邏輯 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("📈 台股 AI 操盤手")
    st.success("🚀 核心：Gemini 2.5 Flash")
    st.info("✅ Google 原生搜尋")
    
    if st.button("📊 今日大盤分析", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "請搜尋今日台股大盤最新走勢，分析技術面與外資動向。"})
        st.rerun()

    if st.button("🔥 今日熱門股推薦", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "請搜尋今日台股熱門股票，推薦 1-2 檔並分析。"})
        st.rerun()
    
    st.markdown("---")
    st.text(get_current_time_info()['datetime'])

st.title("📈 台股 AI 操盤手 (旗艦版)")

# 顯示歷史
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            stock_data = parse_stock_data_from_response(message["content"])
            if stock_data:
                c1, c2, c3 = st.columns(3)
                c1.metric("代號", stock_data.get("code", "-"))
                c2.metric("股價", stock_data.get("price", "-"))
                c3.metric("漲跌", stock_data.get("change", "-"))
            st.markdown(clean_json_from_text(message["content"]))
        else:
            st.markdown(message["content"])

if prompt := st.chat_input("請輸入股票代號或問題..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🚀 Gemini 2.5 正在進行 Google 搜尋..."):
            try:
                # --- 關鍵修正：遵照 400 錯誤指示 ---
                # 錯誤說：Please use google_search tool instead.
                # 所以我們這裡改用 google_search 的字典寫法
                
                tool_config = {"google_search": {}} # 這就是它要的正確名稱
                
                model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash",
                    tools=[tool_config], # 放入列表
                    generation_config={
                        "temperature": 0.7,
                        "max_output_tokens": 8192,
                    }
                )
                
                # 處理歷史訊息 (清理 JSON 避免干擾)
                chat_history = []
                for msg in st.session_state.messages[:-1]:
                    role = "model" if msg["role"] == "assistant" else "user"
                    clean_content = clean_json_from_text(msg["content"])
                    chat_history.append({"role": role, "parts": [clean_content]})

                chat = model.start_chat(history=chat_history)
                
                # 發送訊息
                time_info = get_current_time_info()
                full_prompt = f"{get_system_prompt(time_info)}\n\n使用者問題：{prompt}"
                
                response = chat.send_message(full_prompt)
                ai_response = response.text
                
                # 顯示結果
                stock_data = parse_stock_data_from_response(ai_response)
                if stock_data:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("代號", stock_data.get("code", "-"))
                    c2.metric("股價", stock_data.get("price", "-"))
                    c3.metric("漲跌", stock_data.get("change", "-"))
                
                st.markdown(clean_json_from_text(ai_response))
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                
                stock_code = extract_stock_code(prompt)
                st.components.v1.html(get_tradingview_widget(stock_code), height=620)

            except Exception as e:
                # 這次如果還有錯，我們需要知道是語法錯還是權限錯
                st.error(f"❌ 發生錯誤：{str(e)}")
                st.info("系統提示：請確認是否已更新 requirements.txt 為 clean setup。")