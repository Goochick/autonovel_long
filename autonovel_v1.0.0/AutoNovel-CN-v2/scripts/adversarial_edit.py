#!/usr/bin/env python3
# ============================================================
# adversarial_edit.py - 对抗编辑脚本
# 找出章节中的冗余、废话，给出精简建议
# ============================================================

import argparse
import sys
from pathlib import Path

# 添加项目根目录
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from api.api_client import APIClient
from prompts.prompts_cn import (
    SYSTEM_PROMPT_ADVERSARIAL,
    ADVERSARIAL_EDIT_PROMPT
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


def adversarial_edit(chapter_num: int) -> str:
    """对抗编辑"""
    client = APIClient()

    chapter_text = load_chapter(chapter_num)
    word_count = len(chapter_text.replace('\n', '').replace(' ', ''))

    prompt = ADVERSARIAL_EDIT_PROMPT.format(
        chapter_num=chapter_num,
        word_count=word_count
    )

    # 发送章节文本作为上下文
    full_prompt = prompt + "\n\n章节正文：\n" + chapter_text[:10000]

    print(f"正在对抗编辑第 {chapter_num} 章...", file=sys.stderr)

    response = client.call(
        prompt=full_prompt,
        system_prompt=SYSTEM_PROMPT_ADVERSARIAL,
        api_name=DEFAULT_JUDGE_API,
        max_tokens=8000,
        temperature=0.3
    )

    return response


def save_edit(edit_result: str, chapter_num: int):
    """保存编辑结果"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    edit_dir = OUTPUTS_DIR / "edit_logs"
    edit_dir.mkdir(exist_ok=True)

    filepath = edit_dir / f"adversarial_ch_{chapter_num:02d}.md"
    filepath.write_text(edit_result, encoding="utf-8")
    print(f"编辑结果已保存: {filepath}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="对抗编辑")
    parser.add_argument(
        "chapter",
        type=int,
        help="章节编号"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="保存编辑结果"
    )

    args = parser.parse_args()

    # 检查 API
    client = APIClient()
    if not client.is_configured():
        print("❌ API Key 未配置！"); sys.exit(1)

    # 编辑
    result = adversarial_edit(args.chapter)

    # 输出
    print("\n" + "=" * 60)
    print(f"第 {args.chapter} 章对抗编辑结果：")
    print("=" * 60)
    print(result)

    if args.save:
        save_edit(result, args.chapter)

    print("\n" + "=" * 60)
    print("💡 提示：")
    print("  - 根据编辑建议精简章节")
    print("  - 生成修订版：python scripts/gen_revision.py " + str(args.chapter))
    print("=" * 60)


if __name__ == "__main__":
    main()
