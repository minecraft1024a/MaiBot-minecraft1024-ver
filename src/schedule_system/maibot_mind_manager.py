import os
import datetime
import asyncio
import random
from typing import Any, Dict
from src.llm_models.utils_model import LLMRequest
from src.config.config import global_config
from src.common.logger import get_logger
from peewee import Model, CharField, DateTimeField, AutoField
from src.common.database.database import db
from src.manager.mood_manager import mood_manager
from src.schedule_system.schedule_manager import ScheduleManager

logger = get_logger("maibot_mind")

class MaibotMindRecord(Model):
    id = AutoField()
    date_str = CharField()
    content = CharField()

    class Meta:
        database = db
        table_name = 'maibot_mind_records'

# 确保表存在
MaibotMindRecord.create_table(safe=True)

class MaibotMindManager:
    """
    麦麦小脑袋想法管理器：用于生成和存储麦麦当前的想法
    """
    def __init__(self, model_config: Dict[str, Any], mind_file: str = None):
        self.model_config = model_config
        self.llm = LLMRequest(model=model_config)
        self.mind_file = mind_file or os.path.join(os.path.dirname(__file__), "maibot_mind_records.txt")
        # 新增：初始化ScheduleManager用于清洗

    async def generate_and_save_mind(self, extra_message: str = None, chat_observe_info: str = "", current_thinking_info: str = None, mood_info: str = None):
        """
        生成当前麦麦小脑袋的想法，并保存到文件和数据库，生成时参考历史内容和最新消息
        :param extra_message: 可选，最近一次用户消息内容
        :param current_thinking_info: 可选，当前的想法内容
        :param chat_observe_info: 可选，群聊观察到的话题
        :param mood_info: 可选，当前心情
        :param hf_do_next: 可选，下一步动作
        """
        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d %H:%M:%S")
        name = getattr(global_config.identity, 'nickname', '麦麦')
        personality = getattr(global_config.personality, 'personality_core', '')
        behavior = getattr(global_config.personality, 'personality_sides', '')
        # 查询最近5条历史内容
        history = list(MaibotMindRecord.select().order_by(MaibotMindRecord.id.desc()).limit(5))
        if current_thinking_info is None:
            current_thinking_info = history[-1].content if history else ""
        prompt_personality = f"你是{name}，{personality}，{behavior}"
        extra_info = extra_message or ""
        # 自动获取情感
        if mood_info is None:
            mood_info = mood_manager.get_mood_prompt()
        prompt = ""
        prompt += f"{extra_info}\n"
        prompt += f"{prompt_personality}\n"
        prompt += f"刚刚你的想法是：\n我是{name}，我想，{current_thinking_info}\n"
        prompt += "-----------------------------------\n"
        prompt += f"现在是{date_str}，你正在上网，和qq群里的网友们聊天，群里正在聊的话题是：\n{chat_observe_info}\n"
        prompt += f"\n你现在{mood_info}\n"
        prompt += f"现在请你根据刚刚的想法继续思考，思考时可以想想如何对群聊内容进行回复，要不要对群里的话题进行回复，关注新话题，可以适当转换话题，大家正在说的话才是聊天的主题。\n"
        prompt += "回复的要求是：平淡一些，简短一些，说中文，如果你要回复，最好只回复一个人的一个话题\n"
        prompt += "请注意不要输出多余内容(包括前后缀，冒号和引号，括号， 表情，等)，不要带有括号和动作描写,尽量不要说你说过的话。\n"
        prompt += f"现在请你先生成内心想法,文字不要浮夸"
        result = await self.llm.generate_response_async(prompt)
        # 只用日程表的清洗静态方法
        try:
            # 修正：_clean_schedule_text是实例方法
            logger.info(f"[Mind] 生成的麦麦小脑袋想法: {result}")
            result = self.gentle_clean_mind_text(result)
            logger.info(f"[Mind] 清洗后的麦麦小脑袋想法: {result}")
        except Exception as e:
            logger.warning(f"[Mind] 日程清洗小脑袋想法失败: {e}")
        logger.info(f"[Mind] 生成的麦麦小脑袋想法: {result}")
        # 保存到数据库
        try:
            MaibotMindRecord.create(date_str=date_str, content=result)
            logger.info("[Mind] 已保存麦麦小脑袋想法到数据库")
        except Exception as e:
            logger.error(f"[Mind] 想法保存到数据库失败: {e}")

    async def random_mind_loop(self):
        """
        不定时自动生成麦麦小脑袋想法
        """
        logger.info("[Mind] 启动不定时小脑袋想法生成循环...")
        while True:
            wait_minutes = random.randint(3, 6)
            await asyncio.sleep(wait_minutes * 60)
            await self.generate_and_save_mind()
    @staticmethod
    def gentle_clean_mind_text(text: str) -> str:
        """
        单独温和清洗麦麦小脑袋想法文本，仅去除明显无关符号和多余空白，不做深度裁剪
        :param text: 需要清洗的文本
        :return: 温和清洗后的文本
        """
        import re
        if not isinstance(text, str):
            return text
        cleaned = text.strip()
        # 去除前后常见符号
        cleaned = re.sub(r'^[\s\[\]【】\(\)（）"“”‘’\'\:：,，。.!！?？~～、·…—\-]+', '', cleaned)
        cleaned = re.sub(r'[\s\[\]【】\(\)（）"“”‘’\'\:：,，。.!！?？~～、·…—\-]+$', '', cleaned)
        # 去除全是表情或符号的内容
        cleaned = re.sub(r'^[\W_]+$', '', cleaned)
        logger.info(f"[Mind] 温和清洗后的麦麦小脑袋想法: {cleaned}")
        return cleaned

    def clean_mind_text(self, text: str) -> str:
        """
        单独清洗麦麦小脑袋想法文本
        :param text: 需要清洗的文本
        :return: 清洗后的文本
        """
        try:
            cleaned = self.gentle_clean_mind_text(text)
            logger.info(f"[Mind] 单独清洗后的麦麦小脑袋想法: {cleaned}")
            return cleaned
        except Exception as e:
            logger.warning(f"[Mind] 单独清洗小脑袋想法失败: {e}")
            return text

def get_maimai_brain() -> str:
    """
    获取最近一条麦麦小脑袋想法（同步），用于 prompt 构建。
    :return: 格式化后的麦麦小脑袋内容字符串
    """
    try:
        record = MaibotMindRecord.select().order_by(MaibotMindRecord.id.desc()).first()
        if record and record.content:
            cleaned = MaibotMindManager.gentle_clean_mind_text(record.content)
            if cleaned:
                return f"麦麦小脑袋：{cleaned}"
        return ""
    except Exception as e:
        logger.error(f"获取麦麦小脑袋内容失败: {e}")
        return ""
