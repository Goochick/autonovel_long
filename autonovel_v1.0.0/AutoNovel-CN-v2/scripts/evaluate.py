#!/usr/bin/env python3
# ============================================================
# evaluate.py - 评估系统脚本
# 支持 Foundation 评估（策划阶段）和 Chapter 评估（写作阶段）
# ============================================================

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

import yaml

from api.api_client import APIClient
from prompts.prompts_cn import (
    SYSTEM_PROMPT_JUDGE,
    FOUNDATION_PROMPT,
    CHAPTER_PROMPT,
    FULL_NOVEL_PROMPT,
    TIER1_BANNED_WORDS,
    TIER2_SUSPICIOUS_WORDS,
    TIER3_FILLER_PHRASES
)
from config import DEFAULT_JUDGE_API

# 输出目录
OUTPUTS_DIR = _project_root / "outputs"
CHAPTERS_DIR = OUTPUTS_DIR / "chapters"
EVAL_LOG_DIR = OUTPUTS_DIR / "eval_logs"


def load_config() -> dict:
    """加载配置"""
    config_file = _project_root / "config.yaml"
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def mechanical_check(text: str) -> dict:
    """机械检测（无需 LLM）"""
    violations = []
    warnings = []
    
    text_lower = text.lower()
    
    # Tier 1 检测
    for word in TIER1_BANNED_WORDS:
        if word in text:
            violations.append(f"Tier1禁用词: '{word}'")
    
    # Tier 2 检测
    for word in TIER2_SUSPICIOUS_WORDS:
        if word in text:
            warnings.append(f"Tier2可疑词: '{word}'")
    
    # Tier 3 检测
    for phrase in TIER3_FILLER_PHRASES:
        if phrase in text_lower:
            warnings.append(f"Tier3填充词: '{phrase}'")
    
    # 句式检测
    # 检测 "X不由得Y" 句式
    if re.search(r'[他她]不由得', text):
        count = len(re.findall(r'[他她]不由得', text))
        warnings.append(f"不由得句式出现 {count} 次")
    
    # 检测连续排比
    if re.search(r'[他她][^。\n]+[、，][他她][^。\n]+[、，][他她]', text):
        warnings.append("检测到疑似三连排比")
    
    return {
        "violations": violations,
        "warnings": warnings,
        "tier1_count": len(violations),
        "tier2_count": len(warnings)
    }


def evaluate_foundation() -> dict:
    """评估策划文档"""
    client = APIClient()
    
    # 加载所有策划文档
    world = _load_file(OUTPUTS_DIR / "world.md", "world.md")
    characters = _load_file(OUTPUTS_DIR / "characters.md", "characters.md")
    outline = _load_file(OUTPUTS_DIR / "outline.md", "outline.md")
    canon = _load_file(OUTPUTS_DIR / "canon.md", "canon.md")
    
    config = load_config()
    genre = config.get('genre', '都市脑洞')
    
    prompt = FOUNDATION_PROMPT.format(
        world=world or "(未生成)",
        characters=characters or "(未生成)",
        outline=outline or "(未生成)",
        canon=canon or "(未生成)",
        genre=genre
    )
    
    print("正在评估策划文档...", file=sys.stderr)
    
    response = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_JUDGE,
        api_name=DEFAULT_JUDGE_API,
        max_tokens=8000,
        temperature=0.3
    )
    
    return _parse_json_response(response)


def evaluate_chapter(chapter_num: int) -> dict:
    """评估单章"""
    client = APIClient()
    
    # 加载章节
    chapter_file = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    if not chapter_file.exists():
        print(f"❌ 章节文件不存在: {chapter_file}")
        sys.exit(1)
    
    chapter_text = chapter_file.read_text(encoding="utf-8")
    
    # 加载大纲（获取本章大纲）
    outline = _load_file(OUTPUTS_DIR / "outline.md", "outline.md")
    chapter_outline = _extract_chapter_outline(outline, chapter_num) if outline else "(无大纲)"
    
    # 加载上章结尾
    prev_tail = _get_prev_chapter_ending(chapter_num)
    
    # 机械检测
    mech = mechanical_check(chapter_text)
    
    config = load_config()
    
    # LLM 评估
    prompt = CHAPTER_PROMPT.format(
        chapter_num=chapter_num,
        chapter_text=chapter_text[:12000],  # 截断避免超长
        chapter_outline=chapter_outline[:1000],
        prev_chapter_tail=prev_tail[:500],
        voice="参考角色设定和世界观"
    )
    
    print(f"正在评估第 {chapter_num} 章...", file=sys.stderr)
    
    llm_result = client.call(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_JUDGE,
        api_name=DEFAULT_JUDGE_API,
        max_tokens=8000,
        temperature=0.3
    )
    
    parsed = _parse_json_response(llm_result)
    
    # 合并结果
    result = {
        **parsed,
        "mechanical_check": mech,
        "chapter_num": chapter_num,
        "word_count": len(chapter_text)
    }
    
    return result


