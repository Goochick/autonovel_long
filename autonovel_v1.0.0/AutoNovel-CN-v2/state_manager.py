#!/usr/bin/env python3
# ============================================================
# state_manager.py - 项目状态机
# 驱动阶段流转、断点续传、重试降级
# 版本: v0.8.0 | 更新: 2026-05-23 10:18
# ============================================================

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

_project_root = Path(__file__).resolve().parent
STATE_FILE = _project_root / "outputs" / "state.json"

# ============================================================
# 常量
# ============================================================

PHASES = [
    "seed",           # 种子生成
    "world",          # 世界观构建
    "characters",     # 角色设定
    "voice",          # 语声档案
    "outline",        # 主线大纲（含分卷）
    "mystery",        # 核心悬疑
    "canon_init",     # 初始典据提取
    "foundation",     # 基础构建评估循环
    "drafting",       # 初稿编写（按卷按章）
    "complete",       # 全部完成
]

# Foundation 放行门槛
FOUNDATION_PASS_SCORE = 7.5
LORE_PASS_SCORE = 7.0
MAX_FOUNDATION_ROUNDS = 5

# 修订重试上限
MAX_CHAPTER_RETRIES = 3

# Token 安全阈值
MAX_CONTEXT_CHARS = 20000   # 单次读取文件上限（约15k tokens）
MAX_CHAPTERS_PER_EVAL_BATCH = 5  # 评估时分批，每批5章


# ============================================================
# 核心状态管理
# ============================================================

def load_state() -> Dict[str, Any]:
    """加载当前状态"""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            # 向前兼容：确保所有字段存在
            defaults = _default_state()
            for k, v in defaults.items():
                if k not in data:
                    data[k] = v
            # 确保 sub_state 完整
            if "sub_state" not in data:
                data["sub_state"] = defaults["sub_state"]
            return data
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    return _default_state()


