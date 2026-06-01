# AutoNovel-CN

> 🎯 **下载即用** 的中文网文 AI 生成器 | 三级架构：主线 → 卷纲 → 正文 | 典据GC + 断点续传
> 版本: v1.0.0 | 更新: 2026-06-01

基于 DeepSeek/Qwen/GLM 等便宜中文 API，专注于**番茄小说平台**的 AI 辅助网文创作工具。

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 🆕 v1.0.0 更新 (2026-06-01)

**Prompt 体系架构重构**

| 改进项 | 说明 |
|--------|------|
| 📁 拆分 prompts | 从 prompts_cn.py（2417行）拆分为 13 个独立文件，每个阶段独立 |
| ✂️ System Prompt 精炼 | 所有 22 个 SYSTEM_PROMPT 从 200+ 字压缩到 50-150 字，只保留角色定位+硬性约束 |
| 🔧 共享约束提取 | 7 个 WORLD_BUILDING 模板共享约束块，消除重复代码 |
| 📝 User Prompt 精简 | 各 prompt 压缩 30-50%，重点放输出格式和关键约束 |
| 🎯 权重调整 | CHAPTER_PROMPT 情绪表达权重从 25% 调整到 20%，爽点密度提升到 25% |
| 📖 README 更新 | 新增 Prompt 架构文档 |

---

## 📁 Prompt 架构（v1.0.0 新设计）

### 文件结构

```
prompts/
├── __init__.py          # 包入口，向后兼容所有旧变量名
├── shared.py            # 共享常量：禁用词表、爽点关键词、钩子类型
├── seed.py             # 种子概念生成
├── world.py            # 世界观构建（7品类模板+共享约束）
├── volume.py           # 卷级大纲
├── mystery.py          # 核心悬疑（正文阶段禁止挂载！）
├── voice.py            # 语声档案
├── characters.py       # 角色设定
├── outline.py          # 大线大纲
├── draft.py           # 章节撰写（普通章节+黄金三章）
├── evaluate.py        # 评估审核（策划/单章/全书）
├── revise.py          # 章节修订（手术简报驱动）
├── canon.py           # 典据管理
├── review.py          # 审阅
└── prompts_cn_legacy.py # 旧版备份（仅供参考）

---

### 阶段-Prompt 对照表

| 阶段 | prompt文件 | system_prompt | user_prompt |
|------|-----------|---------------|-------------|
| seed | seed.py | SYSTEM_PROMPT_SEED | GENERATE_PROMPT |
| world | world.py | SYSTEM_PROMPT_WORLD | WORLD_BUILDING_* |
| volume | volume.py | SYSTEM_PROMPT_VOLUME | VOLUME_OUTLINE_PROMPT |
| mystery | mystery.py | SYSTEM_PROMPT_MYSTERY | MYSTERY_GENERATION_PROMPT |
| voice | voice.py | SYSTEM_PROMPT_VOICE | VOICE_GENERATION_PROMPT |
| characters | characters.py | SYSTEM_PROMPT_CHARACTERS | CHARACTER_GENERATION_PROMPT |
| outline | outline.py | SYSTEM_PROMPT_OUTLINE | OUTLINE_GENERATION_PROMPT |
| draft | draft.py | SYSTEM_PROMPT_DRAFT | DRAFT_CHAPTER_PROMPT / GOLDEN_CHAPTERS_PROMPT |
| evaluate | evaluate.py | SYSTEM_PROMPT_JUDGE | FOUNDATION_PROMPT / CHAPTER_PROMPT |
| revise | revise.py | SYSTEM_PROMPT_SURGEON / EDITOR / REVISION | SURGERY_BRIEF_PROMPT / REVISION_PROMPT |
| canon | canon.py | SYSTEM_PROMPT_CANON | CANON_EXTRACTION_PROMPT / UPDATE_PROMPT / GC_PROMPT |
| review | review.py | SYSTEM_PROMPT_REVIEW | REVIEW_PROMPT |

### 设计原则

1. **阶段隔离**：每个阶段只给模型看该阶段的 prompt，减少噪音干扰
2. **System Prompt 精炼**：只放角色定位+硬性约束（50-150字），不塞任务指令
3. **共享常量外置**：禁用词表、爽点关键词等共享内容放在 shared.py
4. **向后兼容**：`__init__.py` 重新导出所有旧变量名，旧代码无需修改

---

## 🆕 v0.9.0 更新 (历史版本)

| 新特性 | 说明 |
|--------|------|
| 🏷️ 品类分流世界观 | 都市不再写创世神话，5种品类各有专属世界观模板 |
| 🥇 黄金三章 | 前3章用专属prompt，爽点密度翻倍（4个/章），3秒抓人开头 |
| ✂️ 分段续写 | 每段约1200字，每段重新注入关键指令防遗忘 |
| 📦 精简注入 | 典据从全塞3000字→按章筛选最多2000字 |
| 🏷️ 风格标签体系 | config.yaml定义genre+tags，12种标签×4阶段影响 |
| 💃 女配性张力 | FEMALE_TENSION_RULES独立模块 |
| 📝 简介生成 | 独立阶段`--phase=blurb` |
| 🃏 典据卡片模板 | CANON_CARD_TEMPLATE约束典据格式统一 |

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    数据分层堆栈                           │
│                                                         │
│  Layer 5: voice.md        文风语气与特定词汇库（控制风格）  │
│  Layer 4: world.md        背景传说、地理历史（控制设定）    │
│  Layer 3: characters.md   角色登记册、人际关系（控制人物）  │
│  Layer 2: outline.md      主线大纲+卷级分卷（控制情节）    │
│        + volume_XX.md     卷级详细大纲（每卷独立文件）     │
│  Layer 1: chapters/       正文（ch_NN.md，单章独立）      │
│                                                         │
│  Cross-cutting: canon.md  典据热库（一致性校验核心）      │
│       archive_canon.md    典据冷库（过期设定归档）        │
│       state.json          状态机（驱动阶段流转）          │
└─────────────────────────────────────────────────────────┘
```

