#!/usr/bin/env python3
# ============================================================
# gen_outline.py - 大纲生成脚本
# 基于种子、世界观、角色生成完整的故事大纲
# ============================================================

import argparse
import re
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

import yaml

from api.api_client import APIClient
from prompts.prompts_cn import (
    SYSTEM_PROMPT_OUTLINE,
    OUTLINE_GENERATION_PROMPT
)
from config import DEFAULT_WRITER_API

# 输出目录
OUTPUTS_DIR = _project_root / "outputs"


def load_seed() -> str:
    """加载种子"""
    seed_file = OUTPUTS_DIR / "seed.md"
    if not seed_file.exists():
        print("❌ seed.md 不存在！请先运行 seed.py")
        sys.exit(1)
    return seed_file.read_text(encoding="utf-8")


def load_world() -> str:
    """加载世界观"""
    world_file = OUTPUTS_DIR / "world.md"
    if not world_file.exists():
        print("❌ world.md 不存在！请先运行 gen_world.py")
        sys.exit(1)
    return world_file.read_text(encoding="utf-8")


def load_characters() -> str:
    """加载角色设定"""
    char_file = OUTPUTS_DIR / "characters.md"
    if not char_file.exists():
        print("❌ characters.md 不存在！请先运行 gen_characters.py")
        sys.exit(1)
    return char_file.read_text(encoding="utf-8")


def load_config() -> dict:
    """加载配置"""
    config_file = _project_root / "config.yaml"
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def generate_outline(
    seed: str,
    world: str,
    characters: str,
    genre: str = None,
    chapter_count: int = 30,
    words_per_chapter: int = 2000
) -> str:
    """生成大纲"""
    client = APIClient()

    if genre is None:
        config = load_config()
        genre = config.get('genre', '都市脑洞')
        chapter_count = config.get('chapter_count', 30)
        words_per_chapter = config.get('words_per_chapter', 2000)

    # 计算总字数和最少剧情弧
    target_word_count = chapter_count * words_per_chapter
    min_arcs = max(3, chapter_count // 10)
    target_words_per_chapter = words_per_chapter

    prompt = OUTLINE_GENERATION_PROMPT.format(
        seed=seed,
        world=world,
        characters=characters,
        genre=genre,
        target_word_count=target_word_count,
        target_chapters=chapter_count,
        min_arcs=min_arcs,
        target_words_per_chapter=target_words_per_chapter
    )

    print(f"正在生成 {chapter_count} 章大纲...", file=sys.stderr)

    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_OUTLINE,
        api_name=DEFAULT_WRITER_API,
        max_tokens=20000,
        temperature=0.6
    )

    return response


