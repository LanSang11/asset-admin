import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise import Tortoise

from app.core.exceptions import SettingNotFound
from app.core.init_app import (
    init_data,
    make_middlewares,
    register_exceptions,
    register_routers,
)
from app.log import logger

try:
    from app.settings.config import settings
except ImportError:
    raise SettingNotFound("Can not import settings")


async def _log_cleanup_loop():
    """定时清理审计/安全日志，防止堆积打满磁盘。"""
    from app.services.security_event_service import cleanup_logs

    interval = max(60, int(getattr(settings, "LOG_CLEANUP_INTERVAL_SECONDS", 3600) or 3600))
    while True:
        try:
            result = await cleanup_logs()
            if any(result.values()):
                logger.info(f"日志清理完成: {result}")
        except Exception as e:
            logger.warning(f"定时日志清理失败: {e}")
        await asyncio.sleep(interval)


async def _agg_flush_loop():
    from app.services.security_agg import flush_attack_buckets

    while True:
        try:
            flushed = await flush_attack_buckets()
            if flushed:
                logger.info(f"攻击聚合落库: buckets={flushed}")
        except Exception as e:
            logger.warning(f"攻击聚合刷新失败: {e}")
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_data()
    # 启动即清理一次
    try:
        from app.services.security_event_service import cleanup_logs

        result = await cleanup_logs()
        if any(result.values()):
            logger.info(f"启动日志清理: {result}")
    except Exception as e:
        logger.warning(f"审计日志清理失败（不影响启动）: {e}")

    cleanup_task = asyncio.create_task(_log_cleanup_loop())
    flush_task = asyncio.create_task(_agg_flush_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        flush_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        try:
            await flush_task
        except asyncio.CancelledError:
            pass
        try:
            from app.services.security_agg import flush_attack_buckets

            await flush_attack_buckets()
        except Exception as e:
            logger.warning(f"关闭前攻击聚合刷新失败: {e}")
        await Tortoise.close_connections()


def create_app() -> FastAPI:
    # 生产环境默认关闭 /docs、/openapi.json（settings.SHOW_DOCS=True 或环境变量 SHOW_DOCS=1 可开启）
    show_docs = settings.SHOW_DOCS
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.VERSION,
        docs_url="/docs" if show_docs else None,
        redoc_url="/redoc" if show_docs else None,
        openapi_url="/openapi.json" if show_docs else None,
        middleware=make_middlewares(),
        lifespan=lifespan,
    )
    register_exceptions(app)
    register_routers(app, prefix="/api")
    return app


app = create_app()
