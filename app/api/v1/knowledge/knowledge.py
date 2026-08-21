from fastapi import APIRouter, Body, File, Query, UploadFile
from fastapi.exceptions import HTTPException

from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth, DependSuperUser
from app.models.admin import User
from app.schemas.base import Fail, Success
from app.services import kb_steward, rag_service, rag_store
from app.utils.identity import resolve_biz_role

router = APIRouter()


@router.post("/upload", summary="知识库入库", dependencies=[DependAuth])
async def kb_upload(file: UploadFile = File(...)):
    data = await file.read()
    result = await rag_service.ingest_upload(file.filename or "doc.txt", data)
    return Success(data=result, msg="已入库")


@router.post("/seed-builtin", summary="导入内置操作说明", dependencies=[DependAuth])
async def kb_seed_builtin():
    result = await rag_service.seed_builtin()
    return Success(data=result, msg="已导入内置操作说明")


@router.get("/list", summary="知识库文档列表", dependencies=[DependAuth])
async def kb_list():
    return Success(data={"list": rag_store.list_documents(), "retrieval": rag_service.index_status()})


@router.post("/ask", summary="知识库问答", dependencies=[DependAuth])
async def kb_ask(payload: dict):
    question = str((payload or {}).get("question") or "")
    data = await rag_service.answer(question)
    return Success(data=data)


@router.post("/steward/analyze", summary="知识库框架分析", dependencies=[DependSuperUser])
async def kb_steward_analyze():
    return Success(data=kb_steward.analyze())


@router.post("/steward/draft", summary="知识库缺章草稿", dependencies=[DependSuperUser])
async def kb_steward_draft(payload: dict = Body(default={})):
    topics = None
    if payload.get("topics"):
        topics = [str(item) for item in payload.get("topics") or []]
    data = await kb_steward.draft_missing(topics)
    return Success(data=data)


@router.post("/steward/ingest", summary="确认入库知识库草稿", dependencies=[DependSuperUser])
async def kb_steward_ingest(payload: dict = Body(default={})):
    try:
        data = await kb_steward.ingest_confirmed(str(payload.get("title") or ""), str(payload.get("text") or ""))
    except HTTPException as exc:
        return Fail(code=400, msg=str(exc.detail))
    except Exception:
        return Fail(code=400, msg="入库失败")
    return Success(data=data, msg="已按确认稿入库")


@router.delete("/delete", summary="删除知识库文档", dependencies=[DependAuth])
async def kb_delete(id: int = Query(..., ge=1)):
    user = await User.get(id=CTX_USER_ID.get())
    emp = None
    try:
        from app.models.business import Employee

        emp = await Employee.filter(user_id=user.id).first()
    except Exception:
        emp = None
    role = await resolve_biz_role(user, emp)
    docs = {d["id"]: d for d in rag_store.list_documents()}
    row = docs.get(id)
    if not row:
        return Fail(code=400, msg="文档不存在")
    if role != "admin" and row.get("created_by") != user.id:
        return Fail(code=403, msg="只能删除自己上传的文档")
    rag_store.delete_document(id)
    return Success(msg="已删除")