### 三级架构

```
主线大纲（全局，定卷定弧）
│  outline.md — 几个剧情弧、关键转折、伏笔总台账、结局方向
│
└→ 卷级大纲（每卷独立，逐章细化）
   │  volume_01.md — 本卷核心冲突、逐章详细大纲、钩子爽点
   │  volume_02.md
   │  ...
   │
   └→ 正文（按卷按章写作）
      │  chapters/ch_01.md
      │  chapters/ch_02.md
      │  ...
      │
      └→ 每章写完 → 轻量更新典据
         每卷写完 → 深度更新典据 → 典据GC → 进入下一卷
```

---

## 🚀 快速开始

### 第一步：填入 API Key

```bash
# 1. 复制配置文件
cp .env.example .env

# 2. 编辑 .env，填入你的 API Key
notepad .env   # Windows
# 或 nano .env  # Linux/Mac
```

**推荐 DeepSeek API**（便宜好用，30章约5-12元）：
- 注册：https://platform.deepseek.com/
- 生成用 DeepSeek V3，审核用 DeepSeek R1

其他可选：
- 阿里云 DashScope（Qwen）：https://dashscope.aliyuncs.com/
- 智谱 AI（GLM）：https://open.bigmodel.cn/

### 第二步：安装依赖

```bash
pip install -r requirements.txt
```

### 第三步：开始创作

```bash
# 查看当前状态
python main.py --phase=status

# 从种子开始，逐步推进
python main.py --phase=seed
```

---

## 📖 完整创作流程

### Phase 1：基础构建（不写任何正文）

这一阶段的目标是把世界观、角色和大纲的底层逻辑配平，**地基不稳不放行**。

