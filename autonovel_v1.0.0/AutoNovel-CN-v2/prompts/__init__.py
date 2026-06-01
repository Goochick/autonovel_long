"""
AutoNovel-CN Prompt Package
==========================
版本: v1.0.0 | 更新: 2026-06-01

本包已从 prompts_cn.py 拆分为多个独立文件：
- seed.py       : 种子概念生成
- world.py      : 世界观构建
- mystery.py    : 核心悬疑设计
- voice.py      : 语声档案
- characters.py : 角色设定
- outline.py    : 大纲生成
- draft.py      : 章节撰写
- evaluate.py   : 评估审核
- revise.py     : 章节修订
- canon.py      : 典据管理
- review.py     : 审阅
- shared.py     : 共享常量（禁用词表等）

向后兼容：重新导出所有变量名，旧代码无需修改即可工作。
"""

# ============================================================
# 导入所有模块
# ============================================================

from . import shared
from . import seed
from . import world
from . import mystery
from . import voice
from . import characters
from . import outline
from . import draft
from . import evaluate
from . import revise
from . import canon
from . import review

# ============================================================
# 共享常量（向后兼容）
# ============================================================

SYSTEM_PROMPT_WRITER = shared.SYSTEM_PROMPT_WRITER
TIER1_BANNED_WORDS = shared.TIER1_BANNED_WORDS
TIER2_SUSPICIOUS_WORDS = shared.TIER2_SUSPICIOUS_WORDS
TIER3_FILLER_PHRASES = shared.TIER3_FILLER_PHRASES
FICTION_AI_PATTERNS = shared.FICTION_AI_PATTERNS
SHUANG_KEYWORDS = shared.SHUANG_KEYWORDS
HOOK_TYPES = shared.HOOK_TYPES
BLURB_GENERATION_PROMPT = shared.BLURB_GENERATION_PROMPT
SYSTEM_PROMPT_BUILD_OUTLINE = shared.SYSTEM_PROMPT_BUILD_OUTLINE
BUILD_OUTLINE_PROMPT = shared.BUILD_OUTLINE_PROMPT
SYSTEM_PROMPT_ADVERSARIAL = shared.SYSTEM_PROMPT_ADVERSARIAL
ADVERSARIAL_EDIT_PROMPT = shared.ADVERSARIAL_EDIT_PROMPT
SYSTEM_PROMPT_ADVERSARIAL_JUDGE = shared.SYSTEM_PROMPT_ADVERSARIAL_JUDGE

# ============================================================
# Seed 阶段（向后兼容）
# ============================================================

SYSTEM_PROMPT_SEED = seed.SYSTEM_PROMPT_SEED
GENERATE_PROMPT = seed.GENERATE_PROMPT
RIFF_PROMPT = seed.RIFF_PROMPT

# ============================================================
# World 阶段（向后兼容）
# ============================================================

SYSTEM_PROMPT_WORLD = world.SYSTEM_PROMPT_WORLD
WORLD_BUILDING_URBAN = world.WORLD_BUILDING_URBAN
WORLD_BUILDING_REBIRTH = world.WORLD_BUILDING_REBIRTH
WORLD_BUILDING_FANTASY = world.WORLD_BUILDING_FANTASY
WORLD_BUILDING_BOSS = world.WORLD_BUILDING_BOSS
WORLD_BUILDING_PERIOD = world.WORLD_BUILDING_PERIOD
WORLD_BUILDING_POSTAPOC = world.WORLD_BUILDING_POSTAPOC
WORLD_BUILDING_GAME = world.WORLD_BUILDING_GAME
WORLD_BUILDING_MAP = world.WORLD_BUILDING_MAP
WORLD_BUILDING_CONSTRAINT_BLOCK = world.WORLD_BUILDING_CONSTRAINT_BLOCK
TAGS_WORLD_INSTRUCTION = world.TAGS_WORLD_INSTRUCTION

# ============================================================
# Mystery 阶段（向后兼容）
# ============================================================

SYSTEM_PROMPT_MYSTERY = mystery.SYSTEM_PROMPT_MYSTERY
MYSTERY_GENERATION_PROMPT = mystery.MYSTERY_GENERATION_PROMPT

# ============================================================
# Voice 阶段（向后兼容）
# ============================================================

