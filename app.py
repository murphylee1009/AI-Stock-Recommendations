import streamlit as st
import google.generativeai as genai
from datetime import datetime
import re
import pytz
import json
from duckduckgo_search import DDGS

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="台股 AI 操盤手 (穩定修復版)",
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
    search_content = ""
    error_msg = ""
    # 增加關鍵字權重，確保搜尋結果與股市有關
    query = f"{keyword} 台灣股市 股價 新聞"
    
    try:
        # 嘗試使用 html 模式，通常比較穩定
        results = DDGS().text(query, region='tw-tw', max_results=5, backend='html')
        
        # 如果 html 模式沒抓到，嘗試預設模式
        if not results:
            results = DDGS().text(query, region='tw-tw', max_results=5)

        if results:
            for res in results:
                search_content += f"- 標題: {res['title']}\n  連結: {res['href']}\n  摘要: {res['body']}\n\n"
        else:
            search_content = "無搜尋結果 (可能暫時無法連線，將依賴模型內建知識)"
            
    except Exception as e:
        error_msg = str(e)
        search_content = f"搜尋發生錯誤: {error_msg}"
        
    return search_content, error_msg

# --- 4. 輔助工具 ---
def get_current_time_info():
    taiwan_tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(taiwan_tz)
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    
    is_trading_day = weekday < 5
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

# --- 5. 介面與邏輯 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("📈 台股 AI 操盤手")
    st.success("🚀 核心：Gemini 2.5 Flash")
    st.info("✅ 搜尋引擎：DuckDuckGo (穩定版)")
    
    if st.button("📊 今日大盤分析", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "請搜尋今日台股大盤最新走勢，分析技術面與外資動向。"})
        st.rerun()

    if st.button("🔥 今日熱門股推薦", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "請搜尋今日台股熱門股票，推薦 1-2 檔並分析。"})
        st.rerun()
    
    st.markdown("---")
    st.text(get_current_time_info()['datetime'])

st.title("📈 台股 AI 操盤手 (穩定修復版)")

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
        # 1. 執行搜尋 (這裡絕對不會報錯，因為是純 Python 程式)
        search_result_text, error_msg = search_web(prompt)
        
        # 顯示搜尋狀況 (讓你知道有沒有抓到資料)
        with st.expander("👀 查看 AI 讀取的搜尋資料", expanded=False):
            if error_msg:
                st.error(f"搜尋模組回報錯誤: {error_msg}")
            elif "無搜尋結果" in search_result_text:
                st.warning("⚠️ 搜尋回傳空值")
            else:
                st.success("✅ 成功抓取網路資料")
                st.code(search_result_text)

        with st.spinner("🚀 Gemini 2.5 正在分析..."):
            try:
                # --- 關鍵：不使用任何 tools 設定，直接用純文字對話 ---
                # 這樣就避開了所有 SDK 版本不相容的問題
                model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash", # 使用你確認可用的版本
                    generation_config={
                        "temperature": 0.7,
                        "max_output_tokens": 8192,
                    }
                )
                
                # 準備 Prompt (將搜尋結果手動餵給 AI)
                time_info = get_current_time_info()
                system_prompt = f"""
                角色：專業台股操盤手。時間：{time_info['datetime']}。
                
                【即時市場資訊】
                以下是剛剛搜尋到的資料，請依據此內容回答，若資料包含股價請優先引用：
                {search_result_text}
                
                【任務】
                1. 第一行輸出 JSON：{{"price": "數值", "change": "數值", "code": "代號"}}
                   (若搜尋資料中無股價，請填 "N/A")
                2. 進行技術面與籌碼面分析。
                3. 使用者問題：{prompt}
                """
                
                chat_history = []
                for msg in st.session_state.messages[:-1]:
                    role = "model" if msg["role"] == "assistant" else "user"
                    clean_content = clean_json_from_text(msg["content"])
                    chat_history.append({"role": role, "parts": [clean_content]})

                chat = model.start_chat(history=chat_history)
                response = chat.send_message(system_prompt)
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
                st.components.v1.html(get_tradingview_widget(stock_code), height