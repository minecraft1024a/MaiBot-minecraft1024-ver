import os
import datetime
import asyncio
import random
from typing import List, Dict, Any
from src.llm_models.utils_model import LLMRequest
from src.config.config import global_config
from src.common.logger import get_logger
from src.common.database.database import db
from peewee import Model, CharField, DateField, DateTimeField, TextField

logger = get_logger("schedule")

class ScheduleRecord(Model):
    date = DateField(index=True)
    schedule_text = TextField()  # 一天的完整日程文本

    class Meta:
        database = db
        table_name = "schedule_records"

class CurrentActivityRecord(Model):
    timestamp = DateTimeField(index=True)
    activity_text = TextField()  # 当前正在做的事

    class Meta:
        database = db
        table_name = "current_activity_records"

# 确保表结构已创建
db.create_tables([ScheduleRecord, CurrentActivityRecord], safe=True)

class ScheduleManager:
    def __init__(self, config: Dict[str, Any], model_config: Dict[str, Any]):
        """
        日程管理器初始化
        :param config: 日程表系统配置（global_config.schedule.__dict__）
        :param model_config: 日程表专用模型配置（global_config.model.schedule）
        
        注意：这个人设是一个19岁女孩，喜欢迫害管理和群主，24小时水群，
        喜欢甜食和珍珠奶茶，常用表情包和颜文字(≧▽≦)，性格活泼幽默。
        日程生成时会结合这些特点。
        """
        self.config = config
        self.model_config = model_config
        self.schedules = []  # type: List[Dict[str, Any]]
        self.llm = LLMRequest(model=model_config)
        self.today = datetime.date.today().isoformat()
        # 启动时优先从数据库获取今日完整日程


    async def refresh(self):
        """使用 LLM 自动刷新日程表"""
        logger.info("[Schedule] 正在刷新日程表...")
        # 兼容 config 可能为对象或 dict
        refresh_prompt = None
        if hasattr(global_config.schedule, 'refresh_prompt'):
            refresh_prompt = getattr(global_config.schedule, 'refresh_prompt')
        elif isinstance(global_config.schedule, dict):
            refresh_prompt = global_config.schedule.get('refresh_prompt')
        if not refresh_prompt:
            refresh_prompt = '请生成今天的日程安排，格式为文本，示例：\n8:00:做xxx\n9:00:做xxx'
        # 构造更智能的prompt，结合个性、行为、昨日安排等
        date_str = datetime.date.today().strftime("%Y-%m-%d")
        weekday = datetime.date.today().strftime("%A")
        # 获取个性、行为、昨日安排（如有）
        name = getattr(global_config.identity, 'nickname', '机器人')
        personality = getattr(global_config.personality, 'personality_core', '')
        behavior = getattr(global_config.personality, 'personality_sides', '')
        # 查询昨日日程
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        yesterday_record = ScheduleRecord.select().where(ScheduleRecord.date == yesterday).first()
        yesterday_schedule_text = yesterday_record.schedule_text if yesterday_record else "无"
        # 构造提示词
        prompt = f"你是{name}，{personality}，{behavior}\n"
        prompt += f"你昨天的日程是：{yesterday_schedule_text}\n"
        prompt += f"请为你生成{date_str}（{weekday}），也就是今天的日程安排，结合你的个人特点和行为习惯以及昨天的安排\n"
        prompt += "推测你的日程安排，包括你一天都在做什么，从起床到睡眠，有什么发现和思考，具体一些，详细一些，确到每半个小时，记得写明时间\n"
        prompt += "直接返回你的日程，现实一点，不要浮夸，从起床到睡觉，不要输出其他内容："
        prompt += f"这里是一些关于日程表生成的提示:{refresh_prompt}"
        prompt += f"\n请生成一个完整的日程表，不使用markdown和json\n"
        result = await self.llm.generate_response_async(prompt)
        result = await self.clean_schedule_text_async(result)
        try:
            self.today = datetime.date.today().isoformat()
            # 不再删除旧日程，若已存在则更新，否则插入
            record, created = ScheduleRecord.get_or_create(date=self.today, defaults={"schedule_text": result})
            if not created:
                record.schedule_text = result
                record.save()
            logger.info(f"[Schedule] 已保存今日完整日程到数据库 (date={self.today})")
            record = ScheduleRecord.select().where(ScheduleRecord.date == self.today).first()
            today_schedule = record.schedule_text if record else ""
            logger.info(f"[Schedule] 启动时今日全部日程: {today_schedule}")
        except Exception as e:
            logger.error(f"[Schedule] 日程表刷新失败: {e}")

    async def auto_refresh(self):
        """每天12点自动刷新日程表"""
        while True:
            now = datetime.datetime.now()
            next_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
            if now >= next_noon:
                next_noon += datetime.timedelta(days=1)
            wait_seconds = (next_noon - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            await self.refresh()

    async def random_activity_loop(self):
        """不定时生成现在做的事并输出和保存"""
        self.generate_and_save_current_activity
        logger.info("[Schedule] 启动不定时活动生成循环...")
        while True:
            # 随机等待 30~40 分钟
            wait_minutes = random.randint(30, 40)
            await asyncio.sleep(wait_minutes * 60)
            await self.generate_and_save_current_activity()

    async def generate_and_save_current_activity(self):
        """生成现在做的事，输出并保存到数据库"""
        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d %H:%M:%S")
        # 构造 prompt，结合个性、行为、今日日程等
        name = getattr(global_config.identity, 'nickname', '机器人')
        personality = getattr(global_config.personality, 'personality_core', '')
        behavior = getattr(global_config.personality, 'personality_sides', '')
        today_schedule = self.get_today_schedule()
        prompt = f"你是{name}，{personality}，{behavior}\n"
        prompt += f"今天的日程安排：{today_schedule}\n"
        prompt += f"现在是{date_str}，请用一句话描述你此刻正在做什么，结合你的性格和行为习惯，真实、具体、有趣一点，不要输出多余内容："
        result = await self.llm.generate_response_async(prompt)
        logger.info(f"[Schedule] 生成的当前活动文本: {result}")
        # 清洗文本
        activity_text = await self.clean_schedule_text_async(result)
        # 输出到日志
        logger.info(f"[Schedule] 现在做的事：{activity_text}")
        # 保存到数据库
        try:
            CurrentActivityRecord.create(timestamp=now.date(), activity_text=activity_text)
            logger.info(f"[Schedule] 已保存当前活动到数据库 (date={now.date()})")
        except Exception as e:
            logger.error(f"[Schedule] 当前活动保存失败: {e}")

    async def ensure_today_schedule(self):
        """启动时自动检查数据库中是否有今日日程，没有则刷新"""
        today = datetime.date.today().isoformat()
        record = ScheduleRecord.select().where(ScheduleRecord.date == today).first()
        if record:
            logger.info("[Schedule] 数据库中已存在今日日程，跳过刷新")
        else:
            logger.info("[Schedule] 数据库中无今日日程，正在刷新...")
            await self.refresh()
        # 启动时自动调用auto_refresh，保证任务被调度
        asyncio.create_task(self.auto_refresh())
        # 启动时自动调用不定时活动生成循环
        asyncio.create_task(self.random_activity_loop())

    def get_today_schedule(self) -> str:
        today = datetime.date.today().isoformat()
        record = ScheduleRecord.select().where(ScheduleRecord.date == today).first()
        return record.schedule_text if record else ""

    async def clean_schedule_text_async(self, schedule_text) -> str:
        """
        只做文本清洗，不做任何JSON解析。支持tuple/list输入，返回第一个非空文本的清洗结果。
        """
        # 支持传入tuple或list，循环尝试每个元素
        if isinstance(schedule_text, (tuple, list)):
            for item in schedule_text:
                if not item or not isinstance(item, str) or not item.strip():
                    continue
                s = item.strip()
                logger.info(f"[Schedule] 清洗前的日程文本: {s}")
                # 深度清洗日程文本
                cleaned = self._clean_schedule_text(s)
                if cleaned:
                    logger.info(f"[Schedule] 清洗后的日程文本: {cleaned}")
                    return cleaned
            return ""
        # 单字符串情况
        if not schedule_text or not isinstance(schedule_text, str) or not schedule_text.strip():
            return ""
        s = schedule_text.strip()
        cleaned = self._clean_schedule_text(s)
        return cleaned

    def _clean_schedule_text(self, text: str) -> str:
        """
        深度清洗日程文本：
        - 去除所有中英文括号及其内容（包括颜文字、表情包等）
        - 去除常见表情包/颜文字/特殊符号
        - 去除.jpg/.gif等图片后缀
        - 去除多余空白、换行
        - 保留时间点和主要事件描述
        """
        import re
        if not text or not isinstance(text, str):
            return ""
        # 去除所有中英文括号及其内容
        text = re.sub(r'\（.*?\）', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\{.*?\}', '', text)
        # 去除颜文字、特殊符号（如“(°∀°)ﾉ”“╯‵□′)╯”等）
        text = re.sub(r'[\u3000-\u303F\uFF00-\uFFEF\u2600-\u26FF\u2700-\u27BF]+', '', text)  # 全角符号、特殊符号
        # 去除.jpg/.gif/.png等图片后缀
        text = re.sub(r'\S+\.(jpg|gif|png|jpeg|webp)', '', text, flags=re.IGNORECASE)
        # 去除awsl、aswl等网络流行语（可选）
        # 去除多余空格
        text = re.sub(r' +', ' ', text)
        # 将\n字符串和多余空白行替换为换行符
        text = text.replace('\\n', '\n')
        text = re.sub(r'\n{2,}', '\n', text)
        # 去除每行首尾空格
        text = '\n'.join([line.strip() for line in text.splitlines() if line.strip()])
        return text.strip()
