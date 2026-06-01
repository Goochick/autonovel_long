# AutoNovel-CN Prompt 体系

> 本目录包含 AutoNovel 中文网文版的所有 Prompt 模板
> 适用于番茄小说平台，替代原版英文奇幻小说的 Prompt 体系

## 文件结构

```
prompts/
├── prompts_cn.py    # 核心 Prompt 定义文件（本文件包含所有 Prompt 常量）
└── README.md        # 本文档
```

## Prompt 常量清单

### 通用 System Prompts

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_WRITER` | writer system | 生成类任务的 System Prompt |
| `SYSTEM_PROMPT_JUDGE` | judge system | 评估类任务的 System Prompt |
| `SYSTEM_PROMPT_EDITOR` | editor system | 编辑/修订类任务的 System Prompt |
| `SYSTEM_PROMPT_FOUNDATION` | foundation system | 基础策划评估的 System Prompt |

### seed.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_SEED` | call_writer system | 种子生成的 System |
| `GENERATE_PROMPT` | `GENERATE_PROMPT` | 生成多个小说概念 |
| `RIFF_PROMPT` | `RIFF_PROMPT` | 从已有想法扩展 |

### gen_world.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_WORLD` | call_writer system | 世界观生成的 System |
| `WORLD_BUILDING_PROMPT` | 内联 prompt | 生成完整世界观设定 |

### gen_characters.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_CHARACTERS` | call_writer system | 角色生成的 System |
| `CHARACTER_GENERATION_PROMPT` | 内联 prompt | 生成角色注册表 |

### gen_outline.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_OUTLINE` | call_writer system | 大纲生成的 System |
| `OUTLINE_GENERATION_PROMPT` | `prompt` | 生成章节大纲 |
| `OUTLINE_PART2_PROMPT` | 内联 prompt | 大纲后半部分续写 |

### draft_chapter.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_DRAFT` | call_writer system | 章节撰写的 System |
| `DRAFT_CHAPTER_PROMPT` | `prompt` | 章节撰写核心 Prompt |

### evaluate.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_JUDGE` | `call_judge` system | 评估 System |
| `FOUNDATION_PROMPT` | `FOUNDATION_PROMPT` | 基础策划评估 |
| `CHAPTER_PROMPT` | `CHAPTER_PROMPT` | 单章评估 |
| `FULL_NOVEL_PROMPT` | `FULL_NOVEL_PROMPT` | 全书评估 |

### review.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_REVIEW` | 内联 system | 审阅的 System |
| `REVIEW_PROMPT` | `REVIEW_PROMPT` | 文学审阅 Prompt |

### gen_revision.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_REVISION` | call_writer system | 章节修订的 System |
| `REVISION_PROMPT` | 内联 prompt | 章节重写 Prompt |

### gen_canon.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_CANON` | call_writer system | 典据提取的 System |
| `CANON_EXTRACTION_PROMPT` | 内联 prompt | 典据数据库提取 |

### build_outline.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_BUILD_OUTLINE` | 内联 system | 大纲结构化的 System |
| `BUILD_OUTLINE_PROMPT` | 内联 prompt | 章节大纲结构化 |

### adversarial_edit.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_ADVERSARIAL` | call_judge system | 对抗编辑的 System |
| `SYSTEM_PROMPT_ADVERSARIAL_JUDGE` | 内联 system | 对抗编辑判断的 System |
| `ADVERSARIAL_EDIT_PROMPT` | `EDIT_PROMPT` | 对抗性编辑 Prompt |

### voice_fingerprint.py 替换

| 常量名 | 对应原版 | 用途 |
|--------|---------|------|
| `SYSTEM_PROMPT_VOICE_ANALYSIS` | 内联 system | 语声分析的 System |
| `VOICE_ANALYSIS_PROMPT` | 内联分析 | 风格特征分析 |

## 辅助常量

### 反AI味检测表

| 常量名 | 用途 |
|--------|------|
| `TIER1_BANNED_WORDS` | Tier 1 禁用词表（立即删除） |
| `TIER2_SUSPICIOUS_WORDS` | Tier 2 可疑词表（集群检测） |
| `TIER3_FILLER_PHRASES` | Tier 3 填充短语（需删除） |
| `FICTION_AI_PATTERNS` | AI味句式正则表 |

