from dataclasses import dataclass
import base64
import json
import numpy as np

@dataclass
class AudioConfig:
    """音訊串流的配置，與 Gemini Live API 規範一致。"""
    sample_rate: int = 24000
    block_size: int = 2400 # 2400 samples * 2 bytes/sample = 4800 bytes per chunk
    channels: int = 1
    dtype: str = 'int16'

def encode_audio_input(data: bytes, config: AudioConfig) -> dict:
    """將用戶音訊位元組編碼為 Gemini API 要求的 JSPB JSON 格式。"""
    return {
        'realtimeInput': {
            'mediaChunks': [{
                'mimeType': f'audio/pcm;rate={config.sample_rate}',
                'data': base64.b64encode(data).decode('UTF-8'),
            }],
        },
    }

def encode_text_input(text: str) -> dict:
    """將文字輸入編碼為 Gemini API 要求的 JSPB JSON 格式。"""
    return {
        'clientContent': {
            'turns': [{
                'role': 'USER',
                'parts': [{'text': text}],
            }],
            'turnComplete': True,
        },
    }

def decode_audio_output(input: dict) -> bytes:
    """解碼 Gemini API 回傳的音訊位元組。"""
    result = []
    content_input = input.get('serverContent', {})
    content = content_input.get('modelTurn', {})
    for part in content.get('parts', []):
        data = part.get('inlineData', {}).get('data', '')
        if data:
            result.append(base64.b64decode(data))
    return b''.join(result)