# 本地 ↔ 云端 同步检查清单

## 上传前（本机）

- [ ] 业务改动只在本项目源码树内
- [ ] 本地能 `python run.py` 或测试通过
- [ ] 若改了前端：`web` 下已 `npm run build`，`web/dist/index.html` 存在
- [ ] 确认 `db/db.sqlite3`（或空库首次启动）符合预期
- [ ] 打包**排除**：`node_modules`、`venv`、`.git`、`__pycache__`

## 上传内容

- [ ] `app/`
- [ ] `web/dist/`
- [ ] `run.py`、`requirements.txt`
- [ ] `deploy/native/`（nginx/systemd 模板）
- [ ] 按需：`db/`

## 云端启动后

- [ ] `systemctl status asset-system` 为 active
- [ ] `curl -I http://127.0.0.1:9999/` 返回 200
- [ ] 公网浏览器打开登录页
- [ ] 使用**业务** admin 账号登录（不是 SSH）
- [ ] 员工/资产分页与筛选可点

## 回滚

- [ ] 保留上一份 `web/dist` 与 `db` 备份目录
- [ ] 异常时 `systemctl stop asset-system` 停止公网 API