SYSTEM_PROMPT_VOICE = voice.SYSTEM_PROMPT_VOICE
VOICE_GENERATION_PROMPT = voice.VOICE_GENERATION_PROMPT
SYSTEM_PROMPT_VOICE_ANALYSIS = voice.SYSTEM_PROMPT_VOICE_ANALYSIS
VOICE_ANALYSIS_PROMPT = voice.VOICE_ANALYSIS_PROMPT

# ============================================================
# Characters 阶段（向后兼容）
# ============================================================

SYSTEM_PROMPT_CHARACTERS = characters.SYSTEM_PROMPT_CHARACTERS
CHARACTER_GENERATION_PROMPT = characters.CHARACTER_GENERATION_PROMPT
TAGS_CHARACTER_INSTRUCTION = characters.TAGS_CHARACTER_INSTRUCTION
FEMALE_TENSION_RULES = characters.FEMALE_TENSION_RULES

# ============================================================
# Outline 阶段（向后兼容）
# ============================================================

SYSTEM_PROMPT_OUTLINE = outline.SYSTEM_PROMPT_OUTLINE
OUTLINE_GENERATION_PROMPT = outline.OUTLINE_GENERATION_PROMPT
OUTLINE_EXTEND_PROMPT = outline.OUTLINE_EXTEND_PROMPT
TAGS_OUTLINE_INSTRUCTION = outline.TAGS_OUTLINE_INSTRUCTION

# ============================================================
# Draft 阶段（向后兼容）
# ============================================================

SYSTEM_PROMPT_DRAFT = draft.SYSTEM_PROMPT_DRAFT
DRAFT_CHAPTER_PROMPT = draft.DRAFT_CHAPTER_PROMPT
GOLDEN_CHAPTERS_PROMPT = draft.GOLDEN_CHAPTERS_PROMPT
SEGMENT_CONTINUE_PROMPT = draft.SEGMENT_CONTINUE_PROMPT
SEGMENT_FINISH_PROMPT = draft.SEGMENT_FINISH_PROMPT
TAGS_DRAFT_INSTRUCTION = draft.TAGS_DRAFT_INSTRUCTION

# ============================================================
# Evaluate 阶段（向后兼容）
# ============================================================

SYSTEM_PROMPT_JUDGE = evaluate.SYSTEM_PROMPT_JUDGE
SYSTEM_PROMPT_FOUNDATION = evaluate.SYSTEM_PROMPT_FOUNDATION
FOUNDATION_PROMPT = evaluate.FOUNDATION_PROMPT
CHAPTER_PROMPT = evaluate.CHAPTER_PROMPT
FULL_NOVEL_PROMPT = evaluate.FULL_NOVEL_PROMPT
SYSTEM_PROMPT_FOUNDATION_FIX = evaluate.SYSTEM_PROMPT_FOUNDATION_FIX
FOUNDATION_FIX_PROMPT = evaluate.FOUNDATION_FIX_PROMPT

# ============================================================
# Revise 阶段（向后兼容）
# ============================================================

SYSTEM_PROMPT_SURGEON = revise.SYSTEM_PROMPT_SURGEON
SYSTEM_PROMPT_EDITOR = revise.SYSTEM_PROMPT_EDITOR
SYSTEM_PROMPT_REVISION = revise.SYSTEM_PROMPT_REVISION
SURGERY_BRIEF_PROMPT = revise.SURGERY_BRIEF_PROMPT
REVISION_PROMPT = revise.REVISION_PROMPT

# ============================================================
# Canon 阶段（向后兼容）
# ============================================================

SYSTEM_PROMPT_CANON = canon.SYSTEM_PROMPT_CANON
CANON_EXTRACTION_PROMPT = canon.CANON_EXTRACTION_PROMPT
CANON_UPDATE_PROMPT = canon.CANON_UPDATE_PROMPT
SYSTEM_PROMPT_CANON_GC = canon.SYSTEM_PROMPT_CANON_GC
CANON_GC_PROMPT = canon.CANON_GC_PROMPT
CANON_RETRIEVAL_PROMPT = canon.CANON_RETRIEVAL_PROMPT
CANON_CARD_TEMPLATE = canon.CANON_CARD_TEMPLATE

# ============================================================
# Review 阶段（向后兼容）
# ============================================================

SYSTEM_PROMPT_REVIEW = review.SYSTEM_PROMPT_REVIEW
REVIEW_PROMPT = review.REVIEW_PROMPT

# ============================================================
# Volume 阶段（向后兼容）
# ============================================================

from . import volume
SYSTEM_PROMPT_VOLUME = volume.SYSTEM_PROMPT_VOLUME
VOLUME_OUTLINE_PROMPT = volume.VOLUME_OUTLINE_PROMPT

