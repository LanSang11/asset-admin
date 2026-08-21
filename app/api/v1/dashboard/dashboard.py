from fastapi import APIRouter

from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.schemas.base import Success
from app.services.dashboard_service import dashboard_stats

router = APIRouter()


@router.get("/stats", summary="看板统计数据", dependencies=[DependAuth])
async def get_dashboard_stats():
    # ISO-B3：按当前登录用户业务角色裁剪看板
    user_id = CTX_USER_ID.get()
    data = await dashboard_stats(user_id=user_id)
    return Success(data=data)
