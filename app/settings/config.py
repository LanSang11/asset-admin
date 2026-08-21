import os
import secrets
import typing

from pydantic_settings import BaseSettings


def _load_or_create_secret(base_dir: str) -> str:
    """SECRET_KEY 来源（安全：无硬编码默认值）：
    1. 环境变量 SECRET_KEY（生产推荐）
    2. 本地 .secret_key 文件（首次运行时用 secrets.token_hex(32) 生成并持久化，
       保证容器重启后 AES 加密的 API Key 仍可解密，且随项目目录可移植）
    """
    env_key = os.getenv("SECRET_KEY")
    if env_key:
        return env_key.strip()
    key_file = os.path.join(base_dir, ".secret_key")
    if os.path.exists(key_file):
        with open(key_file, "r", encoding="utf-8") as f:
            saved = f.read().strip()
        if saved:
            return saved
    new_key = secrets.token_hex(32)
    # 原子创建（O_CREAT|O_EXCL）：防多 worker 并发首启互覆；0o600 权限窗口为零
    try:
        fd = os.open(key_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        # 并发下另一进程已创建：读回其写入的 key，保证各 worker 密钥一致
        with open(key_file, "r", encoding="utf-8") as f:
            return f.read().strip() or new_key
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(new_key)
    return new_key


class Settings(BaseSettings):
    VERSION: str = "0.1.0"
    APP_TITLE: str = "资产管理系统"
    PROJECT_NAME: str = "资产管理系统"
    APP_DESCRIPTION: str = "资产管理系统"

    # 显式 origin 白名单（不再允许任意 Origin 带凭据跨域）
    # 含本机与当前公网演示入口；换 IP 时同步改此列表或环境变量覆盖
    CORS_ORIGINS: typing.List = [
        "http://127.0.0.1:9999",
        "http://localhost:9999",
        "https://asset.example.com",
    ]
    TLS_DOMAIN: str = os.getenv("TLS_DOMAIN", "asset.example.com") or "asset.example.com"
    TLS_HTTPS_URL: str = os.getenv("TLS_HTTPS_URL", "https://asset.example.com") or "https://asset.example.com"
    TLS_HTTP_FALLBACK_URL: str = (
        os.getenv("TLS_HTTP_FALLBACK_URL", "http://127.0.0.1:9999") or "http://127.0.0.1:9999"
    )
    TLS_CERT_PATH: str = (
        os.getenv("TLS_CERT_PATH", "/etc/letsencrypt/live/asset.example.com/fullchain.pem")
        or "/etc/letsencrypt/live/asset.example.com/fullchain.pem"
    )
    TLS_HELPER: str = os.getenv("TLS_HELPER", "/usr/local/sbin/asset-tls") or "/usr/local/sbin/asset-tls"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: typing.List = ["*"]
    CORS_ALLOW_HEADERS: typing.List = ["*"]

    DEBUG: bool = False

    # 是否开放 Swagger 文档（/docs、/openapi.json）。生产环境默认关闭，避免接口定义泄露
    SHOW_DOCS: bool = os.getenv("SHOW_DOCS", "").lower() in ("1", "true", "yes")

    PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    BASE_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, os.pardir))
    LOGS_ROOT: str = os.path.join(BASE_DIR, "app/logs")
    # 密钥来源：环境变量 SECRET_KEY（生产推荐）或 .secret_key 文件（secrets 随机生成并持久化）。
    # 无硬编码默认值——固定默认值可被公开源码利用伪造 JWT / 解密用户 API Key。
    SECRET_KEY: str = _load_or_create_secret(
        os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
    )
    JWT_ALGORITHM: str = "HS256"
    # 访问令牌有效期（分钟）。默认 2h；可用环境变量 JWT_ACCESS_TOKEN_EXPIRE_MINUTES 覆盖。
    # 缩短后旧 token 过期需重新登录（含滑块）。
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 2  # 2 hours

    # —— 零成本安全运营：日志保留与高危二次验证 ——
    # 审计操作日志：超过天数或超过最大行数则清理（先到先清）
    AUDIT_RETENTION_DAYS: int = int(os.getenv("AUDIT_RETENTION_DAYS", "30") or "30")
    AUDIT_MAX_ROWS: int = int(os.getenv("AUDIT_MAX_ROWS", "100000") or "100000")
    # 安全事件 / 登录日志
    SECURITY_EVENT_RETENTION_DAYS: int = int(os.getenv("SECURITY_EVENT_RETENTION_DAYS", "30") or "30")
    SECURITY_EVENT_MAX_ROWS: int = int(os.getenv("SECURITY_EVENT_MAX_ROWS", "50000") or "50000")
    SECURITY_AGG_RETENTION_DAYS: int = int(os.getenv("SECURITY_AGG_RETENTION_DAYS", "180") or "180")
    SECURITY_AGG_MAX_ROWS: int = int(os.getenv("SECURITY_AGG_MAX_ROWS", "200000") or "200000")
    # 高危 step-up token 有效秒数（再输密码后）
    STEP_UP_EXPIRE_SECONDS: int = int(os.getenv("STEP_UP_EXPIRE_SECONDS", "300") or "300")
    # 日志清理后台任务间隔（秒）
    LOG_CLEANUP_INTERVAL_SECONDS: int = int(os.getenv("LOG_CLEANUP_INTERVAL_SECONDS", "3600") or "3600")
    # 离线地理 / 风险标签（只标记，不自动封）
    SECURITY_COMMON_COUNTRIES: str = os.getenv("SECURITY_COMMON_COUNTRIES", "CN,中国") or "CN,中国"
    # 系统助手（可选）。未配置则只返回服务端格式化事实，不访问外网。
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "") or ""
    XAI_MODEL: str = os.getenv("XAI_MODEL", "grok-4-fast-non-reasoning") or "grok-4-fast-non-reasoning"
    GEOIP_XDB_PATH: str = os.getenv("GEOIP_XDB_PATH", "") or ""
    TOR_EXIT_LIST_PATH: str = os.getenv("TOR_EXIT_LIST_PATH", "") or ""
    # 数据库路径：独立目录 db/ 下（修复：容器部署时挂载宿主卷到 /opt/asset-management-system/db，
    # 容器替换/重建不再丢失数据；SQLite 的 -wal/-shm 与主文件同目录持久化）
    TORTOISE_ORM: dict = {
        "connections": {
            # SQLite configuration
            "sqlite": {
                "engine": "tortoise.backends.sqlite",
                "credentials": {"file_path": f"{BASE_DIR}/db/db.sqlite3"},  # Path to SQLite database file
            },
            # MySQL/MariaDB configuration
            # Install with: tortoise-orm[asyncmy]
            # "mysql": {
            #     "engine": "tortoise.backends.mysql",
            #     "credentials": {
            #         "host": "localhost",  # Database host address
            #         "port": 3306,  # Database port
            #         "user": "yourusername",  # Database username
            #         "password": "yourpassword",  # Database password
            #         "database": "yourdatabase",  # Database name
            #     },
            # },
            # PostgreSQL configuration
            # Install with: tortoise-orm[asyncpg]
            # "postgres": {
            #     "engine": "tortoise.backends.asyncpg",
            #     "credentials": {
            #         "host": "localhost",  # Database host address
            #         "port": 5432,  # Database port
            #         "user": "yourusername",  # Database username
            #         "password": "yourpassword",  # Database password
            #         "database": "yourdatabase",  # Database name
            #     },
            # },
            # MSSQL/Oracle configuration
            # Install with: tortoise-orm[asyncodbc]
            # "oracle": {
            #     "engine": "tortoise.backends.asyncodbc",
            #     "credentials": {
            #         "host": "localhost",  # Database host address
            #         "port": 1433,  # Database port
            #         "user": "yourusername",  # Database username
            #         "password": "yourpassword",  # Database password
            #         "database": "yourdatabase",  # Database name
            #     },
            # },
            # SQLServer configuration
            # Install with: tortoise-orm[asyncodbc]
            # "sqlserver": {
            #     "engine": "tortoise.backends.asyncodbc",
            #     "credentials": {
            #         "host": "localhost",  # Database host address
            #         "port": 1433,  # Database port
            #         "user": "yourusername",  # Database username
            #         "password": "yourpassword",  # Database password
            #         "database": "yourdatabase",  # Database name
            #     },
            # },
        },
        "apps": {
            "models": {
                "models": ["app.models", "aerich.models"],
                "default_connection": "sqlite",
            },
        },
        "use_tz": False,  # Whether to use timezone-aware datetimes
        "timezone": "Asia/Shanghai",  # Timezone setting
    }
    DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"


settings = Settings()
