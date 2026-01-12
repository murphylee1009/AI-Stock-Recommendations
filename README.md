# 台股 AI 操盤手 (專業版)

使用 Streamlit 和 Google Gemini 2.0 Flash 模型打造的台股分析應用程式。

## 功能特色

- 🤖 AI 驅動的股市分析，使用 Gemini 2.0 Flash 模型
- 🔍 啟用 Google Search (Grounding) 功能，獲取最新股價和市場資訊
- 📊 自動嵌入 TradingView 技術分析圖表
- ⏰ 智能判斷盤中/盤後，提供對應的分析模式
- 💬 流暢的對話式介面

## 安裝步驟

### 1. 安裝依賴套件

```bash
pip install -r requirements.txt
```

### 2. 設定 API 金鑰

#### Windows PowerShell：
```powershell
# 建立 .streamlit 目錄（如果不存在）
New-Item -ItemType Directory -Force -Path .streamlit

# 建立 secrets.toml 檔案
Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml

# 編輯 secrets.toml，將 your-gemini-api-key-here 替換為您的實際 API 金鑰
notepad .streamlit/secrets.toml
```

#### 或手動建立：

1. 建立 `.streamlit` 資料夾（如果不存在）
2. 在 `.streamlit` 資料夾中建立 `secrets.toml` 檔案
3. 在檔案中輸入：

```toml
GEMINI_API_KEY = "您的-Gemini-API-金鑰"
```

### 3. 取得 Gemini API 金鑰

1. 前往 [Google AI Studio](https://makersuite.google.com/app/apikey)
2. 登入您的 Google 帳號
3. 點擊「Create API Key」
4. 複製 API 金鑰並貼到 `secrets.toml` 中

## 執行應用程式

```bash
streamlit run app.py
```

應用程式會自動在瀏覽器中開啟，預設網址為 `http://localhost:8501`

## 使用說明

1. **快速分析**：使用側邊欄的快速按鈕進行常見分析
2. **自訂問題**：在主畫面輸入框輸入任何股市相關問題
3. **查看圖表**：AI 回覆後會自動顯示對應的 TradingView 技術分析圖表
4. **股票代號**：在問題中包含 4 位數股票代號（如 2330），會自動顯示該股票的圖表

## 注意事項

- ⚠️ 本工具僅供分析參考，非投資建議
- 🔑 請妥善保管您的 API 金鑰，不要將 `secrets.toml` 上傳到公開的版本控制系統
- 📊 TradingView Widget 需要網路連線才能正常顯示
- 💰 API 使用可能產生費用，請注意 Google 的計費政策

## 技術架構

- **前端框架**：Streamlit
- **AI 模型**：Google Gemini 2.0 Flash
- **搜尋功能**：Google Search (Grounding)
- **圖表工具**：TradingView Widget
- **時區處理**：pytz (Asia/Taipei)

## 授權

本專案僅供學習和研究使用。

