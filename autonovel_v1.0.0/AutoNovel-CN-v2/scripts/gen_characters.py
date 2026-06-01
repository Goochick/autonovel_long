#!/usr/bin/env python3
# ============================================================
# gen_characters.py - 角色生成脚本
# 基于种子和世界观生成完整的角色设定
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
    SYSTEM_PROMPT_CHARACTERS,
    CHARACTER_GENERATION_PROMPT
)
from config import DEFAULT_WRITER_API

# 输出目录
OUTPUTS_DIR = _project_root / "outputs"


def load_seed() -> str:
    """加载种子概念"""
    seed_file = OUTPUTS_DIR / "seed.md"
    if not seed_file.exists():
        print("=" * 60)
        print("❌ 错误：seed.md 不存在！")
        print("=" * 60)
        print("请先运行：python scripts/seed.py --save")
        print("=" * 60)
        sys.exit(1)
    return seed_file.read_text(encoding="utf-8")


def load_world() -> str:
    """加载世界观"""
    world_file = OUTPUTS_DIR / "world.md"
    if not world_file.exists():
        print("=" * 60)
        print("❌ 错误：world.md 不存在！")
        print("=" * 60)
        print("请先运行：python scripts/gen_world.py --save")
        print("=" * 60)
        sys.exit(1)
    return world_file.read_text(encoding="utf-8")


def load_config() -> dict:
    """加载配置"""
    config_file = _project_root / "config.yaml"
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def generate_characters(seed: str, world: str, genre: str = None) -> str:
    """生成角色设定"""
    client = APIClient()
    
    if genre is None:
        config = load_config()
        genre = config.get('genre', '都市脑洞')
    
    prompt = CHARACTER_GENERATION_PROMPT.format(
        seed=seed,
        world=world,
        genre=genre
    )
    
    print(f"正在生成 {genre} 角色设定...", file=sys.stderr)
    
    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_CHARACTERS,
        api_name=DEFAULT_WRITER_API,
        max_tokens=16000,
        temperature=0.7
    )
    
    return response


def save_characters(characters_text: str, filename: str = "characters.md"):
    """保存角色设定"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    filepath = OUTPUTS_DIR / filename
    
    if filepath.exists():
        backup = OUTPUTS_DIR / "characters_backup.md"
        filepath.rename(backup)
        print(f"已备份旧文件到: {backup}", file=sys.stderr)
    
    filepath.write_text(characters_text, encoding="utf-8")
    print(f"已保存到: {filepath}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="生成小说角色设定")
    parser.add_argument(
        "--genre", "-g",
        type=str,
        default=None,
        help="指定品类"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="保存到 characters.md"
    )
    
    args = parser.parse_args()
    
    # 检查 API Key
    client = APIClient()
    if not client.is_configured():
        print("=" * 60)
        print("❌ 错误：API Key 未配置！")
        print("=" * 60)
        sys.exit(1)
    
    # 加载必要文件
    seed = load_seed()
    world = load_world()
    
    print(f"已加载种子（{len(seed)} 字）和世界观（{len(world)} 字）", file=sys.stderr)
    
    # 生成角色
    result = generate_characters(seed, world, args.genre)
    
    # 输出
    print("\n" + "=" * 60)
    print("生成结果：")
    print("=" * 60)
    print(result)
    
    if args.save:
        save_characters(result)
    
    print("\n" + "=" * 60)
    print("💡 提示：")
    print("  - 运行下一步生成大纲：python scripts/gen_outline.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
