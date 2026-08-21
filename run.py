import os

import uvicorn
from uvicorn.config import LOGGING_CONFIG

if __name__ == "__main__":
    # 修改默认日志配置
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"][
        "fmt"
    ] = '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    # 修复：生产环境默认关闭 reload。
    # 原 reload=True 在容器内导致：① aerich 生成 migrations 文件触发 WatchFiles 无限重载；
    # ② 重载进程重启时 init_db 重复执行，SQLite WAL 数据未持久化 → 重启后数据库被重建（数据丢失）。
    # 本地开发需要热重载时用环境变量 RELOAD=1 显式开启。
    reload_flag = os.getenv("RELOAD", "0") == "1"

    # 修复：nginx 反代透传真实客户端 IP（review 阻塞项）。
    # 原实现下 request.client.host 恒为 127.0.0.1 → 网关限流/黑名单/登录防爆破全部按共享 IP 计数：
    # 任何匿名用户触发 30 次 404 或 30 个未登录请求，就会把 ip:127.0.0.1 拉黑 → 整个系统 429（全站 DoS）。
    # 配合 deploy/web.conf 的 proxy_set_header X-Forwarded-For，uvicorn 解析出真实客户端 IP。
    proxy_headers_flag = os.getenv("PROXY_HEADERS", "1") == "1"
    forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1")
    # 防御（security_review Low）：拒绝误配 "*"——信任所有来源的 XFF 会让
    # 客户端伪造 IP 绕过限流/黑名单/冒名拉黑
    if forwarded_allow_ips.strip() == "*":
        forwarded_allow_ips = "127.0.0.1"

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=9999,
        reload=reload_flag,
        proxy_headers=proxy_headers_flag,
        forwarded_allow_ips=forwarded_allow_ips,
        log_config=LOGGING_CONFIG,
    )