```bash
# 1. 生成种子概念（10个创意，选1个）
python main.py --phase=seed

# 2. 世界观构建（按品类自动选模板）
python main.py --phase=world

# 3. 角色设定
python main.py --phase=characters

# 4. 语声档案（文风定义）
python main.py --phase=voice

# 5. 主线大纲（自动分卷，一弧一卷）
python main.py --phase=outline

# 6. 核心悬疑与终极底牌
python main.py --phase=mystery

# 7. 初始典据提取（从策划文档提取硬性事实）
python main.py --phase=canon

# 8. Foundation 评估循环
#    自动评估→定向修订最弱维度→重新评估
#    达标（基础7.5+设定7.0）才放行进入写作
#    最多5轮，超限也会放行（防止卡死）
python main.py --phase=foundation
```

### Phase 2：按卷写作（逐卷循环）

```bash
# 9. 生成第1卷详细大纲
python main.py --phase=volume --volume=1

# 10. 自动写第1卷
#     前3章走黄金三章专属prompt（高爽点密度）
#     后续章节分段续写（每段~1200字，防指令遗忘）
#     每章：写初稿→审阅→评估→修订（最多3轮）→典据更新
#     不通过3轮的降级放行，不会卡死整卷
python main.py --phase=autowrite

# 11. 第1卷写完，典据GC
#     🔴保留核心设定 → 🟡压缩次要记忆 → ⚪过期设定移入冷库
python main.py --phase=canon-gc

# 12. 回到第9步，下一卷
python main.py --phase=volume --volume=2
python main.py --phase=autowrite
python main.py --phase=canon-gc

# ... 重复直到所有卷写完
```

### Phase 3：收尾

```bash
# 生成番茄小说简介
python main.py --phase=blurb
```

### 断点续传

**任何阶段中断后，重跑同一条命令即可续传**，系统会从 `state.json` 读取当前位置：

```bash
# 中断后再跑，自动跳到当前卷当前章
python main.py --phase=autowrite

# 查看当前位置
python main.py --phase=status
```

---

## 🎮 命令速查

### --phase 阶段选项

| 阶段 | 命令 | 说明 |
|------|------|------|
| seed | `--phase=seed` | 生成种子概念 |
| world | `--phase=world` | 世界观构建（按品类自动分流） |
| characters | `--phase=characters` | 角色设定 |
| voice | `--phase=voice` | 语声档案（文风定义） |
| outline | `--phase=outline` | 主线大纲（自动分卷） |
| outline-extend | `--phase=outline-extend --extend-count=30` | 续写大纲30章 |
| mystery | `--phase=mystery` | 核心悬疑与终极底牌 |
| canon | `--phase=canon` | 初始典据提取 |
| canon-update | `--phase=canon-update` | 从已写章节更新典据 |
| canon-gc | `--phase=canon-gc` | 典据垃圾回收（卷间执行） |
| foundation | `--phase=foundation` | 地基评估循环 |
| volume | `--phase=volume --volume=1` | 生成第N卷详细大纲 |
| draft | `--phase=draft --chapter=1` | 单独写某章 |
| evaluate | `--phase=evaluate` | 评估 |
| autowrite | `--phase=autowrite` | 按卷自动写作（黄金三章+分段续写） |
| blurb | `--phase=blurb` | 生成番茄小说简介 |
| full | `--phase=full` | 完整Pipeline（一键全流程） |
| status | `--phase=status` | 查看当前项目状态（阶段、卷、章、评分） |

### 其他命令行参数

