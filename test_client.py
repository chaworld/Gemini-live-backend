import asyncio
import websockets.client as websockets_client
import soundfile as sf
import numpy as np
import time
from pathlib import Path
import json

# 引入核心工具
from utils import AudioConfig

# --- 配置 ---
# 連接到本地運行的 FastAPI 代理服務
LOCAL_SERVER_URI = "ws://localhost:8080/ws/gemini_live"
TEST_AUDIO_FILE = "test_input.wav" # 你的測試音訊檔案
OUTPUT_FILE = f"tts_output_{int(time.time())}.wav"
audio_config = AudioConfig()

# 模擬一個簡單的音訊產生器 (從檔案讀取)
def audio_chunk_generator(file_path: str, block_size: int):
    """從音訊檔案中以指定的 block_size 產生二進制數據塊。"""
    print(f"Loading test audio file: {file_path}")
    try:
        # 使用 soundfile 讀取音訊檔案
        with sf.SoundFile(file_path, 'r') as f:
            # 檢查音訊格式是否匹配
            if f.samplerate != audio_config.sample_rate:
                raise ValueError(f"Sample rate mismatch: expected {audio_config.sample_rate} Hz, got {f.samplerate} Hz.")
            if f.channels != audio_config.channels:
                raise ValueError(f"Channels mismatch: expected {audio_config.channels} channel, got {f.channels} channels.")
            
            print(f"Audio properties: {f.samplerate}Hz, {f.channels}ch, {f.format}")
            
            # 逐塊讀取數據
            for block in f.blocks(blocksize=block_size, dtype=audio_config.dtype):
                yield block.tobytes()

    except Exception as e:
        print(f"Error reading audio file: {e}")
        return


async def run_test_client():
    """主非同步函式，執行客戶端連線、發送和接收。"""
    
    # 儲存接收到的 TTS 音訊
    received_audio_data = []

    try:
        # 連接到你的 FastAPI 代理服務
        async with websockets_client.connect(LOCAL_SERVER_URI) as websocket:
            print(f"Successfully connected to FastAPI Proxy: {LOCAL_SERVER_URI}")
            
            # --- 雙向任務 ---

            # 任務 A: 音訊發送
            async def send_audio():
                for chunk_bytes in audio_chunk_generator(TEST_AUDIO_FILE, audio_config.block_size):
                    # 直接將二進制數據發送給 FastAPI 代理
                    await websocket.send(chunk_bytes)
                    # 模擬實時串流，等待一段時間
                    await asyncio.sleep(audio_config.block_size / audio_config.sample_rate)
                print("--- 音訊發送完成 ---")


            # 任務 B: 訊息接收
            async def receive_response():
                async for message in websocket:
                    if isinstance(message, bytes):
                        # 收到二進制音訊數據 (TTS)
                        received_audio_data.append(message)
                        # 實時印出進度
                        print(f"Received TTS chunk, total size: {len(received_audio_data[-1])} bytes", end='\r')
                    elif isinstance(message, str):
                        # 收到 JSON 狀態訊息 (如 turn_complete)
                        msg_json = json.loads(message)
                        if msg_json.get("status") == "turn_complete":
                            print("\n--- 接收到 Round Complete 訊號 ---")
                            break # 結束接收迴圈
                        else:
                            print(f"\nReceived JSON: {msg_json}")

            # 同時運行發送和接收任務
            await asyncio.gather(
                asyncio.create_task(send_audio()),
                asyncio.create_task(receive_response())
            )

    except websockets_client.ConnectionClosed as e:
        print(f"\nConnection closed unexpectedly: {e}")
    except FileNotFoundError:
        print(f"\nERROR: Test audio file '{TEST_AUDIO_FILE}' not found. Please create it first.")
    except Exception as e:
        print(f"\nAn error occurred: {type(e).__name__} - {e}")

    finally:
        if received_audio_data:
            # 將所有接收到的音訊數據合併並儲存為 WAV 檔案
            final_audio_bytes = b''.join(received_audio_data)
            print(f"\nSaving final TTS audio data ({len(final_audio_bytes)} bytes) to {OUTPUT_FILE}")
            
            # 使用 soundfile 寫入 WAV 檔案
            sf.write(
                OUTPUT_FILE,
                np.frombuffer(final_audio_bytes, dtype=np.int16),
                audio_config.sample_rate,
                subtype='PCM_16'
            )
        print("Client stopped.")


if __name__ == "__main__":
    asyncio.run(run_test_client())