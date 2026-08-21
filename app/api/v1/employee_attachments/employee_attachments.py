from urllib.parse import quote

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from app.controllers.employee_attachment import employee_attachment_controller
from app.core.dependency import DependAuth
from app.schemas.base import Success

router = APIRouter()


@router.post("/upload", summary="上传员工附件", dependencies=[DependAuth])
async def upload_attachment(
    file: UploadFile = File(...),
    employee_id: int = Form(0),
):
    data = await file.read()
    obj = await employee_attachment_controller.upload(employee_id or None, file.filename or "", data)
    return Success(data=await obj.to_dict(), msg="附件已上传")


@router.get("/list", summary="员工附件列表", dependencies=[DependAuth])
async def list_attachments(employee_id: int = Query(0, ge=0)):
    items = await employee_attachment_controller.list_for(employee_id or None)
    return Success(data={"list": [await i.to_dict() for i in items], "total": len(items)})


@router.get("/download", summary="下载员工附件", dependencies=[DependAuth])
async def download_attachment(id: int = Query(..., ge=1)):
    obj, path = await employee_attachment_controller.get_file(id)
    filename = quote(obj.original_name or obj.stored_name)
    return FileResponse(
        path,
        media_type=obj.mime or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.delete("/delete", summary="删除员工附件", dependencies=[DependAuth])
async def delete_attachment(id: int = Query(..., ge=1)):
    await employee_attachment_controller.delete(id)
    return Success(msg="附件已删除")
