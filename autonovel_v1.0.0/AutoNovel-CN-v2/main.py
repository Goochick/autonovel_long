# ============================================================
# AutoNovel-CN
# 番茄小说AI辅助创作工具（多API适配版）
# 基于 AutoNovel v1.0 改造
# ============================================================

_VERSION = "v1.0.2"  # 2026-05-31 context_summary构建+format参数修正
_LAST_UPDATED = "2026-05-31 19:45"

"""
AutoNovel-CN 主入口

支持完整的小说创作 Pipeline：
1. seed → 种子概念生成
2. world → 世界观构建
3. characters → 角色设定
4. outline → 大纲生成
5. mystery → 核心悬疑
6. canon → 典据初始化
7. foundation → 基础评估循环
8. volume → 卷级大纲生成
9. draft / autowrite → 章节撰写
10. evaluate → 评估审核

使用方法：
    python main.py --phase=seed              # 生成种子概念
    python main.py --phase=world             # 构建世界观
    python main.py --phase=outline           # 生成大纲
    python main.py --phase=volume --volume=1 # 生成第1卷详细大纲
    python main.py --phase=draft --chapter=1 # 撰写第1章
    python main.py --phase=autowrite         # 自动写作模式
    python main.py --phase=full              # 完整流程
    python main.py --phase=status            # 查看当前状态
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from api.api_client import APIClient, global_client, TokenBudgetExceeded
from prompts import (
    # 共享
    SYSTEM_PROMPT_WRITER,
    SHUANG_KEYWORDS,
    BLURB_GENERATION_PROMPT,
    # Seed
    SYSTEM_PROMPT_SEED,
    GENERATE_PROMPT,
    RIFF_PROMPT,
    # World
    SYSTEM_PROMPT_WORLD,
    WORLD_BUILDING_MAP,
    WORLD_BUILDING_CONSTRAINT_BLOCK,
    WORLD_BUILDING_URBAN,
    WORLD_BUILDING_REBIRTH,
    WORLD_BUILDING_FANTASY,
    WORLD_BUILDING_BOSS,
    WORLD_BUILDING_PERIOD,
    WORLD_BUILDING_POSTAPOC,
    WORLD_BUILDING_GAME,
    TAGS_WORLD_INSTRUCTION,
    # Mystery
    SYSTEM_PROMPT_MYSTERY,
    # Voice
    SYSTEM_PROMPT_VOICE,
    VOICE_GENERATION_PROMPT,
    # Characters
    SYSTEM_PROMPT_CHARACTERS,
    CHARACTER_GENERATION_PROMPT,
    TAGS_CHARACTER_INSTRUCTION,
    FEMALE_TENSION_RULES,
    # Outline
    SYSTEM_PROMPT_OUTLINE,
    OUTLINE_GENERATION_PROMPT,
    OUTLINE_EXTEND_PROMPT,
    TAGS_OUTLINE_INSTRUCTION,
    # Draft
    SYSTEM_PROMPT_DRAFT,
    DRAFT_CHAPTER_PROMPT,
    GOLDEN_CHAPTERS_PROMPT,
    SEGMENT_CONTINUE_PROMPT,
    SEGMENT_FINISH_PROMPT,
    TAGS_DRAFT_INSTRUCTION,
    VOLUME_OUTLINE_PROMPT,
    # Evaluate
    SYSTEM_PROMPT_JUDGE,
    SYSTEM_PROMPT_FOUNDATION,
    FOUNDATION_PROMPT,
    CHAPTER_PROMPT,
    FULL_NOVEL_PROMPT,
    SYSTEM_PROMPT_FOUNDATION_FIX,
    FOUNDATION_FIX_PROMPT,
    # Revise
    SYSTEM_PROMPT_SURGEON,
    SYSTEM_PROMPT_EDITOR,
    SYSTEM_PROMPT_REVISION,
    SURGERY_BRIEF_PROMPT,
    REVISION_PROMPT,
    # Canon
    SYSTEM_PROMPT_CANON,
    CANON_EXTRACTION_PROMPT,
    CANON_UPDATE_PROMPT,
    SYSTEM_PROMPT_CANON_GC,
    CANON_GC_PROMPT,
    CANON_RETRIEVAL_PROMPT,
    CANON_CARD_TEMPLATE,
    # Review
    SYSTEM_PROMPT_REVIEW,
    REVIEW_PROMPT,
)
from config import (
    BASE_DIR,
    OUTPUT_DIR,
    CHAPTERS_DIR,
    EVAL_LOGS_DIR,
    DEFAULT_CHAPTER_COUNT,
    TARGET_CHAPTER_WORDS,
)
from state_manager import (
    load_state, save_state, advance_phase,
    can_proceed_to_draft, foundation_round_needed,
    record_foundation_eval, record_chapter_done,
    should_force_pass, set_volume_status, get_resume_point,
    add_logic_debt, get_pending_debts, resolve_debt,
    safe_read, print_state, MAX_CHAPTER_RETRIES,
    FOUNDATION_PASS_SCORE, LORE_PASS_SCORE, MAX_FOUNDATION_ROUNDS
)


def safe_format(template: str, **kwargs) -> str:
    """
    安全的字符串格式化，替代str.format()。
    解决问题：章节正文等用户内容可能含{xxx}，被.format()误认为占位符导致KeyError。
    原理：1.把占位符替换为\u0000标记 2.把{{}}还原为{} 3.把标记替换为实际内容
    """
    result = template
    for key, value in kwargs.items():
        result = result.replace('{' + key + '}', '\x00' + key + '\x00', 1)
    result = result.replace('{{', '{').replace('}}', '}')
    for key, value in kwargs.items():
        result = result.replace('\x00' + key + '\x00', str(value))
    return result

# v0.9.0: 品类+标签读取工具
def load_genre_tags():
    """从 config.yaml 读取品类和风格标签"""
    import yaml as _yaml
    _cfg_path = BASE_DIR / "config.yaml"
    if _cfg_path.exists():
        with open(_cfg_path, 'r', encoding='utf-8') as f:
            _cfg = _yaml.safe_load(f) or {}
        genre = _cfg.get('genre', '都市脑洞')
        tags = _cfg.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]
    else:
        genre = '都市脑洞'
        tags = []
    return genre, tags

def build_tags_instruction(tag_dict, tags):
    """根据标签列表拼接对应的影响指令"""
    instructions = []
    for tag in tags:
        if tag in tag_dict:
            instructions.append(f"[{tag}] {tag_dict[tag]}")
    return "\n".join(instructions) if instructions else ""

# ============================================================
# 文件操作辅助函数
# ============================================================

def load_file(path: Path) -> str:
    """加载文本文件（使用safe_read防止上下文爆表）"""
    return safe_read(path)

def load_config_yaml() -> dict:
    """加载 config.yaml"""
    import yaml
    config_path = Path(__file__).resolve().parent / "config.yaml"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}

def extract_json(response: str) -> dict:
    """从LLM响应中提取JSON（兼容markdown代码块、文字包裹等）"""
    # 1. 直接解析
    try:
        return json.loads(response)
    except (json.JSONDecodeError, ValueError):
        pass
    
    # 2. 从 ```json ... ``` 中提取
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass
    
    # 3. 找第一个 { 到最后一个 }
    brace_start = response.find('{')
    brace_end = response.rfind('}')
    if brace_start >= 0 and brace_end > brace_start:
        try:
            return json.loads(response[brace_start:brace_end+1])
        except (json.JSONDecodeError, ValueError):
            pass
    
    raise json.JSONDecodeError("无法从响应中提取JSON", response, 0)


def extract_scores_from_prose(response: str) -> dict:
    """当LLM不返回JSON时，从散文式评估中提取分数"""
    result = {}
    
    # 提取 chapter_score / 章节评分（优先）
    chapter_patterns = [
        r'章节评分[：:]\s*(\d+\.?\d*)\s*/\s*10',
        r'章节得分[：:]\s*(\d+\.?\d*)\s*/\s*10',
        r'chapter[_\s]?score["\s：:]*\s*(\d+\.?\d*)',
        r'总评[：:]\s*(\d+\.?\d*)\s*/\s*10',
    ]
    for pat in chapter_patterns:
        m = re.search(pat, response, re.IGNORECASE)
        if m:
            result['chapter_score'] = float(m.group(1))
            break
    
    # 提取 foundation_score / 综合评分 / 总体评分
    patterns = [
        r'综合评分[：:]\s*(\d+\.?\d*)\s*/\s*10',
        r'总体评分[：:]\s*(\d+\.?\d*)\s*/\s*10',
        r'基础评分[：:]\s*(\d+\.?\d*)\s*/\s*10',
        r'foundation[_\s]?score["\s：:]*\s*(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*/\s*10',  # 最后兜底：任何 X/10
    ]
    for pat in patterns:
        m = re.search(pat, response, re.IGNORECASE)
        if m:
            result['foundation_score'] = float(m.group(1))
            break
    
    # 提取 lore_score / 设定评分
    lore_patterns = [
        r'设定评分[：:]\s*(\d+\.?\d*)\s*/\s*10',
        r'lore[_\s]?score["\s：:]*\s*(\d+\.?\d*)',
        r'一致性[（(]\d+%[)）][：:]\s*(\d+\.?\d*)\s*/\s*10',
    ]
    for pat in lore_patterns:
        m = re.search(pat, response, re.IGNORECASE)
        if m:
            result['lore_score'] = float(m.group(1))
            break
    
    # 如果没有单独的lore_score，用foundation_score的90%估算
    if 'lore_score' not in result and 'foundation_score' in result:
        result['lore_score'] = result['foundation_score'] * 0.9
    
    # 提取最弱维度
    weak_patterns = [
        r'最弱维度[：:]\s*(\S+)',
        r'最大问题[：:]\s*(\S+)',
        r'核心隐患[：:]\s*(\S+)',
        r'最需要改进[：:]\s*(\S+)',
    ]
    for pat in weak_patterns:
        m = re.search(pat, response, re.IGNORECASE)
        if m:
            weak = m.group(1).strip()
            # 映射到标准维度名
            dim_map = {
                '世界': 'world', '设定': 'world', '世界观': 'world',
                '角色': 'character', '人物': 'character',
                '爽': 'shuang_structure', '结构': 'shuang_structure', '爽文': 'shuang_structure', '节奏': 'shuang_structure',
                '一致': 'consistency', '矛盾': 'consistency',
                '品类': 'genre_fit', '适配': 'genre_fit',
            }
            for key, val in dim_map.items():
                if key in weak:
                    result['weakest_dimension'] = val
                    break
            break
    
    # 默认最弱维度
    if 'weakest_dimension' not in result:
        result['weakest_dimension'] = 'shuang_structure'
    
    # 提取改进建议（找关键句）
    improvements = []
    improvement_patterns = [
        r'修改建议[：:]\s*(.*?)(?=\n\n|\n#|\Z)',
        r'改进[：:]\s*(.*?)(?=\n\n|\n#|\Z)',
    ]
    for pat in improvement_patterns:
        matches = re.findall(pat, response, re.DOTALL)
        for match in matches:
            lines = [l.strip().lstrip('- ').strip() for l in match.split('\n') if l.strip()]
            improvements.extend(lines[:3])
        if improvements:
            break
    
    result['top_3_improvements'] = improvements[:3] if improvements else ['请人工审阅评估结果']
    
    # 判断是否可以继续
    score = result.get('foundation_score', 0)
    result['can_proceed'] = score >= 7.0
    result['_source'] = 'prose_extraction'  # 标记来源
    
    return result

def save_file(path: Path, content: str):
    """保存文本文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"✓ 已保存: {path}")

def ensure_dir(path: Path):
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)

# ============================================================
# Pipeline 阶段
# ============================================================

