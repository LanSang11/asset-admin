from fastapi.exceptions import HTTPException
from tortoise.expressions import Q
from tortoise.transactions import atomic

from app.core.crud import CRUDBase
from app.models.admin import Dept, DeptClosure
from app.schemas.depts import DeptCreate, DeptUpdate


class DeptController(CRUDBase[Dept, DeptCreate, DeptUpdate]):
    def __init__(self):
        super().__init__(model=Dept)

    async def get_dept_tree(self, name):
        q = Q()
        # 获取所有未被软删除的部门
        q &= Q(is_deleted=False)
        if name:
            q &= Q(name__contains=name)
        all_depts = await self.model.filter(q).order_by("order")

        # 辅助函数，用于递归构建部门树
        def build_tree(parent_id):
            return [
                {
                    "id": dept.id,
                    "name": dept.name,
                    "desc": dept.desc,
                    "order": dept.order,
                    "parent_id": dept.parent_id,
                    "children": build_tree(dept.id),  # 递归构建子部门
                }
                for dept in all_depts
                if dept.parent_id == parent_id
            ]

        # 从顶级部门（parent_id=0）开始构建部门树
        dept_tree = build_tree(0)
        return dept_tree

    async def get_dept_info(self):
        pass

    async def update_dept_closure(self, obj: Dept):
        parent_depts = await DeptClosure.filter(descendant=obj.parent_id)
        dept_closure_objs: list[DeptClosure] = []
        # 插入父级关系（修复：移除残留的 print 调试输出）
        for item in parent_depts:
            dept_closure_objs.append(DeptClosure(ancestor=item.ancestor, descendant=obj.id, level=item.level + 1))
        # 插入自身
        dept_closure_objs.append(DeptClosure(ancestor=obj.id, descendant=obj.id, level=0))
        # 创建关系
        await DeptClosure.bulk_create(dept_closure_objs)

    @atomic()
    async def create_dept(self, obj_in: DeptCreate):
        # 创建
        if obj_in.parent_id != 0:
            parent = await Dept.filter(id=obj_in.parent_id, is_deleted=False).first()
            if not parent:
                raise HTTPException(status_code=400, detail="父部门不存在或已删除")
        new_obj = await self.create(obj_in=obj_in)
        await self.update_dept_closure(new_obj)

    @atomic()
    async def update_dept(self, obj_in: DeptUpdate):
        dept_obj = await self.get(id=obj_in.id)
        data = obj_in.model_dump(exclude_unset=True)
        new_parent_id = data.get("parent_id", dept_obj.parent_id)

        # 防环 + 父部门有效性校验
        if new_parent_id != 0:
            if new_parent_id == dept_obj.id:
                raise HTTPException(status_code=400, detail="父部门不能是自己")
            descendants = await DeptClosure.filter(ancestor=dept_obj.id).values_list("descendant", flat=True)
            if new_parent_id in descendants:
                raise HTTPException(status_code=400, detail="父部门不能是自己的子部门")
            if not await Dept.filter(id=new_parent_id, is_deleted=False).exists():
                raise HTTPException(status_code=400, detail="父部门不存在或已删除")

        moved = dept_obj.parent_id != new_parent_id
        # 先更新 parent_id，再重建闭包（修复：原实现闭包按旧 parent_id 重建，层级永久错乱）
        dept_obj.update_from_dict({k: v for k, v in data.items() if k != "parent_id"})
        dept_obj.parent_id = new_parent_id
        await dept_obj.save()
        if moved:
            await DeptClosure.filter(ancestor=dept_obj.id).delete()
            await DeptClosure.filter(descendant=dept_obj.id).delete()
            await self.update_dept_closure(dept_obj)
        return dept_obj

    @atomic()
    async def delete_dept(self, dept_id: int):
        obj = await self.get(id=dept_id)
        # 修复：删除前校验子部门与员工（原实现产生悬空引用：子部门挂在已删节点、员工 dept_id 指向已删部门）
        if await Dept.filter(parent_id=dept_id, is_deleted=False).exists():
            raise HTTPException(status_code=400, detail="该部门存在子部门，请先调整")
        from app.models.business import Employee
        if await Employee.filter(dept_id=dept_id).exists():
            raise HTTPException(status_code=400, detail="该部门下仍有员工，请先调整员工部门")
        obj.is_deleted = True
        await obj.save()
        # 删除关系（ancestor 残留行一并清理，防止软删后仍出现在祖先链）
        await DeptClosure.filter(descendant=dept_id).delete()
        await DeptClosure.filter(ancestor=dept_id).delete()


dept_controller = DeptController()
