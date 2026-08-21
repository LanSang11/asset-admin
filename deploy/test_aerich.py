"""验证 aerich 无历史时 init_db 的行为（在容器内跑）。"""
import asyncio
import shutil

from aerich import Command
from app.settings.config import settings


async def main():
    command = Command(tortoise_config=settings.TORTOISE_ORM)
    try:
        await command.init_db(safe=True)
        print("init_db(safe=True) OK")
    except FileExistsError:
        print("init_db: FileExistsError (正常,表已存在)")
    await command.init()
    try:
        await command.migrate()
        print("migrate() OK")
    except AttributeError as e:
        print(f"migrate AttributeError: {e}")
    try:
        await command.upgrade(run_in_transaction=True)
        print("upgrade OK")
    except Exception as e:
        print(f"upgrade 异常: {type(e).__name__}: {e}")


asyncio.run(main())
