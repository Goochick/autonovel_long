#!/usr/bin/env python3
# ============================================================
# draft_chapter.py - 章节撰写脚本（核心）
# 生成单章正文，支持2000字/章的网文节奏
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
    SYSTEM_PROMPT_DRAFT,
    DRAFT_CHAPTER_PROMPT
)
from config import DEFAULT_WRITER_API

# 输出目录
OUTPUTS_DIR = _project_root / "outputs"
CHAPTERS_DIR = OUTPUTS_DIR / "chapters"


def load_seed() -> str:
    """
    加载种子

    注意：draft_chapter.py 在撰写正文时不加载 mystery.md
    以防止核心悬疑泄露给写手 AI
    """
    f = OUTPUTS_DIR / "seed.md"
    if not f.exists():
        print("❌ seed.md 不存在！"); sys.exit(1)
    return f.read_text(encoding="utf-8")


def load_world() -> str:
    """加载世界观"""
    f = OUTPUTS_DIR / "world.md"
    if not f.exists():
        print("❌ world.md 不存在！"); sys.exit(1)
    return f.read_text(encoding="utf-8")


def load_characters() -> str:
    """加载角色"""
    f = OUTPUTS_DIR / "characters.md"
    if not f.exists():
        print("❌ characters.md 不存在！"); sys.exit(1)
    return f.read_text(encoding="utf-8")


def load_outline() -> str:
    """加载大纲"""
    f = OUTPUTS_DIR / "outline.md"
    if not f.exists():
        print("❌ outline.md 不存在！"); sys.exit(1)
    return f.read_text(encoding="utf-8")


def load_config() -> dict:
    """加载配置"""
    config_file = _project_root / "config.yaml"
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def extract_chapter_outline(outline_text: str, chapter_num: int) -> str:
    """从大纲中提取指定章节的详情"""
    # 尝试匹配 "第X章" 或 "第 X 章" 格式
    patterns = [
        rf'(?:第\s*{chapter_num}\s*章)[^\n]*\n(.*?)(?=(?:第\s*{chapter_num + 1}\s*章)|$)',
        rf'(?:###\s*第\s*{chapter_num}\s*章)[^\n]*\n(.*?)(?=(?:###\s*第\s*{chapter_num + 1}\s*章)|$)',
    ]

    for pattern in patterns:
        match = re.search(pattern, outline_text, re.DOTALL)
        if match:
            content = match.group(1).strip()
            # 限制长度，避免上下文过长
            if len(content) > 2000:
                content = content[:2000] + "\n..."
            return content

    return f"第{chapter_num}章（请参考完整大纲）"


def extract_title(outline_text: str, chapter_num: int) -> str:
    """从大纲提取章节标题"""
    pattern = rf'(?:第\s*{chapter_num}\s*章)[：:]\s*([^\n]+)'
    match = re.search(pattern, outline_text)
    if match:
        return match.group(1).strip()

    # 备用：尝试提取弧线信息
    arc_match = re.search(rf'弧\s*名\s*称[：:]\s*([^\n]+)', outline_text)
    arc_name = arc_match.group(1).strip() if arc_match else "待定"

    return f"第{chapter_num}章"


def get_prev_chapter_ending(chapter_num: int) -> str:
    """获取上章结尾"""
    if chapter_num <= 1:
        return "(开篇章节 - 无上章衔接)"

    prev_file = CHAPTERS_DIR / f"ch_{chapter_num - 1:02d}.md"
    if not prev_file.exists():
        return f"(第{chapter_num - 1}章文件不存在，跳过衔接)"

    prev_text = prev_file.read_text(encoding="utf-8")
    # 取最后1500字作为衔接上下文
    return prev_text[-1500:] if len(prev_text) > 1500 else prev_text