def _load_file(filepath: Path, name: str) -> str:
    """安全加载文件"""
    if not filepath.exists():
        print(f"⚠ {name} 不存在，跳过", file=sys.stderr)
        return ""
    return filepath.read_text(encoding="utf-8")


def _extract_chapter_outline(outline: str, chapter_num: int) -> str:
    """提取章节大纲"""
    pattern = rf'(?:第\s*{chapter_num}\s*章)[^\n]*\n(.*?)(?=(?:第\s*{chapter_num + 1}\s*章)|$)'
    match = re.search(pattern, outline, re.DOTALL)
    return match.group(1).strip() if match else ""


def _get_prev_chapter_ending(chapter_num: int) -> str:
    """获取上章结尾"""
    if chapter_num <= 1:
        return ""
    prev_file = CHAPTERS_DIR / f"ch_{chapter_num - 1:02d}.md"
    if prev_file.exists():
        text = prev_file.read_text(encoding="utf-8")
        return text[-1000:] if len(text) > 1000 else text
    return ""


def _parse_json_response(response: str) -> dict:
    """解析 JSON 响应"""
    # 尝试提取 JSON 块
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # 返回原始文本
    return {
        "raw_response": response,
        "parse_error": True
    }


def save_evaluation(result: dict, phase: str, identifier: str = ""):
    """保存评估结果"""
    EVAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"eval_{phase}_{identifier or 'unknown'}_{timestamp}.json"
    filepath = EVAL_LOG_DIR / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"评估结果已保存: {filepath}", file=sys.stderr)


def print_evaluation_result(result: dict, phase: str):
    """打印评估结果"""
    print("\n" + "=" * 60)
    print(f"📊 {phase} 评估结果")
    print("=" * 60)
    
    if phase == "foundation":
        # 策划评估结果
        score = result.get("foundation_score", "N/A")
        print(f"\n总体得分：{score}/10")
        
        dimensions = [
            ("world_score", "世界观完整性"),
            ("character_score", "角色吸引力"),
            ("shuang_structure_score", "爽文结构"),
            ("consistency_score", "一致性"),
            ("genre_fit_score", "品类适配")
        ]
        
        for key, name in dimensions:
            if key in result:
                dim = result[key]
                s = dim.get("score", "N/A") if isinstance(dim, dict) else "N/A"
                gap = dim.get("gap", "")[:50] if isinstance(dim, dict) else ""
                print(f"  {name}：{s}/10")
                if gap:
                    print(f"    问题：{gap}...")
        
        can_proceed = result.get("can_proceed", False)
        print(f"\n{'✅ 可以继续' if can_proceed else '❌ 需要修改'}")
    
    elif phase == "chapter":
        # 章节评估结果
        score = result.get("chapter_score", "N/A")
        print(f"\n章节得分：{score}/10")
        
        dimensions = [
            ("shuang_density", "爽点密度"),
            ("hook_quality", "钩子质量"),
            ("immersion", "代入感"),
            ("anti_slop", "反AI味"),
            ("continuity", "连续性")
        ]
        
        for key, name in dimensions:
            if key in result:
                dim = result[key]
                s = dim.get("score", "N/A") if isinstance(dim, dict) else "N/A"
                print(f"  {name}：{s}/10")
        
        # 机械检测结果
        mech = result.get("mechanical_check", {})
        if mech.get("tier1_count", 0) > 0:
            print(f"\n⚠️  禁用词警告：{mech['tier1_count']} 处")
            for v in mech.get("violations", [])[:5]:
                print(f"    - {v}")
        
        rec = result.get("recommendation", "unknown")
        print(f"\n建议：{'✅ 接受' if rec == 'accept' else '🔄 修订' if rec == 'revise' else '❌ 重写'}")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="评估小说策划/章节")
    parser.add_argument(
        "--phase",
        type=str,
        choices=["foundation", "chapter", "full"],
        help="评估阶段"
    )
    parser.add_argument(
        "--chapter", "-c",
        type=int,
        default=None,
        help="评估章节编号"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="保存评估结果"
    )
    
    args = parser.parse_args()
    
    # 检查 API
    client = APIClient()
    if not client.is_configured():
        print("❌ API Key 未配置！"); sys.exit(1)
    
    # 确定评估类型
    phase = args.phase
    if not phase:
        if args.chapter:
            phase = "chapter"
        else:
            print("请指定 --phase=foundation 或 --chapter=数字")
            sys.exit(1)
    
    # 执行评估
    if phase == "foundation":
        result = evaluate_foundation()
        print_evaluation_result(result, "foundation")
        if args.save:
            save_evaluation(result, "foundation")
    
    elif phase == "chapter":
        if not args.chapter:
            print("请指定章节编号：--chapter=1")
            sys.exit(1)
        result = evaluate_chapter(args.chapter)
        print_evaluation_result(result, "chapter")
        if args.save:
            save_evaluation(result, "chapter", f"ch_{args.chapter:02d}")
    
    elif phase == "full":
        print("全书评估功能开发中...")
        sys.exit(1)


if __name__ == "__main__":
    main()
