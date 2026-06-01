#!/usr/bin/env python3
# ============================================================
# review.py - 审阅脚本
# 深度审阅章节，给出具体修改建议
# ============================================================

import argparse
import sys
from pathlib import Path

# 添加项目根目录
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from api.api_client import APIClient
from prompts.prompts_cn import (
    SYSTEM_PROMPT_REVIEW,
    REVIEW_PROMPT
)
from config import DEFAULT_JUDGE_API

# 输出目录
OUTPUTS_DIR = _project_root / "outputs"
CHAPTERS_DIR = OUTPUTS_DIR / "chapters"


def load_chapter(chapter_num: int) -> str:
    """加载章节"""
    chapter_file = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    if not chapter_file.exists():
        print(f"❌ 章节不存在: {chapter_file}")
        sys.exit(1)
    return chapter_file.read_text(encoding="utf-8")


def get_title() -> str:
    """获取书名"""
    # 尝试从大纲获取
    outline_file = OUTPUTS_DIR / "outline.md"
    if outline_file.exists():
        first_line = outline_file.read_text(encoding="utf-8").split("\n")[0]
        if first_line.startswith("#"):
            return first_line.lstrip("# ").strip()

    # 尝试从种子获取
    seed_file = OUTPUTS_DIR / "seed.md"
    if seed_file.exists():
        first_line = seed_file.read_text(encoding="utf-8").split("\n")[0]
        if len(first_line) < 50:
            return first_line

    return "未命名小说"


def review_chapter(chapter_num: int) -> str:
    """审阅章节"""
    client = APIClient()

    chapter_text = load_chapter(chapter_num)
    title = get_title()

    prompt = REVIEW_PROMPT.format(
        title=title,
        manuscript=chapter_text[:15000]  # 截断
    )

    print(f"正在审阅第 {chapter_num} 章...", file=sys.stderr)

    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_REVIEW,
        api_name=DEFAULT_JUDGE_API,
        max_tokens=8000,
        temperature=0.4
    )

    return response


def save_review(review_text: str, chapter_num: int):
    """保存审阅结果"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    review_dir = OUTPUTS_DIR / "reviews"
    review_dir.mkdir(exist_ok=True)

    filepath = review_dir / f"review_ch_{chapter_num:02d}.txt"
    filepath.write_text(review_text, encoding="utf-8")
    print(f"审阅结果已保存: {filepath}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="审阅小说章节")
    parser.add_argument(
        "chapter",
        type=int,
        nargs="?",
        default=1,
        help="章节编号"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="保存审阅结果"
    )

    args = parser.parse_args()

    # 检查 API
    client = APIClient()
    if not client.is_configured():
        print("❌ API Key 未配置！"); sys.exit(1)

    # 审阅
    result = review_chapter(args.chapter)

    # 输出
    print("\n" + "=" * 60)
    print(f"第 {args.chapter} 章审阅结果：")
    print("=" * 60)
    print(result)

    if args.save:
        save_review(result, args.chapter)

    print("\n" + "=" * 60)
    print("💡 提示：")
    print(f"  - 根据审阅意见修改章节")
    print(f"  - 或直接生成修订版：python scripts/gen_revision.py {args.chapter}")
    print("=" * 60)


if __name__ == "__main__":
    main()