| 参数 | 缩写 | 说明 | 示例 |
|------|------|------|------|
| `--version` | `-v` | 显示版本号 | `python main.py -v` |
| `--chapter=N` | — | 章节号（draft阶段必填） | `--chapter=5` |
| `--volume=N` | `-V` | 卷号（volume阶段，默认1） | `--volume=2` |
| `--count=N` | — | 生成概念数量（seed阶段，默认5） | `--count=10` |
| `--riff=TEXT` | — | 基于已有概念扩展（seed阶段） | `--riff="末世+系统"` |
| `--chapter-count=N` | — | 大纲总章节数 | `--chapter-count=50` |
| `--extend-count=N` | — | 续写大纲章节数（outline-extend，默认30） | `--extend-count=30` |
| `--eval-phase=PHASE` | — | 评估阶段：foundation / chapter / full | `--eval-phase=chapter` |
| `--writer-api=API` | — | 指定写作API（覆盖config.yaml） | `--writer-api=deepseek_v3` |
| `--judge-api=API` | — | 指定审核API（覆盖config.yaml） | `--judge-api=deepseek_r1` |
| `--budget=N` | — | 全局token预算（千tokens） | `--budget=200` |
| `--no-cost` | — | 不显示每次调用的费用估算 | `--no-cost` |
| `--force` | — | 强制执行（忽略state检查） | `--force` |

### 常用组合示例

```bash
# 完整创作流程（半手动推荐）
python main.py --phase=seed --count=10
python main.py --phase=world
python main.py --phase=characters
python main.py --phase=voice
python main.py --phase=outline --chapter-count=60
python main.py --phase=mystery
python main.py --phase=canon
python main.py --phase=foundation
python main.py --phase=volume --volume=1
python main.py --phase=autowrite
python main.py --phase=canon-gc
python main.py --phase=blurb

# 一键全流程（省心但不可控）
python main.py --phase=full --budget=500

# 只跑写作，限制预算
python main.py --phase=autowrite --budget=200

# 强制重跑Foundation（忽略之前的评估结果）
python main.py --phase=foundation --force

# 手动写单章
python main.py --phase=draft --chapter=7

# 换个API跑大纲
python main.py --phase=outline --writer-api=qwen_max
```

---

## 🏷️ 风格标签体系 (v0.9.0)

在 `config.yaml` 中配置品类和标签，全流程自动适配：

```yaml
# 品类（决定世界观模板、核心节奏）
genre: "都市脑洞"

# 风格标签（影响角色/大纲/正文的写作风格）
tags:
  - 搞笑
  - 悬疑
  - 群像
```

### 支持的标签（12种）

| 标签 | 影响范围 | 说明 |
|------|---------|------|
| 搞笑 | 全流程 | 对白俏皮，情节反转，吐槽担当 |
| 悬疑 | 全流程 | 伏笔密集，信息差，反转优先 |
| 群像 | 角色+大纲 | 多线并行，各有弧光 |
| 热血 | 大纲+正文 | 升级打怪，燃点密集 |
| 后宫 | 角色+正文 | 女配性张力，暧昧氛围 |
| 纯爱 | 角色+正文 | 甜蜜互动，CP感 |
| 脑洞 | 世界观+大纲 | 设定新奇，逻辑自洽即可 |
| 黑暗 | 全流程 | 灰色地带，反英雄，道德模糊 |
| 治愈 | 全流程 | 温暖基调，日常向 |
| 权谋 | 大纲+正文 | 博弈布局，反转反转再反转 |
| 种田 | 世界观+大纲 | 稳步升级，经营积累 |
| 无敌 | 大纲+正文 | 主角碾压，爽感优先 |

### 女配性张力 (v0.9.0)

当 tags 含 `后宫`/`纯爱`/`热血` 时，自动追加 FEMALE_TENSION_RULES 到写作 prompt：
- 每个女配出场必有**画面感描写**（外貌+气质+标志性动作）
- 建立**吸引力标签**（清冷禁欲/妩媚/元气/知性等）
- 与男主的**互动张力**（暧昧/对峙/保护/竞争）
- 避免工具人化，每个女配有独立人格和动机

---

## 📚 典据系统

典据数据库是整个系统的**一致性校验核心**，记录所有硬性事实。

### 典据内容

- 角色姓名、年龄、外貌、能力
- 地点名称、地理位置
- 装备/物品、属性、获取章节
- 技能/能力、使用限制、成长条件
- 势力/组织、成员、关系
- 人物关系变化、原因和章节
- 时间线、重要事件