def draft_chapter(
    chapter_num: int,
    genre: str = None,
    words_per_chapter: int = 2000,
    shuang_per_chapter: int = 3
) -> str:
    """撰写单章"""
    client = APIClient()

    config = load_config()
    if genre is None:
        genre = config.get('genre', '都市脑洞')
        words_per_chapter = config.get('words_per_chapter', 2000)
        shuang_per_chapter = config.get('shuang_per_chapter', 3)

    # 加载素材
    seed = load_seed()
    world = load_world()
    characters = load_characters()
    outline = load_outline()

    # 加载典据（装备/技能/关系追踪）
    canon_file = OUTPUTS_DIR / "canon.md"
    canon = canon_file.read_text(encoding="utf-8")[:3000] if canon_file.exists() else "(未生成典据，请先运行 gen_canon.py)"

    # 提取本章大纲
    chapter_outline = extract_chapter_outline(outline, chapter_num)
    title = extract_title(outline, chapter_num)
    prev_ending = get_prev_chapter_ending(chapter_num)

    # 生成爽点分布建议
    shuang_positions = _generate_shuang_positions(chapter_num, shuang_per_chapter, words_per_chapter)

    # 构建写作风格说明（简化版，避免过长）
    voice = f"""
    风格要求：
    1. 开篇300字内出钩子
    2. 每800字一个小爽点
    3. 章末留钩子
    4. 禁止：缓缓/微微/竟然/轻声柔声等AI味词汇
    5. 对话口语化
    """

    prompt = DRAFT_CHAPTER_PROMPT.format(
        chapter_num=chapter_num,
        title=title,
        genre=genre,
        arc_name="（参考大纲）",
        voice=voice,
        world=world[:3000] + ("..." if len(world) > 3000 else ""),
        characters=characters[:2000] + ("..." if len(characters) > 2000 else ""),
        canon=canon,
        chapter_outline=chapter_outline,
        prev_chapter_ending=prev_ending,
        next_chapter_intro="（参考大纲中的下章预告）",
        min_shuang_points=shuang_per_chapter,
        shuang_points_positions=shuang_positions,
        target_words=words_per_chapter
    )

    print(f"正在撰写第 {chapter_num} 章（目标 {words_per_chapter} 字）...", file=sys.stderr)

    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_DRAFT,
        api_name=DEFAULT_WRITER_API,
        max_tokens=16000,
        temperature=0.85
    )

    return response


def _generate_shuang_positions(chapter_num: int, count: int, total_words: int) -> str:
    """生成爽点分布建议"""
    positions = []
    segment_size = total_words // (count + 1)

    for i in range(count):
        pos = segment_size * (i + 1)
        positions.append(f"第{i + 1}个爽点：约第{pos}字处")

    return "\n".join(positions)


def save_chapter(chapter_num: int, text: str):
    """保存章节"""
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    filepath = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    filepath.write_text(text, encoding="utf-8")

    word_count = len(text.replace('\n', '').replace(' ', ''))
    print(f"已保存第 {chapter_num} 章到: {filepath}", file=sys.stderr)
    print(f"字数：约 {word_count} 字", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="撰写小说章节")
    parser.add_argument(
        "chapter",
        type=int,
        nargs="?",
        default=1,
        help="章节编号（默认第1章）"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="保存章节文件"
    )
    parser.add_argument(
        "--words", "-w",
        type=int,
        default=None,
        help="目标字数"
    )

    args = parser.parse_args()

    # 检查 API
    client = APIClient()
    if not client.is_configured():
        print("❌ API Key 未配置！"); sys.exit(1)

    config = load_config()
    words = args.words or config.get('words_per_chapter', 2000)
    shuang = config.get('shuang_per_chapter', 3)

    # 撰写
    result = draft_chapter(args.chapter, words_per_chapter=words, shuang_per_chapter=shuang)

    # 输出
    print("\n" + "=" * 60)
    print(f"第 {args.chapter} 章草稿：")
    print("=" * 60)
    print(result)

    if args.save:
        save_chapter(args.chapter, result)

    print("\n" + "=" * 60)
    print("💡 提示：")
    print(f"  - 评估本章：python scripts/evaluate.py --chapter={args.chapter}")
    if args.chapter > 1:
        print(f"  - 写下一章：python scripts/draft_chapter.py {args.chapter + 1} --save")
    print("=" * 60)


if __name__ == "__main__":
    main()