def phase_seed(client: APIClient, count: int = 5, riff: str = None, extra_requirements: str = None):
    """
    阶段1: 种子概念生成
    
    生成多个小说概念供选择
    """
    print("\n" + "="*50)
    print("阶段 1: 种子概念生成")
    print("="*50)
    
    client.set_phase("seed")
    
    # 检查是否已有用户手写的种子
    existing_seed = load_file(OUTPUT_DIR / "seed.md")
    if existing_seed and not riff:
        print(f"⚠️  检测到 outputs/seed.md 已存在（{len(existing_seed)} 字）")
        print("如果你是自己写的想法，不需要跑 seed 阶段，直接从 world 开始")
        print("如果确实要覆盖，请加 --count 参数或先删除 outputs/seed.md")
        confirm = input("确定要覆盖吗？(y/N): ").strip().lower()
        if confirm != 'y':
            print("已跳过种子生成，保留现有 seed.md")
            return existing_seed
    
    if riff:
        # 基于已有概念扩展
        prompt = RIFF_PROMPT.format(idea=riff)
        print(f"基于概念扩展: {riff[:50]}...")
    else:
        # 生成新概念
        # 注入额外要求到prompt内部（非append），确保模型优先遵循
        extra_block = ""
        if extra_requirements:
            extra_block = f"【核心方向要求（最高优先级，必须遵循）】\n{extra_requirements}\n\n所有概念必须围绕上述方向生成，品类、设定、金手指都要贴合这个方向。"
            print(f"  额外要求: {extra_requirements[:80]}...")
        else:
            extra_block = "【品类多样性要求】\n概念之间品类要多样化，覆盖不同风格（都市/玄幻/悬疑/种田等）。"
        prompt = GENERATE_PROMPT.format(count=count, extra_requirements_block=extra_block)
        print(f"生成 {count} 个新概念...")
    
    response = client.call_model("seed_generation", prompt, max_tokens=6000, system_prompt=SYSTEM_PROMPT_SEED)
    
    # 保存结果
    output_path = OUTPUT_DIR / "seed.md"
    save_file(output_path, response)
    
    print("\n世界观预览:")
    print("-"*40)
    print(response[:1500] if len(response) > 1500 else response)
    
    return response

def phase_world(client: APIClient, seed: str = None, extra_requirements: str = None, revision_note: str = None):
    """
    阶段2: 世界观构建
    
    基于选定的种子概念构建完整世界观
    """
    print("\n" + "="*50)
    print("阶段 2: 世界观构建")
    print("="*50)
    
    client.set_phase("world")
    
    # 获取种子概念
    if not seed:
        seed = load_file(OUTPUT_DIR / "seed.md")
        if not seed:
            print("错误: 请先运行 --phase=seed 生成种子概念")
            return None
    
    print("正在分析种子概念并构建世界观...")
    
    # v0.9.0: 按品类分流世界观 prompt
    genre, tags = load_genre_tags()
    tags_str = "、".join(tags) if tags else "无"
    tags_instruction = build_tags_instruction(TAGS_WORLD_INSTRUCTION, tags)
    
    # 选择品类对应的世界观 prompt
    world_prompt_name = WORLD_BUILDING_MAP.get(genre, "WORLD_BUILDING_URBAN")
    world_prompt_map = {
        "WORLD_BUILDING_URBAN": WORLD_BUILDING_URBAN,
        "WORLD_BUILDING_REBIRTH": WORLD_BUILDING_REBIRTH,
        "WORLD_BUILDING_FANTASY": WORLD_BUILDING_FANTASY,
        "WORLD_BUILDING_BOSS": WORLD_BUILDING_BOSS,
        "WORLD_BUILDING_PERIOD": WORLD_BUILDING_PERIOD,
        "WORLD_BUILDING_POSTAPOC": WORLD_BUILDING_POSTAPOC,
        "WORLD_BUILDING_GAME": WORLD_BUILDING_GAME,
    }
    world_prompt = world_prompt_map.get(world_prompt_name, WORLD_BUILDING_URBAN)
    
    print(f"  品类：{genre} | 标签：{tags_str}")
    print(f"  世界观模板：{world_prompt_name}")
    
    prompt = world_prompt.format(
        genre=genre,
        tags=tags_str,
        tags_instruction=tags_instruction,
        seed=seed,
        WORLD_BUILDING_CONSTRAINT_BLOCK=WORLD_BUILDING_CONSTRAINT_BLOCK
    )
    
    # 注入额外要求
    if extra_requirements:
        prompt += f"\n\n【额外要求（必须遵循）】\n{extra_requirements}"
        print(f"  额外要求: {extra_requirements[:80]}...")
    
    # 注入修订意见（基于已有内容局部修改）
    if revision_note:
        existing = load_file(OUTPUT_DIR / "world.md") or ""
        prompt += f"\n\n【人工修订意见（基于已生成内容进行局部修改）】\n已有内容摘要:\n{existing[:3000]}\n\n修订意见:\n{revision_note}"
        print(f"  修订意见: {revision_note[:80]}...")
    
    response = client.call_model("world_building", prompt, max_tokens=12000, system_prompt=SYSTEM_PROMPT_WORLD)
    
    # 保存结果
    output_path = OUTPUT_DIR / "world.md"
    save_file(output_path, response)
    
    print("\n世界观预览:")
    print("-"*40)
    print(response[:1500] if len(response) > 1500 else response)
    
    return response

def phase_mystery(client: APIClient, seed: str = None, world: str = None, characters: str = None, outline: str = None, extra_requirements: str = None):
    """
    阶段2.5: 核心悬疑与终极底牌生成
    
    【重要】此文件在正文初稿阶段严禁挂载到写手 AI 上下文！
    """
    print("\n" + "="*50)
    print("阶段 2.5: 核心悬疑与终极底牌生成")
    print("="*50)
    
    client.set_phase("mystery")
    print("⚠️  警告：mystery.md 在正文初稿阶段不得加载！")
    
    if not seed:
        seed = load_file(OUTPUT_DIR / "seed.md")
    if not world:
        world = load_file(OUTPUT_DIR / "world.md")
    if not characters:
        characters = load_file(OUTPUT_DIR / "characters.md")
    if not outline:
        outline = load_file(OUTPUT_DIR / "outline.md")
    
    print("正在生成核心悬疑设计...")
    
    from prompts.mystery import MYSTERY_GENERATION_PROMPT
    prompt = MYSTERY_GENERATION_PROMPT.format(
        seed=seed,
        world=world,
        characters=characters,
        outline=outline
    )
    
    if extra_requirements:
        prompt += f"\n\n【额外要求（必须遵循）】\n{extra_requirements}"
        print(f"  额外要求: {extra_requirements[:80]}...")
    
    response = client.call_model("mystery_gen", prompt, max_tokens=8000, system_prompt=SYSTEM_PROMPT_MYSTERY)
    
    output_path = OUTPUT_DIR / "mystery.md"
    save_file(output_path, response)
    
    print("\n悬疑设计预览:")
    print("-"*40)
    print(response[:1500] if len(response) > 1500 else response)
    
    return response

def phase_voice(client: APIClient, world: str = None, characters: str = None, extra_requirements: str = None):
    """
    阶段2.6: 语声档案生成
    
    基于世界观和角色确定小说语声
    """
    print("\n" + "="*50)
    print("阶段 2.6: 语声档案生成")
    print("="*50)
    
    client.set_phase("voice")
    
    if not world:
        world = load_file(OUTPUT_DIR / "world.md")
    if not characters:
        characters = load_file(OUTPUT_DIR / "characters.md")
    
    import yaml
    config_file = BASE_DIR / "config.yaml"
    genre = "都市脑洞"
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            genre = config.get('genre', '都市脑洞')
    
    print("正在生成语声档案...")
    
    from prompts import VOICE_GENERATION_PROMPT
    prompt = VOICE_GENERATION_PROMPT.format(
        world=world,
        characters=characters,
        genre=genre
    )
    
    if extra_requirements:
        prompt += f"\n\n【额外要求（必须遵循）】\n{extra_requirements}"
        print(f"  额外要求: {extra_requirements[:80]}...")
    
    response = client.call_model("voice_analysis", prompt, max_tokens=8000, system_prompt=SYSTEM_PROMPT_VOICE)
    
    output_path = OUTPUT_DIR / "voice.md"
    save_file(output_path, response)
    
    print("\n语声档案预览:")
    print("-"*40)
    print(response[:1500] if len(response) > 1500 else response)
    
    return response

def phase_characters(client: APIClient, seed: str = None, world: str = None, extra_requirements: str = None, revision_note: str = None):
    """
    阶段3: 角色设定
    
    生成主角、配角、反派等角色设定
    """
    print("\n" + "="*50)
    print("阶段 3: 角色设定")
    print("="*50)
    
    client.set_phase("characters")
    
    if not seed:
        seed = load_file(OUTPUT_DIR / "seed.md")
    if not world:
        world = load_file(OUTPUT_DIR / "world.md")
    
    print("正在生成角色设定...")
    
    prompt = f"""基于以下世界观设定，生成主角团队和重要配角的详细设定：

【世界观】
{world}

【故事种子】
{seed}

请生成：
1. 主角设定（身份背景、性格特点、修炼天赋、成长轨迹）
2. 金手指/特殊能力（必须有明确边界和代价）
3. 女主/后宫设定（如果需要的话）
4. 主要配角（师门长辈、挚友、追随者）
5. 主要反派（动机清晰，有自己的逻辑）
6. 势力关系图

每个角色都要有独特的记忆点和成长空间。"""
    
    if extra_requirements:
        prompt += f"\n\n【额外要求（必须遵循）】\n{extra_requirements}"
        print(f"  额外要求: {extra_requirements[:80]}...")
    
    if revision_note:
        existing = load_file(OUTPUT_DIR / "characters.md") or ""
        prompt += f"\n\n【人工修订意见（基于已生成内容进行局部修改）】\n已有内容摘要:\n{existing[:3000]}\n\n修订意见:\n{revision_note}"
        print(f"  修订意见: {revision_note[:80]}...")
    
    response = client.call_model("character_gen", prompt, max_tokens=8000, system_prompt=SYSTEM_PROMPT_CHARACTERS)
    
    output_path = OUTPUT_DIR / "characters.md"
    save_file(output_path, response)
    
    print("\n角色预览:")
    print("-"*40)
    print(response[:1500] if len(response) > 1500 else response)
    
    return response

