import streamlit as st
import google.generativeai as genai
from datetime import datetime
import re
import pytz
import json
from duckduckgo_search import DDGS

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="台股 AI 操盤手 (資深專家版)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 初始化 API ---
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ 請設定 GEMINI_API_KEY 在 .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- 3. 搜尋函式 (優化版：針對股價準確度) ---
def search_web(keyword):
    search_content = ""
    error_msg = ""
    # 優化關鍵字：強制加上 "即時"、"行情"、"今日"，提高抓到最新股價的機率
    query = f"{keyword} 股價 即時行情 今日漲跌 鉅亨網 Yahoo股市"
    
    try:
        # 使用 DuckDuckGo 搜尋 (嘗試 html 模式)
        with st.spinner(f"🔍 正在搜尋 {keyword} 的最新市場報價..."):
            results = DDGS().text(query, region='tw-tw', max_results=6, backend='html')
            if not results:
                results = DDGS().text(query, region='tw-tw', max_results=6)

            if results:
                for res in results:
                    # 抓取標題與摘要，這通常包含股價數字
                    search_content += f"來源:{res['title']}\n摘要:{res['body']}\n---\n"
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
    """解析 AI 回傳的第一行 JSON 數據"""
    if not text: return None
    try:
        lines = text.split('\n')
        # 只檢查前 20 行，避免讀到內文的 JSON 範例
        for line in lines[:20]: 
            line = line.strip()
            if '{' in line and '}' in line and '"price"' in line:
                try:
                    # 擷取最外層的 {}
                    json_str = line[line.find('{'):line.rfind('}')+1]
                    data = json.loads(json_str)
                    if isinstance(data, dict) and "price" in data:
                        return data
                except: continue
    except: pass
    return None

def clean_text(text):
    """移除 JSON 字串，只顯示分析內文"""
    if not text: return ""
    # 移除被 markdown 包裹的 json
    text = re.sub(r'```json\s*\{.*?\}\s*```', '', text, flags=re.DOTALL)
    # 移除裸露的 json
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
    st.markdown("### 資深專家版")
    st.success("核心引擎：Gemini 2.5 Flash")
    
    if st.button("📊 大盤分析", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "分析今日台股大盤"})
        st.rerun()

    if st.button("🔥 熱門股推薦", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "推薦今日熱門股"})
        st.rerun()
    
    st.markdown("---")
    st.text(get_current_time_info()['datetime'])

st.title("📈 台股 AI 操盤手 (資深專家版)")

# 顯示歷史訊息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            # 嘗試解析並顯示指標
            data = parse_stock_data(message["content"])
            if data:
                c1, c2, c3 = st.columns(3)
                c1.metric("代號", data.get("code", "-"))
                c2.metric("股價", data.get("price", "-"))
                c3.metric("漲跌", data.get("change", "-"))
            # 顯示清洗後的文字內容
            st.markdown(clean_text(message["content"]))
        else:
            st.markdown(message["content"])

# 處理使用者輸入
if prompt := st.chat_input("請輸入股票代號 (例如 2330) 或詢問..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # 1. 執行搜尋
        search_res, err = search_web(prompt)
        
        # 除錯區塊 (可選)
        with st.expander("查看 AI 讀取的即時新聞資料", expanded=False):
            if err: st.error(err)
            else: st.text(search_res)

        with st.spinner("資深操盤手正在分析數據..."):
            try:
                # 2. 設定模型
                model = genai.GenerativeModel("gemini-2.5-flash")
                
                # 3. 組合 Prompt (整合 Role 檔案的精華)
                time_info = get_current_time_info()
                
                sys_prompt = f"""
                # Role (角色設定)
                你是一位擁有 20 年以上台股實戰經驗的資深操盤手與分析師。
                現在時間：{time_info['datetime']}，市場狀態：{time_info['status']}。
                你的風格穩健帶攻擊性，精通基本面、籌碼面、技術面與消息面的綜合研判。

                # Data Sources (資料來源)
                以下是剛剛從網路搜尋到的【最新即時資訊】：
                {search_res}
                
                【重要指令：股價檢核】
                1. 請仔細檢查搜尋結果中的「日期」與「數值」。
                2. 若搜尋結果是舊新聞(例如上個月)，請勿將其當作今日股價。
                3. 若找不到今日確切股價，請在 JSON 的 price 欄位填寫 "N/A"，並在內文中說明。

                # Output Format (輸出格式 - 非常重要)
                **請務必先輸出以下 JSON 格式在第一行，這是系統顯示用的：**
                {{"price": "123.4", "change": "+1.5 (+1.2%)", "code": "股票代號"}}
                
                接著，請依照以下架構進行專業分析：

                ## 🎯 [股票代號] [股票名稱] 投資評等：(強力買進/分批佈局/觀望/賣出)

                ### 1. 推薦原因 (The Why)
                * **財報亮點**: (依據搜尋到的EPS、營收數據)
                * **消息題材**: (依據搜尋到的新聞)
                * **技術型態**: (綜合判斷均線、KD、MACD、支撐壓力)

                ### 2. 持有週期建議 (Strategy)
                * **短線 (1週)**:
                * **中線 (2週以上)**:

                ### 3. 進出場規劃 (Action Plan)
                * **建議買入區間**: [價格]
                * **停利點**: [價格]
                * **停損點**: [價格] (請嚴格設定)

                ### 4. 風險提示
                * (請指出最大潛在風險)

                # Constraints (限制)
                * 若當天沒有適合的股票，請誠實告知「今日建議觀望」。
                * 文末必須加上：「*本建議僅供參考，投資人應獨立判斷，審慎評估並自負投資風險。*」

                使用者問題：{prompt}
                """
                
                # 4. 進行對話
                history = []
                for msg in st.session_state.messages[:-1]:
                    role = "model" if msg["role"] == "assistant" else "user"
                    history.append({"role": role, "parts": [clean_text(msg["content"])]})

                chat = model.start_chat(history=history)
                response = chat.send_message(sys_prompt)
                ai_msg = response.text
                
                # 5. 處理結果
                data = parse_stock_data(ai_msg)
                if data:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("代號", data.get("code", "-"))
                    c2.metric("股價", data.get("price", "-"))
                    c3.metric("漲跌", data.get("change", "-"))
                
                st.markdown(clean_text(ai_msg))
                st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                
                # 6. 顯示圖表
                code = extract_stock_code(prompt)
                st.components.v1.html(get_chart(code), height=600)

            except Exception as e:
                st.error(f"分析過程發生錯誤：{str(e)}")