# ============================================================
# 向后兼容：保留旧版 prompt 以备不时之需
# ============================================================

# 旧版大世界观 prompt（已废弃，但仍保留引用）
WORLD_BUILDING_PROMPT = """【已废弃】请使用 world.WORLD_BUILDING_* 系列模板"""

# 旧版 OUTLINE_PART2_PROMPT（已废弃）
OUTLINE_PART2_PROMPT = """【已废弃】请使用 outline.OUTLINE_EXTEND_PROMPT"""

__all__ = [
    # 共享
    'SYSTEM_PROMPT_WRITER',
    'TIER1_BANNED_WORDS',
    'TIER2_SUSPICIOUS_WORDS',
    'TIER3_FILLER_PHRASES',
    'FICTION_AI_PATTERNS',
    'SHUANG_KEYWORDS',
    'HOOK_TYPES',
    'BLURB_GENERATION_PROMPT',
    'SYSTEM_PROMPT_BUILD_OUTLINE',
    'BUILD_OUTLINE_PROMPT',
    'SYSTEM_PROMPT_ADVERSARIAL',
    'ADVERSARIAL_EDIT_PROMPT',
    'SYSTEM_PROMPT_ADVERSARIAL_JUDGE',
    # Seed
    'SYSTEM_PROMPT_SEED',
    'GENERATE_PROMPT',
    'RIFF_PROMPT',
    # World
    'SYSTEM_PROMPT_WORLD',
    'WORLD_BUILDING_URBAN',
    'WORLD_BUILDING_REBIRTH',
    'WORLD_BUILDING_FANTASY',
    'WORLD_BUILDING_BOSS',
    'WORLD_BUILDING_PERIOD',
    'WORLD_BUILDING_POSTAPOC',
    'WORLD_BUILDING_GAME',
    'WORLD_BUILDING_MAP',
    'TAGS_WORLD_INSTRUCTION',
    # Volume
    'SYSTEM_PROMPT_VOLUME',
    'VOLUME_OUTLINE_PROMPT',
    # Mystery
    'SYSTEM_PROMPT_MYSTERY',
    'MYSTERY_GENERATION_PROMPT',
    # Voice
    'SYSTEM_PROMPT_VOICE',
    'VOICE_GENERATION_PROMPT',
    'SYSTEM_PROMPT_VOICE_ANALYSIS',
    'VOICE_ANALYSIS_PROMPT',
    # Characters
    'SYSTEM_PROMPT_CHARACTERS',
    'CHARACTER_GENERATION_PROMPT',
    'TAGS_CHARACTER_INSTRUCTION',
    'FEMALE_TENSION_RULES',
    # Outline
    'SYSTEM_PROMPT_OUTLINE',
    'OUTLINE_GENERATION_PROMPT',
    'OUTLINE_EXTEND_PROMPT',
    'TAGS_OUTLINE_INSTRUCTION',
    # Draft
    'SYSTEM_PROMPT_DRAFT',
    'DRAFT_CHAPTER_PROMPT',
    'GOLDEN_CHAPTERS_PROMPT',
    'SEGMENT_CONTINUE_PROMPT',
    'SEGMENT_FINISH_PROMPT',
    'TAGS_DRAFT_INSTRUCTION',
    # Evaluate
    'SYSTEM_PROMPT_JUDGE',
    'SYSTEM_PROMPT_FOUNDATION',
    'FOUNDATION_PROMPT',
    'CHAPTER_PROMPT',
    'FULL_NOVEL_PROMPT',
    'SYSTEM_PROMPT_FOUNDATION_FIX',
    'FOUNDATION_FIX_PROMPT',
    # Revise
    'SYSTEM_PROMPT_SURGEON',
    'SYSTEM_PROMPT_EDITOR',
    'SYSTEM_PROMPT_REVISION',
    'SURGERY_BRIEF_PROMPT',
    'REVISION_PROMPT',
    # Canon
    'SYSTEM_PROMPT_CANON',
    'CANON_EXTRACTION_PROMPT',
    'CANON_UPDATE_PROMPT',
    'SYSTEM_PROMPT_CANON_GC',
    'CANON_GC_PROMPT',
    'CANON_RETRIEVAL_PROMPT',
    'CANON_CARD_TEMPLATE',
    # Review
    'SYSTEM_PROMPT_REVIEW',
    'REVIEW_PROMPT',
]