def phase_outline(client: APIClient, seed: str = None, world: str = None, characters: str = None, target_volumes: int = None, extra_requirements: str = None, revision_note: str = None):
    """
    阶段4: 主线大纲生成（含分卷结构）
    
    注意：章数由AI根据故事需要自然规划，不是硬性参数。
    target_volumes 是建议卷数，AI可以调整。
    """
    print("\n" + "="*50)
    print("阶段 4: 主线大纲生成")
    print("="*50)
    
    client.set_phase("outline")
    
    if not seed:
        seed = load_file(OUTPUT_DIR / "seed.md")
    if not world:
        world = load_file(OUTPUT_DIR / "world.md")
    if not characters:
        characters = load_file(OUTPUT_DIR / "characters.md")
    
    # 读取建议卷数（来自config或命令行），但不强制
    if target_volumes is None:
        config = load_config_yaml()
        target_volumes = config.get('target_volumes', 0)  # 0表示让AI自由规划
    
    volume_hint = f"\n建议规划约 {target_volumes} 卷（你可以根据故事需要调整）。" if target_volumes else "\n请根据故事需要自由规划卷数，不要刻意凑数或压缩。"
    
    print(f"正在生成主线大纲（AI自由规划分卷）...")
    
    prompt = f"""基于以下设定，生成这本网文的主线大纲。

【故事种子】
{seed}

【世界观】
{world}

【角色设定】
{characters}
{volume_hint}
## 主线大纲输出要求

### 1. 全书概述
- 全书核心矛盾（一句话）
- 主角成长路线（起点→终点）
- 预计总字数和总卷数
- 品类：番茄网文

### 2. 分卷规划

按剧情弧自然划分卷，一弧一卷。每卷必须包含：

#### 第X卷: [卷标题]
- **章节范围**：第XX章 ~ 第XX章（共XX章）
- **核心冲突**：本卷最核心的矛盾
- **主角状态**：本卷开始时主角的实力/处境
- **关键事件**：本卷必须发生的3-5个关键事件
- **转折点**：本卷最大的转折
- **本卷结尾**：为主角进入下一卷的起点
- **伏笔**：本卷铺设/回收的伏笔ID

### 3. 伏笔总台账
| 伏笔ID | 伏笔内容 | 埋设章节 | 预计回收章节 | 所属卷 | 状态 |
|--------|---------|---------|------------|-------|------|
| F01 | xxx | ch_01 | ch_45 | 第1卷 | Pending |

伏笔规则：
- 埋设与引爆必须间隔≥3章
- 核心反转线索必须至少3次侧面提及
- 每卷至少收束1个旧伏笔+铺设1个新伏笔

### 4. 全局节拍表
标注关键转折点在全书中的位置：
- 催化事件：第X卷第X章
- 跨入第二幕：第X卷
- 中点爆发：第X卷第X章
- 灵魂黑夜：第X卷
- 大结局：第X卷第X章

### 5. 抗击"稳定性陷阱"
- 故事结束时角色必须发生颠覆性、不可逆的质变
- 让糟糕的事情保持糟糕，不准完美修复
- 强迫角色做出不可逆转的决定

【关键原则】
- 章数由故事需要决定，不要凑整或压缩
- 每卷章数可以不同（紧凑的弧15-20章，展开的弧30-40章都正常）
- 前10章必须留住读者（黄金三章+爽点密集）
- 每卷结尾要有阶段性收束，同时留悬念引向下一卷
- 最后一卷的结局要出人意料又在情理之中"""
    
    if extra_requirements:
        prompt += f"\n\n【额外要求（必须遵循）】\n{extra_requirements}"
        print(f"  额外要求: {extra_requirements[:80]}...")
    
    if revision_note:
        existing = load_file(OUTPUT_DIR / "outline.md") or ""
        prompt += f"\n\n【人工修订意见（基于已生成内容进行局部修改）】\n已有内容摘要:\n{existing[:3000]}\n\n修订意见:\n{revision_note}"
        print(f"  修订意见: {revision_note[:80]}...")
    
    response = client.call_model("outline_gen", prompt, max_tokens=16000, system_prompt=SYSTEM_PROMPT_OUTLINE)
    
    output_path = OUTPUT_DIR / "outline.md"
    save_file(output_path, response)
    
    # 解析分卷信息
    volumes = parse_outline_volumes(response)
    if volumes:
        print(f"\n分卷信息:")
        total_chapters = 0
        for v in volumes:
            ch_count = v.get('end_ch', 0) - v.get('start_ch', 1) + 1
            total_chapters = max(total_chapters, v.get('end_ch', 0))
            print(f"  第{v['volume']}卷: {v['title']} ({v.get('start_ch', '?')}-{v.get('end_ch', '?')}章, 约{ch_count}章)")
        print(f"  全书预计: {len(volumes)}卷, 约{total_chapters}章")
        
        # 更新state
        state = load_state()
        state["chapter_count"] = total_chapters
        for v in volumes:
            set_volume_status(state, v['volume'], 'pending', 
                            v.get('end_ch', 0) - v.get('start_ch', 1) + 1)
        save_state(state)
    else:
        print("\n⚠️ 未能自动解析分卷信息，请手动检查 outline.md")
    
    return response

