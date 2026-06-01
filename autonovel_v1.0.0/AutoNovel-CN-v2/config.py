# ============================================================
# AutoNovel-CN 配置文件
# 基于 AutoNovel v1.0 改造，适配多个中文便宜API
# ============================================================

import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# ============================================================
# API 配置
# ============================================================

# DeepSeek API（主力生成 + 关键审核）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# 阿里云 DashScope（Qwen 系列，快速草稿）
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 智谱 AI（GLM 系列，免费额度）
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

# ============================================================
# 默认 API 选择
# ============================================================

# 默认的生成类任务 API
DEFAULT_WRITER_API = os.environ.get("DEFAULT_WRITER_API", "deepseek_flash")

# 默认的审核/评估类任务 API
DEFAULT_JUDGE_API = os.environ.get("DEFAULT_JUDGE_API", "deepseek_pro")

# ============================================================
# 任务路由配置
# ============================================================

# 根据任务类型自动路由到最合适的 API
# v0.9.5: 迁移到 DeepSeek V4（旧模型 deepseek-chat/reasoner 2026-07-24 弃用）
# Flash = 高速低成本，Pro = 高性能推理
ROUTE_MAP = {
    # 创意生成类 - 使用 V4 Flash（便宜+生成质量好）
    "seed_generation": "deepseek_flash",   # 种子概念生成
    "world_building": "deepseek_flash",    # 世界观构建
    "character_gen": "deepseek_flash",     # 角色生成
    "outline_gen": "deepseek_flash",       # 大纲生成
    "chapter_draft": "deepseek_flash",     # 章节撰写（主力）
    "chapter_revision": "deepseek_flash", # 章节修订
    "revision": "deepseek_flash",          # 修订
    "canon_extract": "deepseek_flash",     # 典据提取
    "voice_analysis": "deepseek_flash",    # 语声分析

    # 关键/审核类 - Pro推理更强，格式遵从更好
    "chapter_draft_key": "deepseek_pro",   # 关键高潮章节（需深度推理）
    "foundation_eval": "deepseek_pro",     # Foundation 评估（需JSON输出）
    "chapter_eval": "deepseek_pro",        # 章节评估（7维度JSON+top_revisions）
    "full_eval": "deepseek_pro",           # 全书评估（需JSON输出）
    "review": "deepseek_pro",              # 审阅（纯推理）
    "adversarial_edit": "deepseek_pro",    # 对抗编辑

    # 免费 API（机械检测/格式化）
    "slop_detection": "glm_4_flash",       # AI 味检测
    "formatting": "glm_4_flash",           # 格式化处理
}

# ============================================================
# API 提供商详细配置
# ============================================================

API_PROVIDERS = {
    "deepseek_flash": {
        "name": "DeepSeek V4 Flash",
        "base_url": DEEPSEEK_BASE_URL,
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_key": DEEPSEEK_API_KEY,
        "model": "deepseek-v4-flash",      # V4 Flash（替代旧 deepseek-chat）
        "max_tokens_limit": 8192,
        "supports_reasoning": False,        # 非思考模式
        "default_temperature": 0.8,         # 写作温度
        "fallback": "qwen_turbo",           # 降级目标
    },
    "deepseek_pro": {
        "name": "DeepSeek V4 Pro",
        "base_url": DEEPSEEK_BASE_URL,
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_key": DEEPSEEK_API_KEY,
        "model": "deepseek-v4-pro",         # V4 Pro（替代旧 deepseek-reasoner）
        "max_tokens_limit": 16384,
        "supports_reasoning": True,         # 支持思考模式
        "default_temperature": 0.5,         # 评估/推理温度
        "fallback": "deepseek_flash",       # 降级到 Flash
    },
    # 旧模型兼容（2026-07-24 弃用后删除）
    "deepseek_v3": {
        "name": "DeepSeek V3 (legacy)",
        "base_url": DEEPSEEK_BASE_URL,
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_key": DEEPSEEK_API_KEY,
        "model": "deepseek-chat",           # 已自动路由到 V4 Flash
        "max_tokens_limit": 8192,
        "supports_reasoning": False,
        "default_temperature": 0.8,
        "fallback": "qwen_turbo",
    },
    "deepseek_r1": {
        "name": "DeepSeek R1 (legacy)",
        "base_url": DEEPSEEK_BASE_URL,
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_key": DEEPSEEK_API_KEY,
        "model": "deepseek-reasoner",       # 已自动路由到 V4 Flash 思考模式
        "max_tokens_limit": 16384,
        "supports_reasoning": True,
        "default_temperature": 0.5,
        "fallback": "deepseek_flash",
    },
    "qwen_turbo": {
        "name": "Qwen Turbo",
        "base_url": DASHSCOPE_BASE_URL,
        "api_key_env": "DASHSCOPE_API_KEY",
        "api_key": DASHSCOPE_API_KEY,
        "model": "qwen-turbo",
        "max_tokens_limit": 8192,
        "supports_reasoning": False,
        "default_temperature": 0.8,
        "fallback": "glm_4_flash",          # 降级到免费 API
    },
    "glm_4_flash": {
        "name": "GLM-4-Flash",
        "base_url": ZHIPU_BASE_URL,
        "api_key_env": "ZHIPU_API_KEY",
        "api_key": ZHIPU_API_KEY,
        "model": "glm-4-flash",
        "max_tokens_limit": 4096,
        "supports_reasoning": False,
        "default_temperature": 0.7,
        "fallback": None,                   # 免费 API，不再降级
    },
}

