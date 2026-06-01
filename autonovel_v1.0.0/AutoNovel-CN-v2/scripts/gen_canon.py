#!/usr/bin/env python3
# ============================================================
# gen_canon.py - 典据提取脚本
# 从策划文档中提取硬性事实，建立典据数据库
# ============================================================

import argparse
import sys
from pathlib import Path

# 添加项目根目录
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from api.api_client import APIClient
from prompts.prompts_cn import (
    SYSTEM_PROMPT_CANON,
    CANON_EXTRACTION_PROMPT
)
from config import DEFAULT_WRITER_API

# 输出目录
OUTPUTS_DIR = _project_root / "outputs"


def load_seed() -> str:
    """加载种子"""
    f = OUTPUTS_DIR / "seed.md"
    return f.read_text(encoding="utf-8") if f.exists() else "(无)"


def load_world() -> str:
    """加载世界观"""
    f = OUTPUTS_DIR / "world.md"
    return f.read_text(encoding="utf-8") if f.exists() else "(无)"


def load_characters() -> str:
    """加载角色"""
    f = OUTPUTS_DIR / "characters.md"
    return f.read_text(encoding="utf-8") if f.exists() else "(无)"


def generate_canon() -> str:
    """生成典据数据库"""
    client = APIClient()

    seed = load_seed()
    world = load_world()
    characters = load_characters()

    prompt = CANON_EXTRACTION_PROMPT.format(
        seed=seed,
        world=world,
        characters=characters
    )

    print("正在提取典据...", file=sys.stderr)

    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_CANON,
        api_name=DEFAULT_WRITER_API,
        max_tokens=12000,
        temperature=0.3
    )

    return response


def save_canon(canon_text: str, filename: str = "canon.md"):
    """保存典据"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    filepath = OUTPUTS_DIR / filename

    if filepath.exists():
        backup = OUTPUTS_DIR / "canon_backup.md"
        filepath.rename(backup)
        print(f"已备份旧典据到: {backup}", file=sys.stderr)

    filepath.write_text(canon_text, encoding="utf-8")
    print(f"已保存到: {filepath}", file=sys.stderr)


def update_canon(from_chapter: int = None, to_chapter: int = None) -> str:
    """从已写章节更新典据，追踪装备/技能/人物关系变化"""
    from prompts.prompts_cn import CANON_UPDATE_PROMPT, SYSTEM_PROMPT_CANON

    client = APIClient()

    # 加载旧版典据
    canon_file = OUTPUTS_DIR / "canon.md"
    if canon_file.exists():
        old_canon = canon_file.read_text(encoding="utf-8")
    else:
        print("⚠️  canon.md 不存在，先执行全新提取", file=sys.stderr)
        return generate_canon()

    # 加载已写章节
    chapters_dir = OUTPUTS_DIR / "chapters"
    if not chapters_dir.exists():
        print("❌ 还没有写任何章节！", file=sys.stderr)
        sys.exit(1)

    chapter_files = sorted(chapters_dir.glob("ch_*.md"))
    # 过滤掉非章节文件（如 _original, _passed 等）
    chapter_files = [f for f in chapter_files if not any(x in f.stem for x in ['original', 'passed', 'revised'])]

    if not chapter_files:
        print("❌ 没有找到章节文件！", file=sys.stderr)
        sys.exit(1)

    # 如果指定了章节范围
    if from_chapter is not None:
        chapter_files = [f for f in chapter_files if int(f.stem.split("_")[1]) >= from_chapter]
    if to_chapter is not None:
        chapter_files = [f for f in chapter_files if int(f.stem.split("_")[1]) <= to_chapter]

    # 读取章节内容（合并，限制总长度避免超token）
    chapters_content = []
    total_len = 0
    for cf in chapter_files:
        ch_num = cf.stem.split("_")[1]
        text = cf.read_text(encoding="utf-8")
        chapters_content.append(f"=== 第 {int(ch_num)} 章 ===\n{text}")
        total_len += len(text)
        if total_len > 50000:  # 限制约50k字符
            break

    new_chapters = "\n\n".join(chapters_content)

    ch_range = f"第 {chapter_files[0].stem.split('_')[1]} ~ {chapter_files[-1].stem.split('_')[1]} 章" if chapter_files else "0 章"
    print(f"正在从 {ch_range} 更新典据...", file=sys.stderr)

    prompt = CANON_UPDATE_PROMPT.format(
        old_canon=old_canon[:15000],
        new_chapters=new_chapters[:30000]
    )

    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_CANON,
        api_name=DEFAULT_WRITER_API,
        max_tokens=16000,
        temperature=0.3
    )

    return response


def main():
    parser = argparse.ArgumentParser(description="提取典据")
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="保存典据"
    )
    parser.add_argument(
        "--update", "-u",
        action="store_true",
        help="从已写章节更新典据（追踪装备/技能/关系变化）"
    )
    parser.add_argument(
        "--from-chapter",
        type=int,
        default=None,
        help="更新起始章节（配合 --update 使用）"
    )
    parser.add_argument(
        "--to-chapter",
        type=int,
        default=None,
        help="更新结束章节（配合 --update 使用）"
    )

    args = parser.parse_args()

    # 检查 API
    client = APIClient()
    if not client.is_configured():
        print("❌ API Key 未配置！"); sys.exit(1)

    if args.update:
        # 更新模式
        result = update_canon(from_chapter=args.from_chapter, to_chapter=args.to_chapter)
    else:
        # 全新生成模式
        result = generate_canon()

    # 输出
    print("\n" + "=" * 60)
    print("典据数据库：")
    print("=" * 60)
    print(result)

    if args.save:
        save_canon(result)

    print("\n" + "=" * 60)
    print("💡 提示：")
    print("  - 典据数据库用于保持全书一致性")
    print("  - 写稿时自动加载，确保角色名/地名/能力名不打架")
    print("=" * 60)


if __name__ == "__main__":
    main()