def save_state(state: Dict[str, Any]):
    """保存状态"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _default_state() -> Dict[str, Any]:
    """默认初始状态"""
    return {
        "phase": "seed",
        "chapter_count": 30,
        "words_per_chapter": 2000,
        # 子状态：精确追踪
        "sub_state": {
            "current_volume": 0,        # 当前写到第几卷
            "current_chapter": 0,       # 当前章（全局编号）
            "current_draft_round": 0,   # 当前章节的第几稿
            "volume_status": {},        # { "1": {"status": "drafting", "chapters_done": 6, "chapters_total": 30}, ... }
        },
        # Foundation 评估
        "foundation_rounds": 0,
        "foundation_score": 0,
        "lore_score": 0,
        "last_weak_dimension": "",
        # 重试降级
        "retry_count": {},           # { "ch_7": 3 } 记录每章重试了几轮
        "force_passed": [],          # ["ch_7", "ch_15"] 降级放行的章节
        # 逻辑欠债
        "logic_debts": [],
        # 典据版本
        "canon_version": 0,
        # 历史
        "history": [],
        "last_updated": None,
    }


# ============================================================
# 阶段推进
# ============================================================

def advance_phase(state: Dict[str, Any], to_phase: str, reason: str = "") -> Dict[str, Any]:
    """推进到指定阶段"""
    old_phase = state["phase"]
    state["phase"] = to_phase
    state["history"].append({
        "from": old_phase,
        "to": to_phase,
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
    })
    save_state(state)
    return state


def can_proceed_to_draft(state: Dict[str, Any]) -> bool:
    """判断是否可以进入draft阶段"""
    return (
        state.get("foundation_score", 0) >= FOUNDATION_PASS_SCORE
        and state.get("lore_score", 0) >= LORE_PASS_SCORE
    )


def foundation_round_needed(state: Dict[str, Any]) -> bool:
    """是否需要继续foundation循环"""
    return (
        state.get("foundation_rounds", 0) < MAX_FOUNDATION_ROUNDS
        and not can_proceed_to_draft(state)
    )


def record_foundation_eval(state: Dict[str, Any], foundation_score: float,
                           lore_score: float, weakest: str,
                           can_proceed: bool) -> Dict[str, Any]:
    """记录foundation评估结果"""
    state["foundation_score"] = foundation_score
    state["lore_score"] = lore_score
    state["last_weak_dimension"] = weakest
    state["foundation_rounds"] = state.get("foundation_rounds", 0) + 1

    if can_proceed or can_proceed_to_draft(state):
        advance_phase(state, "drafting",
                      f"Foundation passed: score={foundation_score}, lore={lore_score}")
    else:
        save_state(state)

    return state


# ============================================================
# 章节进度追踪
# ============================================================

def record_chapter_done(state: Dict[str, Any], chapter_num: int,
                        score: float, passed: bool, forced: bool = False):
    """记录章节完成"""
    state["sub_state"]["current_chapter"] = chapter_num

    ch_key = f"ch_{chapter_num}"
    if not passed and not forced:
        retry = state["retry_count"].get(ch_key, 0)
        state["retry_count"][ch_key] = retry + 1

    if forced:
        state["force_passed"].append(ch_key)

    # 更新卷进度
    vol = state["sub_state"]["current_volume"]
    vol_key = str(vol)
    if vol_key in state["sub_state"]["volume_status"]:
        state["sub_state"]["volume_status"][vol_key]["chapters_done"] = chapter_num

    save_state(state)


def should_force_pass(state: Dict[str, Any], chapter_num: int) -> bool:
    """判断是否应该降级放行"""
    ch_key = f"ch_{chapter_num}"
    return state["retry_count"].get(ch_key, 0) >= MAX_CHAPTER_RETRIES


def get_resume_point(state: Dict[str, Any]) -> tuple:
    """获取断点续传位置：返回 (volume, chapter)"""
    vol = state["sub_state"].get("current_volume", 0)
    ch = state["sub_state"].get("current_chapter", 0)
    return vol, ch


def set_volume_status(state: Dict[str, Any], volume_num: int, status: str,
                      chapters_total: int, chapters_done: int = 0):
    """设置卷状态"""
    vol_key = str(volume_num)
    state["sub_state"]["volume_status"][vol_key] = {
        "status": status,
        "chapters_done": chapters_done,
        "chapters_total": chapters_total,
    }
    state["sub_state"]["current_volume"] = volume_num
    save_state(state)


# ============================================================
# 逻辑欠债
# ============================================================

def add_logic_debt(state: Dict[str, Any], description: str,
                   chapter: int, category: str = "world"):
    """添加逻辑欠债"""
    state.setdefault("logic_debts", []).append({
        "description": description,
        "chapter": chapter,
        "category": category,
        "status": "pending",
        "created": datetime.now().isoformat(),
    })
    save_state(state)


def get_pending_debts(state: Dict[str, Any]) -> List[Dict]:
    """获取未解决的逻辑欠债"""
    return [d for d in state.get("logic_debts", []) if d.get("status") == "pending"]


def resolve_debt(state: Dict[str, Any], index: int):
    """解决逻辑欠债"""
    debts = state.get("logic_debts", [])
    if 0 <= index < len(debts):
        debts[index]["status"] = "resolved"
        debts[index]["resolved_at"] = datetime.now().isoformat()
        save_state(state)


# ============================================================
# Token 安全
# ============================================================

def safe_read(path: Path, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """安全读取文件，防止上下文爆表"""
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return ""
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[截断，原文{}字]".format(len(text))
    return text


# ============================================================
# 显示
# ============================================================

def print_state(state: Dict[str, Any]):
    """打印当前状态摘要"""
    sub = state.get("sub_state", {})
    vol = sub.get("current_volume", 0)
    ch = sub.get("current_chapter", 0)

    print(f"\n{'='*50}")
    print(f"📋 项目状态")
    print(f"{'='*50}")
    print(f"  当前阶段: {state.get('phase', 'seed')}")
    print(f"  进度: 第{vol}卷 / 第{ch}章")

    if state.get("phase") == "foundation" or state.get("foundation_rounds", 0) > 0:
        print(f"  Foundation: 第 {state.get('foundation_rounds', 0)} 轮")
        print(f"  基础评分: {state.get('foundation_score', 0):.1f} / {FOUNDATION_PASS_SCORE}")
        print(f"  设定评分: {state.get('lore_score', 0):.1f} / {LORE_PASS_SCORE}")
        if state.get("last_weak_dimension"):
            print(f"  最弱维度: {state.get('last_weak_dimension')}")

    # 卷状态
    vol_status = sub.get("volume_status", {})
    if vol_status:
        print(f"  卷状态:")
        for vk, vs in vol_status.items():
            print(f"    第{vk}卷: {vs['status']} ({vs['chapters_done']}/{vs['chapters_total']}章)")

    # 降级放行
    fp = state.get("force_passed", [])
    if fp:
        print(f"  ⚠️  降级放行: {', '.join(fp)}")

    # 逻辑欠债
    debts = get_pending_debts(state)
    if debts:
        print(f"  ⚠️  逻辑欠债: {len(debts)} 条")
        for i, d in enumerate(debts[:5]):
            print(f"    [{i}] (第{d['chapter']}章) {d['description'][:50]}")
        if len(debts) > 5:
            print(f"    ...还有 {len(debts)-5} 条")

    print(f"{'='*50}")
