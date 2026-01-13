import streamlit as st
import google.generativeai as genai
from datetime import datetime
import re
import pytz
import json
from duckduckgo_search import DDGS  # 引入搜尋工具

# --- 1. 頁面設定 (必須在第一行) ---
st.set_page_config(
    page_title="台股 AI 操盤手 (專業版)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 初始化 API ---
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ 請設定 GEMINI_API_KEY 在 .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- 3. 搜尋函式 (DuckDuckGo) ---
def search_web(keyword):
    """使用 DuckDuckGo 搜尋最新財經資訊"""
    try:
        # 搜尋台灣地區的財經新聞與股價
        with st.spinner(f"🔍 正在為您搜尋：{keyword} ..."):
            results = DDGS().text(f"{keyword} 台灣股市 股價 新聞", region='tw-tw', max_results=5)
            search_content = ""
            if results:
                for res in results:
                    search_content += f"- 標題: {res['title']}\n  連結: {res['href']}\n  摘要: {res['body']}\n\n"
            return search_content if search_content else "無搜尋結果"
    except Exception as e:
        return f"搜尋發生錯誤: {str(e)}"

# --- 4. 輔助工具函式 ---
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
    """從文字中提取4位數股票代號"""
    if not text: return None
    pattern = r'\b(\d{4})\b'
    matches = re.findall(pattern, text)
    for match in matches:
        code = int(match)
        if 1000 <= code <= 9999:
            return match
    return None

def parse_stock_data_from_response(response_text):
    """從 AI 回覆中解析 JSON 數據"""
    if not response_text: return None
    try:
        lines = response_text.split('\n')
        for line in lines[:15]: # 檢查前15行
            line = line.strip()
            # 嘗試抓取 JSON 格式
            if '{' in line and '}' in line and '"price"' in line:
                try:
                    # 提取 {} 內的內容
                    json_str = line[line.find('{'):line.rfind('}')+1]
                    data = json.loads(json_str)
                    if isinstance(data, dict) and "price" in data and "code" in data:
                        if data["price"] == "" and data["code"] == "": return None
                        return data
                except: continue
    except: pass
    return None

def clean_json_from_text(text):
    """移除顯示用的 JSON，保留分析內容"""
    if not text: return ""
    text = re.sub(r'```json\s*\{.*?\}\s*```', '', text, flags=re.DOTALL)
    text = re.sub(r'\{[\s\n]*"price".*?"code".*?\}', '', text, flags=re.DOTALL)
    return text.strip()

def get_tradingview_widget(stock_code=None):
    """生成 TradingView Widget"""
    symbol = f"TWSE:{stock_code}" if stock_code else "TWSE:TAIEX"
    title = f"台股 {stock_code}" if stock_code else "台股大盤"
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

# --- 5. 系統提示詞 (維持專業版設定) ---
def get_system_prompt(time_info):
    return f"""
    角色：你是一位擁有 20 年經驗的台股操盤手，風格穩健帶攻擊性。
    當前時間：{time_info['datetime']} ({time_info['weekday']}) | 狀態：{time_info['trading_status']}
    
    任務要求：
    1. **最重要的格式要求**：在回答的最開頭，必須輸出一個單行的 JSON 格式數據，包含股價資訊。
       - 格式範例：{{"price": "1050.00", "change": "+15.0 (+1.45%)", "code": "2330"}}
       - 如果沒有特定股票或無法取得，請填空：{{"price": "", "change": "", "code": ""}}
       - 這行 JSON 不要用 markdown code block 包起來，直接放第一行。
    
    2. **資料來源**：請務必根據 Prompt 中提供的【DuckDuckGo 搜尋結果】進行分析，這是最新的市場資訊。
    
    3. **分析架構**：
       - **結論**：直接給出多/空/觀望建議。
       - **基本面/消息面**：整合搜尋到的新聞與營收資訊。
       - **技術面**：分析均線、支撐壓力 (配合 TradingView 畫面)。
       - **操作策略**：給出短中長線的具體價位建議。
    
    4. 請使用繁體中文，語氣專業。
    """

# --- 6. 介面與邏輯 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("📈 台股 AI 操盤手")
    st.markdown("### 專業旗艦版")
    st.success(f"🚀 核心模型：Gemini 2.5 Flash")
    
    st.markdown("---")
    st.markdown("### ⚠️ 免責聲明")
    st.warning("本工具僅供分析參考，非投資建議。")
    
    st.markdown("---")
    st.markdown("### 🚀 快速分析")
    
    if st.button("📊 今日大盤分析", use_container_width=True):
        st.session_state.messages.append({
            "role": "user",
            "content": "請分析今日台股大盤走勢，包含技術面、外資動向和操作建議。"
        })
        st.rerun()

    if st.button("🔥 今日熱門股推薦", use_container_width=True):
        st.session_state.messages.append({
            "role": "user",
            "content": "請推薦今日台股熱門股票，並提供詳細分析。"
        })
        st.rerun()
    
    # 已移除台積電快速按鈕
    
    st.markdown("---")
    time_info = get_current_time_info()
    st.markdown("### ⏰ 當前時間")
    st.info(f"{time_info['datetime']}\n{time_info['trading_status']}")

# 主畫面
st.title("📈 台股 AI 操盤手 (專業版)")

# 顯示聊天訊息歷史
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # 嘗試解析並顯示股票 Metrics
        if message["role"] == "assistant":
            stock_data = parse_stock_data_from_response(message["content"])
            if stock_data:
                c1, c2, c3 = st.columns(3)
                c1.metric("股票代號", stock_data.get("code", "-"))
                c2.metric("最新股價", stock_data.get("price", "-"))
                c3.metric("漲跌幅", stock_data.get("change", "-"))
            st.markdown(clean_json_from_text(message["content"]))
        else:
            st.markdown(message["content"])

# 處理使用者輸入
if prompt := st.chat_input("請輸入股票代號或問題..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # 1. 先執行 DuckDuckGo 搜尋 (取得最新資料)
            search_results = search_web(prompt)
            
            # 2. 準備 Prompt
            time_info = get_current_time_info()
            system_prompt = get_system_prompt(time_info)
            
            # 組合完整 Prompt：系統提示 + 搜尋結果 + 使用者問題
            full_prompt = f"""
            {system_prompt}
            
            【即時搜尋結果 (DuckDuckGo)】
            {search_results}
            
            使用者問題：{prompt}
            """
            
            # 3. 初始化 Gemini 2.5 Flash (不需 tools 設定，因已手動搜尋)
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash", # ✅ 使用你確認可用的版本
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                }
            )
            
            # 4. 建立對話並發送
            chat_history = []
            for msg in st.session_state.messages[:-1]:
                role = "model" if msg["role"] == "assistant" else "user"
                # 簡單處理歷史紀錄，避免 token 過多，這裡只傳送純文字
                clean_content = clean_json_from_text(msg["content"])
                chat_history.append({"role": role, "parts": [clean_content]})
            
            chat = model.start_chat(history=chat_history)
            
            with st.spinner("🚀 Gemini 2.5 正在整合最新資訊分析中..."):
                response = chat.send_message(full_prompt)
                ai_response = response.text
            
            # 5. 解析數據並顯示 UI
            stock_data = parse_stock_data_from_response(ai_response)
            if stock_data:
                c1, c2, c3 = st.columns(3)
                c1.metric("股票代號", stock_data.get("code", "-"))
                c2.metric("最新股價", stock_data.get("price", "-"))
                c3.metric("漲跌幅", stock_data.get("change", "-"))
            
            # 顯示回答內容
            st.markdown(clean_json_from_text(ai_response))
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            
            # 6. 顯示圖表
            stock_code = extract_stock_code(prompt)
            st.components.v1.html(get_tradingview_widget(stock_code), height=620)

        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                st.error("⚠️ 速度限制：請稍等幾秒後再試。")
            else:
                st.error(f"❌ 發生錯誤：{error_str}")
                st.info("若為 404 錯誤，請確認 API Key 是否仍有 gemini-2.5-flash 權限。")