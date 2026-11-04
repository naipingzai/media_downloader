"""数据导出 —— 表格/列表数据落盘为 CSV / JSON。

UI 只需调用 export_dialog(parent, headers, rows) 弹保存框完成导出。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

__all__ = ["export_rows", "SUPPORTED_FORMATS"]

SUPPORTED_FORMATS = "CSV (*.csv);;JSON (*.json)"


def export_rows(headers: list[str], rows: list[list],
                path: str | Path) -> Path | None:
    """将表格数据写入 path (按扩展名选择格式)。返回路径或 None。"""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix.lower() == ".json":
            _export_json(headers, rows, p)
        else:
            _export_csv(headers, rows, p)
        return p
    except OSError:
        return None


def _export_csv(headers: list[str], rows: list[list], p: Path) -> None:
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def _export_json(headers: list[str], rows: list[list], p: Path) -> None:
    items = [dict(zip(headers, map(str, r))) for r in rows]
    with open(p, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def export_dialog(parent, headers: list[str], rows: list[list],
                  suggested_name: str = "export") -> Path | None:
    """弹出系统保存对话框并导出。返回导出路径 (取消返回 None)。"""
    if not rows:
        return None
    try:
        from PySide6.QtWidgets import QFileDialog, QMessageBox
    except ImportError:
        return None
    path, _ = QFileDialog.getSaveFileName(
        parent, "导出数据", f"{suggested_name}.csv", SUPPORTED_FORMATS)
    if not path:
        return None
    out = export_rows(headers, rows, path)
    if out:
        QMessageBox.information(parent, "导出成功", f"已导出 {len(rows)} 条到:\n{out}")
    else:
        QMessageBox.warning(parent, "导出失败", "写入文件失败, 请检查路径权限")
    return out
