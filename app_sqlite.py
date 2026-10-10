"""
个人信息管理系统（Streamlit + SQLite3 版）
=========================================
基于 index.html 的全部功能，数据持久化改用 SQLite3 数据库。

启动方式：streamlit run app_sqlite.py
"""

import csv
import io
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

import streamlit as st

# ============================================================
# 路径定义（pathlib，禁止越界）
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "records.db"

# 固定类型选项（与 index.html 完全一致）
TYPE_OPTIONS = ["荣誉", "证书", "经历", "工作记录"]


# ============================================================
# SQLite3 数据层
# ============================================================
# 异常路径 1 — 数据库文件不存在：自动建目录 + 建表，空库可启动
# 异常路径 2 — 数据库为空（表无数据）：正常返回空列表
# 异常路径 3 — 数据库损坏（无法打开/表结构错误）：备份原文件 → 重建空库

def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（每次操作独立连接，用完即关）。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH))


def init_db() -> None:
    """初始化数据库：建表（若不存在）。首次启动自动调用。"""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT    NOT NULL,
                type      TEXT    NOT NULL,
                note      TEXT    DEFAULT '',
                create_time TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def load_records() -> list[dict]:
    """读取全部记录，返回字典列表（按 id 正序，与录入顺序一致）。"""
    # 路径 1：文件不存在 → 初始化后返回空
    if not DB_PATH.exists():
        init_db()
        return []

    try:
        conn = _get_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, name, type, note, create_time FROM records ORDER BY id"
        ).fetchall()
        conn.close()
        # 路径 2：空表 → 空列表
        return [dict(r) for r in rows]
    except sqlite3.DatabaseError:
        # 路径 3：数据库损坏 → 备份 + 重建
        _backup_and_rebuild()
        return []


