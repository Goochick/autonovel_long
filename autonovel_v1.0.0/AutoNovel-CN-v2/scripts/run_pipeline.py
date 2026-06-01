#!/usr/bin/env python3
# ============================================================
# run_pipeline.py - 主 Pipeline 流程脚本
# 整合所有脚本的执行，支持断点续跑
# ============================================================

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

import yaml

from api.api_client import APIClient, TokenBudgetExceeded

# 导入所有脚本模块
from scripts import seed as seed_module
from scripts import gen_world as world_module
from scripts import gen_characters as characters_module
from scripts import gen_outline as outline_module
from scripts import draft_chapter as draft_module
from scripts import evaluate as eval_module
from scripts import gen_revision as revision_module
from scripts import gen_canon as canon_module

# 输出目录
OUTPUTS_DIR = _project_root / "outputs"
STATE_FILE = OUTPUTS_DIR / "pipeline_state.json"


def load_config() -> dict:
    """加载配置"""
    config_file = _project_root / "config.yaml"
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def load_state() -> dict:
    """加载 Pipeline 状态"""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {
        "completed_phases": [],
        "chapter_status": {},
        "last_updated": None
    }


def save_state(state: dict):
    """保存 Pipeline 状态"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    state["last_updated"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def check_api_configured() -> bool:
    """检查 API 是否配置"""
    client = APIClient()
    return client.is_configured()


def run_phase_seed(config: dict) -> bool:
    """运行种子生成阶段"""
    print("\n" + "=" * 60)
    print("📝 阶段 1/8：种子概念生成")
    print("=" * 60)
    
    count = config.get('seed_count', 10)
    result = seed_module.generate_seeds(count)
    
    # 保存
    seed_module.save_seed(result)
    
    print(f"\n✅ 种子已保存到 outputs/seed.md")
    return True


def run_phase_world(config: dict) -> bool:
    """运行世界观生成阶段"""
    print("\n" + "=" * 60)
    print("🌍 阶段 2/8：世界观生成")
    print("=" * 60)
    
    genre = config.get('genre', '都市脑洞')
    result = world_module.generate_world(
        world_module.load_seed(),
        genre
    )
    
    world_module.save_world(result)
    
    print(f"\n✅ 世界观已保存到 outputs/world.md")
    return True


def run_phase_characters(config: dict) -> bool:
    """运行角色生成阶段"""
    print("\n" + "=" * 60)
    print("👥 阶段 3/8：角色生成")
    print("=" * 60)
    
    genre = config.get('genre', '都市脑洞')
    result = characters_module.generate_characters(
        characters_module.load_seed(),
        characters_module.load_world(),
        genre
    )
    
    characters_module.save_characters(result)
    
    print(f"\n✅ 角色设定已保存到 outputs/characters.md")
    return True


def run_phase_outline(config: dict) -> bool:
    """运行大纲生成阶段"""
    print("\n" + "=" * 60)
    print("📋 阶段 4/8：大纲生成")
    print("=" * 60)
    
    chapter_count = config.get('chapter_count', 30)
    words_per_chapter = config.get('words_per_chapter', 2000)
    genre = config.get('genre', '都市脑洞')
    
    result = outline_module.generate_outline(
        outline_module.load_seed(),
        outline_module.load_world(),
        outline_module.load_characters(),
        genre,
        chapter_count,
        words_per_chapter
    )
    
    outline_module.save_outline(result)
    
    print(f"\n✅ 大纲已保存到 outputs/outline.md")
    return True


def run_phase_canon(config: dict) -> bool:
    """运行典据提取阶段"""
    print("\n" + "=" * 60)
    print("📚 阶段 5/8：典据提取")
    print("=" * 60)
    
    result = canon_module.generate_canon()
    canon_module.save_canon(result)
    
    print(f"\n✅ 典据已保存到 outputs/canon.md")
    return True


def run_phase_draft(config: dict, start_chapter: int = 1, end_chapter: int = None) -> dict:
    """运行章节撰写阶段"""
    print("\n" + "=" * 60)
    print("✍️  阶段 6/8：章节撰写")
    print("=" * 60)
    
    if end_chapter is None:
        end_chapter = config.get('chapter_count', 30)
    
    chapter_count = config.get('chapter_count', 30)
    words_per_chapter = config.get('words_per_chapter', 2000)
    shuang_per_chapter = config.get('shuang_per_chapter', 3)
    
    status = {}
    
    for ch in range(start_chapter, min(end_chapter, chapter_count) + 1):
        print(f"\n--- 撰写第 {ch} 章 ---")
        
        result = draft_module.draft_chapter(
            ch,
            words_per_chapter=words_per_chapter,
            shuang_per_chapter=shuang_per_chapter
        )
        
        draft_module.save_chapter(ch, result)
        status[ch] = "drafted"
        
        print(f"✅ 第 {ch} 章已完成")
    
    return status


def run_phase_evaluate(config: dict, start_chapter: int = 1, end_chapter: int = None) -> dict:
    """运行评估阶段"""
    print("\n" + "=" * 60)
    print("🔍 阶段 7/8：章节评估")
    print("=" * 60)
    
    if end_chapter is None:
        end_chapter = config.get('chapter_count', 30)
    
    min_score = config.get('min_chapter_score', 6.0)
    auto_revise = config.get('auto_revise', True)
    max_rounds = config.get('max_revision_rounds', 3)
    
    status = {}
    
    for ch in range(start_chapter, end_chapter + 1):
        print(f"\n--- 评估第 {ch} 章 ---")
        
        # 评估
        result = eval_module.evaluate_chapter(ch)
        score = result.get('chapter_score', 0)
        
        # 检查是否通过
        passed = score >= min_score
        
        status[ch] = {
            "score": score,
            "passed": passed,
            "recommendation": result.get('recommendation', 'unknown')
        }
        
        if passed:
            print(f"✅ 第 {ch} 章评分 {score}/10，通过")
        else:
            print(f"⚠️  第 {ch} 章评分 {score}/10，未通过")
            
            # 自动修订
            if auto_revise:
                for round_num in range(1, max_rounds + 1):
                    # 检查单章修订预算
                    client = APIClient()
                    phase_tokens = client._per_phase_tokens.get(f"revision_ch{ch}", {"input": 0, "output": 0})
                    revision_used = phase_tokens["input"] + phase_tokens["output"]
                    if client._per_chapter_revision_limit and revision_used > client._per_chapter_revision_limit:
                        print(f"   ⚠️  第 {ch} 章修订 token 超限 ({revision_used:,} > {client._per_chapter_revision_limit:,})，停止修订")
                        break
                    
                    print(f"   正在修订（第 {round_num} 轮）...")
                    client.set_phase(f"revision_ch{ch}")
                    
                    try:
                        # 生成修订版
                        revision_module.generate_revision(ch)
                        revision_module.save_revision(ch, revision_module.generate_revision(ch), round_num)
                        
                        # 重新评估
                        client.set_phase(f"eval_ch{ch}")
                        result = eval_module.evaluate_chapter(ch)
                        score = result.get('chapter_score', 0)
                        status[ch]['score'] = score
                        
                        if score >= min_score:
                            print(f"   ✅ 修订后评分 {score}/10，通过")
                            break
                        elif round_num < max_rounds:
                            print(f"   ⚠️  修订后评分 {score}/10，继续...")
                    except TokenBudgetExceeded as e:
                        print(f"   🛑 修订中断: {e}")
                        break
                else:
                    print(f"   ❌ 超过最大修订轮数，放弃")
    
    return status


def run_full_pipeline(
    start_phase: int = 1,
    start_chapter: int = 1,
    end_chapter: int = None
) -> dict:
    """运行完整 Pipeline"""
    
    # 检查 API
    if not check_api_configured():
        print("=" * 60)
        print("❌ 错误：API Key 未配置！")
        print("=" * 60)
        print("请复制 .env.example 为 .env，并填入你的 API Key")
        print("=" * 60)
        sys.exit(1)
    
    config = load_config()
    state = load_state()
    
    if end_chapter is None:
        end_chapter = config.get('chapter_count', 30)
    
    results = {
        "phases": {},
        "chapters": {}
    }
    
    # 阶段 1：种子
    if start_phase <= 1:
        run_phase_seed(config)
        state["completed_phases"].append("seed")
        results["phases"]["seed"] = "completed"
    
    # 阶段 2：世界观
    if start_phase <= 2:
        run_phase_world(config)
        state["completed_phases"].append("world")
        results["phases"]["world"] = "completed"
    
    # 阶段 3：角色
    if start_phase <= 3:
        run_phase_characters(config)
        state["completed_phases"].append("characters")
        results["phases"]["characters"] = "completed"
    
    # 阶段 4：大纲
    if start_phase <= 4:
        run_phase_outline(config)
        state["completed_phases"].append("outline")
        results["phases"]["outline"] = "completed"
    
    # 阶段 5：典据
    if start_phase <= 5:
        run_phase_canon(config)
        state["completed_phases"].append("canon")
        results["phases"]["canon"] = "completed"
    
    # 阶段 6：撰写
    if start_phase <= 6:
        chapter_status = run_phase_draft(config, start_chapter, end_chapter)
        state["chapter_status"].update(chapter_status)
        results["chapters"] = chapter_status
    
    # 阶段 7：评估
    if start_phase <= 7:
        eval_status = run_phase_evaluate(config, start_chapter, end_chapter)
        for ch, status in eval_status.items():
            if ch in state["chapter_status"]:
                state["chapter_status"][ch].update(status)
        results["chapters"].update(eval_status)
    
    # 保存状态
    save_state(state)
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 Pipeline 执行完成")
    print("=" * 60)
    
    passed = sum(1 for ch in results.get("chapters", {}).values() 
                 if isinstance(ch, dict) and ch.get("passed"))
    total = len(results.get("chapters", {}))
    
    print(f"完成章节：{total} 章")
    print(f"通过评估：{passed} 章")
    print(f"状态已保存：{STATE_FILE}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="运行 AutoNovel-CN Pipeline")
    parser.add_argument(
        "--phase", "-p",
        type=int,
        default=1,
        help="从哪个阶段开始（1-7，默认1）"
    )
    parser.add_argument(
        "--start-chapter", "-s",
        type=int,
        default=1,
        help="从第几章开始写（默认1）"
    )
    parser.add_argument(
        "--end-chapter", "-e",
        type=int,
        default=None,
        help="到第几章结束（默认从config.yaml读取）"
    )
    parser.add_argument(
        "--step",
        type=str,
        choices=["seed", "world", "characters", "outline", "canon", "draft", "evaluate"],
        help="运行单个步骤"
    )
    
    args = parser.parse_args()
    
    config = load_config()
    
    if args.step:
        # 运行单个步骤
        if not check_api_configured():
            print("❌ API Key 未配置！"); sys.exit(1)
        
        step_map = {
            "seed": (run_phase_seed, 1),
            "world": (run_phase_world, 2),
            "characters": (run_phase_characters, 3),
            "outline": (run_phase_outline, 4),
            "canon": (run_phase_canon, 5),
        }
        
        if args.step in step_map:
            func, _ = step_map[args.step]
            func(config)
        elif args.step == "draft":
            run_phase_draft(config, args.start_chapter, args.end_chapter)
        elif args.step == "evaluate":
            run_phase_evaluate(config, args.start_chapter, args.end_chapter)
    
    else:
        # 运行完整 pipeline
        run_full_pipeline(
            start_phase=args.phase,
            start_chapter=args.start_chapter,
            end_chapter=args.end_chapter
        )


if __name__ == "__main__":
    main()