### 爽点系统

| 常量名 | 用途 |
|--------|------|
| `SHUANG_KEYWORDS` | 爽点关键词词典（用于检测爽点密度） |
| `HOOK_TYPES` | 章末钩子类型定义 |

## 使用方法

### Python 导入

```python
from prompts.prompts_cn import (
    # System Prompts
    SYSTEM_PROMPT_WRITER,
    SYSTEM_PROMPT_JUDGE,
    SYSTEM_PROMPT_EDITOR,

    # Prompts with variables
    GENERATE_PROMPT,
    DRAFT_CHAPTER_PROMPT,
    FOUNDATION_PROMPT,

    # Constants
    TIER1_BANNED_WORDS,
    SHUANG_KEYWORDS,
    HOOK_TYPES,
)

# 使用示例
prompt = DRAFT_CHAPTER_PROMPT.format(
    chapter_num=5,
    title="都市最强系统",
    genre="都市脑洞",
    arc_name="初露锋芒",
    voice="...",
    world="...",
    characters="...",
    chapter_outline="...",
    prev_chapter_ending="...",
    next_chapter_intro="...",
    min_shuang_points=2,
    shuang_points_positions="开篇打脸、中段收获",
    target_words=2500
)
```

### Prompt 变量占位符说明

每个 Prompt 的 `.format()` 调用需要提供以下变量：

| Prompt | 必需变量 |
|--------|---------|
| `GENERATE_PROMPT` | `count` |
| `RIFF_PROMPT` | `idea` |
| `WORLD_BUILDING_PROMPT` | `genre`, `seed` |
| `CHARACTER_GENERATION_PROMPT` | `seed`, `world`, `genre` |
| `OUTLINE_GENERATION_PROMPT` | `seed`, `world`, `characters`, `genre`, `target_word_count`, `target_chapters`, `min_arcs`, `target_words_per_chapter` |
| `OUTLINE_PART2_PROMPT` | `last_chapter`, `total_chapters`, `min_foreshadows` |
| `DRAFT_CHAPTER_PROMPT` | 见上方示例 |
| `FOUNDATION_PROMPT` | `world`, `characters`, `outline`, `canon`, `genre` |
| `CHAPTER_PROMPT` | `chapter_num`, `chapter_text`, `chapter_outline`, `prev_chapter_tail`, `voice` |
| `FULL_NOVEL_PROMPT` | `title`, `genre`, `world_summary`, `characters`, `outline`, `chapter_summaries` |
| `REVIEW_PROMPT` | `title`, `manuscript` |
| `REVISION_PROMPT` | `chapter_num`, `revision_brief`, `voice`, `characters`, `world`, `prev_tail`, `next_head`, `old_text` |
| `CANON_EXTRACTION_PROMPT` | `seed`, `world`, `characters` |
| `BUILD_OUTLINE_PROMPT` | `chapter_num`, `title`, `word_count`, `chapter_text` |
| `ADVERSARIAL_EDIT_PROMPT` | `chapter_num`, `word_count` |
| `VOICE_ANALYSIS_PROMPT` | `chapter_text` |

## 与原版 AutoNovel 的主要差异

| 维度 | 原版 AutoNovel | AutoNovel-CN |
|------|---------------|--------------|
| 目标平台 | 英文奇幻小说 | 番茄小说平台 |
| 目标字数 | ~10万字 | 50-200万字 |
| 章节字数 | ~3000词 | ~2000字 |
| 品类 | 仅限奇幻 | 都市/玄幻/重生/年代等 |
| 核心节奏 | 文学性节奏 | 爽点密度 |
| 评估维度 | 文学质量为主 | 读者留存预测 |
| 禁用词表 | 英文slop词汇 | 中文AI味高频词 |
| 章末钩子 | 文学性留白 | 悬念/冲突中断 |
| 金手指 | 魔法体系 | 系统/重生/特殊体质 |

## 更新日志

- v1.0 (2024) - 初始版本，完成所有核心 Prompt 的中文化
