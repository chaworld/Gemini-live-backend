import websockets.client as websockets_client
from websockets.exceptions import ConnectionClosedOK
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware # 考慮前端跨域問題
from starlette.websockets import WebSocketState
import asyncio
import json
import os
from dotenv import load_dotenv
import logging
from datetime import datetime

# 設定 logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 引入核心工具
from utils import AudioConfig, encode_audio_input, encode_audio_stream_end, encode_text_input, decode_audio_output

# --- 設定 ---
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env file or environment variables")

HOST = 'generativelanguage.googleapis.com'

MODEL = 'models/gemini-2.5-flash-native-audio-preview-09-2025' 

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
    client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "Unknown"
    logging.info(f"[CLIENT CONNECT] 接收到來自 {client_info} 的連線請求")
    
    await websocket.accept()
    logging.info(f"[CLIENT ACCEPTED] 成功接受前端 Client 連線 (WebSocket A) - 客戶端: {client_info}")

    try:
        logging.info(f"[GEMINI CONNECTING] 正在連線到 Gemini API...")
        async with websockets_client.connect(GEMINI_WS_URI) as gemini_ws:
            logging.info(f"[GEMINI CONNECTED] 成功連線到 Gemini API (WebSocket B)")
            
            # 1. 先發送 setup 訊息
            # 注意: 原生音訊模型會自動選擇語言,不支援手動設定 languageCode
            setup_message = {
                'setup': {
                    'model': MODEL,
                    'generationConfig': {
                        'responseModalities': ['AUDIO']
                    }
                }
            }
            logging.debug(f"[GEMINI SEND] 發送 setup 訊息: {setup_message}")
            await gemini_ws.send(json.dumps(setup_message))
            
            # 2. 等待 setupComplete 確認
            setup_complete = False
            async for msg in gemini_ws:
                msg_data = json.loads(msg)
                if 'setupComplete' in msg_data:
                    logging.info(f"[GEMINI] 收到 setupComplete 確認")
                    setup_complete = True
                    break
            
            if not setup_complete:
                raise Exception("未收到 setupComplete 確認")
            
            logging.info(f"[GEMINI READY] Setup 完成,開始接收音訊...")
            
            # 測試: 發送一個文字訊息看看 Gemini 是否回應
            test_message = {
                'clientContent': {
                    'turns': [{
                        'role': 'user',
                        'parts': [{'text': '你好,請用音訊回應我'}]
                    }],
                    'turnComplete': True
                }
            }
            logging.info(f"[TEST] 發送測試文字訊息")
            await gemini_ws.send(json.dumps(test_message))

            async def forward_to_gemini():
                # 處理所有音訊區塊,並偵測暫停
                chunk_count = 0
                last_audio_time = None
                
                while True:
                    try:
                        # 等待音訊資料,但有 1 秒的超時
                        data = await asyncio.wait_for(websocket.receive_bytes(), timeout=1.0)
                        chunk_count += 1
                        last_audio_time = asyncio.get_event_loop().time()
                        
                        logging.debug(f"[CLIENT→GEMINI] 收到音訊 chunk #{chunk_count}, 大小: {len(data)} bytes")
                        gemini_message = encode_audio_input(data, audio_config)
                        await gemini_ws.send(json.dumps(gemini_message))
                        logging.debug(f"[CLIENT→GEMINI] 已轉發音訊 chunk #{chunk_count} 到 Gemini API")
                        
                    except asyncio.TimeoutError:
                        # 超過 1 秒沒收到音訊,發送 audio_stream_end
                        if last_audio_time is not None:
                            logging.info(f"[CLIENT→GEMINI] 偵測到音訊暫停,發送 audio_stream_end")
                            stream_end_msg = encode_audio_stream_end()
                            await gemini_ws.send(json.dumps(stream_end_msg))
                            last_audio_time = None  # 重置,避免重複發送

            async def forward_to_client():
                response_count = 0
                async for msg in gemini_ws:
                    # 完整記錄所有 Gemini 回應以便除錯
                    logging.info(f"[GEMINI→CLIENT] 收到 Gemini 回應: {msg}")
                    msg = json.loads(msg)
                    
                    # 檢查各種訊息類型
                    server_content = msg.get('serverContent', {})
                    
                    # 檢查是否有音訊輸出
                    if to_play := decode_audio_output(msg):
                        response_count += 1
                        logging.info(f"[GEMINI→CLIENT] 發送音訊回應 #{response_count}, 大小: {len(to_play)} bytes")
                        await websocket.send_bytes(to_play)
                    
                    # 檢查 turnComplete
                    if server_content.get('turnComplete'):
                        logging.info(f"[GEMINI→CLIENT] 發送 turn_complete 訊號")
                        await websocket.send_json({"status": "turn_complete"})
                    
                    # 檢查 interrupted
                    if server_content.get('interrupted'):
                        logging.info(f"[GEMINI→CLIENT] 發送 interrupted 訊號")
                        await websocket.send_json({"status": "interrupted"})
                    
                    # 記錄使用統計
                    if 'usageMetadata' in msg:
                        logging.info(f"[GEMINI] 使用統計: {msg['usageMetadata']}")

            await asyncio.gather(forward_to_gemini(), forward_to_client())

    # --- 例外處理 ---
    except ConnectionClosedOK:
        logging.info(f"[GEMINI CLOSED] Gemini API 連線正常關閉")
    except WebSocketDisconnect as e:
        logging.warning(f"[CLIENT DISCONNECT] 前端 Client 連線中斷 - 原因: {e}")
    except Exception as e:
        logging.error(f"[ERROR] 發生錯誤: {type(e).__name__} - {e}", exc_info=True)
    finally:
        # --- 修改 3: 使用正確的狀態檢查 ---
        if websocket.client_state != WebSocketState.DISCONNECTED:
             logging.info(f"[CLIENT CLOSING] 正在關閉與客戶端 {client_info} 的連線")
             await websocket.close()
             logging.info(f"[CLIENT CLOSED] 已關閉 FastAPI WebSocket")

# --- 運行指令 ---
# uvicorn api_server:app --host 0.0.0.0 --port 8080