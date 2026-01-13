import streamlit as st
import google.generativeai as genai
from datetime import datetime
import re
import pytz
import json
from duckduckgo_search import DDGS

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="台股 AI 操盤手",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 初始化 API ---
if "GEMINI_API_KEY" not in st.secrets:
    st.error("請設定 GEMINI_API_KEY")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- 3. 搜尋函式 ---
def search_web(keyword):
    search_content = ""
    error_msg = ""
    query = f"{keyword} 台灣股市 股價 新聞"
    
    try:
        # 使用 html 後端搜尋，較為穩定
        results = DDGS().text(query, region='tw-tw', max_results=5, backend='html')
        if not results:
            results = DDGS().text(query, region='tw-tw', max_results=5)

        if results:
            for res in results:
                search_content += f"標題:{res['title']}\n摘要:{res['body']}\n\n"
        else:
            search_content = "無搜尋結果"
            
    except Exception as e:
        error_msg = str(e)
        search_content = f"搜尋錯誤: {error_msg}"
        
    return search_content, error_msg

# --- 4. 輔助工具 ---
def get_current_time_info():
    taiwan_tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(taiwan_tz)
    weekday = now.weekday()
    
    is_trading_day = weekday < 5
    trading_status = "休市"
    if is_trading_day:
        h = now.hour
        m = now.minute
        if 9 <= h < 13: trading_status = "盤中"
        elif h == 13 and m <= 30: trading_status = "盤中"
        elif h < 9: trading_status = "盤前"
        else: trading_status = "盤後"
        
    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "status": trading_status
    }

def extract_stock_code(text):
    if not text: return None
    matches = re.findall(r'\b(\d{4})\b', text)
    for match in matches:
        if 1000 <= int(match) <= 9999: return match
    return None

def parse_stock_data(text):
    if not text: return None
    try:
        lines = text.split('\n')
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

def clean_text(text):
    if not text: return ""
    text = re.sub(r'```json\s*\{.*?\}\s*```', '', text, flags=re.DOTALL)
    text = re.sub(r'\{[\s\n]*"price".*?"code".*?\}', '', text, flags=re.DOTALL)
    return text.strip()

def get_chart(stock_code=None):
    symbol = f"TWSE:{stock_code}" if stock_code else "TWSE:TAIEX"
    return f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {{
      "autosize": true, "symbol": "{symbol}", "interval": "D", "timezone": "Asia/Taipei", "theme": "light", "style": "1", "locale": "zh_TW", "hide_top_toolbar": false, "allow_symbol_change": true, "save_image": false, "calendar": false, "support_host": "https://www.tradingview.com"
    }}
      </script>
    </div>
    """

# --- 5. 主程式 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("📈 台股 AI 操盤手")
    st.success("引擎：Gemini 2.5 Flash")
    
    if st.button("📊 大盤分析", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "分析今日台股大盤"})
        st.rerun()

    if st.button("🔥 熱門股推薦", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "推薦今日熱門股"})
        st.rerun()
    
    st.markdown("---")
    st.text(get_current_time_info()['datetime'])

# 這是你報錯的第 134 行附近，我已經確保它是完整的字串
st.title("📈 台股 AI 操盤手 (修復版)")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            data = parse_stock_data(message["content"])
            if data:
                c1, c2, c3 = st.columns(3)
                c1.metric("代號", data.get("code", "-"))
                c2.metric("股價", data.get("price", "-"))
                c3.metric("漲跌", data.get("change", "-"))
            st.markdown(clean_text(message["content"]))
        else:
            st.markdown(message["content"])

if prompt := st.chat_input("請輸入股票代號..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # 1. 執行搜尋
        search_res, err = search_web(prompt)
        
        # 顯示除錯資訊
        with st.expander("查看搜尋結果", expanded=False):
            if err: st.error(err)
            else: st.text(search_res)

        with st.spinner("Gemini 2.5 分析中..."):
            try:
                # 2. 設定模型
                model = genai.GenerativeModel("gemini-2.5-flash")
                
                # 3. 組合 Prompt
                time_info = get_current_time_info()
                sys_prompt = f"""
                角色：台股操盤手。時間：{time_info['datetime']}。
                參考資料：
                {search_res}
                
                任務：
                1. 第一行JSON：{{"price": "數值", "change": "數值", "code": "代號"}}
                2. 詳細分析。
                3. 用戶問題：{prompt}
                """
                
                # 4. 對話
                history = []
                for msg in st.session_state.messages[:-1]:
                    role = "model" if msg["role"] == "assistant" else "user"
                    history.append({"role": role, "parts": [clean_text(msg["content"])]})

                chat = model.start_chat(history=history)
                response = chat.send_message(sys_prompt)
                ai_msg = response.text
                
                # 5. 顯示
                data = parse_stock_data(ai_msg)
                if data:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("代號", data.get("code", "-"))
                    c2.metric("股價", data.get("price", "-"))
                    c3.metric("漲跌", data.get("change", "-"))
                
                st.markdown(clean_text(ai_msg))
                st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                
                # 這是之前報錯的第 220 行附近，我確認括號已閉合
                code = extract_stock_code(prompt)
                st.components.v1.html(get_chart(code), height=600)

            except Exception as e:
                st.error(f"錯誤：{str(e)}")