### 典据更新机制

| 时机 | 方式 | 说明 |
|------|------|------|
| 每章写完 | 轻量更新（正则扫描） | 自动检测新角色名、地名，无需API调用 |
| 每5-10章 | 深度更新（API调用） | 追踪装备变化、技能获取、关系进展 |
| 卷间 | 典据GC | 清理过期设定，精简上下文 |

### 典据GC（垃圾回收）

每卷写完后执行，将典据分为三类：

| 类别 | 处理方式 | 示例 |
|------|---------|------|
| 🔴 高权重常量 | 完整保留 | 主角等级、核心金手指、主线仇人 |
| 🟡 中权重记忆 | 压缩为一句话 | "张三：原XX宗弟子，第2卷已叛变" |
| ⚪ 低权重垃圾 | 移入冷库 archive_canon.md | 已死亡路人甲、废弃低级地图 |

**冷库不会物理删除**，只有当后续剧情涉及"历史旧账"时，才会临时检出冷库数据。

### 典据卡片模板 (v0.9.0)

新增 CANON_CARD_TEMPLATE 约束典据格式统一，每条典据按卡片格式记录：

```
【角色】姓名 | 年龄 | 外貌关键词 | 首次出场章节
  特征：...
  变化：第X章 → ...

【装备】名称 | 类型 | 属性 | 获取章节
  描述：...
```

### 精简注入 (v0.9.0)

写作时典据不再全塞，而是按当前章节筛选相关条目：
- 典据注入上限：2000字（原来3000字）
- 世界观/角色注入上限：1500字（原来2000字）
- 只注入当前章节相关角色、地点和事件

### 手动操作

```bash
# 从所有已写章节更新典据
python scripts/gen_canon.py --update --save

# 只更新最近10章
python scripts/gen_canon.py --update --from-chapter=21 --save

# 续写大纲30章
python scripts/gen_outline.py --extend 30 --save

# 单独写第5章
python scripts/draft_chapter.py 5 --save

# 审阅第3章并保存
python scripts/review.py 3 --save

# 修订第3章
python scripts/gen_revision.py 3 --save
```

---

## ⚙️ 配置说明

### config.yaml

```yaml
# ========== 品类与风格 (v0.9.0) ==========
# 品类配置（决定世界观模板）
genre: "都市脑洞"              # 都市脑洞/重生穿越/玄幻仙侠/豪门总裁/年代种田

# 风格标签（影响全流程写作风格）
tags:
  - 搞笑
  - 悬疑
  - 群像

# ========== 生成参数 ==========
chapter_count: 30            # 总章节数
words_per_chapter: 2000      # 每章字数
shuang_per_chapter: 3        # 每章小爽点数（黄金三章翻倍为4）

# ========== API 配置 ==========
writer_api: "deepseek_v3"    # 生成用
judge_api: "deepseek_r1"     # 审核用

# ========== Pipeline 控制 ==========
auto_revise: true            # 评估不通过时自动修订
max_revision_rounds: 3       # 最大修订轮数
min_chapter_score: 6.0       # 最低合格分

# ========== 卷级配置 ==========
chapters_per_volume: 30      # 每卷默认章数（实际由大纲决定）

# ========== 典据 GC 配置 ==========
canon_gc_enabled: true       # 卷间是否执行典据GC
canon_archive_enabled: true  # 是否启用冷库归档

# ========== Foundation 循环配置 ==========
foundation_pass_score: 7.5   # 基础评分放行线
lore_pass_score: 7.0         # 设定评分放行线
max_foundation_rounds: 5     # Foundation最大循环轮数

# ========== Token 预算控制 ==========
token_budget_k: 0            # 全局token预算（千tokens），0=不限
per_phase_limit_k: 200       # 单阶段token上限
per_chapter_revision_limit_k: 30  # 单章修订token上限
show_cost_estimate: true     # 是否显示每次调用费用估算
```

