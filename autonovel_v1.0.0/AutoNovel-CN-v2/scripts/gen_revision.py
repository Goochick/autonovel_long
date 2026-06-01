#!/usr/bin/env python3
# ============================================================
# gen_revision.py - 修订脚本
# 根据审阅意见修订章节
# ============================================================

import argparse
import re
import sys
from pathlib import Path

# 添加项目根目录
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from api.api_client import APIClient
from prompts.prompts_cn import (
    SYSTEM_PROMPT_REVISION,
    REVISION_PROMPT
)
from config import DEFAULT_WRITER_API

# 输出目录
OUTPUTS_DIR = _project_root / "outputs"
CHAPTERS_DIR = OUTPUTS_DIR / "chapters"
REVIEWS_DIR = OUTPUTS_DIR / "reviews"


def load_chapter(chapter_num: int) -> str:
    """加载章节"""
    chapter_file = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    if not chapter_file.exists():
        print(f"❌ 章节不存在: {chapter_file}")
        sys.exit(1)
    return chapter_file.read_text(encoding="utf-8")


def load_review(chapter_num: int) -> str:
    """加载审阅意见"""
    review_file = REVIEWS_DIR / f"review_ch_{chapter_num:02d}.txt"
    if not review_file.exists():
        # 尝试作为brief文件
        brief_file = _project_root / f"{chapter_num}_revision_brief.md"
        if brief_file.exists():
            return brief_file.read_text(encoding="utf-8")
        print(f"⚠️ 审阅文件不存在: {review_file}")
        print("请先运行：python scripts/review.py " + str(chapter_num))
        return ""
    return review_file.read_text(encoding="utf-8")


def load_world() -> str:
    """加载世界观"""
    f = OUTPUTS_DIR / "world.md"
    return f.read_text(encoding="utf-8") if f.exists() else "(无)"


def load_characters() -> str:
    """加载角色"""
    f = OUTPUTS_DIR / "characters.md"
    return f.read_text(encoding="utf-8") if f.exists() else "(无)"


def get_prev_chapter_ending(chapter_num: int) -> str:
    """获取上章结尾"""
    if chapter_num <= 1:
        return "(开篇)"
    prev_file = CHAPTERS_DIR / f"ch_{chapter_num - 1:02d}.md"
    if prev_file.exists():
        text = prev_file.read_text(encoding="utf-8")
        return text[-800:] if len(text) > 800 else text
    return ""


def get_next_chapter_head(chapter_num: int) -> str:
    """获取下章开头"""
    next_file = CHAPTERS_DIR / f"ch_{chapter_num + 1:02d}.md"
    if next_file.exists():
        text = next_file.read_text(encoding="utf-8")
        return text[:800] if len(text) > 800 else text
    return "(完结)"


def generate_revision(chapter_num: int, revision_brief: str = None) -> str:
    """生成修订版"""
    client = APIClient()
    
    if not revision_brief:
        revision_brief = load_review(chapter_num)
    
    if not revision_brief:
        print("❌ 没有修订意见！")
        sys.exit(1)
    
    old_text = load_chapter(chapter_num)
    world = load_world()
    characters = load_characters()
    prev_tail = get_prev_chapter_ending(chapter_num)
    next_head = get_next_chapter_head(chapter_num)
    
    # 简化风格说明
    voice = """
    风格要求：
    1. 保持原有优秀内容
    2. 修复所有指出的问题
    3. 不引入新问题
    4. 禁止：缓缓/微微/竟然/不由得 等AI味词汇
    """
    
    prompt = REVISION_PROMPT.format(
        chapter_num=chapter_num,
        revision_brief=revision_brief[:5000],
        voice=voice,
        characters=characters[:1500],
        world=world[:2000],
        prev_tail=prev_tail,
        next_head=next_head,
        old_text=old_text[:10000]
    )
    
    print(f"正在修订第 {chapter_num} 章...", file=sys.stderr)
    
    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_REVISION,
        api_name=DEFAULT_WRITER_API,
        max_tokens=16000,
        temperature=0.8
    )
    
    return response


def save_revision(chapter_num: int, text: str, round_num: int = 1):
    """保存修订版"""
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 备份原版
    original = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    if original.exists() and round_num == 1:
        backup = CHAPTERS_DIR / f"ch_{chapter_num:02d}_original.md"
        original.rename(backup)
        print(f"已备份原版到: {backup}", file=sys.stderr)
    
    filepath = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    filepath.write_text(text, encoding="utf-8")
    
    word_count = len(text.replace('\n', '').replace(' ', ''))
    print(f"已保存修订版到: {filepath}", file=sys.stderr)
    print(f"字数：约 {word_count} 字", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="修订小说章节")
    parser.add_argument(
        "chapter",
        type=int,
        help="章节编号"
    )
    parser.add_argument(
        "--brief", "-b",
        type=str,
        default=None,
        help="修订brief文件路径"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="保存修订结果"
    )
    parser.add_argument(
        "--round", "-r",
        type=int,
        default=1,
        help="修订轮次（默认1）"
    )
    
    args = parser.parse_args()
    
    # 检查 API
    client = APIClient()
    if not client.is_configured():
        print("❌ API Key 未配置！"); sys.exit(1)
    
    # 加载brief
    brief = ""
    if args.brief:
        brief_file = Path(args.brief)
        if brief_file.exists():
            brief = brief_file.read_text(encoding="utf-8")
        else:
            brief = args.brief  # 直接使用字符串
    
    # 生成修订
    result = generate_revision(args.chapter, brief)
    
    # 输出
    print("\n" + "=" * 60)
    print(f"第 {args.chapter} 章修订版：")
    print("=" * 60)
    print(result)
    
    if args.save:
        save_revision(args.chapter, result, args.round)
    
    print("\n" + "=" * 60)
    print("💡 提示：")
    print(f"  - 评估修订后章节：python scripts/evaluate.py --chapter={args.chapter}")
    print("=" * 60)


if __name__ == "__main__":
    main()
