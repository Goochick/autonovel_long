#!/usr/bin/env python3
# ============================================================
# seed.py - 种子概念生成脚本
# 用于生成小说种子概念（故事起点）
# ============================================================

import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from api.api_client import APIClient
from prompts.prompts_cn import (
    SYSTEM_PROMPT_SEED,
    GENERATE_PROMPT,
    RIFF_PROMPT
)
from config import DEFAULT_WRITER_API

# 输出目录
OUTPUTS_DIR = _project_root / "outputs"


def generate_seeds(count: int = 10) -> str:
    """生成多个种子概念"""
    client = APIClient()

    prompt = GENERATE_PROMPT.format(count=count)

    print(f"正在生成 {count} 个种子概念...", file=sys.stderr)

    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_SEED,
        api_name=DEFAULT_WRITER_API,
        max_tokens=8000,
        temperature=1.0
    )

    return response


def riff_on_seed(seed: str) -> str:
    """基于已有种子扩展变体"""
    client = APIClient()

    prompt = RIFF_PROMPT.format(idea=seed)

    print("正在生成变体...", file=sys.stderr)

    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_SEED,
        api_name=DEFAULT_WRITER_API,
        max_tokens=6000,
        temperature=0.9
    )

    return response


def save_seed(seed_text: str, filename: str = "seed.md"):
    """保存种子到文件"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    OUTPUTS_DIR.mkdir(exist_ok=True)
    filepath = OUTPUTS_DIR / filename

    # 如果已存在，追加而不是覆盖
    if filepath.exists():
        backup = OUTPUTS_DIR / f"seed_backup_{Path(__file__).stat().st_mtime}.txt"
        filepath.rename(backup)

    filepath.write_text(seed_text, encoding="utf-8")
    print(f"已保存到: {filepath}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="生成小说种子概念")
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=10,
        help="生成多少个种子概念（默认10个）"
    )
    parser.add_argument(
        "--riff", "-r",
        type=str,
        default=None,
        help="基于已有种子生成变体（填入种子内容）"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="保存到 seed.md"
    )
    parser.add_argument(
        "--genre",
        type=str,
        default=None,
        help="指定品类筛选（都市脑洞/重生穿越/玄幻仙侠/豪门总裁/年代种田）"
    )

    args = parser.parse_args()

    # 检查 API Key
    client = APIClient()
    if not client.is_configured():
        print("=" * 60)
        print("❌ 错误：API Key 未配置！")
        print("=" * 60)
        print("请先复制 .env.example 为 .env，然后填入你的 API Key：")
        print("  1. cp .env.example .env")
        print("  2. 编辑 .env，填入 DEEPSEEK_API_KEY")
        print("  3. 获取 API Key: https://platform.deepseek.com/")
        print("=" * 60)
        sys.exit(1)

    if args.riff:
        # 基于种子生成变体
        result = riff_on_seed(args.riff)
    else:
        # 生成新种子
        result = generate_seeds(args.count)

    # 输出结果
    print("\n" + "=" * 60)
    print("生成结果：")
    print("=" * 60)
    print(result)

    if args.save:
        save_seed(result)

    print("\n" + "=" * 60)
    print("💡 提示：")
    print("  - 复制喜欢的种子到 seed.txt，然后运行下一步")
    print("  - python scripts/gen_world.py  # 生成世界观")
    print("=" * 60)


if __name__ == "__main__":
    main()
