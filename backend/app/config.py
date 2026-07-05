"""应用配置。

基于 pydantic-settings 从 .env 读取配置。
- 双 API key：DASHSCOPE_API_KEY（识图）+ BAILIAN_API_KEY（对话）
- AI 模型名集中在此（业务代码只传 scene）
- 服务器：118.178.229.21，端口默认，密码 1234
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置单例。

    所有字段从环境变量或 .env 文件读取，缺失必填项时 fail fast。
    """

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ===== AI 双平台（关键字段，必填，缺失 fail fast）=====
    DASHSCOPE_API_KEY: str = Field(description="通义千问 VL API Key")
    BAILIAN_API_KEY: str = Field(description="阿里百练 API Key")
    BAILIAN_BASE_URL: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="百练兼容 OpenAI 接口的 base_url",
    )

    # ===== AI 模型名集中管理 =====
    QWEN_VL_MODEL: str = Field(default="qwen-vl-max", description="识菜主模型")
    QWEN_VL_MODEL_FALLBACK: str = Field(default="qwen-vl-plus", description="识菜降级模型")
    QWEN_PLUS_MODEL: str = Field(default="qwen3.7-plus", description="对话/语音多模态")
    QWEN_MAX_MODEL: str = Field(default="qwen3.7-max", description="周报/复杂推演")
    QWEN_FLASH_MODEL: str = Field(default="qwen3.7-flash", description="情绪/摘要/短回复")

    # ===== 数据库（关键字段，必填，缺失 fail fast）=====
    PG_DSN: str = Field(description="PostgreSQL 异步连接串")
    REDIS_URL: str = Field(description="Redis 连接串")
    MONGO_URL: str = Field(default="", description="MongoDB 连接串（空则跳过）")
    MONGO_DB: str = Field(default="food_healing", description="MongoDB 数据库名")

    # ===== MQ（RabbitMQ，可选；Phase 1 暂不用，识图改 asyncio.create_task）=====
    RABBITMQ_URL: str = Field(default="", description="RabbitMQ 连接串（可选，空则跳过）")
    RABBITMQ_EXCHANGE: str = Field(default="food_healing", description="RabbitMQ 主交换机名")
    RABBITMQ_EXCHANGE_TYPE: str = Field(default="direct", description="交换机类型：direct/topic/fanout")

    # ===== OSS（关键字段，必填；MinIO 兼容 S3，但用 oss2 SDK 直连）=====
    OSS_ENDPOINT: str = Field(description="OSS/MinIO endpoint，如 http://118.178.229.21:9000")
    OSS_BUCKET: str = Field(default="food-healing-images")
    OSS_ACCESS_KEY_ID: str = Field(description="OSS/MinIO Access Key ID")
    OSS_ACCESS_KEY_SECRET: str = Field(description="OSS/MinIO Access Key Secret")

    # ===== Nacos（可选，未部署时 NACOS_ENABLED=false 跳过）=====
    NACOS_ENABLED: bool = Field(default=False, description="是否启用 Nacos 探活")
    NACOS_SERVER: str = Field(default="118.178.229.21:8848")
    NACOS_NAMESPACE: str = Field(default="dev")
    NACOS_USERNAME: str = Field(default="nacos")
    NACOS_PASSWORD: str = Field(default="1234")

    # ===== 应用 =====
    ENV: Literal["dev", "staging", "prod"] = Field(default="dev")
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["*"])
    RATE_LIMIT_RECOGNIZE: str = Field(default="10/minute")
    RATE_LIMIT_CHAT: str = Field(default="20/minute")
    MAX_IMAGE_SIZE_MB: int = Field(default=5)
    LOG_LEVEL: str = Field(default="INFO")
    LOG_DIR: str = Field(default="logs", description="日志文件目录（按日轮转）")
    LOG_RETENTION_DAYS: int = Field(default=14, description="日志保留天数")
    TIMEZONE: str = Field(default="Asia/Shanghai", description="APScheduler 时区，影响 daily_reports 触发时点")
    APP_NAME: str = Field(default="食愈校园")
    APP_VERSION: str = Field(default="0.1.0")

    # ===== Redis Key 前缀（统一）=====
    REDIS_KEY_PREFIX: str = Field(default="food_healing:")

    # ===== 鉴权（JWT + bcrypt）=====
    JWT_SECRET: str = Field(
        default="food-healing-demo-secret-change-in-prod",
        description="JWT 签名密钥，dev 默认值，生产必改",
    )
    JWT_EXPIRE_HOURS: int = Field(default=168, description="JWT 过期时间（小时），默认 7 天")
    AVATAR_UPLOAD_DIR: str = Field(default="uploads/avatars", description="头像本地存储目录")


settings = Settings()
"""全局配置单例，业务代码 `from app.config import settings` 取用。"""
