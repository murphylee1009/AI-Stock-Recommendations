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
    hour = now.hour
    minute = now.minute
    
    is_trading_day = weekday < 5
    is_trading_hours = False
    trading_status = ""
    
    if is_trading_day:
        if hour < 9:
            trading_status = "盤前"
        elif hour == 9 and minute < 0:
            trading_status = "盤前"
        elif (hour == 9 and minute >= 0) or (hour >= 10 and hour < 13) or (hour == 13 and minute <= 30):
            trading_status = "盤中"
            is_trading_hours = True
        else:
            trading_status = "盤後"
    else:
        trading_status = "休市"
        
    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": ["週一", "週二", "週三", "週四", "週五", "週六", "週日"][weekday],
        "trading_status": trading_status,
        "is_trading_hours": is_trading_hours,
        "is_trading_day": is_trading_day,
    }

def extract_stock_code(text):
    if not text: return None
    pattern = r'\b(\d{4})\b'
    matches = re.findall(pattern, text)
    for match in matches:
        code = int(match)
        if 1000 <= code <= 9999:
            return match
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
    
    【你的核心能力：Google Search】
    你擁有原生的 Google 搜尋工具。
    當使用者詢問股價、大盤或分析時，**請務必使用工具進行聯網搜尋**，獲取當下最新的股價與新聞。
    
    【任務要求】
    1. **回答格式**：第一行必須是 JSON 數據（如果有股價）。
       範例：{{"price": "1080.00", "change": "+15.0 (+1.45%)", "code": "2330"}}
       若無股價則填 "N/A"。
    2. **分析邏輯**：
       - 整合搜尋到的【最新新聞】與【財報數據】。
       - 結合技術面（均線、KD、RSI）給出操作建議。
    3. **操作建議**：
       - 明確指出「多/空」方向。
       - 給出短中長線的關鍵價位。
    
    請使用繁體中文回答。
    """

# --- 5. 介面與邏輯 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("📈 台股 AI 操盤手")
    st.markdown("### 旗艦版")
    st.success("🚀 核心：Gemini 2.5 Flash")
    st.info("✅ 已啟用 Google 原生搜尋")
    
    st.markdown("---")
    
    if st.button("📊 今日大盤分析", use_container_width=True):
        st.session_state.messages.append({
            "role": "user",
            "content": "請使用 Google 搜尋今日台股大盤最新走勢，分析技術面與外資動向。"
        })
        st.rerun()

    if st.button("🔥 今日熱門股推薦", use_container_width=True):
        st.session_state.messages.append({
            "role": "user",
            "content": "請搜尋今日台股成交量大且漲勢強勁的熱門股票，推薦 1-2 檔並分析。"
        })
        st.rerun()
    
    st.markdown("---")
    time_info = get_current_time_info()
    st.markdown(f"**{time_info['datetime']}**")

st.title("📈 台股 AI 操盤手 (Google原生版)")

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

# 輸入框
if prompt := st.chat_input("請輸入股票代號或問題..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🚀 Gemini 2.5 正在進行 Google 搜尋分析..."):
            try:
                time_info = get_current_time_info()
                system_prompt = get_system_prompt(time_info)
                
                # --- 關鍵修改：使用原廠 Google Search 工具 ---
                # tools=[{"google_search": {}}] 是啟動搜尋的關鍵指令
                model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash",
                    tools=[{"google_search": {}}], 
                    generation_config={
                        "temperature": 0.7,
                        "max_output_tokens": 8192,
                    }
                )
                
                # 處理歷史訊息轉換 (Google Search 工具對歷史訊息格式要求較嚴格)
                chat_history = []
                for msg in st.session_state.messages[:-1]:
                    role = "model" if msg["role"] == "assistant" else "user"
                    # 清理內容，避免 JSON 干擾
                    clean_content = clean_json_from_text(msg["content"])
                    chat_history.append({"role": role, "parts": [clean_content]})

                chat = model.start_chat(history=chat_history)
                
                # 發送訊息
                response = chat.send_message(f"{system_prompt}\n\n使用者問題：{prompt}")
                ai_response = response.text
                
                # 解析與顯示
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
                error_str = str(e)
                if "429" in error_str:
                     st.error("⚠️ Google 搜尋請求過於頻繁 (429)，請稍等 30 秒再試。")
                elif "not found" in error_str.lower():
                     st.error(f"❌ 模型設定錯誤：{error_str} (請確認您的帳號是否支援 2.5 搜尋)")
                else:
                    st.error(f"❌ 發生錯誤：{error_str}")