def save_outline(outline_text: str, filename: str = "outline.md"):
    """保存大纲"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    filepath = OUTPUTS_DIR / filename

    if filepath.exists():
        backup = OUTPUTS_DIR / "outline_backup.md"
        filepath.rename(backup)
        print(f"已备份旧文件到: {backup}", file=sys.stderr)

    filepath.write_text(outline_text, encoding="utf-8")
    print(f"已保存到: {filepath}", file=sys.stderr)


def extend_outline(extend_count: int = 30, genre: str = None, words_per_chapter: int = None) -> str:
    """续写大纲：在现有大纲基础上续写N章"""
    from prompts.prompts_cn import OUTLINE_EXTEND_PROMPT, SYSTEM_PROMPT_OUTLINE

    client = APIClient()
    config = load_config()

    # 参数
    genre = genre or config.get('genre', '都市脑洞')
    words_per_chapter = words_per_chapter or config.get('words_per_chapter', 2000)

    # 加载现有大纲
    outline_file = OUTPUTS_DIR / "outline.md"
    if not outline_file.exists():
        print("❌ outline.md 不存在！请先运行 gen_outline.py", file=sys.stderr)
        sys.exit(1)

    existing_outline = outline_file.read_text(encoding="utf-8")

    # 解析已有大纲的章节数
    chapter_markers = re.findall(r'###\s*第\s*(\d+)\s*章', existing_outline)
    if chapter_markers:
        last_chapter = max(int(n) for n in chapter_markers)
    else:
        # 尝试其他格式
        chapter_markers = re.findall(r'第\s*(\d+)\s*章', existing_outline)
        last_chapter = max(int(n) for n in chapter_markers) if chapter_markers else 0

    if last_chapter == 0:
        print("❌ 无法从大纲中解析章节号！请检查大纲格式", file=sys.stderr)
        sys.exit(1)

    next_chapter = last_chapter + 1
    total_chapters = last_chapter + extend_count

    # 提取大纲最后5章作为上下文
    all_chapters = re.split(r'(###\s*第\s*\d+\s*章)', existing_outline)
    tail_chapters = ""
    if len(all_chapters) > 2:
        # 取最后几章
        tail_parts = all_chapters[-10:]  # 最后5章左右
        tail_chapters = "".join(tail_parts)[-3000:]
    else:
        tail_chapters = existing_outline[-3000:]

    # 提取伏笔台账
    foreshadow_match = re.search(r'(##\s*四、全书伏笔.*|##\s*伏笔.*?)(?=\n##|\Z)', existing_outline, re.DOTALL)
    existing_foreshadows = foreshadow_match.group(0)[-2000:] if foreshadow_match else "(未找到伏笔台账)"

    # 加载其他素材
    seed = load_seed()
    world = load_world()
    characters = load_characters()

    # 加载mystery（可选）
    mystery_file = OUTPUTS_DIR / "mystery.md"
    mystery = mystery_file.read_text(encoding="utf-8")[-1500:] if mystery_file.exists() else "(未生成)"

    min_arcs = max(2, extend_count // 10)
    min_outline_words = extend_count * 150

    prompt = OUTLINE_EXTEND_PROMPT.format(
        existing_outline_tail=tail_chapters,
        existing_foreshadows=existing_foreshadows,
        mystery=mystery,
        seed=seed[:2000],
        world=world[:3000],
        characters=characters[:2000],
        genre=genre,
        last_chapter=last_chapter,
        next_chapter=next_chapter,
        total_chapters=total_chapters,
        extend_count=extend_count,
        words_per_chapter=words_per_chapter,
        min_arcs=min_arcs,
        min_outline_words=min_outline_words
    )

    print(f"正在续写大纲：第 {next_chapter} ~ {total_chapters} 章（续写 {extend_count} 章）...", file=sys.stderr)

    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_OUTLINE,
        api_name=DEFAULT_WRITER_API,
        max_tokens=20000,
        temperature=0.6
    )

    return response, existing_outline


def save_extended_outline(new_outline_text: str, old_outline: str):
    """保存续写大纲（追加模式）"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    filepath = OUTPUTS_DIR / "outline.md"

    # 备份旧大纲
    backup = OUTPUTS_DIR / "outline_backup.md"
    if filepath.exists():
        filepath.rename(backup)
        print(f"已备份旧大纲到: {backup}", file=sys.stderr)

    # 合并：旧大纲 + 新续写部分
    # 去掉新大纲里可能重复的已有章节
    combined = old_outline.rstrip() + "\n\n---\n\n## 续写大纲\n\n" + new_outline_text
    filepath.write_text(combined, encoding="utf-8")
    print(f"已保存合并大纲到: {filepath}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="生成小说大纲")
    parser.add_argument(
        "--genre", "-g",
        type=str,
        default=None,
        help="指定品类"
    )
    parser.add_argument(
        "--chapters", "-c",
        type=int,
        default=None,
        help="目标章节数（默认从 config.yaml 读取）"
    )
    parser.add_argument(
        "--words", "-w",
        type=int,
        default=None,
        help="每章字数（默认2000）"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="保存到 outline.md"
    )
    parser.add_argument(
        "--extend", "-e",
        type=int,
        default=None,
        help="续写N章大纲（从现有大纲末尾延续）"
    )

    args = parser.parse_args()

    # 检查 API
    client = APIClient()
    if not client.is_configured():
        print("❌ API Key 未配置！请配置 .env")
        sys.exit(1)

    config = load_config()

    # 续写模式
    if args.extend:
        genre = args.genre or config.get('genre', '都市脑洞')
        words_per_chapter = args.words or config.get('words_per_chapter', 2000)

        new_outline, old_outline = extend_outline(
            extend_count=args.extend,
            genre=genre,
            words_per_chapter=words_per_chapter
        )

        print("\n" + "=" * 60)
        print("续写大纲结果：")
        print("=" * 60)
        print(new_outline)

        if args.save:
            save_extended_outline(new_outline, old_outline)

        print("\n" + "=" * 60)
        print("💡 提示：续写后记得更新典据 python scripts/gen_canon.py --update")
        print("=" * 60)
        return

    # 正常生成模式
    # 加载文件
    seed = load_seed()
    world = load_world()
    characters = load_characters()

    # 参数
    genre = args.genre or config.get('genre', '都市脑洞')
    chapter_count = args.chapters or config.get('chapter_count', 30)
    words_per_chapter = args.words or config.get('words_per_chapter', 2000)

    print(f"配置：{genre}，{chapter_count}章 x {words_per_chapter}字", file=sys.stderr)

    # 生成
    result = generate_outline(
        seed, world, characters,
        genre, chapter_count, words_per_chapter
    )

    # 输出
    print("\n" + "=" * 60)
    print("生成结果：")
    print("=" * 60)
    print(result)

    if args.save:
        save_outline(result)

    print("\n" + "=" * 60)
    print("💡 提示：")
    print("  - 接下来可以生成典据：python scripts/gen_canon.py")
    print("  - 或者直接开始写稿：python scripts/draft_chapter.py 1")
    print("=" * 60)


if __name__ == "__main__":
    main()
