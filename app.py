import streamlit as st
import google.generativeai as genai
from datetime import datetime
import re
import pytz
import json

# 設定頁面配置
st.set_page_config(
    page_title="台股 AI 操盤手 (專業版)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化 Gemini API
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ 請設定 GEMINI_API_KEY 在 .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 取得當前時間（台灣時區）
def get_current_time_info():
    """取得當前時間資訊，判斷是盤中還是盤後"""
    taiwan_tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(taiwan_tz)
    
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    hour = now.hour
    minute = now.minute
    
    # 判斷是否為交易日（週一到週五）
    is_trading_day = weekday < 5
    
    # 台股交易時間：09:00-13:30
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
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": ["週一", "週二", "週三", "週四", "週五", "週六", "週日"][weekday],
        "trading_status": trading_status,
        "is_trading_hours": is_trading_hours,
        "is_trading_day": is_trading_day,
    }

# 系統提示詞
def get_system_prompt(time_info):
    return f"""
    角色：你是一位擁有 20 年經驗的台股操盤手，風格穩健帶攻擊性，年化報酬率 > 5%。
    
    當前時間資訊：
    - 日期時間：{time_info['datetime']}
    - 星期：{time_info['weekday']}
    - 交易狀態：{time_info['trading_status']}
    - 是否為交易日：{'是' if time_info['is_trading_day'] else '否'}
    - 是否為交易時間：{'是' if time_info['is_trading_hours'] else '否'}
    
    任務：
    1. **重要：在回答的最開頭，必須先以 JSON 格式輸出股票數據**：
       - 如果分析的是特定股票，輸出格式：{{ "price": "最新股價", "change": "漲跌幅（例如：+2.5% 或 -1.2%）", "code": "股票代號（4位數）" }}
       - 如果分析的是大盤或無特定股票，輸出格式：{{"price": "", "change": "", "code": ""}}
       - JSON 必須是有效的 JSON 格式，且必須在回答的第一行或前幾行
       - JSON 必須單獨一行，不要與其他文字混在一起
       - 範例：{{"price": "580.00", "change": "+2.5%", "code": "2330"}}
       - 請務必使用 Google Search 搜尋最新股價和漲跌幅數據
    2. 根據當前時間判斷，如果是「盤中」則進行「盤中即時分析」，如果是「盤後」則進行「盤後籌碼分析」。
    3. 若使用者未指定股票，請先使用 Google Search 搜尋「今日成交量排行」或「熱門股」再推薦。
    4. 分析架構必須包含：
       - 基本面：財報數據、營收、獲利能力
       - 消息面：最新新聞、重大事件
       - 技術面：10種技術指標分析
         * MA (移動平均線)
         * KD (隨機指標)
         * MACD (指數平滑異同移動平均線)
         * RSI (相對強弱指標)
         * 布林通道
         * 成交量分析
         * 三大法人買賣超
         * OBV (能量潮指標)
         * 乖離率
         * 支撐壓力位
    5. 輸出格式：使用 Markdown，必須包含以下區塊：
       - **推薦原因**：簡潔說明為什麼推薦或分析這檔股票
       - **操作建議**：
         * 短線（1-5天）
         * 中線（1-4週）
         * 長線（1-3個月）
       - **關鍵價位**：
         * 停損價位
         * 停利價位
         * 支撐位
         * 壓力位
    6. 嚴格遵守：一定要使用 Google Search 聯網搜尋最新數據，不能憑空臆測。所有股價、成交量、技術指標數據都必須是即時或最新的。
    7. 回答要專業、有條理，使用繁體中文。
    """

# 從訊息中提取股票代號（4位數）
def extract_stock_code(text):
    """從文字中提取4位數股票代號"""
    pattern = r'\b(\d{4})\b'
    matches = re.findall(pattern, text)
    # 過濾掉明顯不是股票代號的數字（如年份、時間等）
    for match in matches:
        code = int(match)
        # 台股代號通常在 1000-9999 之間
        if 1000 <= code <= 9999:
            return match
    return None

