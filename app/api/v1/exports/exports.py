from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth, DependPermission, require_operation, require_step_up
from app.models.admin import User
from app.schemas.base import Success
from app.services.export_service import export_asset_uses, export_assets, export_employees
from app.services.import_service import import_assets

router = APIRouter()


async def _require_admin():
    """导出属于高敏感操作：仅超管可执行（权限表之外的双保险，即时生效）。"""
    user = await User.filter(id=CTX_USER_ID.get()).first()
    if not user or not user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可导出数据")


@router.get("/employees", summary="导出员工数据 CSV", dependencies=[DependPermission])
async def export_employees_csv(
    keyword: str = Query("", description="搜索关键词"),
    current_user: User = require_operation("export_employees"),
):
    await _require_admin()
    return await export_employees(keyword)


@router.get("/assets", summary="导出资产数据 CSV", dependencies=[DependPermission])
async def export_assets_csv(
    keyword: str = Query("", description="搜索关键词"),
    category: str = Query("", description="分类"),
    status: int = Query(0, description="状态"),
    current_user: User = require_operation("export_assets"),
):
    await _require_admin()
    return await export_assets(keyword, category, status)


@router.get("/asset-uses", summary="导出领用记录 CSV", dependencies=[DependPermission])
async def export_asset_uses_csv(
    status: int = Query(0, description="状态"),
    use_type: int = Query(0, description="类型"),
    current_user: User = require_operation("export_asset_uses"),
):
    await _require_admin()
    return await export_asset_uses(status, use_type)


@router.post("/import-assets", summary="导入资产 CSV（默认预检）", dependencies=[DependPermission])
async def import_assets_csv(
    request: Request,
    file: UploadFile = File(...),
    commit: int = Query(0, description="0=预检不写库 1=写入"),
    current_user: User = DependAuth,
):
    await _require_admin()
    if commit:
        await require_step_up("asset_import_commit", request, current_user)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大（上限 2MB）")
    try:
        data = await import_assets(raw, commit=bool(commit))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    msg = "已写入" if commit else "预检完成（未写库）"
    return Success(data=data, msg=msg)
