import asyncio
import hashlib
from pathlib import Path
from src.common.logger import get_logger
from .config import reload_config,get_config_dir

logger = get_logger("hot_update")

def calc_file_hash(file_path: Path) -> str:
    """
    计算文件内容的SHA256哈希值
    """
    if not file_path.exists():
        return ""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

async def hot_update_config_task(interval: int = 10):
    """
    async定时检测配置文件内容哈希值变动并自动热更新。
    :param interval: 检查间隔秒数，默认10秒
    """
    config_dir = Path(get_config_dir())
    config_path = config_dir / "bot_config.toml"
    logger.info(f"[热更新] 配置文件路径: {config_path}")
    last_hash = None
    logger.info(f"[热更新] 启动配置文件热更新监控（哈希），间隔{interval}秒...")
    while True:
        try:
            if config_path.exists():
                file_hash = calc_file_hash(config_path)
                if last_hash is None:
                    last_hash = file_hash
                elif file_hash != last_hash:
                    logger.info(f"[热更新] 检测到配置文件内容变动（哈希），自动更新...")
                    reload_config()
                    last_hash = calc_file_hash(config_path)
        except Exception as e:
            logger.error(f"[热更新] 检查或更新配置文件时出错: {e}")
        await asyncio.sleep(interval)
