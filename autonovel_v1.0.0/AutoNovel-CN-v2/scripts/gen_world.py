#!/usr/bin/env python3
# ============================================================
# gen_world.py - 世界观生成脚本
# 基于种子概念生成完整的世界观设定
# ============================================================

import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

import yaml

from api.api_client import APIClient
from prompts.prompts_cn import (
    SYSTEM_PROMPT_WORLD,
    WORLD_BUILDING_PROMPT
)
from config import DEFAULT_WRITER_API

# 输出目录
OUTPUTS_DIR = _project_root / "outputs"


def load_seed() -> str:
    """从 seed.md 加载种子概念"""
    seed_file = OUTPUTS_DIR / "seed.md"
    if not seed_file.exists():
        print("=" * 60)
        print("❌ 错误：seed.md 不存在！")
        print("=" * 60)
        print("请先运行种子生成：")
        print("  python scripts/seed.py --save")
        print("=" * 60)
        sys.exit(1)
    return seed_file.read_text(encoding="utf-8")


def load_config() -> dict:
    """加载 config.yaml 配置"""
    config_file = _project_root / "config.yaml"
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def generate_world(seed: str, genre: str = None) -> str:
    """生成世界观"""
    client = APIClient()

    # 从配置获取品类
    if genre is None:
        config = load_config()
        genre = config.get('genre', '都市脑洞')

    prompt = WORLD_BUILDING_PROMPT.format(
        genre=genre,
        seed=seed
    )

    print(f"正在生成 {genre} 世界观...", file=sys.stderr)

    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_WORLD,
        api_name=DEFAULT_WRITER_API,
        max_tokens=16000,
        temperature=0.7
    )

    return response


def save_world(world_text: str, filename: str = "world.md"):
    """保存世界观到文件"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    filepath = OUTPUTS_DIR / filename

    # 如果已存在，备份
    if filepath.exists():
        backup = OUTPUTS_DIR / f"world_backup.md"
        filepath.rename(backup)
        print(f"已备份旧文件到: {backup}", file=sys.stderr)

    filepath.write_text(world_text, encoding="utf-8")
    print(f"已保存到: {filepath}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="生成小说世界观")
    parser.add_argument(
        "--genre", "-g",
        type=str,
        default=None,
        help="指定品类（默认从 config.yaml 读取）"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="保存到 world.md"
    )
    parser.add_argument(
        "--seed-file",
        type=str,
        default="seed.md",
        help="种子文件路径（默认 outputs/seed.md）"
    )

    args = parser.parse_args()

    # 检查 API Key
    client = APIClient()
    if not client.is_configured():
        print("=" * 60)
        print("❌ 错误：API Key 未配置！")
        print("=" * 60)
        print("请先配置 .env 文件，填入你的 API Key")
        print("=" * 60)
        sys.exit(1)

    # 加载种子
    seed = load_seed()
    print(f"已加载种子概念（{len(seed)} 字）", file=sys.stderr)

    # 生成世界观
    result = generate_world(seed, args.genre)

    # 输出结果
    print("\n" + "=" * 60)
    print("生成结果：")
    print("=" * 60)
    print(result)

    if args.save:
        save_world(result)

    print("\n" + "=" * 60)
    print("💡 提示：")
    print("  - 运行下一步生成角色：python scripts/gen_characters.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
