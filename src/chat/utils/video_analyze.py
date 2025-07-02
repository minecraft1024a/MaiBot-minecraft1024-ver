import os
import tempfile
import subprocess
import uuid
import base64
from typing import List, Optional
from src.llm_models.utils_model import LLMRequest
from src.common.logger import get_logger
from src.config.config import get_global_config_obj

logger = get_logger("video_analyze")

class BotVideoAnalyzer:
    """Bot主体视频内容分析器（仿照 video_analyzer.py 结构重写）"""
    def __init__(self):
        self.llm_image = LLMRequest(
            model=get_global_config_obj().model.vlm,
            temperature=0.4,
            max_tokens=300,
            request_type="image"
        )
        self.ffmpeg_available = self._check_ffmpeg()
        logger.info(f"视频分析器初始化完成，ffmpeg可用: {self.ffmpeg_available}")

    def _check_ffmpeg(self) -> bool:
        """检查ffmpeg是否可用"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"ffmpeg不可用: {e}")
            return False

    def image_to_base64(self, img_path: str) -> Optional[str]:
        try:
            with open(img_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception as e:
            logger.error(f"图片转base64失败: {e}")
            return None

    async def analyze_image_with_llm(self, img_b64, prompt=None, image_format="jpg"):
        if prompt is None:
            prompt = "请分析这张图片的内容。"
        return await self.llm_image.generate_response_for_image(prompt, img_b64, image_format)

    def extract_keyframes(self, video_path: str, keyframe_dir: str) -> List[str]:
        """使用ffmpeg抽取关键帧，返回图片路径列表"""
        if not self.ffmpeg_available:
            logger.error("ffmpeg不可用，无法提取关键帧")
            return []
        try:
            os.makedirs(keyframe_dir, exist_ok=True)
            ffmpeg_cmd = [
                "ffmpeg", "-i", video_path, "-vf", "select='eq(pict_type,PICT_TYPE_I)'", "-vsync", "vfr",
                os.path.join(keyframe_dir, "keyframe_%03d.jpg")
            ]
            subprocess.run(ffmpeg_cmd, check=True)
            keyframes = sorted([
                os.path.join(keyframe_dir, f)
                for f in os.listdir(keyframe_dir) if f.endswith('.jpg')
            ])
            logger.info(f"提取到{len(keyframes)}个关键帧")
            return keyframes
        except Exception as e:
            logger.error(f"提取关键帧失败: {e}")
            return []

    async def analyze_video_url(self, video_url: str) -> str:
        """
        下载视频，抽取关键帧，送入LLM分析，返回分析结果。
        """
        tmp_dir = tempfile.gettempdir()
        unique_id = uuid.uuid4().hex[:8]
        video_path = os.path.join(tmp_dir, f"maibot_video_{unique_id}.mp4")
        keyframe_dir = os.path.join(tmp_dir, f"maibot_video_keyframes_{unique_id}")
        try:
            # 下载视频
            import requests
            r = requests.get(video_url, stream=True, timeout=10)
            with open(video_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            # 抽取关键帧
            keyframes = self.extract_keyframes(video_path, keyframe_dir)
            if not keyframes:
                return "[视频分析失败] 未能提取关键帧"
            llm_results = []
            for img_path in keyframes:
                img_b64 = self.image_to_base64(img_path)
                if not img_b64:
                    continue
                result = await self.analyze_image_with_llm(img_b64, prompt="请分析这张视频关键帧的内容。", image_format="jpg")
                llm_results.append(result)
            summary = "\n".join([str(r) for r in llm_results])
            summary += "\n\n[提示: 该消息为用户发送的视频消息识别的结果,，可能会有不准确的地方，请根据上下文语境来合理推测可能识别错误的内容并在此基础上做出尽量正确的回应]"
            return f"[视频分析结果] {summary}"
        except Exception as e:
            logger.error(f"视频识别失败: {e}")
            return "[视频分析失败]"
        finally:
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
                if os.path.exists(keyframe_dir):
                    import shutil
                    shutil.rmtree(keyframe_dir)
            except Exception:
                pass

# 全局实例
bot_video_analyzer = BotVideoAnalyzer()

# 兼容原有导出
analyze_video_url = bot_video_analyzer.analyze_video_url
image_to_base64 = bot_video_analyzer.image_to_base64
__all__ = ['analyze_video_url', 'image_to_base64']