### .env 配置

```bash
# DeepSeek API（推荐）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx

# 备选 API
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxx
ZHIPU_API_KEY=xxxxxxxxxxxx

# API 路由（可选，不填用默认）
DEFAULT_WRITER_API=deepseek_v3
DEFAULT_JUDGE_API=deepseek_r1
```

---

## 🛡️ 安全机制

### Token 切片防护

- 所有文件读取经过 `safe_read()` 限制，单次不超过 20k 字符（约15k tokens）
- 长文本评估分批执行，每批5章
- 防止一次性吞吐几十万字导致上下文爆表

### 重试降级

- 每章评估修订最多3轮
- 超过3轮未通过 → 降级放行，记入 `force_passed` 列表
- 不会因为单章质量卡死整卷进度

### 逻辑欠债

- 写作时发现高层设定漏洞（如第7章突然需要空间传送规则，但世界观里没写）
- **不在正文里瞎编**，记录为"逻辑欠债"挂起
- 后续由 Foundation 循环或人工处理

### 断点续传

- 所有进度保存在 `outputs/state.json`
- 记录：当前阶段、卷号、章节号、评分、重试次数、逻辑欠债
- 中断后重跑同命令，自动从断点继续

---

## 📁 项目结构

```
AutoNovel-CN/
├── prompts/                  # Prompt 模板
│   ├── __init__.py
│   └── prompts_cn.py         # 中文网文 Prompt（v0.9.0: 品类分流+黄金三章+分段续写+标签体系+女配性张力）
├── api/                      # API 客户端
│   ├── __init__.py
│   └── api_client.py         # 统一 API 调用层（DeepSeek/Qwen/GLM）
├── scripts/                  # 创作脚本（可单独调用）
│   ├── seed.py               # 种子生成
│   ├── gen_world.py          # 世界观
│   ├── gen_characters.py     # 角色
│   ├── gen_outline.py        # 大纲（支持 --extend 续写）
│   ├── gen_canon.py          # 典据（支持 --update 更新）
│   ├── draft_chapter.py      # 章节撰写
│   ├── evaluate.py           # 评估
│   ├── review.py             # 审阅（--save 保存）
│   ├── gen_revision.py       # 修订
│   ├── adversarial_edit.py   # 对抗编辑
│   └── run_pipeline.py       # Pipeline（旧版）
├── outputs/                  # 生成内容
│   ├── state.json            # 状态机
│   ├── seed.md               # 种子
│   ├── world.md              # 世界观
│   ├── characters.md         # 角色
│   ├── voice.md              # 语声档案
│   ├── outline.md            # 主线大纲
│   ├── mystery.md            # 核心悬疑
│   ├── canon.md              # 典据热库
│   ├── archive_canon.md      # 典据冷库
│   ├── blurb.md              # 番茄简介（v0.9.0）
│   ├── volume_01.md          # 第1卷大纲
│   ├── volume_02.md          # 第2卷大纲
│   ├── chapters/             # 正文
│   │   ├── ch_01.md
│   │   └── ...
│   ├── reviews/              # 审阅意见
│   └── eval_logs/            # 评估日志
├── state_manager.py          # 状态机引擎
├── config.py                 # Python 配置
├── config.yaml               # YAML 配置（用户编辑）
├── .env.example              # 环境变量示例
├── requirements.txt          # Python 依赖
├── VERSION                   # 版本号
├── main.py                   # 入口文件（v0.9.0）
└── README.md
```

---

## 💰 费用估算

| 阶段 | Token 消耗 | DeepSeek 费用 |
|------|-----------|--------------|
| Phase 1 基础构建 | ~150k tokens | ~¥0.5-1 |
| Phase 2 每章写作+评估 | ~40-70k tokens | — |
| 30章全书 | ~1.2-2.1M tokens | ~¥5-12 |
| 典据GC（每卷1次） | ~20k tokens | ~¥0.1 |
| 简介生成（blurb） | ~5k tokens | ~¥0.03 |

