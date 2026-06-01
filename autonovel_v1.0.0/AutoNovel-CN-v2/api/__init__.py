"""
AutoNovel-CN API 适配层
支持多个 OpenAI 兼容格式的中文 API
"""

# 注意：避免在 __init__.py 中导入 api_client，
# 因为 api_client 内部会使用 importlib 导入 config
# 如需使用，请直接导入：
#   from api.api_client import APIClient, call_writer, call_judge

__all__ = ["api_client"]