# 從 AI 回覆中解析 JSON 數據
def parse_stock_data_from_response(response_text):
    """從 AI 回覆中解析股票數據 JSON，解析失敗時返回 None"""
    if not response_text:
        return None
        
    try:
        # 方法1：嘗試在前幾行找到 JSON（通常 AI 會在開頭輸出）
        lines = response_text.split('\n')
        for line in lines[:10]: # 只檢查前10行
            line = line.strip()
            if line.startswith('{') and '"price"' in line and '"change"' in line and '"code"' in line:
                try:
                    data = json.loads(line)
                    if isinstance(data, dict) and "price" in data and "change" in data and "code" in data:
                         # 如果所有欄位都是空字串，返回 None
                        if data["price"] == "" and data["change"] == "" and data["code"] == "":
                            return None
                        return data
                except json.JSONDecodeError:
                    continue

        # 方法2：使用正則表達式匹配 JSON 格式
        json_pattern = r'\{[\s\n]*"price"[\s\n]*:[\s\n]*"[^"]*"[\s\n]*,[\s\n]*"change"[\s\n]*:[\s\n]*"[^"]*"[\s\n]*,[\s\n]*"code"[\s\n]*:[\s\n]*"[^"]*"[\s\n]*\}'
        match = re.search(json_pattern, response_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        if match:
            json_str = match.group(0)
            # 清理可能的換行和空格
            json_str = re.sub(r'\s+', ' ', json_str).strip()
            # 解析 JSON
            data = json.loads(json_str)
            # 驗證數據格式
            if isinstance(data, dict) and "price" in data and "change" in data and "code" in data:
                # 如果所有欄位都是空字串，返回 None
                if data["price"] == "" and data["change"] == "" and data["code"] == "":
                    return None
                return data
    except (json.JSONDecodeError, KeyError, AttributeError, ValueError, TypeError) as e:
        # 解析失敗時靜默返回 None，不報錯
        pass
        
    return None

def clean_json_from_text(text):
    """移除文字中的 JSON 區塊，只保留分析內容，避免畫面雜亂"""
    if not text:
        return ""
    # 移除被 ```json ... ``` 包住的區塊
    text = re.sub(r'```json\s*\{.*?\}\s*```', '', text, flags=re.DOTALL)
    # 移除單純的 JSON {} 區塊 (針對 Prompt 格式，匹配包含 price, change, code 的 JSON)
    # 這裡使用較嚴格的匹配以免誤刪其他內容
    text = re.sub(r'\{[\s\n]*"price".*?"code".*?\}', '', text, flags=re.DOTALL)
    return text.strip()

# 生成 TradingView Widget HTML
def get_tradingview_widget(stock_code=None):
    """生成 TradingView Widget HTML"""
    if stock_code:
        symbol = f"TWSE:{stock_code}"
        title = f"台股 {stock_code}"
    else:
        symbol = "TWSE:TAIEX"
        title = "台股大盤 (加權指數)"
        
    return f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {{
      "autosize": true,
      "symbol": "{symbol}",
      "interval": "D",
      "timezone": "Asia/Taipei",
      "theme": "light",
      "style": "1",
      "locale": "zh_TW",
      "backgroundColor": "rgba(255, 255, 255, 1)",
      "gridColor": "rgba(0, 0, 0, 0.06)",
      "width": "100%",
      "height": "600",
      "hide_top_toolbar": false,
      "hide_legend": false,
      "allow_symbol_change": true,
      "save_image": false,
      "calendar": false,
      "support_host": "https://www.tradingview.com"
    }}
      </script>
    </div>
    """

# 初始化聊天歷史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 側邊欄
with st.sidebar:
    st.title("📈 台股 AI 操盤手")
    st.markdown("### 專業版")
    
    st.markdown("---")
    st.markdown("### ⚠️ 免責聲明")
    st.warning("本工具僅供分析參考，非投資建議。投資有風險，請謹慎評估。")
    
    st.markdown("---")
    st.markdown("### 🚀 快速分析")
    
    # 快速按鈕
    if st.button("📊 今日大盤分析", use_container_width=True):
        st.session_state.messages.append({
            "role": "user",
            "content": "請分析今日台股大盤走勢，包含技術面、資金流向和操作建議。"
        })
        st.rerun()

    if st.button("🔥 今日熱門股推薦", use_container_width=True):
        st.session_state.messages.append({
            "role": "user",
            "content": "請推薦今日台股熱門股票，並提供詳細分析。"
        })
        st.rerun()

    if st.button("💎 台積電 (2330) 分析", use_container_width=True):
        st.session_state.messages.append({
            "role": "user",
            "content": "請詳細分析台積電 (2330) 的投資價值，包含基本面、技術面和操作建議。"
        })
        st.rerun()
        
    st.markdown("---")
    
    # 顯示當前時間資訊
    time_info = get_current_time_info()
    st.markdown("### ⏰ 當前時間")
    st.info(f"""
    **{time_info['datetime']}**
    {time_info['weekday']} | {time_info['trading_status']}
    """)

# 主畫面
st.title("📈 台股 AI 操盤手 (專業版)")
st.info("💡 目前使用 Gemini 2.0 Flash 高速模型進行深度分析")

# 顯示聊天訊息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # 如果是 AI 的回覆，先解析並顯示股票數據
        if message["role"] == "assistant":
            try:
                stock_data = parse_stock_data_from_response(message["content"])
                if stock_data and stock_data.get("code") and stock_data.get("price"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("股票代號", stock_data.get("code", "-"))
                    with col2:
                        price_value = stock_data.get("price", "-")
                        st.metric("最新股價", price_value if price_value else "-")
                    with col3:
                        change_value = stock_data.get("change", "-")
                        # 判斷漲跌顏色
                        if change_value and change_value != "-" and change_value != "":
                            try:
                                # 嘗試提取數值用於 delta
                                delta_match = re.search(r'([+-]?\d+\.?\d*)', change_value)
                                delta_num = float(delta_match.group(1)) if delta_match else None
                                # delta_color="inverse" 代表紅漲綠跌 (台股模式)
                                st.metric("漲跌幅", change_value, delta=delta_num if delta_num else None, delta_color="inverse")
                            except (ValueError, AttributeError):
                                st.metric("漲跌幅", change_value)
                        else:
                            st.metric("漲跌幅", "-")
            except Exception:
                pass
            
            # 顯示清理過的文字 (隱藏原始 JSON)
            st.markdown(clean_json_from_text(message["content"]))
        else:
            st.markdown(message["content"])

        # 如果是 AI 的回覆，顯示 TradingView Widget
        if message["role"] == "assistant":
            # 檢查使用者問題中是否有股票代號
            user_messages = [m for m in st.session_state.messages[:st.session_state.messages.index(message)] 
                             if m["role"] == "user"]
            stock_code = None
            if user_messages:
                last_user_msg = user_messages[-1]["content"]
                stock_code = extract_stock_code(last_user_msg)
            
            # 顯示 TradingView Widget
            st.components.v1.html(
                get_tradingview_widget(stock_code),
                height=620
            )

# 使用者輸入
if prompt := st.chat_input("請輸入您的問題..."):
    # 加入使用者訊息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # AI 回覆
    with st.chat_message("assistant"):
        with st.spinner("🤔 AI 正在分析中，請稍候..."):
            try:
                # 取得時間資訊
                time_info = get_current_time_info()
                
                # 建立模型實例，使用正確的 tools 設定
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    tools=[{"google_search_retrieval": {}}],   # 正確的 Google Search 工具設定
                    generation_config={
                        "temperature": 0.7,
                        "top_p": 0.95,
                        "top_k": 40,
                        "max_output_tokens": 8192,
                    },
                    safety_settings=[
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                    ],
                )

                # 建立對話歷史
                chat_history = []
                for msg in st.session_state.messages[:-1]: # 排除剛加入的使用者訊息
                    if msg["role"] == "user":
                        chat_history.append({"role": "user", "parts": [msg["content"]]})
                    elif msg["role"] == "assistant":
                        chat_history.append({"role": "model", "parts": [msg["content"]]})

                # 建立聊天會話
                chat = model.start_chat(history=chat_history)
                
                # 組合系統提示詞和使用者問題
                system_prompt = get_system_prompt(time_info)
                full_prompt = f"{system_prompt}\n\n使用者問題：{prompt}"
                
                # 發送訊息
                response = chat.send_message(full_prompt)
                
                # 取得回覆內容
                ai_response = response.text
                
                # 解析股票數據（如果解析失敗會返回 None，不會報錯）
                try:
                    stock_data = parse_stock_data_from_response(ai_response)
                    
                    # 如果有股票數據，顯示 metrics
                    if stock_data and stock_data.get("code") and stock_data.get("price"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("股票代號", stock_data.get("code", "-"))
                        with col2:
                            price_value = stock_data.get("price", "-")
                            st.metric("最新股價", price_value if price_value else "-")
                        with col3:
                            change_value = stock_data.get("change", "-")
                            # 判斷漲跌顏色
                            if change_value and change_value != "-" and change_value != "":
                                try:
                                    # 嘗試提取數值用於 delta
                                    delta_match = re.search(r'([+-]?\d+\.?\d*)', change_value)
                                    delta_num = float(delta_match.group(1)) if delta_match else None
                                    # delta_color="inverse" 代表紅漲綠跌 (台股模式)
                                    st.metric("漲跌幅", change_value, delta=delta_num if delta_num else None, delta_color="inverse")
                                except (ValueError, AttributeError):
                                    st.metric("漲跌幅", change_value)
                            else:
                                st.metric("漲跌幅", "-")
                except Exception:
                    # 如果解析或顯示過程中出現任何錯誤，靜默跳過，不影響主要內容顯示
                    pass

                # 顯示 AI 回覆 (使用 clean_json_from_text 隱藏原始 JSON)
                st.markdown(clean_json_from_text(ai_response))
                
                # 儲存 AI 回覆到歷史 (這裡保留原始 response 以便下次對話時 AI 記得它輸出過什麼)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                
                # 顯示 TradingView Widget
                stock_code = extract_stock_code(prompt)
                st.components.v1.html(
                    get_tradingview_widget(stock_code),
                    height=620
                )

            except Exception as e:
                error_str = str(e)
                # 檢查是否為 429 錯誤（API 額度上限）
                if "429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower():
                    st.error("⚠️ API 額度已達上限，請等待一分鐘後再試")
                    st.info("💡 提示：Gemini API 有使用頻率限制，請稍候再試。")
                else:
                    error_msg = f"❌ 發生錯誤：{error_str}"
                    st.error(error_msg)
                    st.info("💡 提示：請確認 API 金鑰是否正確，以及網路連線是否正常。")