# ============================================================
# 生成参数配置
# ============================================================

# 写作参数
WRITER_TEMPERATURE = float(os.environ.get("WRITER_TEMPERATURE", "0.8"))
WRITER_MAX_TOKENS = int(os.environ.get("WRITER_MAX_TOKENS", "4000"))

# 审核参数
JUDGE_TEMPERATURE = float(os.environ.get("JUDGE_TEMPERATURE", "0.3"))
JUDGE_MAX_TOKENS = int(os.environ.get("JUDGE_MAX_TOKENS", "2000"))

# 重试配置
MAX_RETRIES = int(os.environ.get("API_MAX_RETRIES", "3"))
RETRY_BACKOFF = float(os.environ.get("API_RETRY_BACKOFF", "1.5"))  # 指数退避基数

# 超时配置（秒）
REQUEST_TIMEOUT = int(os.environ.get("API_REQUEST_TIMEOUT", "120"))

# ============================================================
# 文件路径配置
# ============================================================

OUTPUT_DIR = BASE_DIR / "outputs"
CHAPTERS_DIR = OUTPUT_DIR / "chapters"
EVAL_LOGS_DIR = OUTPUT_DIR / "eval_logs"

# 确保目录存在
OUTPUT_DIR.mkdir(exist_ok=True)
CHAPTERS_DIR.mkdir(exist_ok=True)
EVAL_LOGS_DIR.mkdir(exist_ok=True)

# ============================================================
# 项目配置
# ============================================================

PROJECT_NAME = "AutoNovel-CN"
PROJECT_VERSION = "1.0.0"
PROJECT_DESC = "番茄小说AI辅助创作工具（多API适配版）"

# 默认章节数
DEFAULT_CHAPTER_COUNT = 30

# 每章目标字数
TARGET_CHAPTER_WORDS = 3000

# ============================================================
# 文件名常量（与 config.yaml 保持一致）
# ============================================================

SEED_FILE = "seed.md"
WORLD_FILE = "world.md"
CHARACTERS_FILE = "characters.md"
OUTLINE_FILE = "outline.md"
CANON_FILE = "canon.md"
MYSTERY_FILE = "mystery.md"
VOICE_FILE = "voice.md"

# 模板目录
TEMPLATES_DIR = BASE_DIR / "templates"

# ============================================================
# Token 预算控制
# ============================================================

# 全局 token 预算上限（千tokens），0 = 不限
TOKEN_BUDGET_K = int(os.environ.get("TOKEN_BUDGET_K", "0"))

# 单阶段 token 上限（千tokens），0 = 不限
PER_PHASE_LIMIT_K = int(os.environ.get("PER_PHASE_LIMIT_K", "50"))

# 单章修订 token 上限（千tokens）
PER_CHAPTER_REVISION_LIMIT_K = int(os.environ.get("PER_CHAPTER_REVISION_LIMIT_K", "30"))

# 是否显示每次调用的预估费用
SHOW_COST_ESTIMATE = os.environ.get("SHOW_COST_ESTIMATE", "true").lower() == "true"

# ============================================================
# 费率表（元/千tokens，用于估算）
# ============================================================

PRICING = {
    "deepseek_flash": {"input": 0.001, "output": 0.002},   # V4 Flash: $0.14/$0.28 per MTok
    "deepseek_pro":  {"input": 0.003, "output": 0.006},   # V4 Pro: $0.435/$0.87 per MTok (75%永久折扣)
    "deepseek_v3":   {"input": 0.002, "output": 0.008},   # 旧V3（已路由到Flash）
    "deepseek_r1":   {"input": 0.004, "output": 0.016},   # 旧R1（已路由到Flash思考模式）
    "qwen_turbo":    {"input": 0.0003, "output": 0.0006}, # Qwen Turbo
    "glm_4_flash":   {"input": 0.0, "output": 0.0},       # GLM-4-Flash 免费
}
