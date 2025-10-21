import websockets.client as websockets_client
from websockets.exceptions import ConnectionClosedOK
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware # 考慮前端跨域問題
from starlette.websockets import WebSocketState
import asyncio
import json
import os
from dotenv import load_dotenv

# 引入核心工具
from utils import AudioConfig, encode_audio_input, encode_text_input, decode_audio_output

# --- 設定 ---
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env file or environment variables")

HOST = 'generativelanguage.googleapis.com'

MODEL = 'models/gemini-live-2.5-flash-preview' # 此模型 2025/12 以後停用，要改成 gemini-2.5-flash-native-audio-preview-09-2025

# FastAPI 伺服器連線的 URL
GEMINI_WS_URI = f'wss://{HOST}/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={GOOGLE_API_KEY}'

app = FastAPI(title="Gemini Live WebSocket Proxy")
audio_config = AudioConfig()

# 啟用 CORS 供前端開發測試使用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源 (開發階段，生產環境請限制)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/gemini_live")
async def websocket_proxy_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(">>> 成功接收前端 Client 連線 (WebSocket A) <<<")

    try:
        async with websockets_client.connect(GEMINI_WS_URI) as gemini_ws:
            print(">>> 成功連線到 Gemini API (WebSocket B) <<<")

            initial_request = {'setup': {'model': MODEL}}
            await gemini_ws.send(json.dumps(initial_request))
            await gemini_ws.send(json.dumps(encode_text_input("HI")))

            async def forward_to_gemini():
                while True:
                    data = await websocket.receive_bytes()
                    gemini_message = encode_audio_input(data, audio_config)
                    await gemini_ws.send(json.dumps(gemini_message))

            async def forward_to_client():
                async for msg in gemini_ws:
                    msg = json.loads(msg)
                    if to_play := decode_audio_output(msg):
                        await websocket.send_bytes(to_play)
                    elif 'turnComplete' in msg.get('serverContent', {}):
                        await websocket.send_json({"status": "turn_complete"})
                    elif 'interrupted' in msg.get('serverContent', {}):
                        await websocket.send_json({"status": "interrupted"})

            await asyncio.gather(forward_to_gemini(), forward_to_client())

    # --- 例外處理 ---
    except ConnectionClosedOK:
        print("--- Gemini API 連線正常關閉 ---")
    except WebSocketDisconnect:
        print("--- 前端 Client 連線中斷 (WebSocketDisconnect) ---")
    except Exception as e:
        print(f"--- 發生錯誤: {type(e).__name__} - {e} ---")
    finally:
        # --- 修改 3: 使用正確的狀態檢查 ---
        if websocket.client_state != WebSocketState.DISCONNECTED:
             await websocket.close()
             print("--- 確保 FastAPI WebSocket 已關閉 ---")

# --- 運行指令 ---
# uvicorn api_server:app --host 0.0.0.0 --port 8080