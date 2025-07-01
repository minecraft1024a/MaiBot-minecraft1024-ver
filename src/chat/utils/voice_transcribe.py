import aiohttp
import base64
import os
from src.common.logger import get_logger
from src.config.config import global_config
# 从配置文件中获取API相关信息
logger = get_logger("voice_transcribe")

SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
SILICONFLOW_MODEL = "FunAudioLLM/SenseVoiceSmall"
try:
    SILICONFLOW_TOKEN = (global_config.model.siliconflow_token)  # 建议通过config注入token
except AttributeError:
    logger.warning("未配置SILICONFLOW_TOKEN，无法进行语音转写！请在配置文件中设置model.siliconflow_token")
    SILICONFLOW_TOKEN = None

async def voice_base64_to_text(audio_base64: str) -> str:
    """
    将语音base64转为文字，调用siliconflow API
    :param audio_base64: base64编码的音频数据（wav/mp3等）
    :return: 识别到的文字
    """
    if not SILICONFLOW_TOKEN:
        logger.error("未设置SILICONFLOW_TOKEN环境变量，无法进行语音转写！")
        return "[语音转写失败: 未配置API Token]"
    try:
        # 解码base64为二进制
        audio_bytes = base64.b64decode(audio_base64)
        # aiohttp上传文件需要BytesIO
        import io
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"  # API要求有文件名
        data = aiohttp.FormData()
        data.add_field('model', SILICONFLOW_MODEL)
        data.add_field('file', audio_file, filename="audio.wav", content_type="audio/wav")
        headers = {
            "Authorization": f"Bearer {SILICONFLOW_TOKEN}",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(SILICONFLOW_API_URL, headers=headers, data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    result = result.get("text", "[语音转写无结果]")
                    result += "\n\n[提示: 该消息为用户发送的语音消息识别的结果，可能会有不准确的地方，请根据上下文语境来合理推测可能识别错误的内容（通常是同音字一类的识别错误）并在此基础上做出尽量正确的回应"
                    return result
                else:
                    logger.error(f"语音转写API请求失败: {resp.status}, {await resp.text()}")
                    return f"[语音转写失败: {resp.status} {await resp.text()}]"
    except Exception as e:
        logger.error(f"语音转写异常: {e}")
        return f"[语音转写异常: {e}]"