def parse_outline_volumes(outline: str) -> list:
    """
    从 outline.md 中解析各卷信息
    返回: [{"volume": 1, "title": "卷标题", "start_ch": 1, "end_ch": 80}, ...]
    """
    volumes = []
    # 匹配卷标题模式：第X卷 或 卷X
    volume_pattern = re.compile(r'第\s*([一二三四五六七八九十百\d]+)\s*卷\s*[：:]\s*([^\n]+)')
    # 匹配章节范围：第1章 ~ 第80章 / 第1章—第80章 / 第1章-第80章 等
    chapter_range_pattern = re.compile(r'第\s*(\d+)\s*章\s*[~—\-～]\s*第\s*(\d+)\s*章')
    
    current_vol = None
    current_title = None
    current_start = 1
    current_end = None
    
    lines = outline.split('\n')
    for i, line in enumerate(lines):
        # 检查是否是卷标题
        vol_match = volume_pattern.search(line)
        if vol_match:
            # 保存上一卷
            if current_vol is not None:
                volumes.append({
                    "volume": current_vol,
                    "title": current_title,
                    "start_ch": current_start,
                    "end_ch": current_end if current_end else current_start + 29
                })
            
            vol_num_str = vol_match.group(1)
            vol_title = vol_match.group(2).strip()
            
            # 转换中文数字
            cn_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
            if vol_num_str in cn_nums:
                vol_num = cn_nums[vol_num_str]
            else:
                try:
                    vol_num = int(vol_num_str)
                except:
                    vol_num = len(volumes) + 1
            
            current_vol = vol_num
            current_title = vol_title
            current_start = None
            current_end = None
        
        # 在当前卷内查找章节范围（如"第1章 ~ 第80章"）
        if current_vol is not None and current_start is None:
            range_match = chapter_range_pattern.search(line)
            if range_match:
                current_start = int(range_match.group(1))
                current_end = int(range_match.group(2))
    
    # 保存最后一卷
    if current_vol is not None:
        volumes.append({
            "volume": current_vol,
            "title": current_title,
            "start_ch": current_start if current_start else len(volumes) * 30 + 1,
            "end_ch": current_end if current_end else (current_start if current_start else len(volumes) * 30 + 1) + 29
        })
    
    # 如果没有找到卷标记，创建默认卷结构
    if not volumes:
        total_chapters = 30
        vol_count = max(1, (total_chapters + 29) // 30)
        chapters_per_vol = (total_chapters + vol_count - 1) // vol_count
        for v in range(1, vol_count + 1):
            start = (v - 1) * chapters_per_vol + 1
            end = min(v * chapters_per_vol, total_chapters)
            volumes.append({
                "volume": v,
                "title": f"第{v}卷",
                "start_ch": start,
                "end_ch": end
            })
    
    return volumes

def phase_volume(client: APIClient, volume_num: int = 1):
    """
    生成卷级详细大纲
    
    从 outline.md 解析出各卷信息，生成详细的卷级大纲
    """
    print("\n" + "="*50)
    print(f"阶段 5: 卷级大纲生成 - 第 {volume_num} 卷")
    print("="*50)
    
    client.set_phase(f"volume_{volume_num}")
    
    # 加载所有必要文件
    outline = load_file(OUTPUT_DIR / "outline.md")
    seed = load_file(OUTPUT_DIR / "seed.md")
    world = load_file(OUTPUT_DIR / "world.md")
    characters = load_file(OUTPUT_DIR / "characters.md")
    mystery = load_file(OUTPUT_DIR / "mystery.md")
    canon = load_file(OUTPUT_DIR / "canon.md")
    
    # 解析卷结构
    volumes = parse_outline_volumes(outline)
    
    if volume_num > len(volumes) or volume_num < 1:
        print(f"错误: 大纲中只有 {len(volumes)} 卷，指定卷号 {volume_num} 无效")
        return None
    
    vol_info = volumes[volume_num - 1]
    vol_title = vol_info.get("title", f"第{volume_num}卷")
    start_ch = vol_info.get("start_ch", (volume_num - 1) * 30 + 1)
    end_ch = vol_info.get("end_ch", volume_num * 30)
    chapter_count = end_ch - start_ch + 1
    
    # 提取主线大纲中本卷相关部分
    # 简化处理：使用正则提取本卷章节范围
    main_outline_section = outline
    
    # 获取上一卷结尾（如果有）
    prev_volume_ending = ""
    if volume_num > 1:
        prev_vol_file = OUTPUT_DIR / f"volume_{volume_num - 1}.md"
        if prev_vol_file.exists():
            prev_vol_content = load_file(prev_vol_file)
            # 提取最后500字作为上一卷结尾
            prev_volume_ending = prev_vol_content[-500:] if len(prev_volume_ending) > 500 else prev_vol_content
        else:
            # 从上一卷最后一章获取
            prev_last_ch = (volume_num - 2) * 30 + 30
            prev_last_ch_file = CHAPTERS_DIR / f"ch_{prev_last_ch:02d}.md"
            if prev_last_ch_file.exists():
                prev_last_ch_content = load_file(prev_last_ch_file)
                prev_volume_ending = prev_last_ch_content[-500:] if len(prev_last_ch_content) > 500 else prev_last_ch_content
    
    # 读取配置
    import yaml
    config_file = BASE_DIR / "config.yaml"
    genre = "都市脑洞"
    words_per_chapter = TARGET_CHAPTER_WORDS
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            genre = config.get('genre', '都市脑洞')
            words_per_chapter = config.get('words_per_chapter', 2000)
    
    print(f"正在生成第 {volume_num} 卷详细大纲...")
    print(f"  卷标题: {vol_title}")
    print(f"  章节范围: 第 {start_ch} - {end_ch} 章")
    
    # 构建 prompt
    prompt = VOLUME_OUTLINE_PROMPT.format(
        volume_num=volume_num,
        volume_title=vol_title,
        main_outline_section=main_outline_section[:8000],  # 限制长度
        seed=seed[:2000],
        world=world[:3000],
        characters=characters[:2000],
        mystery=mystery[:2000] if mystery else "",
        canon=canon[:2000] if canon else "",
        prev_volume_ending=prev_volume_ending,
        start_chapter=start_ch,
        end_chapter=end_ch,
        chapter_count=chapter_count,
        words_per_chapter=words_per_chapter,
        genre=genre,
        min_outline_words=3000
    )
    
    response = client.call_model("volume_outline", prompt, max_tokens=12000, system_prompt=SYSTEM_PROMPT_OUTLINE)
    
    # 保存卷级大纲
    output_path = OUTPUT_DIR / f"volume_{volume_num:02d}.md"
    save_file(output_path, response)
    
    # 更新 state
    state = load_state()
    set_volume_status(state, volume_num, "outlined", chapter_count, 0)
    save_state(state)
    
    print("\n卷级大纲预览:")
    print("-"*40)
    print(response[:1500] if len(response) > 1500 else response)
    
    return response

def phase_canon(client: APIClient):
    """
    典据初始化：从策划文档中提取典据
    """
    print("\n" + "="*50)
    print("阶段: 典据初始化")
    print("="*50)
    
    client.set_phase("canon_init")
    
    seed = load_file(OUTPUT_DIR / "seed.md")
    world = load_file(OUTPUT_DIR / "world.md")
    characters = load_file(OUTPUT_DIR / "characters.md")
    
    from prompts.canon import CANON_EXTRACTION_PROMPT
    prompt = CANON_EXTRACTION_PROMPT.format(
        seed=seed,
        world=world,
        characters=characters
    )
    
    response = client.call_model("canon_extraction", prompt, max_tokens=10000, system_prompt=SYSTEM_PROMPT_CANON)
    
    output_path = OUTPUT_DIR / "canon.md"
    save_file(output_path, response)
    
    # 更新 state
    state = load_state()
    state["canon_version"] = 1
    save_state(state)
    
    print("\n典据数据库预览:")
    print("-"*40)
    print(response[:1500] if len(response) > 1500 else response)
    
    return response

def phase_canon_update(client: APIClient, chapter_nums: list = None):
    """
    典据更新：根据新写的章节更新典据
    """
    print("\n" + "="*50)
    print("阶段: 典据更新")
    print("="*50)
    
    client.set_phase("canon_update")
    
    if chapter_nums is None:
        # 自动收集所有未标记通过的章节
        chapters = sorted(CHAPTERS_DIR.glob("ch_*.md"))
        chapter_nums = [int(c.stem.split("_")[1]) for c in chapters]
    
    if not chapter_nums:
        print("没有需要更新典据的章节")
        return
    
    # 加载旧典据和新章节
    old_canon = load_file(OUTPUT_DIR / "canon.md")
    new_chapters = []
    for ch_num in chapter_nums:
        ch_file = CHAPTERS_DIR / f"ch_{ch_num:02d}.md"
        if ch_file.exists():
            new_chapters.append(f"=== 第 {ch_num} 章 ===\n" + load_file(ch_file))
    
    if not new_chapters:
        print("没有找到新章节")
        return
    
    from prompts.canon import CANON_UPDATE_PROMPT
    prompt = CANON_UPDATE_PROMPT.format(
        old_canon=old_canon,
        new_chapters="\n\n".join(new_chapters)
    )
    
    response = client.call_model("canon_update", prompt, max_tokens=10000, system_prompt=SYSTEM_PROMPT_CANON)
    
    output_path = OUTPUT_DIR / "canon.md"
    save_file(output_path, response)
    
    # 更新版本号
    state = load_state()
    state["canon_version"] = state.get("canon_version", 0) + 1
    save_state(state)
    
    print(f"✓ 已更新典据（第 {len(chapter_nums)} 章）")
    
    return response

def phase_canon_gc(client: APIClient, next_volume: int = None):
    """
    典据垃圾回收（GC）
    
    清理过期条目，将重要信息归档到冷库
    """
    print("\n" + "="*50)
    print("阶段: 典据 GC")
    print("="*50)
    
    import yaml
    config_file = BASE_DIR / "config.yaml"
    canon_gc_enabled = True
    canon_archive_enabled = True
    
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            canon_gc_enabled = config.get('canon_gc_enabled', True)
            canon_archive_enabled = config.get('canon_archive_enabled', True)
    
    if not canon_gc_enabled:
        print("典据GC已禁用，跳过")
        return
    
    client.set_phase("canon_gc")
    
    state = load_state()
    
    # 确定下一卷
    if next_volume is None:
        next_volume = state["sub_state"].get("current_volume", 1) + 1
    
    current_canon = load_file(OUTPUT_DIR / "canon.md")
    
    # 获取已完成卷信息
    completed_volumes = state["sub_state"].get("current_volume", 1)
    last_chapter = state["sub_state"].get("current_chapter", 0)
    
    # 获取下一卷大纲摘要
    next_vol_file = OUTPUT_DIR / f"volume_{next_volume:02d}.md"
    next_volume_outline = ""
    if next_vol_file.exists():
        next_volume_outline = load_file(next_vol_file)[:2000]
    
    from prompts.canon import CANON_GC_PROMPT
    prompt = CANON_GC_PROMPT.format(
        canon=current_canon,
        completed_volumes=completed_volumes,
        last_chapter=last_chapter,
        next_volume=next_volume,
        next_volume_outline=next_volume_outline
    )
    
    response = client.call_model("canon_gc", prompt, max_tokens=10000, system_prompt=SYSTEM_PROMPT_CANON_GC)
    
    # 解析输出
    try:
        # 分离 CANON_HOT 和 CANON_ARCHIVE
        canon_hot_match = re.search(r'=== CANON_HOT ===\s*(.*?)(?:=== CANON_ARCHIVE ===|$)', response, re.DOTALL)
        canon_archive_match = re.search(r'=== CANON_ARCHIVE ===\s*(.*?)$', response, re.DOTALL)
        
        canon_hot = canon_hot_match.group(1).strip() if canon_hot_match else response
        canon_archive = canon_archive_match.group(1).strip() if canon_archive_match else ""
        
        # 更新 canon.md
        save_file(OUTPUT_DIR / "canon.md", canon_hot)
        print(f"✓ 已更新 canon.md")
        
        # 更新/追加 archive_canon.md
        if canon_archive_enabled and canon_archive:
            archive_path = OUTPUT_DIR / "archive_canon.md"
            if archive_path.exists():
                existing_archive = load_file(archive_path)
                new_archive = existing_archive + "\n\n" + canon_archive
            else:
                new_archive = canon_archive
            save_file(archive_path, new_archive)
            print(f"✓ 已追加 archive_canon.md ({len(canon_archive)} 字)")
        
        # 更新版本号
        state["canon_version"] = state.get("canon_version", 0) + 1
        save_state(state)
        
    except Exception as e:
        print(f"⚠️  GC解析失败，保存原始输出: {e}")
        save_file(OUTPUT_DIR / "canon_gc_raw.md", response)
    
    return response

def canon_retrieval(client: APIClient, mentioned_name: str):
    """
    典据冷库检出
    
    当正文提到某个名字但典据中没有时，从冷库检索
    """
    print("\n" + "="*50)
    print(f"典据检索: {mentioned_name}")
    print("="*50)
    
    archive_canon = load_file(OUTPUT_DIR / "archive_canon.md")
    current_canon = load_file(OUTPUT_DIR / "canon.md")
    
    if not archive_canon:
        return None
    
    from prompts import CANON_RETRIEVAL_PROMPT
    prompt = CANON_RETRIEVAL_PROMPT.format(
        mentioned_name=mentioned_name,
        archive_canon=archive_canon,
        current_canon=current_canon
    )
    
    response = client.call_model("canon_retrieval", prompt, max_tokens=3000, system_prompt=SYSTEM_PROMPT_CANON)
    
    # 检查是否找到
    if "NOT_FOUND" in response:
        print(f"未在冷库中找到 {mentioned_name}")
        return None
    
    # 如果找到且建议恢复，追加到 canon.md
    if "建议" in response and ("恢复" in response or "需要" in response):
        # 提取恢复条目
        entry_match = re.search(r'条目原文[:：]\s*(.*?)(?:建议|$)', response, re.DOTALL)
        if entry_match:
            entry = entry_match.group(1).strip()
            current_canon = load_file(OUTPUT_DIR / "canon.md")
            updated_canon = current_canon + "\n\n" + entry
            save_file(OUTPUT_DIR / "canon.md", updated_canon)
            print(f"✓ 已从冷库恢复: {mentioned_name}")
            return entry
    
    return response

def phase_foundation(client: APIClient, force: bool = False):
    """
    Foundation 评估循环
    
    评估世界观、角色、大纲等基础设定，直到达标或达到最大轮数
    """
    print("\n" + "="*50)
    print("阶段: Foundation 评估")
    print("="*50)
    
    state = load_state()
    
    # 如果已达标准，直接放行
    if can_proceed_to_draft(state) and not force:
        print(f"✓ Foundation 已达标（基础评分: {state.get('foundation_score', 0):.1f}）")
        return state
    
    while foundation_round_needed(state):
        round_num = state.get("foundation_rounds", 0) + 1
        print(f"\n--- Foundation 评估第 {round_num} 轮 ---")
        
        # 加载评估材料
        world = load_file(OUTPUT_DIR / "world.md")
        characters = load_file(OUTPUT_DIR / "characters.md")
        outline = load_file(OUTPUT_DIR / "outline.md")
        canon = load_file(OUTPUT_DIR / "canon.md")
        
        import yaml
        config_file = BASE_DIR / "config.yaml"
        genre = "都市脑洞"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                genre = config.get('genre', '都市脑洞')
        
        prompt = FOUNDATION_PROMPT.format(
            world=world[:4000],
            characters=characters[:3000],
            outline=outline[:4000],
            canon=canon[:2000] if canon else "",
            genre=genre
        )
        
        response = client.call_model("foundation_eval", prompt, max_tokens=8192, system_prompt=SYSTEM_PROMPT_FOUNDATION)
        
        # 解析评分（兼容 markdown 代码块包裹的 JSON）
        try:
            result = extract_json(response)
            foundation_score = result.get("foundation_score", 0)
            lore_score = result.get("lore_score", 0)
            weakest_dimension = result.get("weakest_dimension", "")
            can_proceed = result.get("can_proceed", False)
            top_improvements = result.get("top_3_improvements", [])
            
            print(f"  基础评分: {foundation_score}/10")
            print(f"  设定评分: {lore_score}/10")
            print(f"  最弱维度: {weakest_dimension}")
            print(f"  可继续: {can_proceed}")
            
            # 记录评估结果
            record_foundation_eval(state, foundation_score, lore_score, weakest_dimension, can_proceed)
            
            # 如果达标，退出循环
            if can_proceed_to_draft(state):
                print(f"\n✓ Foundation 评估通过！")
                advance_phase(state, "drafting", f"Foundation passed: score={foundation_score}, lore={lore_score}")
                return state
            
            # 如果不达标，进行定向修订
            print(f"\n⚠️  需要修订最弱维度: {weakest_dimension}")
            
            # 确定需要修订的文件
            dimension_to_file = {
                "world": ("world.md", "世界观设定"),
                "character": ("characters.md", "角色设定"),
                "shuang_structure": ("outline.md", "大纲爽文结构"),
                "consistency": ("canon.md", "典据一致性"),
                "genre_fit": ("outline.md", "品类适配")
            }
            
            target_file, target_name = dimension_to_file.get(weakest_dimension, ("outline.md", "大纲"))
            target_path = OUTPUT_DIR / target_file
            target_content = load_file(target_path)
            
            # 收集其他文件摘要
            other_files = {
                "world.md": world[:1000],
                "characters.md": characters[:1000],
                "outline.md": outline[:1000]
            }
            del other_files[target_file]
            other_summary = "\n".join([f"【{k}】\n{v}" for k, v in other_files.items()])
            
            # 调用修订 prompt
            fix_prompt = FOUNDATION_FIX_PROMPT.format(
                foundation_score=foundation_score,
                lore_score=lore_score,
                weakest_dimension=weakest_dimension,
                weakness_details="\n".join([f"- {imp}" for imp in top_improvements]),
                target_file=target_file,
                target_content=target_content[:6000],
                world_summary=other_files.get("world.md", "")[:500],
                characters_summary=other_files.get("characters.md", "")[:500],
                outline_summary=other_files.get("outline.md", "")[:500]
            )
            
            fix_response = client.call_model("foundation_fix", fix_prompt, max_tokens=8000, system_prompt=SYSTEM_PROMPT_FOUNDATION_FIX)
            
            # 保存修订后的文件
            save_file(target_path, fix_response)
            print(f"✓ 已修订 {target_file}")
            
            # 处理 CROSS-FILE 标注
            cross_file_match = re.search(r'CROSS-FILE:\s*(.*?)(?:\n|$)', fix_response, re.DOTALL)
            if cross_file_match:
                cross_file_desc = cross_file_match.group(1).strip()
                print(f"⚠️  发现跨文件依赖: {cross_file_desc}")
                # 记录逻辑欠债
                add_logic_debt(state, f"CROSS-FILE: {cross_file_desc}", 
                              chapter=0, category="cross_file")
            
            # 处理 [NEW] 标注的新事实
            new_facts = re.findall(r'\[NEW\]\s*(.*?)(?:\n|$)', fix_response)
            if new_facts:
                print(f"  发现 {len(new_facts)} 个新事实，追加到 canon.md")
                canon_path = OUTPUT_DIR / "canon.md"
                existing_canon = load_file(canon_path)
                new_canon_entries = "\n".join([f"- [NEW] {fact}" for fact in new_facts])
                updated_canon = existing_canon + "\n\n## 新增设定（来自 Foundation 修订）\n" + new_canon_entries
                save_file(canon_path, updated_canon)
            
        except json.JSONDecodeError as e:
            # JSON解析失败，尝试从散文中提取分数
            print(f"⚠️  JSON解析失败，尝试从散文中提取分数...")
            try:
                result = extract_scores_from_prose(response)
                foundation_score = result.get("foundation_score", 0)
                lore_score = result.get("lore_score", 0)
                weakest_dimension = result.get("weakest_dimension", "shuang_structure")
                can_proceed = result.get("can_proceed", False)
                top_improvements = result.get("top_3_improvements", [])
                
                print(f"  基础评分: {foundation_score}/10 (散文提取)")
                print(f"  设定评分: {lore_score}/10 (散文提取)")
                print(f"  最弱维度: {weakest_dimension}")
                
                # 记录评估结果
                record_foundation_eval(state, foundation_score, lore_score, weakest_dimension, can_proceed)
                
                # 如果达标，退出循环
                if can_proceed_to_draft(state):
                    print(f"\n✓ Foundation 评估通过！")
                    advance_phase(state, "drafting", f"Foundation passed: score={foundation_score}, lore={lore_score}")
                    return state
                
                # 不达标，继续定向修订逻辑（复用上面的代码）
                print(f"\n⚠️  需要修订最弱维度: {weakest_dimension}")
                
                dimension_to_file = {
                    "world": ("world.md", "世界观设定"),
                    "character": ("characters.md", "角色设定"),
                    "shuang_structure": ("outline.md", "大纲爽文结构"),
                    "consistency": ("canon.md", "典据一致性"),
                    "genre_fit": ("outline.md", "品类适配")
                }
                
                target_file, target_name = dimension_to_file.get(weakest_dimension, ("outline.md", "大纲"))
                target_path = OUTPUT_DIR / target_file
                target_content = load_file(target_path)
                
                other_files = {
                    "world.md": world[:1000],
                    "characters.md": characters[:1000],
                    "outline.md": outline[:1000]
                }
                if target_file in other_files:
                    del other_files[target_file]
                
                fix_prompt = FOUNDATION_FIX_PROMPT.format(
                    foundation_score=foundation_score,
                    lore_score=lore_score,
                    weakest_dimension=weakest_dimension,
                    weakness_details="\n".join([f"- {imp}" for imp in top_improvements]),
                    target_file=target_file,
                    target_content=target_content[:6000],
                    world_summary=other_files.get("world.md", "")[:500],
                    characters_summary=other_files.get("characters.md", "")[:500],
                    outline_summary=other_files.get("outline.md", "")[:500]
                )
                
                fix_response = client.call_model("foundation_fix", fix_prompt, max_tokens=8000, system_prompt=SYSTEM_PROMPT_FOUNDATION_FIX)
                save_file(target_path, fix_response)
                print(f"✓ 已修订 {target_file}")
                
            except Exception as inner_e:
                print(f"⚠️  散文提取也失败: {inner_e}")
                print("原始响应前500字:")
                print(response[:500])
                # 保存原始评估结果供人工审阅
                save_file(OUTPUT_DIR / "foundation_eval_raw.md", response)
                break
        
        # 重新加载 state（因为可能被更新了）
        state = load_state()
    
    # 达到最大轮数仍未达标
    if foundation_round_needed(state):
        print(f"\n⚠️  已达到最大评估轮数 ({MAX_FOUNDATION_ROUNDS})，强制进入 drafting")
        advance_phase(state, "drafting", f"Max foundation rounds reached, force proceed")
    
    return state

def phase_draft(client: APIClient, chapter_num: int, volume_num: int = None, outline: str = None, world: str = None, characters: str = None):
    """
    阶段5: 章节撰写（v0.9.0 重构）
    
    - 黄金三章（1-3章）用专属 prompt
    - 分段续写（每段1000字左右，每段重新注入指令）
    - 典据按章筛选（只给相关条目）
    - 风格标签贯穿
    """
    print("\n" + "="*50)
    print(f"阶段 5: 撰写第 {chapter_num} 章")
    print("="*50)
    
    client.set_phase(f"draft_ch{chapter_num}")
    genre, tags = load_genre_tags()
    tags_str = "、".join(tags) if tags else "无"
    tags_draft_inst = build_tags_instruction(TAGS_DRAFT_INSTRUCTION, tags)
    
    # 确定卷号
    if volume_num is None:
        state = load_state()
        volume_num = state["sub_state"].get("current_volume", 1)
    
    # 优先从 volume_XX.md 提取章节大纲
    volume_outline_path = OUTPUT_DIR / f"volume_{volume_num:02d}.md"
    volume_outline = None
    if volume_outline_path.exists():
        volume_outline = load_file(volume_outline_path)
        pattern = rf'###\s*第\s*{chapter_num}\s*章.*?(?=###\s*第\s*{chapter_num + 1}\s*章|###\s*[^\d]|$)'
        match = re.search(pattern, volume_outline, re.DOTALL)
        chapter_outline = match.group(0) if match else f"第 {chapter_num} 章"
    else:
        if not outline:
            outline = load_file(OUTPUT_DIR / "outline.md")
        pattern = rf'###\s*第\s*{chapter_num}\s*章.*?(?=###\s*第\s*{chapter_num + 1}\s*章|###\s*尾声|$)'
        match = re.search(pattern, outline, re.DOTALL)
        chapter_outline = match.group(0) if match else f"第 {chapter_num} 章"
    
    # 加载其他必要文件（精简版）
    if not world:
        world = load_file(OUTPUT_DIR / "world.md")
    if not characters:
        characters = load_file(OUTPUT_DIR / "characters.md")
    
    # v0.9.0: 典据按章筛选，只给相关条目
    canon_full = load_file(OUTPUT_DIR / "canon.md")
    canon = _filter_canon_for_chapter(canon_full, chapter_outline)
    
    # 获取前情提要（上一章结尾500字）
    if chapter_num > 1:
        prev_chapter_file = CHAPTERS_DIR / f"ch_{chapter_num-1:02d}.md"
        if prev_chapter_file.exists():
            prev_content = load_file(prev_chapter_file)
            prev_summary = prev_content[-500:] if len(prev_content) > 500 else prev_content
        else:
            pattern = rf'###\s*第\s*{chapter_num - 1}\s*章.*?(?=###\s*第\s*{chapter_num}\s*章|$)'
            prev_match = re.search(pattern, outline if not volume_outline else (volume_outline or outline), re.DOTALL)
            prev_summary = prev_match.group(0)[-300:] if prev_match else ""
    else:
        prev_summary = ""
    
    # 获取下一章开头（用于留钩子）
    next_chapter_intro = ""
    if volume_outline:
        pattern = rf'###\s*第\s*{chapter_num + 1}\s*章.*?(?=###\s*第\s*{chapter_num + 2}\s*章|###\s*[^\d]|$)'
        next_match = re.search(pattern, volume_outline, re.DOTALL)
        if next_match:
            next_chapter_intro = next_match.group(0)[:300]
    
    # 判断是否为关键章节
    is_key = any(kw in chapter_outline.lower() for kw in ['高潮', '转折', '大战', '突破', '危机', '揭秘', '真相'])
    is_golden = chapter_num <= 3  # v0.9.0: 黄金三章
    
    chapter_type = "黄金三章" if is_golden else ("关键章节（R1）" if is_key else "普通章节（V3）")
    print(f"章节类型: {chapter_type}")
    
    # 加载写作风格
    voice = load_file(OUTPUT_DIR / "voice.md")
    title = load_file(OUTPUT_DIR / "seed.md")[:50] if (OUTPUT_DIR / "seed.md").exists() else ""
    
    # 构建核心上下文摘要（替代直接塞整个world/characters/canon）
    world = load_file(OUTPUT_DIR / "world.md") or ""
    characters = load_file(OUTPUT_DIR / "characters.md") or ""
    canon = load_file(OUTPUT_DIR / "canon.md") or ""
    _ctx_parts = []
    if world:
        _ctx_parts.append(f"【世界观】\n{world[:1200]}")
    if characters:
        _ctx_parts.append(f"【角色】\n{characters[:1000]}")
    if canon:
        _ctx_parts.append(f"【典据】\n{canon[:800]}")
    context_summary = "\n\n".join(_ctx_parts) if _ctx_parts else "无"
    
    # 计算爽点
    min_shuang = 4 if is_golden else (3 if is_key else 2)
    positions = _calc_shuang_positions(TARGET_CHAPTER_WORDS, min_shuang)
    
    # ===== 选择 prompt 模板 =====
    if is_golden:
        prompt = GOLDEN_CHAPTERS_PROMPT.format(
            chapter_num=chapter_num,
            genre=genre,
            tags=tags_str,
            voice=voice[:1500] if voice else "",
            context_summary=context_summary,
            chapter_outline=chapter_outline,
            prev_chapter_ending=prev_summary,
            target_words=TARGET_CHAPTER_WORDS,
            min_shuang_points=min_shuang,
            shuang_points_positions=positions,
        )
    else:
        # 普通章节：用 DRAFT_CHAPTER_PROMPT
        from prompts.draft import DRAFT_CHAPTER_PROMPT
        prompt = DRAFT_CHAPTER_PROMPT.format(
            chapter_num=chapter_num,
            genre=genre,
            title=title,
            arc_name=f"第{volume_num}卷",
            voice=voice[:1500] if voice else "",
            context_summary=context_summary,
            chapter_outline=chapter_outline,
            prev_chapter_ending=prev_summary,
            target_words=TARGET_CHAPTER_WORDS,
            min_shuang_points=min_shuang,
            shuang_points_positions=positions,
        )
    
    # v0.9.0: 追加风格标签指令 + 女配性张力规则
    if tags_draft_inst:
        prompt += f"\n\n【风格标签指引】\n{tags_draft_inst}"
    if any(t in tags for t in ['后宫', '纯爱', '热血']):
        prompt += f"\n\n{FEMALE_TENSION_RULES}"
    
    # ===== 分段续写 =====
    target_total = TARGET_CHAPTER_WORDS
    segment_size = 1200  # 每段目标字数
    num_segments = max(2, target_total // segment_size)
    
    task_type = "chapter_draft_key" if (is_key or is_golden) else "chapter_draft"
    
    if num_segments <= 1 or TARGET_CHAPTER_WORDS <= 1500:
        # 短章节，一次性写
        response = client.call_model(task_type, prompt, max_tokens=8000, system_prompt=SYSTEM_PROMPT_DRAFT)
    else:
        # 分段续写
        print(f"  分段续写: {num_segments} 段，每段约 {segment_size} 字")
        response = _write_in_segments(
            client, task_type, prompt, 
            chapter_num, chapter_outline, genre, tags_str,
            target_total, segment_size, num_segments
        )
    
    # 保存章节
    output_path = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    save_file(output_path, response)
    
    print(f"  ✓ 第 {chapter_num} 章初稿完成（{len(response)}字）")
    
    return response


def _extract_chapter_outline(outline: str, chapter_num: int) -> str:
    """从大纲中提取指定章节的大纲内容"""
    if not outline:
        return ""
    pattern = rf'(?:第\s*{chapter_num}\s*章)[^\n]*\n(.*?)(?=(?:第\s*{chapter_num + 1}\s*章)|$)'
    match = re.search(pattern, outline, re.DOTALL)
    return match.group(1).strip() if match else ""


def _evaluate_chapter(client: APIClient, chapter_num: int, verbose: bool = True) -> dict:
    """
    v0.9.1: 统一的章节评估函数
    
    使用 CHAPTER_PROMPT + SYSTEM_PROMPT_JUDGE，统一处理JSON解析和散文回退。
    返回 dict，至少包含：
      - chapter_score: float (0-10)
      - top_revisions: list[str]
      - recommendation: str
      - _raw_response: str (原始输出)
      - _parse_method: str ("json" 或 "prose" 或 "fallback")
    """
    from prompts import CHAPTER_PROMPT
    
    # 加载评估所需上下文
    chapter_file = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    chapter_text = load_file(chapter_file) if chapter_file.exists() else ""
    if not chapter_text:
        return {"chapter_score": 0, "top_revisions": [], "recommendation": "rewrite",
                "_raw_response": "", "_parse_method": "no_chapter"}
    
    voice = load_file(OUTPUT_DIR / "voice.md")
    outline = load_file(OUTPUT_DIR / "outline.md")
    chapter_outline = _extract_chapter_outline(outline, chapter_num) if outline else ""
    prev_ch_path = CHAPTERS_DIR / f"ch_{chapter_num-1:02d}.md"
    prev_tail = load_file(prev_ch_path)[-500:] if prev_ch_path.exists() else ""
    
    # v0.9.5: 用safe_format替代str.format，彻底解决花括号冲突
    prompt = safe_format(CHAPTER_PROMPT,
        chapter_num=chapter_num,
        chapter_text=chapter_text,
        chapter_outline=chapter_outline[:1000],
        prev_chapter_tail=prev_tail,
        voice=voice[:1500] if voice else "",
    )
    
    response = client.call_model("chapter_eval", prompt, max_tokens=16000, system_prompt=SYSTEM_PROMPT_JUDGE)
    
    # v0.9.1 debug: 打印R1返回长度，帮助排查JSON解析失败
    if verbose and len(response) < 200:
        print(f"  ⚠️ R1返回过短（{len(response)}字），可能思考过程消耗了输出空间")
        print(f"  原始返回: {response}")
    
    # 尝试解析
    result = {"_raw_response": response}
    
    try:
        parsed = extract_json(response)
        result.update(parsed)
        result['_parse_method'] = 'json'
        score = parsed.get('chapter_score', 0)
        if verbose:
            print(f"  评分: {score}/10 (JSON)")
    except (json.JSONDecodeError, ValueError):
        # JSON 解析失败，尝试散文提取
        prose = extract_scores_from_prose(response)
        score = prose.get('chapter_score', prose.get('foundation_score', 0))
        result.update(prose)
        result['_parse_method'] = 'prose'
        
        if score > 0:
            if verbose:
                print(f"  评分: {score}/10 (散文提取)")
        else:
            # 散文也没提取到分数——R1可能返回了无法解析的格式
            # 给一个保守分数，不触发修订（避免无限循环）
            score = 7.0
            result['chapter_score'] = score
            if verbose:
                print(f"  ⚠️ 无法提取评分，R1原始输出前500字：")
                print(f"  {response[:500]}")
                print(f"  保守评分: {score}/10（不触发修订）")
    
    # 确保 chapter_score 字段存在
    if 'chapter_score' not in result:
        result['chapter_score'] = score
    
    # 确保 top_revisions 字段存在
    if not result.get('top_revisions') and not result.get('top_3_revisions'):
        result['top_revisions'] = []
    
    return result


def _filter_canon_for_chapter(canon_full: str, chapter_outline: str) -> str:
    """v0.9.0: 从完整典据中筛选与当前章节相关的条目"""
    if not canon_full:
        return ""
    if len(canon_full) <= 1500:
        return canon_full  # 典据本身就短，全给
    
    # 按行分割，只保留包含大纲关键词的条目
    keywords = set()
    for line in chapter_outline.split('\n'):
        for word in line.strip().split():
            if len(word) >= 2:
                keywords.add(word)
    
    # 也保留所有【角色】【物品】【技能】开头的核心条目
    relevant_lines = []
    for line in canon_full.split('\n'):
        if line.strip().startswith('【角色】') or line.strip().startswith('【物品】') or line.strip().startswith('【技能】'):
            relevant_lines.append(line)
        elif any(kw in line for kw in keywords):
            relevant_lines.append(line)
    
    filtered = '\n'.join(relevant_lines)
    # 如果筛选后太短，回退到取前1500字
    if len(filtered) < 200:
        return canon_full[:1500]
    return filtered[:2000]


def _calc_shuang_positions(target_words: int, count: int) -> str:
    """计算爽点分布位置描述"""
    positions = []
    interval = target_words // (count + 1)
    for i in range(1, count + 1):
        pos = interval * i
        positions.append(f"第{pos}字左右")
    return "、".join(positions)


def _count_emotion_words(text):
    """v0.9.0+: 统计已写文本中的高频情绪词，用于分段续写时传递累计计数"""
    emotion_words = ['操', '卧槽', '他妈', '什么玩意', '什么鬼', '我靠', '我去', '妈的', '草', '靠']
    counts = {}
    for w in emotion_words:
        c = text.count(w)
        if c > 0:
            counts[w] = c
    if not counts:
        return "暂无高频情绪词"
    lines = []
    for w, c in sorted(counts.items(), key=lambda x: -x[1]):
        status = "⛔本段禁用" if c >= 2 else f"⚠️还可再用{2-c}次"
        lines.append(f"  「{w}」已用{c}次 {status}")
    return "\n".join(lines)


def _write_in_segments(client, task_type, first_prompt, chapter_num, chapter_outline, genre, tags_str, target_total, segment_size, num_segments):
    """v0.9.0: 分段续写核心逻辑"""
    # 第一段：用完整 prompt
    response = client.call_model(task_type, first_prompt, max_tokens=6000, system_prompt=SYSTEM_PROMPT_DRAFT)
    written = len(response)
    print(f"  第1段完成: {written}字")
    
    # 后续段落：续写
    for seg_idx in range(1, num_segments):
        remaining_words = target_total - written
        if remaining_words <= 300:
            break  # 已经够了
        
        # 最后一段用 finish prompt（强钩子结尾）
        is_last = (seg_idx == num_segments - 1) or (remaining_words <= segment_size + 300)
        
        # 提取剩余大纲（简化）
        remaining_outline = chapter_outline[:500]  # 简化处理
        
        # 本段要包含的事件（从大纲中粗略提取）
        segment_events = f"继续推进大纲中的下一个事件"
        
        # 统计前文情绪词（整章累计，不是单段）
        emotion_count = _count_emotion_words(response)
        
        if is_last:
            seg_prompt = SEGMENT_FINISH_PROMPT.format(
                chapter_num=chapter_num,
                genre=genre,
                tags=tags_str,
                written_words=written,
                previous_text=response[-2000:],
                emotion_word_count=emotion_count,
            )
        else:
            # 提取上段最后几句作为衔接锚点
            last_sentences = response[-200:].strip() if len(response) > 200 else response.strip()
            # 章末钩子预告（从大纲提取）
            chapter_ultimate_goal = chapter_outline[-300:] if chapter_outline else "按大纲推进至章末高潮"
            
            seg_prompt = SEGMENT_CONTINUE_PROMPT.format(
                chapter_num=chapter_num,
                genre=genre,
                tags=tags_str,
                chapter_ultimate_goal=chapter_ultimate_goal,
                emotion_word_count=emotion_count,
                segment_target_words=min(segment_size, remaining_words),
                remaining_outline=remaining_outline,
                segment_events=segment_events,
                last_few_sentences_of_previous_text=last_sentences,
            )
        
        seg_response = client.call_model(task_type, seg_prompt, max_tokens=4000, system_prompt=SYSTEM_PROMPT_DRAFT)
        
        # 拼接（去掉可能的重复开头）
        seg_text = seg_response.strip()
        if response.strip().endswith(seg_text[:50]):
            seg_text = seg_text[50:]  # 去掉重复
        
        response = response.rstrip() + "\n\n" + seg_text
        written = len(response)
        print(f"  第{seg_idx+1}段完成: 累计{written}字")
    
    return response

def phase_evaluate(client: APIClient, phase: str = "foundation", chapter: int = None):
    """
    阶段6: 评估审核
    
    支持三种模式：
    - foundation: 基础设定评估（世界观、角色、大纲）
    - chapter: 单章评估
    - full: 全书评估
    """
    print("\n" + "="*50)
    print(f"阶段 6: {'基础设定' if phase == 'foundation' else '章节' if phase == 'chapter' else '全书'}评估")
    print("="*50)
    
    client.set_phase(f"eval_{phase}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if phase == "foundation":
        # 评估基础设定
        seed = load_file(OUTPUT_DIR / "seed.md")
        world = load_file(OUTPUT_DIR / "world.md")
        characters = load_file(OUTPUT_DIR / "characters.md")
        outline = load_file(OUTPUT_DIR / "outline.md")
        
        prompt = f"""严格评估以下小说基础设定，给出可执行的修改建议：

【种子概念】
{seed}

【世界观】
{world}

【角色设定】
{characters}

【大纲】
{outline}

请评估：
1. 世界观是否撑得起长篇？（至少能支持 200 万字）
2. 金手指是否有边界感？（不能无敌）
3. 爽点是否可持续？（不是一次性爽）
4. 角色是否有成长空间？
5. 大纲节奏是否合理？
6. 有哪些潜在的崩盘风险？

请输出 JSON 格式：
{{
  "world_score": 1-10,
  "character_score": 1-10,
  "outline_score": 1-10,
  "overall_score": 1-10,
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"]
}}"""
        
        response = client.call_model("foundation_eval", prompt, max_tokens=8192, system_prompt=SYSTEM_PROMPT_FOUNDATION)
        
        # 尝试解析 JSON
        try:
            result = extract_json(response)
            print(f"\n评估结果: 总体 {result.get('overall_score', 'N/A')}/10")
            print(f"世界观: {result.get('world_score', 'N/A')}/10")
            print(f"角色: {result.get('character_score', 'N/A')}/10")
            print(f"大纲: {result.get('outline_score', 'N/A')}/10")
            print(f"\n问题: {result.get('issues', [])}")
            print(f"建议: {result.get('suggestions', [])}")
        except:
            print(response)
        
        output_path = EVAL_LOGS_DIR / f"foundation_eval_{timestamp}.json"
        save_file(output_path, response)
    
    elif phase == "chapter":
        # 评估已写的章节（使用统一的 _evaluate_chapter）
        # 如果指定了 --chapter 只评估那一章
        target_ch = chapter
        
        chapters = sorted(CHAPTERS_DIR.glob("ch_*.md"))
        if not chapters:
            print("错误: 还没有撰写任何章节")
            return
        
        for chapter_file in chapters:
            chapter_num = int(chapter_file.stem.split("_")[1])
            if target_ch and chapter_num != target_ch:
                continue
            
            print(f"\n第 {chapter_num} 章评估:")
            result = _evaluate_chapter(client, chapter_num, verbose=True)
            
            # 打印详细结果
            score = result.get('chapter_score', 0)
            print(f"  总分: {score}/10")
            print(f"  最弱维度: {result.get('weakest_dimension', '')}")
            print(f"  建议: {result.get('recommendation', '')}")
            
            top_revisions = result.get('top_revisions', []) or result.get('top_3_revisions', [])
            if top_revisions:
                print(f"  修改意见:")
                for i, r in enumerate(top_revisions):
                    print(f"    {i+1}. {r[:120]}...")
            
            # 打印各维度分数
            dim_names = {
                'shuang_density': '爽点密度', 'hook_quality': '钩子质量',
                'logic_consistency': '逻辑一致性', 'emotion_variety': '情绪表达',
                'anti_slop': '反AI味', 'continuity': '连续性',
                'character_presence': '人设与女配'
            }
            for dim_key, dim_name in dim_names.items():
                dim = result.get(dim_key)
                if isinstance(dim, dict) and 'score' in dim:
                    print(f"  {dim_name}: {dim['score']}/10")
                    for v in dim.get('violations', dim.get('problems', []))[:2]:
                        print(f"    - {str(v)[:100]}")
            
            output_path = EVAL_LOGS_DIR / f"ch{chapter_num:02d}_eval_{timestamp}.json"
            save_file(output_path, result.get('_raw_response', str(result)))
    
    elif phase == "full":
        # 全书评估
        all_content = []
        chapters = sorted(CHAPTERS_DIR.glob("ch_*.md"))
        
        for chapter_file in chapters:
            chapter_num = int(chapter_file.stem.split("_")[1])
            content = load_file(chapter_file)
            all_content.append(f"=== 第 {chapter_num} 章 ===\n{content}")
        
        combined = "\n\n".join(all_content)
        
        prompt = f"""评估整本书的整体质量：

{combined[:30000]}

请评估：
1. 整体节奏是否一致？
2. 是否有前后矛盾？
3. 伏笔是否回收？
4. 爽点密度是否足够？
5. 高潮是否够高？

输出详细的分析报告。"""
        
        response = client.call_model("full_eval", prompt, max_tokens=6000, system_prompt=SYSTEM_PROMPT_JUDGE)
        
        output_path = EVAL_LOGS_DIR / f"full_eval_{timestamp}.txt"
        save_file(output_path, response)
        
        print("\n全书评估结果:")
        print("-"*40)
        print(response[:2000])

# ============================================================
# 完整流程
# ============================================================

def run_full_pipeline(client: APIClient, chapter_count: int = None, start_chapter: int = 1):
    """
    运行完整的创作流程
    
    Args:
        client: API 客户端
        chapter_count: 章节数量，默认使用配置值
        start_chapter: 从第几章开始写正文（跳过前面的生成阶段）
    """
    print("\n" + "#"*60)
    print("# AutoNovel-CN 完整创作流程")
    print("#"*60)
    
    chapter_count = chapter_count or DEFAULT_CHAPTER_COUNT
    
    if start_chapter == 1:
        # 从头开始
        print("\n>>> 步骤1: 种子概念生成")
        try:
            phase_seed(client, count=5)
        except TokenBudgetExceeded as e:
            print(f"\n🛑 {e}")
            client.print_usage()
            return
        
        print("\n>>> 步骤2: 世界观构建")
        try:
            phase_world(client)
        except TokenBudgetExceeded as e:
            print(f"\n🛑 {e}")
            client.print_usage()
            return
        
        print("\n>>> 步骤3: 角色设定")
        try:
            phase_characters(client)
        except TokenBudgetExceeded as e:
            print(f"\n🛑 {e}")
            client.print_usage()
            return
        
        print("\n>>> 步骤3.5: 语声档案生成")
        try:
            phase_voice(client)
        except TokenBudgetExceeded as e:
            print(f"\n🛑 {e}")
            client.print_usage()
            return
        
        print("\n>>> 步骤4: 大纲生成")
        try:
            phase_outline(client)
        except TokenBudgetExceeded as e:
            print(f"\n🛑 {e}")
            client.print_usage()
            return
        
        print("\n>>> 步骤4.5: 核心悬疑与终极底牌生成")
        try:
            phase_mystery(client)
        except TokenBudgetExceeded as e:
            print(f"\n🛑 {e}")
            client.print_usage()
            return
    
    # 章节撰写
    print(f"\n>>> 步骤5: 章节撰写 (共 {chapter_count} 章)")
    for i in range(start_chapter, chapter_count + 1):
        try:
            phase_draft(client, i)
            print(f"✓ 第 {i} 章完成")
        except TokenBudgetExceeded as e:
            print(f"\n🛑 预算耗尽！{e}")
            print(f"已完成 {i-1} 章，剩余章节可稍后继续")
            client.print_usage()
            return
        except Exception as e:
            print(f"✗ 第 {i} 章失败: {e}")
    
    print("\n>>> 步骤6: 评估全书")
    try:
        phase_evaluate(client, phase="full")
    except TokenBudgetExceeded as e:
        print(f"\n🛑 {e}")
        client.print_usage()
        return
    
    # 最终统计
    client.print_usage()
    
    print("\n" + "#"*60)
    print("# 创作流程完成!")
    print("#"*60)


def phase_blurb(client: APIClient):
    """v0.9.0: 生成小说简介"""
    print("\n" + "="*50)
    print("阶段: 简介生成")
    print("="*50)
    
    client.set_phase("blurb")
    genre, tags = load_genre_tags()
    tags_str = "、".join(tags) if tags else "无"
    
    world = load_file(OUTPUT_DIR / "world.md")
    characters = load_file(OUTPUT_DIR / "characters.md")
    outline = load_file(OUTPUT_DIR / "outline.md")
    seed = load_file(OUTPUT_DIR / "seed.md")
    title = seed[:50] if seed else "未命名"
    
    # 提取前3章大纲
    outline_summary = outline[:1500] if outline else ""
    
    prompt = BLURB_GENERATION_PROMPT.format(
        genre=genre,
        tags=tags_str,
        title=title,
        world_summary=world[:1500] if world else "",
        character_summary=characters[:1000] if characters else "",
        outline_summary=outline_summary,
    )
    
    response = client.call_model("seed_generation", prompt, max_tokens=3000, system_prompt=SYSTEM_PROMPT_SEED)
    
    output_path = OUTPUT_DIR / "blurb.md"
    save_file(output_path, response)
    
    print("\n生成的简介：")
    print("-"*40)
    print(response)
    
    return response


def phase_autowrite(client: APIClient, start_volume: int = 1, start_chapter: int = None, end_chapter: int = None, force: bool = False):
    """
    自动写作模式（按卷写作）
    
    流程：大纲 → 卷纲 → 写正文
    章节依赖：写第N章时，第N-1章必须存在（重写已有章节除外）
    
    用法：
      --phase=autowrite                                    # 从头开始写
      --phase=autowrite --start-chapter=9                  # 从第9章开始（需1-8章已存在）
      --phase=autowrite --start-chapter=9 --end-chapter=12 # 只写9-12章
      --phase=autowrite --start-chapter=9 --force          # 强制重写第9章起
    
    对每一章执行：
    1. 确保卷纲存在（不存在则先生成）
    2. 写初稿（phase_draft）
    3. 评估打分(evaluate)
    4. 不通过 → 手术简报 → 修订 → 重评（最多3轮，超限降级放行）
    5. 通过 → 记录到state
    """
    import yaml
    import re as regex
    
    # 尝试导入脚本模块
    try:
        from scripts import review as review_module
        from scripts import evaluate as eval_module
        from scripts import gen_revision as revision_module
        has_scripts = True
    except ImportError:
        has_scripts = False
    
    state = load_state()
    
    # 从 config.yaml 读取控制参数
    config_path = Path(__file__).resolve().parent / "config.yaml"
    min_score = 5.5
    golden_score = 7.5
    max_revise_rounds = 3
    canon_gc_enabled = True
    
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
        min_score = cfg.get('min_chapter_score', 5.5)
        golden_score = cfg.get('golden_chapter_score', 7.5)
        max_revise_rounds = cfg.get('max_revision_rounds', 3)
        canon_gc_enabled = cfg.get('canon_gc_enabled', True)
    
    # 解析卷结构
    outline = load_file(OUTPUT_DIR / "outline.md")
    if not outline:
        print("❌ 错误: outline.md 不存在，请先运行 outline 阶段")
        return
    volumes = parse_outline_volumes(outline)
    
    if not volumes:
        print("❌ 错误: 无法解析大纲中的卷结构")
        return
    
    # === 收集已有章节 ===
    existing_chapters = set()
    if CHAPTERS_DIR.exists():
        for f in CHAPTERS_DIR.iterdir():
            m = re.match(r'ch_(\d+)\.md', f.name)
            if m:
                existing_chapters.add(int(m.group(1)))
    
    # === 确定实际起止章节 ===
    if start_chapter is not None:
        actual_start = start_chapter
    elif not force and state["sub_state"].get("current_chapter", 0) > 0:
        # 断点续传
        actual_start = state["sub_state"]["current_chapter"] + 1
        check_path = CHAPTERS_DIR / f"ch_{actual_start:02d}.md"
        if not check_path.exists() and actual_start > 1:
            print(f"  ⚠️ state记录第{actual_start}章不存在，从第1章开始")
            actual_start = 1
    else:
        actual_start = 1
    
    if end_chapter is not None:
        actual_end = end_chapter
    else:
        actual_end = volumes[-1].get("end_ch", volumes[-1]["start_ch"] + 29)
    
    print("\n" + "="*60)
    print(f"🚀 自动写作模式")
    print(f"   合格线: {min_score}/10（黄金三章: {golden_score}/10）| 最大修订: {max_revise_rounds}轮")
    print(f"   章节: {actual_start} → {actual_end}")
    print(f"   已有章节: {sorted(existing_chapters)[:10]}{'...' if len(existing_chapters)>10 else ''}")
    print("="*60)
    
    # === 章节依赖检查 ===
    if actual_start > 1 and (actual_start - 1) not in existing_chapters:
        print(f"\n❌ 错误: 第 {actual_start - 1} 章不存在！")
        print(f"   写第 {actual_start} 章需要第 {actual_start - 1} 章作为上下文衔接。")
        print(f"   请先写前面的章节，或者从第1章开始。")
        print(f"   如需重写已有章节: --start-chapter={actual_start} --force")
        return
    
    # === 遍历章节写正文 ===
    ch = actual_start
    while ch <= actual_end:
        # 找到当前章节所属的卷
        vol_info = None
        for v in volumes:
            if ch >= v["start_ch"] and ch <= v.get("end_ch", v["start_ch"] + 29):
                vol_info = v
                break
        
        if vol_info is None:
            print(f"⚠️  第 {ch} 章不在任何卷范围内，跳过")
            ch += 1
            continue
        
        vol_num = vol_info["volume"]
        vol_title = vol_info.get("title", f"第{vol_num}卷")
        
        # === 确保卷纲存在 ===
        vol_outline_path = OUTPUT_DIR / f"volume_{vol_num:02d}.md"
        if not vol_outline_path.exists():
            print(f"\n📋 第 {vol_num} 卷卷纲不存在，正在生成...")
            phase_volume(client, vol_num)
        
        # === 跳过已存在的章节（除非force） ===
        ch_path = CHAPTERS_DIR / f"ch_{ch:02d}.md"
        if ch in existing_chapters and not force:
            print(f"⏭️  第 {ch} 章已存在，跳过（--force 可重写）")
            ch += 1
            continue
        
        # === 章节依赖：写前确认上一章存在 ===
        if ch > 1 and (ch - 1) not in existing_chapters:
            print(f"⏸️  第 {ch - 1} 章未写，无法继续。请先写前面的章节。")
            break
        
        print(f"\n{'─'*50}")
        print(f"📝 第 {vol_num} 卷 第 {ch} 章 | {vol_title}")
        print(f"{'─'*50}")
        
        # 更新 state
        state = load_state()
        state["sub_state"]["current_volume"] = vol_num
        state["sub_state"]["current_chapter"] = ch
        save_state(state)
        
        passed = False
        score = 0
        best_score = 0
        best_text = None
        revise_round = 0
        
        # 黄金三章用更高的合格线
        is_golden_ch = ch <= 3
        ch_min_score = golden_score if is_golden_ch else min_score
        if is_golden_ch:
            print(f"👑 黄金三章，合格线: {ch_min_score}/10")
            
            # 检查是否已有通过标记
            pass_flag = CHAPTERS_DIR / f"ch_{ch:02d}.passed"
            if not force and pass_flag.exists():
                print(f"⏭️  已有通过标记，跳过")
                continue
            
            # 步骤1: 写初稿
            try:
                client.set_phase(f"draft_ch{ch}")
                phase_draft(client, ch, volume_num=vol_num)
            except TokenBudgetExceeded as e:
                print(f"\n🛑 预算耗尽！{e}")
                client.print_usage()
                return
            except Exception as e:
                print(f"✗ 初稿失败: {e}")
                continue
            
            # 步骤2+3: 评估（使用统一的 _evaluate_chapter）
            eval_result = {}
            try:
                client.set_phase(f"eval_ch{ch}")
                eval_result = _evaluate_chapter(client, ch, verbose=True)
                score = eval_result.get('chapter_score', 0)
            except TokenBudgetExceeded as e:
                print(f"\n🛑 预算耗尽！{e}")
                client.print_usage()
                return
            except Exception as e:
                print(f"⚠️  评估失败: {e}")
                score = 7.0  # 评估异常时给保守分，不触发修订
                eval_result = {"chapter_score": score, "top_revisions": []}
            
            # v0.9.7: 记录初稿为候选最佳版本
            chapter_path_init = CHAPTERS_DIR / f"ch_{ch:02d}.md"
            if chapter_path_init.exists() and score > best_score:
                best_score = score
                best_text = load_file(chapter_path_init)
            
            # 步骤4: 修订循环（手术简报驱动：评估→简报→修订）
            while score < ch_min_score and revise_round < max_revise_rounds:
                revise_round += 1
                print(f"🔧 第 {ch} 章 — 修订第 {revise_round} 轮 (当前 {score}/10)")
                
                # v0.9.4: 手术简报——把评估JSON翻译成精确施工指令
                try:
                    client.set_phase(f"surgery_ch{ch}_r{revise_round}")
                    
                    chapter_path_surg = CHAPTERS_DIR / f"ch_{ch:02d}.md"
                    original_text_surg = load_file(chapter_path_surg) if chapter_path_surg.exists() else ""
                    
                    # 把eval_result转成JSON字符串给简报prompt
                    import json as _json
                    # 清理eval_result中的内部字段
                    brief_input = {k: v for k, v in eval_result.items() if not k.startswith('_')}
                    judge_json_str = _json.dumps(brief_input, ensure_ascii=False, indent=2)
                    
                    surgery_prompt = safe_format(SURGERY_BRIEF_PROMPT,
                        judge_json_output=judge_json_str,
                        original_chapter_text=original_text_surg,
                    )
                    
                    revision_brief = client.call_model("chapter_revision", surgery_prompt, max_tokens=4000, system_prompt=SYSTEM_PROMPT_SURGEON)
                    print(f"  📋 手术简报已生成")
                    # 打印简报摘要
                    for line in revision_brief.split('\n')[:8]:
                        if line.strip():
                            print(f"    {line.strip()[:80]}")
                    
                except TokenBudgetExceeded as e:
                    print(f"\n🛑 预算耗尽！{e}")
                    client.print_usage()
                    return
                except Exception as e:
                    print(f"⚠️ 手术简报生成失败: {e}，回退到直接修订")
                    # 回退：用top_revisions作为revision_brief
                    top_revisions = eval_result.get('top_revisions', []) or eval_result.get('top_3_revisions', [])
                    if top_revisions:
                        revision_brief = "\n".join([f"{i+1}. {r}" for i, r in enumerate(top_revisions[:3])])
                    else:
                        revision_brief = f"本章评分{score}/10，低于合格线{ch_min_score}。请提升最低分维度、修复逻辑问题、减少AI味表达。"
                
                # 使用评估意见驱动修订
                try:
                    client.set_phase(f"revision_ch{ch}_r{revise_round}")
                    
                    # 读取当前章节
                    chapter_path = CHAPTERS_DIR / f"ch_{ch:02d}.md"
                    old_text = load_file(chapter_path) if chapter_path.exists() else ""
                    
                    # 读取上下文
                    voice_rev = load_file(OUTPUT_DIR / "voice.md")
                    characters_rev = load_file(OUTPUT_DIR / "characters.md")
                    world_rev = load_file(OUTPUT_DIR / "world.md")
                    
                    # 获取上章结尾
                    prev_ch_rev_path = CHAPTERS_DIR / f"ch_{ch-1:02d}.md"
                    prev_tail_rev = load_file(prev_ch_rev_path)[-500:] if prev_ch_rev_path.exists() else ""
                    
                    # v0.9.5: 用safe_format替代str.format
                    revision_prompt = safe_format(REVISION_PROMPT,
                        chapter_num=ch,
                        revision_brief=revision_brief,
                        voice=voice_rev[:1500] if voice_rev else "",
                        characters=characters_rev[:1500] if characters_rev else "",
                        world=world_rev[:1500] if world_rev else "",
                        prev_tail=prev_tail_rev,
                        next_head="",
                        old_text=old_text,
                    )
                    
                    revised_text = client.call_model("chapter_revision", revision_prompt, max_tokens=12000, system_prompt=SYSTEM_PROMPT_EDITOR)
                    
                    # 保存修订版
                    if chapter_path.exists():
                        backup_path = CHAPTERS_DIR / f"ch_{ch:02d}_original.md"
                        if not backup_path.exists():
                            import shutil
                            shutil.copy2(chapter_path, backup_path)
                    save_file(chapter_path, revised_text)
                    print(f"  已保存修订版 (第{revise_round}轮)")
                    
                except TokenBudgetExceeded as e:
                    print(f"\n🛑 预算耗尽！{e}")
                    client.print_usage()
                    return
                except Exception as e:
                    print(f"✗ 修订失败: {e}")
                    break
                    
                # 重新评估（用统一的 _evaluate_chapter）
                try:
                    client.set_phase(f"eval_ch{ch}_r{revise_round}")
                    eval_result = _evaluate_chapter(client, ch, verbose=False)
                    score = eval_result.get('chapter_score', 0)
                    print(f"   修订后评分: {score}/10")
                    # v0.9.7: 记录最高分版本
                    chapter_path_rev = CHAPTERS_DIR / f"ch_{ch:02d}.md"
                    if chapter_path_rev.exists() and score > best_score:
                        best_score = score
                        best_text = load_file(chapter_path_rev)
                except Exception as e:
                    print(f"⚠️  重评失败: {e}")
                    score = 0  # v0.9.4: 重评失败设0分，让降级放行逻辑接管
                    break
            
            # v0.9.7: 超限且分数不够时，恢复最高分版本
            if not passed and best_text and best_score > score:
                chapter_path_final = CHAPTERS_DIR / f"ch_{ch:02d}.md"
                save_file(chapter_path_final, best_text)
                score = best_score
                print(f"📋 第 {ch} 章 — 恢复最高分版本 ({best_score}/10)")
            
            # 判定结果
            forced = False
            if score >= ch_min_score:
                passed = True
                print(f"✅ 第 {ch} 章通过！({score}/10)")
            elif revise_round >= max_revise_rounds:
                # 超限降级放行
                forced = True
                should_force = should_force_pass(state, ch)
                if should_force:
                    print(f"⚠️  第 {ch} 章降级放行（已达最大修订轮数）")
                    passed = True
                else:
                    print(f"❌ 第 {ch} 章未通过 ({score}/10)")
            else:
                print(f"❌ 第 {ch} 章未通过 ({score}/10)")
            
            # 记录章节完成
            if passed:
                record_chapter_done(state, ch, score, True, forced)
                
                # 写通过标记
                pass_flag = CHAPTERS_DIR / f"ch_{ch:02d}.passed"
                pass_flag.write_text(f"score={score}\nrounds={revise_round}\n", encoding="utf-8")
                
                # 将本章加入已有集合（供后续章节依赖检查）
                existing_chapters.add(ch)
                
                # 轻量更新典据（正则扫描新角色名/地名）
                _light_canon_update(ch)
        
        # 检查本卷是否全部写完
        vol_start = vol_info["start_ch"]
        vol_end = vol_info.get("end_ch", vol_start + 29)
        vol_all_done = all(c in existing_chapters for c in range(vol_start, vol_end + 1))
        
        if vol_all_done and ch >= vol_end:
            # 本卷写完：API深度更新典据
            print(f"\n📚 第 {vol_num} 卷完成，更新典据...")
            vol_chapters = list(range(vol_start, vol_end + 1))
            try:
                phase_canon_update(client, vol_chapters)
            except Exception as e:
                print(f"⚠️  典据更新失败: {e}")
            
            # 典据GC
            if canon_gc_enabled:
                print(f"\n🗑️  执行典据GC...")
                try:
                    phase_canon_gc(client, vol_num + 1)
                except Exception as e:
                    print(f"⚠️  典据GC失败: {e}")
            
            set_volume_status(state, vol_num, "completed", vol_end - vol_start + 1, vol_end - vol_start + 1)
            save_state(state)
            print(f"\n🎉 第 {vol_num} 卷完成！")
        
        ch += 1
    
    # 最终统计
    print("\n" + "="*60)
    print(f"🏁 自动写作完成")
    print("="*60)
    client.print_usage()


def _light_canon_update(chapter_num: int):
    """
    轻量更新典据：使用正则扫描新角色名/地名
    不需要调用API，快速执行
    """
    ch_file = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    if not ch_file.exists():
        return
    
    content = load_file(ch_file)
    new_entries = []
    
    # 扫描新角色名（常见模式：引号内的对话）
    dialogue_pattern = re.compile(r'[""'']([^""'']{2,8})[""'']')
    potential_names = dialogue_pattern.findall(content)
    
    # 扫描地名（常见模式：来到、到达、前往等后面的地名）
    location_pattern = re.compile(r'(?:来到|到达|前往|进入|离开|穿过)\s*([^\s，。！？]{2,6})')
    potential_locations = location_pattern.findall(content)
    
    # 如果发现新条目，可以追加到 canon.md
    if new_entries:
        canon_path = OUTPUT_DIR / "canon.md"
        existing_canon = load_file(canon_path)
        updated_canon = existing_canon + "\n" + "\n".join(new_entries)
        save_file(canon_path, updated_canon)

# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="AutoNovel-CN: 番茄小说AI辅助创作工具"
    )
    
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="显示版本号"
    )
    
    parser.add_argument(
        "--phase",
        type=str,
        choices=["seed", "world", "voice", "characters", "outline", "outline-extend",
                 "mystery", "canon", "canon-update", "canon-gc",
                 "foundation", "volume", "draft", "evaluate",
                 "autowrite", "full", "blurb", "status"],
        default="seed",
        help="要执行的阶段"
    )
    
    parser.add_argument(
        "--chapter",
        type=int,
        default=None,
        help="章节号（用于 draft 阶段）"
    )
    
    parser.add_argument(
        "--volume", "-V",
        type=int,
        default=1,
        help="卷号（用于 volume 阶段，默认第1卷）"
    )
    
    parser.add_argument(
        "--start-chapter",
        type=int,
        default=None,
        help="起始章节号（用于 autowrite 阶段，不指定则从state断点续传）"
    )
    
    parser.add_argument(
        "--end-chapter",
        type=int,
        default=None,
        help="结束章节号（用于 autowrite 阶段，不指定则写到最后）"
    )
    
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="生成的概念数量（seed 阶段）"
    )
    
    parser.add_argument(
        "--riff",
        type=str,
        default=None,
        help="基于已有概念扩展（seed 阶段）"
    )
    
    parser.add_argument(
        "--chapter-count",
        type=int,
        default=None,
        help="大纲总章节数"
    )
    
    parser.add_argument(
        "--extend-count",
        type=int,
        default=None,
        help="续写大纲的章节数（配合 --phase=outline-extend 使用，默认30）"
    )
    
    parser.add_argument(
        "--eval-phase",
        type=str,
        choices=["foundation", "chapter", "full"],
        default="foundation",
        help="评估阶段"
    )
    
    parser.add_argument(
        "--writer-api",
        type=str,
        default=None,
        help="指定写作 API"
    )
    
    parser.add_argument(
        "--judge-api",
        type=str,
        default=None,
        help="指定审核 API"
    )
    
    parser.add_argument(
        "--budget",
        type=float,
        default=None,
        help="全局 token 预算（千tokens），如 --budget=200 表示最多 200k tokens"
    )
    
    parser.add_argument(
        "--extra-requirements",
        type=str,
        default=None,
        help="额外要求/约束（注入到对应阶段prompt末尾，如\"金手指必须是XX\"）"
    )
    
    parser.add_argument(
        "--revision-note",
        type=str,
        default=None,
        help="修订意见（对已生成内容的人工反馈，用于局部修订）"
    )
    
    parser.add_argument(
        "--no-cost",
        action="store_true",
        help="不显示每次调用的费用估算"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制执行（忽略 state 检查）"
    )
    
    args = parser.parse_args()
    
    if args.version:
        print(f"AutoNovel-CN {_VERSION}")
        sys.exit(0)
    
    # 初始化客户端
    client = APIClient(
        default_writer_api=args.writer_api,
        default_judge_api=args.judge_api
    )
    
    # Token 预算控制 - 优先级：命令行 > config.yaml > config.py默认值
    yaml_cfg = load_config_yaml()
    if args.budget:
        client.set_budget(args.budget * 1000)
    elif yaml_cfg.get("token_budget_k", 0) > 0:
        client.set_budget(yaml_cfg["token_budget_k"] * 1000)
    
    # 单阶段限额 - 从 yaml 覆盖 config.py 的环境变量默认值
    if yaml_cfg.get("per_phase_limit_k", 0) > 0:
        client._per_phase_limit = yaml_cfg["per_phase_limit_k"] * 1000
    
    # 单章修订限额 - 暂存到 client 属性供后续使用
    if yaml_cfg.get("per_chapter_revision_limit_k", 0) > 0:
        client._per_chapter_revision_limit = yaml_cfg["per_chapter_revision_limit_k"] * 1000

    if args.no_cost:
        client.show_cost = False
    
    # 显示状态
    if args.phase == "status":
        state = load_state()
        print_state(state)
        sys.exit(0)
    
    # 执行对应阶段
    try:
        if args.phase == "seed":
            phase_seed(client, count=args.count, riff=args.riff, extra_requirements=args.extra_requirements)
        
        elif args.phase == "world":
            phase_world(client, extra_requirements=args.extra_requirements, revision_note=args.revision_note)
        
        elif args.phase == "voice":
            phase_voice(client, extra_requirements=args.extra_requirements)
        
        elif args.phase == "characters":
            phase_characters(client, extra_requirements=args.extra_requirements, revision_note=args.revision_note)
        
        elif args.phase == "outline":
            phase_outline(client, extra_requirements=args.extra_requirements, revision_note=args.revision_note)
        
        elif args.phase == "mystery":
            phase_mystery(client, extra_requirements=args.extra_requirements)
        
        elif args.phase == "canon":
            phase_canon(client)
        
        elif args.phase == "canon-update":
            phase_canon_update(client)
        
        elif args.phase == "canon-gc":
            phase_canon_gc(client, next_volume=args.volume)
        
        elif args.phase == "foundation":
            phase_foundation(client, force=args.force)
        
        elif args.phase == "volume":
            phase_volume(client, volume_num=args.volume)
        
        elif args.phase == "draft":
            if args.chapter is None:
                print("错误: draft 阶段需要指定 --chapter 参数")
                sys.exit(1)
            phase_draft(client, args.chapter)
        
        elif args.phase == "evaluate":
            phase_evaluate(client, phase=args.eval_phase, chapter=args.chapter if hasattr(args, 'chapter') and args.chapter else None)
        
        elif args.phase == "autowrite":
            phase_autowrite(client, start_volume=args.volume, start_chapter=args.start_chapter, end_chapter=args.end_chapter, force=args.force)
        
        elif args.phase == "blurb":
            phase_blurb(client)
        
        elif args.phase == "full":
            run_full_pipeline(client, chapter_count=args.chapter_count)
        
        else:
            print(f"未知阶段: {args.phase}")
            sys.exit(1)
    
    except TokenBudgetExceeded as e:
        print(f"\n🛑 Token 预算耗尽: {e}")
        client.print_usage()
        sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(0)
    
    except Exception as e:
        print(f"\n❌ 执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import sys
    main()