**DeepSeek 定价参考**：
- V3：2元/百万输入，8元/百万输出
- R1：4元/百万输入，16元/百万输出
- R1评估一次约0.07元，1元≈62.5k输出tokens

**建议**：设置 token 预算防止超支：`python main.py --budget=500`（500k tokens 约2-3元）

---

## ❓ 常见问题

### Q: 已有旧版outputs，怎么升级？

不需要删，直接替换代码文件。新版兼容旧版 outputs 目录。跑 `python main.py --phase=status` 会自动识别已有进度。

### Q: Foundation 循环一直不达标怎么办？

最多5轮后会自动放行。你也可以 `python main.py --phase=foundation --force` 跳过检查。或者手动编辑 world.md / characters.md / outline.md 补强最弱维度。

### Q: 典据太大怎么办？

每卷写完后跑 `python main.py --phase=canon-gc`，会自动清理过期设定。冷库不删除，需要时可检出。v0.9.0起写作时典据按章筛选注入，不会全塞。

### Q: 支持哪些品类？

- ✅ 都市脑洞（世界观模板：隐藏规则型）
- ✅ 重生穿越（世界观模板：信息差型）
- ✅ 玄幻仙侠（世界观模板：传统宏大型）
- ✅ 豪门总裁（世界观模板：权力场型）
- ✅ 年代种田（世界观模板：时代红利型）

修改 `config.yaml` 中的 `genre` 即可切换。世界观构建时自动匹配对应模板。

### Q: 生成的文字有 AI 味吗？

内置了三级禁用词表 + AI味句式正则检测 + 对抗编辑。评估不通过会自动修订。但完全不AI味很难保证，建议人工过一遍。

### Q: 怎么控制Token花费？

```bash
# 方式1：命令行指定全局预算
python main.py --phase=autowrite --budget=200

# 方式2：config.yaml中设置单阶段上限
per_phase_limit_k: 200

# 方式3：关闭费用显示（省屏幕空间）
python main.py --no-cost
```

### Q: 黄金三章是什么？

番茄小说的读者留存主要看前3章。v0.9.0起，前3章自动使用专属GOLDEN_CHAPTERS_PROMPT：
- 爽点密度翻倍（4个/章 vs 普通3个/章）
- 3秒抓人开头（不铺垫直接进事件）
- 章末强钩子（必须让读者想翻下一章）

---

## 🔄 与原版 AutoNovel 的差异

| 特性 | 原版 AutoNovel | AutoNovel-CN v0.9 |
|------|--------------|-------------------|
| 目标平台 | 英文奇幻 | 中文网文（番茄） |
| 架构 | 单层大纲 | 三级架构：主线→卷纲→正文 |
| API | Anthropic | DeepSeek/Qwen/GLM |
| 评估维度 | 文学性 | 爽文节奏+反AI味 |
| 典据系统 | 静态提取 | 动态更新+GC+冷库+卡片模板+精简注入 |
| 状态机 | 无 | state.json + 断点续传 |
| Foundation循环 | 无 | 评估→定向修订→放行 |
| 逻辑欠债 | 无 | 挂起不瞎编 |
| Token防护 | 无 | safe_read切片+预算控制 |
| 重试降级 | 无 | 3轮降级放行 |
| 品类分流 | 无 | 5种品类×专属世界观模板 |
| 黄金三章 | 无 | 前3章高密度爽点专属prompt |
| 分段续写 | 无 | ~1200字/段，每段重新注入指令 |
| 风格标签 | 无 | 12种标签×4阶段指令体系 |
| 女配性张力 | 无 | 自动追加（后宫/纯爱/热血标签触发） |
| 简介生成 | 无 | 独立blurb阶段 |

---

## 🙏 致谢

- 基于 [AutoNovel](https://github.com/aomapjj/AutoNovel) 改造
