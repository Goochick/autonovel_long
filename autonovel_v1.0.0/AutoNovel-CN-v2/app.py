"""
炼章 - AI小说创作工作台
基于 Streamlit 的 AutoNovel-CN Web 界面
v0.3 — 修复[ERR]误标、seed选择器解析、最高分保留
"""

import streamlit as st
import subprocess
import sys
import os
import time
import threading
import re
from pathlib import Path

st.set_page_config(
    page_title="炼章 - AI小说创作工具",
    page_icon="🦉",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs"
CHAPTERS_DIR = OUTPUT_DIR / "chapters"
_LOG_FILE = BASE_DIR / "outputs" / "_web_log.txt"

# ============================================================
# 日志工具
# ============================================================
def _write_log(msg: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def _read_logs() -> list[str]:
    if _LOG_FILE.exists():
        return _LOG_FILE.read_text(encoding="utf-8").splitlines()
    return []

def _clear_logs():
    if _LOG_FILE.exists():
        _LOG_FILE.unlink()

# ============================================================
# Session state
# ============================================================
if "running" not in st.session_state:
    st.session_state.running = False
if "current_phase" not in st.session_state:
    st.session_state.current_phase = ""
if "editing_file" not in st.session_state:
    st.session_state.editing_file = None

# ============================================================
# 子进程工具
# ============================================================
def _decode_line(line_bytes: bytes) -> str:
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return line_bytes.decode(enc).rstrip()
        except (UnicodeDecodeError, LookupError):
            continue
    return line_bytes.decode("utf-8", errors="replace").rstrip()


def run_pipeline(phase: str, extra_args: list = None):
    cmd = [sys.executable, str(BASE_DIR / "main.py"), f"--phase={phase}"]
    if extra_args:
        cmd.extend(extra_args)

    import time as _time
    run_id = f"{phase}_{int(_time.time())}"
    st.session_state.running = True
    st.session_state.current_phase = phase
    st.session_state._run_id = run_id
    _clear_logs()
    _write_log(f"[启动:{run_id}] 命令: {' '.join(cmd)}")

    def _run():
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            env_path = BASE_DIR / ".env"
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
                _write_log(f"[环境] 已加载 .env (DEEPSEEK_KEY={'已设置' if env.get('DEEPSEEK_API_KEY') else '未设置'})")
            else:
                _write_log("[警告] 未找到 .env 文件")

            _write_log(f"[工作目录] {BASE_DIR}")
            _write_log(f"[Python] {sys.executable}")

            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=str(BASE_DIR), env=env, bufsize=0,
            )
            st.session_state._proc_pid = proc.pid

            def _read_stderr():
                for line in proc.stderr:
                    text = _decode_line(line)
                    if text:
                        # 区分真实错误和日志：INFO/DEBUG/WARNING不标ERR
                        if any(kw in text for kw in [" ERROR ", " CRITICAL ", "Traceback", "Exception:", "Error:"]):
                            _write_log(f"[ERR] {text}")
                        elif any(kw in text for kw in [" INFO ", " DEBUG ", " WARNING "]):
                            _write_log(text)  # 日志级别的正常输出，不标红
                        else:
                            _write_log(text)  # 其他stderr内容也正常显示

            stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
            stderr_thread.start()

            for line in proc.stdout:
                text = _decode_line(line)
                if text:
                    _write_log(text)

            proc.wait()
            stderr_thread.join(timeout=5)
            _write_log(f"[完成:{run_id}] 退出码: {proc.returncode}")
        except Exception as e:
            _write_log(f"[错误:{run_id}] {type(e).__name__}: {e}")
        finally:
            st.session_state.running = False
            st.session_state._proc_pid = None

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def stop_pipeline():
    pid = st.session_state.get("_proc_pid")
    if pid:
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
            _write_log("[手动停止]")
        except ProcessLookupError:
            pass
    st.session_state.running = False


# ============================================================
# 文件读写
# ============================================================
def read_file(path: Path) -> str | None:
    if path.exists() and path.is_file():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            try:
                return path.read_text(encoding="utf-16")
            except Exception:
                return None
    return None


def save_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def get_phase_status() -> dict:
    return {
        "seed": (OUTPUT_DIR / "seed.md").exists(),
        "world": (OUTPUT_DIR / "world.md").exists(),
        "characters": (OUTPUT_DIR / "characters.md").exists(),
        "outline": (OUTPUT_DIR / "outline.md").exists(),
        "voice": (OUTPUT_DIR / "voice.md").exists(),
        "mystery": (OUTPUT_DIR / "mystery.md").exists(),
        "chapters": any(CHAPTERS_DIR.glob("ch_*.md")) if CHAPTERS_DIR.exists() else False,
    }


def get_chapter_list() -> list[Path]:
    if not CHAPTERS_DIR.exists():
        return []
    return sorted(CHAPTERS_DIR.glob("ch_*.md"))


def get_config_value(key: str, default: str = "") -> str:
    config_path = BASE_DIR / "config.yaml"
    if not config_path.exists():
        return default
    try:
        content = config_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith(f"{key}:"):
                val = line.split(":", 1)[1].strip().strip('"').strip("'")
                return val
    except Exception:
        pass
    return default


def get_config_list(key: str) -> list[str]:
    config_path = BASE_DIR / "config.yaml"
    if not config_path.exists():
        return []
    try:
        content = config_path.read_text(encoding="utf-8")
        in_key = False
        items = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{key}:"):
                in_key = True
                continue
            if in_key:
                if stripped.startswith("- "):
                    items.append(stripped[2:].strip('"').strip("'"))
                elif not stripped.startswith("#") and stripped and not stripped.startswith("-"):
                    break
        return items
    except Exception:
        return []


def parse_seeds(content: str) -> list[dict]:
    """解析seed.md中的多个种子概念，返回 [{title, content}] 列表"""
    seeds = []
    # 策略1: 按 ### 级标题分割（AI生成常用格式）
    parts = re.split(r'\n(?=###\s)', content)
    if len(parts) > 1:
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            # 跳过总结段（不含具体概念的段落）
            if re.match(r'^###?\s*(总结|汇总|说明|备注)', part):
                continue
            first_line = part.split("\n")[0][:80]
            title = re.sub(r'^#{1,4}\s*', '', first_line).strip() or f"概念 {i+1}"
            seeds.append({"title": title, "content": part})
        if seeds:
            return seeds
    
    # 策略2: 按数字编号分割（1. / 1） / 一、等）
    parts = re.split(r'\n(?=(?:\d+[\.\、）]\s))', content)
    if len(parts) > 1:
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            first_line = part.split("\n")[0][:80]
            title = re.sub(r'^[\d\.\、）#\s]+', '', first_line).strip() or f"概念 {i+1}"
            # 跳过总结段
            if any(kw in title for kw in ["总结", "汇总", "说明", "备注", "品类覆盖"]):
                continue
            seeds.append({"title": title, "content": part})
        if seeds:
            return seeds
    
    # 策略3: 没有明确分割，整篇作为一个
    return [{"title": "种子概念", "content": content.strip()}]


# ============================================================
# 通用阶段渲染器
# ============================================================
def render_phase_tab(
    phase_key: str,
    phase_label: str,
    file_name: str,
    prerequisite: str = None,
    prerequisite_status: bool = True,
    extra_requirements_help: str = None,
    supports_revision: bool = True,
):
    """
    通用阶段tab渲染，包含：前置输入、生成/重新生成、内容展示、在线编辑、人工修订
    
    phase_key: CLI命令行的phase名（如 world, characters, outline）
    phase_label: 显示名（如 世界观, 角色, 大纲）
    """
    file_path = OUTPUT_DIR / file_name
    content = read_file(file_path)

    col1, col2 = st.columns([2, 1])

    with col1:
        # 内容展示
        if content:
            # 如果正在编辑这个文件
            if st.session_state.editing_file == file_name:
                edited = st.text_area("📝 编辑内容", value=content, height=500, key=f"edit_{file_name}")
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    if st.button("💾 保存编辑", key=f"save_edit_{file_name}"):
                        save_file(file_path, edited)
                        st.session_state.editing_file = None
                        st.success("已保存")
                        st.rerun()
                with col_e2:
                    if st.button("❌ 取消", key=f"cancel_edit_{file_name}"):
                        st.session_state.editing_file = None
                        st.rerun()
            else:
                st.markdown(content)
                if st.button("✏️ 编辑", key=f"edit_btn_{file_name}"):
                    st.session_state.editing_file = file_name
                    st.rerun()
        else:
            if prerequisite and not prerequisite_status:
                st.info(f"⚠️ 需要先完成 {prerequisite} 阶段")
            else:
                st.info(f"还没有{phase_label}。在右侧填写要求后点击生成。")

    with col2:
        st.subheader("操作")

        # 前置输入
        extra_req = st.text_area(
            "💡 额外要求",
            placeholder="如：金手指必须是XX、不能有YY...",
            height=80,
            key=f"extra_{file_name}",
            help=extra_requirements_help or "生成前填写额外约束，会注入到AI的prompt中"
        )

        # 生成按钮
        btn_disabled = st.session_state.running or not prerequisite_status
        if content:
            if st.button(f"🔄 重新生成{phase_label}", disabled=btn_disabled, key=f"regen_{file_name}"):
                extra_args = []
                if extra_req:
                    extra_args.append(f"--extra-requirements={extra_req}")
                # 重新生成前删旧文件
                if file_path.exists():
                    file_path.unlink()
                run_pipeline(phase_key, extra_args if extra_args else None)
                st.rerun()
        else:
            if st.button(f"🎲 生成{phase_label}", disabled=btn_disabled, type="primary", key=f"gen_{file_name}"):
                extra_args = []
                if extra_req:
                    extra_args.append(f"--extra-requirements={extra_req}")
                run_pipeline(phase_key, extra_args if extra_args else None)
                st.rerun()

        # 人工修订（生成完才有）
        if content and supports_revision:
            st.divider()
            st.subheader("🔧 人工修订")
            revision_note = st.text_area(
                "修订意见",
                placeholder="如：角色B的动机不合理，改成XX...",
                height=80,
                key=f"revision_{file_name}",
                help="输入意见后点击提交，AI会基于已有内容局部修改"
            )
            if st.button("📝 提交修订", disabled=st.session_state.running or not revision_note,
                         key=f"submit_rev_{file_name}"):
                extra_args = [f"--revision-note={revision_note}"]
                if extra_req:
                    extra_args.append(f"--extra-requirements={extra_req}")
                run_pipeline(phase_key, extra_args)
                st.rerun()

        # 下载
        if content:
            st.download_button("📥 下载", content, file_name=file_name)


# ============================================================
# 侧边栏
# ============================================================
with st.sidebar:
    st.title("🦉 炼章")
    st.caption("AI小说创作工作台 v0.3")

    st.divider()

    # API Key 配置
    st.subheader("🔑 API 配置")
    env_path = BASE_DIR / ".env"
    existing_keys = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                existing_keys[k.strip()] = v.strip()

    deepseek_key = st.text_input(
        "DeepSeek API Key", type="password",
        value=existing_keys.get("DEEPSEEK_API_KEY", ""),
        help="必填",
    )
    dashscope_key = st.text_input(
        "DashScope API Key", type="password",
        value=existing_keys.get("DASHSCOPE_API_KEY", ""),
        help="选填，Qwen备用",
    )
    zhipu_key = st.text_input(
        "智谱 API Key", type="password",
        value=existing_keys.get("ZHIPU_API_KEY", ""),
        help="选填，GLM备用",
    )

    if st.button("💾 保存 API Key", key="save_env_btn"):
        env_content = f"""DEEPSEEK_API_KEY={deepseek_key}
DASHSCOPE_API_KEY={dashscope_key}
ZHIPU_API_KEY={zhipu_key}
"""
        env_path.write_text(env_content, encoding="utf-8")
        st.success("已保存")

    st.divider()

    # 项目进度
    st.subheader("📊 项目进度")
    status = get_phase_status()
    phase_labels = [
        ("🌱 种子", "seed"),
        ("🌍 世界观", "world"),
        ("👥 角色", "characters"),
        ("🔮 悬疑", "mystery"),
        ("🎤 语声", "voice"),
        ("📋 大纲", "outline"),
        ("✍️ 章节", "chapters"),
    ]
    for label, key in phase_labels:
        icon = "✅" if status.get(key) else "⬜"
        st.markdown(f"{icon} {label}")

    if status["chapters"]:
        n_chapters = len(get_chapter_list())
        st.caption(f"已生成 {n_chapters} 章")

    st.divider()

    # 快捷配置
    st.subheader("⚙️ 快捷配置")
    current_genre = get_config_value("genre", "都市脑洞")
    _genre_options = [
        "都市脑洞", "重生穿越", "玄幻仙侠", "豪门总裁", "年代种田",
        "废土末世", "游戏竞技", "异界后宫", "系统流", "种田经营",
        "古言宫斗", "悬疑推理", "无限流", "修真炼丹", "末世囤物资", "军事谍战",
        "✏️ 自定义...",
    ]
    _genre_idx = _genre_options.index(current_genre) if current_genre in _genre_options else len(_genre_options) - 1
    genre = st.selectbox("品类", _genre_options, index=_genre_idx)
    
    # 自定义品类输入
    if genre == "✏️ 自定义...":
        custom_genre = st.text_input("输入自定义品类", placeholder="如：赛博朋克、星际冒险...", key="custom_genre")
        if custom_genre:
            genre = custom_genre
        else:
            genre = current_genre  # 没填就用原来的

    current_tags = get_config_list("tags")
    all_tags = ["搞笑", "热血", "悬疑", "暗黑", "后宫", "纯爱", "脑洞", "群像", "复仇", "治愈", "讽刺", "冒险"]
    tags = st.multiselect("风格标签", all_tags, default=[t for t in current_tags if t in all_tags])

    if st.button("💾 保存配置", key="save_config_btn"):
        config_path = BASE_DIR / "config.yaml"
        if config_path.exists():
            content = config_path.read_text(encoding="utf-8")
            content = re.sub(r'genre:\s*"[^"]*"', f'genre: "{genre}"', content)
            tags_str = "\n".join(f'  - "{t}"' for t in tags)
            content = re.sub(
                r'tags:\s*\n(?:  - "[^"]*"\s*\n)*',
                f"tags:\n{tags_str}\n",
                content,
            )
            config_path.write_text(content, encoding="utf-8")
            st.success("配置已保存")


# ============================================================
# 主内容区
# ============================================================
st.title("🦉 炼章 - AI小说创作工作台")

# 检测运行完成
_log_lines_check = _read_logs()
_run_id = st.session_state.get("_run_id", "")
if _log_lines_check and st.session_state.running and _run_id:
    for line in _log_lines_check:
        if line.startswith(f"[完成:{_run_id}]") or line.startswith(f"[错误:{_run_id}]"):
            st.session_state.running = False
            break

# 运行状态
if st.session_state.running:
    st.warning(f"⏳ 正在运行: **{st.session_state.current_phase}** 阶段...")
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("🛑 停止", type="secondary", key="stop_btn"):
            stop_pipeline()
            st.rerun()
    with col2:
        if st.button("🔄 刷新", key="top_refresh_btn"):
            st.rerun()
    st.caption("💡 点击「🔄 刷新」查看最新进度")

# 日志
log_lines = _read_logs()
with st.expander("📜 运行日志", expanded=True):
    if log_lines:
        recent_lines = log_lines[-80:]
        log_text = "\n".join(recent_lines)
        st.code(log_text, language="log")
    else:
        st.caption("暂无日志")
    col_log1, col_log2 = st.columns(2)
    with col_log1:
        if st.button("🔄 刷新日志", key="log_refresh_btn"):
            st.rerun()
    with col_log2:
        if st.button("🗑️ 清空日志", key="log_clear_btn"):
            _clear_logs()
            st.rerun()
    if st.session_state.running:
        st.info("⏳ 运行中，点击「🔄 刷新日志」查看最新输出")
    elif log_lines:
        last_line = log_lines[-1]
        if "[完成:" in last_line:
            st.success("✅ 运行结束")
        elif "[错误:" in last_line:
            st.error("❌ 运行出错，请查看日志")

# ============================================================
# 阶段选项卡
# ============================================================
tab_seed, tab_world, tab_char, tab_outline, tab_write, tab_files = st.tabs(
    ["🌱 种子", "🌍 世界观", "👥 角色", "📋 大纲", "✍️ 写作", "📂 文件"]
)

# --- 种子阶段（特殊：有选择器）---
with tab_seed:
    st.header("🌱 种子概念")
    seed_content = read_file(OUTPUT_DIR / "seed.md")

    col1, col2 = st.columns([2, 1])

    with col1:
        if seed_content:
            # seed选择器：检测是否有多个概念
            seeds = parse_seeds(seed_content)
            if len(seeds) > 1:
                st.subheader("📋 请选择一个种子概念")
                # 用session_state记住选择（Streamlit按钮触发rerun后局部变量会重置）
                if "_pick_seed_idx" not in st.session_state:
                    st.session_state._pick_seed_idx = None
                
                # 如果上一轮点了"选这个"，现在保存
                if st.session_state._pick_seed_idx is not None:
                    idx = st.session_state._pick_seed_idx
                    if idx < len(seeds):
                        save_file(OUTPUT_DIR / "seed.md", seeds[idx]["content"])
                        st.session_state._pick_seed_idx = None
                        st.success(f"✅ 已选中概念 {idx + 1}")
                        st.rerun()
                    st.session_state._pick_seed_idx = None

                for i, s in enumerate(seeds):
                    with st.expander(f"概念 {i+1}: {s['title']}", expanded=(i == 0)):
                        st.markdown(s["content"][:2000])
                        if len(s["content"]) > 2000:
                            st.caption(f"... 共 {len(s['content'])} 字")
                        if st.button(f"✅ 选这个", key=f"pick_seed_{i}"):
                            st.session_state._pick_seed_idx = i
                            st.rerun()
            else:
                # 只有一个概念，直接展示
                if st.session_state.editing_file == "seed.md":
                    edited = st.text_area("📝 编辑内容", value=seed_content, height=500, key="edit_seed_md")
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        if st.button("💾 保存编辑", key="save_edit_seed"):
                            save_file(OUTPUT_DIR / "seed.md", edited)
                            st.session_state.editing_file = None
                            st.success("已保存")
                            st.rerun()
                    with col_e2:
                        if st.button("❌ 取消", key="cancel_edit_seed"):
                            st.session_state.editing_file = None
                            st.rerun()
                else:
                    st.markdown(seed_content)
                    if st.button("✏️ 编辑", key="edit_btn_seed"):
                        st.session_state.editing_file = "seed.md"
                        st.rerun()
        else:
            st.info("还没有种子概念。在右侧填写要求后点击生成，或直接手动输入。")

    with col2:
        st.subheader("操作")
        count = st.number_input("生成数量", min_value=1, max_value=10, value=5, key="seed_count")

        extra_req = st.text_area(
            "💡 额外要求",
            placeholder="如：想要穿越+后宫类型、不要修仙...",
            height=80,
            key="extra_seed",
            help="生成前的额外约束，注入到AI的prompt中"
        )

        if seed_content:
            if st.button("🔄 重新生成种子", disabled=st.session_state.running, key="regen_seed_btn"):
                extra_args = [f"--count={count}"]
                if extra_req:
                    extra_args.append(f"--extra-requirements={extra_req}")
                if (OUTPUT_DIR / "seed.md").exists():
                    (OUTPUT_DIR / "seed.md").unlink()
                run_pipeline("seed", extra_args)
                st.rerun()
        else:
            if st.button("🎲 生成种子", disabled=st.session_state.running, type="primary", key="gen_seed_btn"):
                extra_args = [f"--count={count}"]
                if extra_req:
                    extra_args.append(f"--extra-requirements={extra_req}")
                run_pipeline("seed", extra_args)
                st.rerun()

        st.divider()
        st.subheader("✍️ 直接写种子")
        st.caption("跳过AI生成，自己写种子概念")
        manual_seed = st.text_area("输入种子概念", height=200, key="manual_seed")
        if st.button("💾 保存", disabled=st.session_state.running, key="save_seed_btn") and manual_seed:
            save_file(OUTPUT_DIR / "seed.md", manual_seed)
            st.success("种子已保存")
            st.rerun()

        if seed_content:
            st.download_button("📥 下载种子", seed_content, file_name="seed.md")


# --- 世界观 ---
with tab_world:
    st.header("🌍 世界观")
    render_phase_tab(
        "world", "世界观", "world.md",
        prerequisite="种子", prerequisite_status=status["seed"],
        extra_requirements_help="如：金手指必须是XX、背景必须是古代、不能有YY...",
        supports_revision=True,
    )


# --- 角色 ---
with tab_char:
    st.header("👥 角色设定")
    render_phase_tab(
        "characters", "角色", "characters.md",
        prerequisite="世界观", prerequisite_status=status["world"],
        extra_requirements_help="如：女主必须独立有事业线、反派不能脸谱化...",
        supports_revision=True,
    )


# --- 大纲 ---
with tab_outline:
    st.header("📋 大纲")

    # 前置：悬疑和语声
    col_pre1, col_pre2 = st.columns(2)
    with col_pre1:
        mystery_content = read_file(OUTPUT_DIR / "mystery.md")
        st.subheader("🔮 悬疑设计")
        if mystery_content:
            with st.expander("查看", expanded=False):
                st.markdown(mystery_content)
        extra_mystery = st.text_area("悬疑额外要求", placeholder="如：终极反转要出人意料...",
                                      height=60, key="extra_mystery")
        if st.button("🔮 生成悬疑", disabled=st.session_state.running or not status["characters"], key="gen_mystery_btn"):
            args = []
            if extra_mystery:
                args.append(f"--extra-requirements={extra_mystery}")
            run_pipeline("mystery", args if args else None)
            st.rerun()

    with col_pre2:
        voice_content = read_file(OUTPUT_DIR / "voice.md")
        st.subheader("🎤 语声档案")
        if voice_content:
            with st.expander("查看", expanded=False):
                st.markdown(voice_content)
        extra_voice = st.text_area("语声额外要求", placeholder="如：对白要更接地气...",
                                    height=60, key="extra_voice")
        if st.button("🎤 生成语声", disabled=st.session_state.running or not status["characters"], key="gen_voice_btn"):
            args = []
            if extra_voice:
                args.append(f"--extra-requirements={extra_voice}")
            run_pipeline("voice", args if args else None)
            st.rerun()

    st.divider()

    # 大纲主体
    render_phase_tab(
        "outline", "大纲", "outline.md",
        prerequisite="角色", prerequisite_status=status["characters"],
        extra_requirements_help="如：第一卷节奏要快、不要虐主...",
        supports_revision=True,
    )


# --- 写作阶段 ---
with tab_write:
    st.header("✍️ 写作")

    col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
    with col_cfg1:
        st.number_input("普通章节合格线", min_value=3.0, max_value=10.0,
                        value=float(get_config_value("min_chapter_score", "5.5")), step=0.5, key="cfg_min_score")
    with col_cfg2:
        st.number_input("黄金三章合格线", min_value=5.0, max_value=10.0,
                        value=float(get_config_value("golden_chapter_score", "7.5")), step=0.5, key="cfg_golden_score")
    with col_cfg3:
        st.number_input("最大修订轮数", min_value=1, max_value=10,
                        value=int(get_config_value("max_revise_rounds", "5")), key="cfg_max_revise")

    st.divider()

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        start_vol = st.number_input("起始卷", min_value=1, value=1, key="start_vol")
        start_ch = st.number_input("起始章", min_value=1, value=1, key="start_ch")
        end_ch = st.number_input("结束章", min_value=0, value=0, help="0=写到最后一章", key="end_ch")
    with col_btn2:
        end_ch_arg = [] if end_ch == 0 else [f"--end-chapter={end_ch}"]
        if st.button("🚀 开始自动写作", disabled=st.session_state.running or not status["outline"],
                     type="primary", key="auto_write_btn"):
            run_pipeline("autowrite", [f"--volume={start_vol}", f"--start-chapter={start_ch}"] + end_ch_arg)
            st.rerun()
        if st.button("🔄 强制重写", disabled=st.session_state.running or not status["outline"], key="force_write_btn"):
            run_pipeline("autowrite", [f"--volume={start_vol}", f"--start-chapter={start_ch}", "--force"] + end_ch_arg)
            st.rerun()

    if not status["outline"]:
        st.warning("⚠️ 需要先完成大纲阶段")

    st.divider()

    chapters = get_chapter_list()
    if chapters:
        st.subheader(f"📖 已生成 {len(chapters)} 章")
        for ch_path in chapters:
            ch_name = ch_path.stem
            ch_num = ch_name.replace("ch_", "").split("_")[0]
            label = f"第 {int(ch_num)} 章" if ch_num.isdigit() else ch_name
            with st.expander(label):
                ch_content = read_file(ch_path)
                if ch_content:
                    st.markdown(ch_content[:3000])
                    if len(ch_content) > 3000:
                        st.caption(f"... 共 {len(ch_content)} 字")
                    st.download_button("📥 下载", ch_content, file_name=f"{ch_name}.md",
                                       key=f"dl_{ch_name}")


# --- 文件管理 ---
with tab_files:
    st.header("📂 文件管理")

    st.subheader("输出文件")
    output_files = []
    if OUTPUT_DIR.exists():
        for f in sorted(OUTPUT_DIR.iterdir()):
            if f.is_file() and f.suffix == ".md" and not f.name.startswith("_"):
                output_files.append(f)

    if output_files:
        for f in output_files:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.text(f.name)
            with col2:
                size_kb = f.stat().st_size / 1024
                st.text(f"{size_kb:.1f} KB")
            with col3:
                content = read_file(f)
                if content:
                    st.download_button("📥", content, file_name=f.name, key=f"dl_files_{f.name}")
    else:
        st.info("还没有输出文件")

    st.divider()
    st.subheader("章节文件")
    chapters = get_chapter_list()
    if chapters:
        if st.button("📦 打包下载所有章节", key="pack_chapters_btn"):
            import zipfile
            import io
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for ch_path in chapters:
                    content = read_file(ch_path)
                    if content:
                        zf.writestr(ch_path.name, content)
            zip_buffer.seek(0)
            st.download_button("📥 下载 ZIP", zip_buffer.getvalue(),
                               file_name="chapters.zip", mime="application/zip")

        for ch_path in chapters:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.text(ch_path.name)
            with col2:
                content = read_file(ch_path) or ""
                st.text(f"{len(content)} 字")
            with col3:
                if content:
                    st.download_button("📥", content, file_name=ch_path.name,
                                       key=f"dl_ch_{ch_path.name}")
    else:
        st.info("还没有章节文件")

    st.divider()
    st.subheader("评估日志")
    eval_dir = OUTPUT_DIR / "eval_logs"
    if eval_dir.exists():
        eval_files = sorted(eval_dir.glob("*.md"))
        if eval_files:
            for ef in eval_files[-10:]:
                with st.expander(ef.name):
                    content = read_file(ef)
                    if content:
                        st.code(content)
        else:
            st.info("没有评估日志")
    else:
        st.info("没有评估日志")

    st.divider()
    st.subheader("⚠️ 危险操作")
    col_clean1, col_clean2 = st.columns(2)
    with col_clean1:
        if st.button("🗑️ 清空章节文件", disabled=st.session_state.running, key="clear_ch_btn"):
            for ch in get_chapter_list():
                ch.unlink()
            st.success("章节文件已清空")
            st.rerun()
    with col_clean2:
        if st.button("🗑️ 清空所有输出", disabled=st.session_state.running, key="clear_all_btn"):
            import shutil
            if OUTPUT_DIR.exists():
                for f in OUTPUT_DIR.iterdir():
                    if f.is_file():
                        f.unlink()
                    elif f.is_dir():
                        shutil.rmtree(f)
            OUTPUT_DIR.mkdir(exist_ok=True)
            CHAPTERS_DIR.mkdir(exist_ok=True)
            st.success("所有输出已清空")
            st.rerun()
