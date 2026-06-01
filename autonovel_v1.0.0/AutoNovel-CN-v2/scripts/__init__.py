# ============================================================
# AutoNovel-CN Scripts
# 脚本模块初始化
# ============================================================

"""
AutoNovel-CN 中文网文生成器脚本集

使用方式：
1. 独立运行：python scripts/seed.py
2. Pipeline运行：python main.py --phase=seed

依赖关系：
seed -> gen_world -> gen_characters -> gen_outline -> draft_chapter -> evaluate -> revise
"""

__version__ = "1.0.0"
