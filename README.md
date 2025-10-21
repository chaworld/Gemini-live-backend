# Gemini Live Backend

這是一個 Gemini Live API 的 WebSocket 代理後端服務，讓你可以輕鬆地將 Gemini 的語音對話功能整合到你的應用中。

> ⚠️ **重要提醒**：Gemini Live Mode API 目前需要付費帳戶才能使用（截至 2025/10/21）

## 功能特色

- 🎤 **即時語音串流**：支援雙向音訊串流處理
- 🔄 **WebSocket 代理**：將客戶端連線轉發到 Google Gemini API
- 🌐 **CORS 支援**：方便前端開發整合
- 🧪 **測試客戶端**：內附完整的測試腳本

## 系統需求

- Python 3.8 或以上版本
- Google API Key（需要付費帳戶）
- 虛擬環境（建議）

## 安裝步驟

### 1. 克隆專案

```bash
git clone https://github.com/chaworld/Gemini-live-backend.git
cd Gemini-live-backend
```

### 2. 建立虛擬環境

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安裝依賴套件

```bash
pip install -r requirements.txt
```

### 4. 設定環境變數

在專案根目錄建立 `.env` 檔案，並加入你的 Google API Key：

```env
GOOGLE_API_KEY=你的_API_KEY
```

> 💡 **如何取得 API Key**：
> 1. 前往 [Google AI Studio](https://aistudio.google.com/)
> 2. 登入你的 Google 帳號（需付費帳戶）
> 3. 建立新的 API Key

## 使用方法

### 啟動伺服器

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8080
```

伺服器啟動後會監聽 `ws://localhost:8080/ws/gemini_live`

### 測試伺服器

使用內附的測試客戶端來驗證伺服器功能：

```bash
python test_client.py
```

> 📝 **注意**：測試前需要準備一個名為 `test_input.wav` 的音訊檔案（24000Hz, 單聲道, PCM_16）

## API 端點

### WebSocket 連線

- **路徑**：`/ws/gemini_live`
- **協定**：WebSocket
- **音訊格式**：PCM, 24000Hz, 單聲道, 16-bit

### 訊息格式

**發送（客戶端 → 伺服器）**：
- 原始音訊二進制數據（bytes）

**接收（伺服器 → 客戶端）**：
- 音訊數據：二進制格式（bytes）
- 狀態訊息：JSON 格式
  ```json
  {"status": "turn_complete"}
  {"status": "interrupted"}
  ```

## 專案結構

```
Gemini-live-backend/
├── api_server.py        # FastAPI WebSocket 代理伺服器
├── test_client.py       # 測試客戶端腳本
├── utils.py             # 工具函式
├── requirements.txt     # Python 依賴套件
├── .env                 # 環境變數設定（需自行建立）
└── README.md           # 專案說明文件
```

## 技術架構

```
客戶端 (WebSocket A)
    ↕
FastAPI 代理伺服器 (本專案)
    ↕
Google Gemini API (WebSocket B)
```

## 相依套件

- `fastapi` - Web 框架
- `uvicorn[standard]` - ASGI 伺服器
- `websockets` - WebSocket 客戶端
- `python-dotenv` - 環境變數管理
- `google-generativeai` - Google AI SDK
- `numpy` - 數值運算（測試用）
- `soundfile` - 音訊檔案處理（測試用）

## 注意事項

1. **模型版本**：目前使用 `gemini-live-2.5-flash-preview`，此模型將於 2025/12 後停用，屆時需改用 `gemini-2.5-flash-native-audio-preview-09-2025`

2. **付費限制**：Gemini Live Mode API 目前僅供付費帳戶使用

3. **CORS 設定**：生產環境請修改 `allow_origins` 限制允許的來源

4. **安全性**：請勿將 `.env` 檔案提交到版本控制系統

## 故障排除

### 連線失敗

- 檢查 API Key 是否正確
- 確認帳戶是否為付費帳戶
- 檢查網路連線狀態

### 音訊問題

- 確認音訊格式符合規格（24000Hz, 單聲道, PCM_16）
- 檢查音訊檔案路徑是否正確

## 授權條款

MIT License

## 貢獻

歡迎提交 Issue 或 Pull Request！

## 聯絡方式

如有任何問題，歡迎開啟 Issue 討論。