def save_record(name: str, rec_type: str, note: str) -> None:
    """新增一条记录。"""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO records (name, type, note, create_time) VALUES (?, ?, ?, ?)",
            (name, rec_type, note, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        conn.commit()
    finally:
        conn.close()


def delete_record(record_id: int) -> None:
    """按 id 删除一条记录。"""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
    finally:
        conn.close()


def count_by_type() -> dict[str, int]:
    """统计各类型记录条数（用于简历模态框显示）。"""
    if not DB_PATH.exists():
        return {t: 0 for t in TYPE_OPTIONS}
    try:
        conn = _get_conn()
        counts = {}
        for t in TYPE_OPTIONS:
            row = conn.execute(
                "SELECT COUNT(*) FROM records WHERE type = ?", (t,)
            ).fetchone()
            counts[t] = row[0]
        conn.close()
        return counts
    except sqlite3.DatabaseError:
        return {t: 0 for t in TYPE_OPTIONS}


def _backup_and_rebuild() -> None:
    """数据库损坏时：备份原文件 → 删除 → 重建空库。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = DB_PATH.with_suffix(f".db.bak.{timestamp}")
    try:
        shutil.copy2(DB_PATH, bak_path)
    except Exception:
        pass
    try:
        DB_PATH.unlink()
    except Exception:
        pass
    init_db()


# ============================================================
# CSV 导入导出（与 index.html 逻辑一致）
# ============================================================
def export_csv() -> str:
    """导出全部记录为 CSV 字符串（带 BOM）。"""
    records = load_records()
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM
    writer = csv.writer(buf)
    writer.writerow(["名称", "类型", "备注", "录入时间"])
    for r in records:
        writer.writerow([r["name"], r["type"], r.get("note", ""), r["create_time"]])
    return buf.getvalue()


def import_csv(text: str) -> int:
    """从 CSV 文本导入记录（合并到现有数据），返回导入条数。"""
    text = text.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if len(rows) < 2:
        return 0
    added = 0
    for cells in rows[1:]:
        if len(cells) >= 2 and cells[0].strip():
            name = cells[0].strip()
            rec_type = cells[1].strip() if cells[1].strip() in TYPE_OPTIONS else "经历"
            note = cells[2].strip() if len(cells) > 2 else ""
            time_str = cells[3].strip() if len(cells) > 3 and cells[3].strip() else \
                datetime.now().strftime("%Y-%m-%d %H:%M")
            save_record(name, rec_type, note)
            # 注意：导入时不使用 CSV 中的原始时间，而是用当前时间
            # 如需保留原始时间，可改用直接 SQL 插入
            added += 1
    return added


# ============================================================
# 页面
# ============================================================
st.set_page_config(page_title="个人信息管理系统", page_icon="📋", layout="centered")
st.title("📋 个人信息管理系统")
st.caption("记录你的获奖、证书、经历和工作记录（SQLite3 数据库版）")

# 确保数据库已初始化
init_db()

# ------------------------------------------------------------
# 新增记录表单
# ------------------------------------------------------------
st.subheader("➕ 新增记录")

with st.form("add_form", clear_on_submit=True):
    name_input = st.text_input("名称 *", placeholder="例如：全国大学生数学竞赛一等奖")
    type_input = st.selectbox("类型 *", TYPE_OPTIONS, index=None,
                               placeholder="请选择类型")
    note_input = st.text_area("备注", placeholder="选填，例如：2024年12月获得")

    submitted = st.form_submit_button("保存记录", use_container_width=True)

    if submitted:
        if not name_input.strip():
            st.error("❌ 名称不能为空，请填写后再提交。")
        elif type_input not in TYPE_OPTIONS:
            st.error("❌ 请从下拉框中选择一个类型。")
        else:
            save_record(name_input.strip(), type_input, note_input.strip())
            st.success(f"✅ 已保存：{name_input.strip()}（{type_input}）")

st.divider()

# ------------------------------------------------------------
# CSV 导入导出
# ------------------------------------------------------------
ioc1, ioc2 = st.columns(2)
with ioc1:
    st.download_button(
        "⬇ 导出 CSV",
        data=export_csv(),
        file_name="records.csv",
        mime="text/csv",
        use_container_width=True,
    )
with ioc2:
    uploaded = st.file_uploader("⬆ 导入 CSV", type=["csv"],
                                label_visibility="collapsed")
    if uploaded is not None:
        text = uploaded.read().decode("utf-8")
        added = import_csv(text)
        if added > 0:
            st.success(f"已导入 {added} 条记录。")
        else:
            st.warning("CSV 文件为空或格式不正确。")

st.divider()

# ------------------------------------------------------------
# 全部记录（展示层，筛选只影响显示）
# ------------------------------------------------------------
st.subheader("📄 全部记录")

all_records = load_records()

filter_type = st.selectbox(
    "按类型筛选",
    ["全部"] + TYPE_OPTIONS,
    index=0,
    help="筛选只影响显示，保存时始终基于完整数据。",
)

# 筛选只作用于展示层
if filter_type == "全部":
    display_records = all_records
else:
    display_records = [r for r in all_records if r["type"] == filter_type]

# 计数信息
if all_records:
    st.caption(f"共 {len(all_records)} 条记录，当前显示 {len(display_records)} 条"
               + (f"（筛选：{filter_type}）" if filter_type != "全部" else ""))

# 展示
if not all_records:
    st.info("📭 暂无记录，在上方填写表单添加第一条吧。")
elif not display_records:
    st.info(f"📭 没有「{filter_type}」类型的记录。")
else:
    # 表格视图
    st.dataframe(
        display_records,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": None,
            "name": st.column_config.TextColumn("名称", width="medium"),
            "type": st.column_config.TextColumn("类型", width="small"),
            "note": st.column_config.TextColumn("备注", width="large"),
            "create_time": st.column_config.TextColumn("录入时间", width="medium"),
        },
    )

    # 删除功能
    with st.expander("🗑 删除记录", expanded=False):
        for r in display_records:
            dcol1, dcol2, dcol3 = st.columns([4, 3, 1])
            dcol1.write(r["name"])
            dcol2.write(f"{r['type']} ｜ {r['create_time']}")
            if dcol3.button("删除", key=f"del_{r['id']}"):
                delete_record(r["id"])
                st.rerun()

# ------------------------------------------------------------
# 页脚
# ------------------------------------------------------------
st.divider()
st.caption(f"📁 数据库位置：`{DB_PATH}`")
st.caption("数据保存在 SQLite3 数据库中，可随时备份或迁移。关闭浏览器后数据不丢失。")
