"""手动刷新 API 表（先初始化 Tortoise 连接）。"""
import asyncio

from tortoise import Tortoise

from app.controllers.api import api_controller
from app.settings.config import settings


async def main():
    await Tortoise.init(config=settings.TORTOISE_ORM)
    await api_controller.refresh_api()
    await Tortoise.close_connections()
    print("API 表刷新完成")


asyncio.run(main())
