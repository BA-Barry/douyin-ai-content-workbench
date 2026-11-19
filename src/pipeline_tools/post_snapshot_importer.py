"""Import manually exported creator-centre CSV/XLSX into the frozen snapshot contract."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


TEMPLATE = Path(__file__).resolve().parents[2] / "workflow" / "templates" / "POST_SNAPSHOTS_TEMPLATE.csv"
OUTPUT_COLUMNS = tuple(next(csv.reader(TEMPLATE.open("r", encoding="utf-8-sig", newline=""))))
ALIASES = {
    "video_id": ("video_id", "作品id", "作品ID", "视频id", "视频ID", "作品编号"),
    "snapshot_type": ("snapshot_type", "快照类型", "统计阶段", "复盘节点"),
    "captured_at": ("captured_at", "采集时间", "数据时间", "统计时间", "导出时间"),
    "published_at": ("published_at", "发布时间", "作品发布时间"),
    "work_url": ("work_url", "作品链接", "视频链接", "分享链接"),
    "plays": ("plays", "播放量", "播放次数"),
    "likes": ("likes", "点赞量", "点赞数"),
    "comments": ("comments", "评论量", "评论数"),
    "collects": ("collects", "收藏量", "收藏数"),
    "shares": ("shares", "分享量", "分享数"),
    "new_followers": ("new_followers", "新增粉丝", "涨粉数"),
    "avg_watch_s": ("avg_watch_s", "平均观看时长", "平均播放时长", "平均观看时长(秒)", "平均播放时长(秒)"),
    "completion_rate": ("completion_rate", "完播率", "播放完成率"),
    "retention_2s": ("retention_2s", "2秒留存率", "2s留存率", "2秒留存"),
    "retention_5s": ("retention_5s", "5秒留存率", "5s留存率", "5秒留存"),
    "source_screenshot_path": ("source_screenshot_path", "来源截图路径", "截图路径"),
    "notes": ("notes", "备注", "说明"),
}
METRICS = ("plays", "likes", "comments", "collects", "shares", "new_followers", "avg_watch_s", "completion_rate", "retention_2s", "retention_5s")
RATE_FIELDS = {"completion_rate", "retention_2s", "retention_5s"}
INTEGER_FIELDS = {"plays", "likes", "comments", "collects", "shares", "new_followers"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(encoding)
            return [dict(row) for row in csv.DictReader(text.splitlines())]
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV encoding must be UTF-8/UTF-8-BOM or GB18030")


def _read_xlsx(path: Path) -> list[dict[str, str]]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", ns):
                shared.append("".join(node.text or "" for node in item.findall(".//m:t", ns)))
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        first_sheet = workbook.find("m:sheets/m:sheet", ns)
        if first_sheet is None:
            return []
        rel_id = first_sheet.attrib.get(f"{{{ns['r']}}}id")
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_ns = {"p": "http://schemas.openxmlformats.org/package/2006/relationships"}
        target = None
        for rel in rels.findall("p:Relationship", rel_ns):
            if rel.attrib.get("Id") == rel_id:
                target = rel.attrib.get("Target")
                break
        if not target:
            raise ValueError("Cannot resolve first worksheet")
        sheet_path = "xl/" + target.lstrip("/").removeprefix("xl/")
        sheet = ET.fromstring(archive.read(sheet_path))
        table: list[list[str]] = []
        for row in sheet.findall(".//m:sheetData/m:row", ns):
            values: dict[int, str] = {}
            for cell in row.findall("m:c", ns):
                reference = cell.attrib.get("r", "A1")
                column = _column_index(re.match(r"[A-Z]+", reference).group(0))
                cell_type = cell.attrib.get("t")
                value_node = cell.find("m:v", ns)
                inline_node = cell.find("m:is", ns)
                if cell_type == "s" and value_node is not None:
                    value = shared[int(value_node.text or "0")]
                elif cell_type == "inlineStr" and inline_node is not None:
                    value = "".join(node.text or "" for node in inline_node.findall(".//m:t", ns))
                else:
                    value = value_node.text if value_node is not None and value_node.text is not None else ""
                values[column] = value
            width = max(values, default=-1) + 1
            table.append([values.get(index, "") for index in range(width)])
    if not table:
        return []
    headers = table[0]
    return [{headers[index]: row[index] if index < len(row) else "" for index in range(len(headers))} for row in table[1:]]


def _column_index(label: str) -> int:
    value = 0
    for character in label:
        value = value * 26 + (ord(character) - 64)
    return value - 1


def _source_rows(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path)
    if suffix == ".xlsx":
        return _read_xlsx(path)
    raise ValueError("Only manually exported .csv and .xlsx files are supported")


def _pick(row: dict[str, str], field: str) -> str:
    normalized = {str(key).strip(): "" if value is None else str(value).strip() for key, value in row.items()}
    for alias in ALIASES.get(field, (field,)):
        if alias in normalized:
            return normalized[alias]
    return ""


def _metric(value: str, field: str) -> str:
    text = value.strip().replace(",", "").replace("，", "")
    if not text or text in {"-", "--", "不可见", "暂无数据", "N/A", "n/a"}:
        return ""
    multiplier = 1.0
    if text.endswith("万"):
        multiplier, text = 10000.0, text[:-1]
    elif text.endswith("亿"):
        multiplier, text = 100000000.0, text[:-1]
    percent = text.endswith("%")
    if percent:
        text = text[:-1]
    try:
        number = float(text) * multiplier
    except ValueError as exc:
        raise ValueError(f"Invalid metric {field}={value!r}") from exc
    if field in RATE_FIELDS:
        if percent:
            number /= 100.0
        if not 0 <= number <= 1:
            raise ValueError(f"Rate outside 0..1: {field}={value!r}")
        return format(number, ".12g")
    if field in INTEGER_FIELDS:
        if number < 0 or not number.is_integer():
            raise ValueError(f"Expected non-negative integer metric: {field}={value!r}")
        return str(int(number))
    if number < 0:
        raise ValueError(f"Expected non-negative metric: {field}={value!r}")
    return format(number, ".12g")


def import_snapshots(
    input_path: str | Path,
    output_path: str | Path,
    *,
    video_id: str = "",
    snapshot_type: str = "",
    captured_at: str = "",
    append: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    source = Path(input_path).resolve()
    destination = Path(output_path).resolve()
    if destination.exists() and not append and not overwrite:
        raise FileExistsError(f"Output already exists; use --append or --overwrite: {destination}")
    rows: list[dict[str, str]] = []
    for source_row in _source_rows(source):
        target = {field: "" for field in OUTPUT_COLUMNS}
        for field in OUTPUT_COLUMNS:
            if field not in {"field_availability"}:
                target[field] = _pick(source_row, field)
        target["video_id"] = target["video_id"] or video_id
        target["snapshot_type"] = target["snapshot_type"] or snapshot_type
        target["captured_at"] = target["captured_at"] or captured_at
        for field in METRICS:
            target[field] = _metric(target[field], field)
        target["field_availability"] = ";".join(field for field in METRICS if target[field] != "")
        for required in ("video_id", "snapshot_type", "captured_at"):
            if not target[required]:
                raise ValueError(f"Required field missing after mapping: {required}")
        rows.append(target)

    existing: list[dict[str, str]] = []
    if append and destination.exists():
        with destination.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != OUTPUT_COLUMNS:
                raise ValueError("Existing output does not match frozen POST_SNAPSHOTS header")
            existing = [dict(row) for row in reader]
    keys: set[tuple[str, str, str]] = set()
    for row in [*existing, *rows]:
        key = (row["video_id"], row["snapshot_type"], row["captured_at"])
        if key in keys:
            raise ValueError(f"Duplicate snapshot blocked: {key}")
        keys.add(key)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows([*existing, *rows])
    return {"status": "PASS", "input_path": str(source), "output_path": str(destination), "rows_imported": len(rows), "rows_total": len(existing) + len(rows)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize a manually exported Douyin creator-centre CSV/XLSX; no login or browser automation.")
    parser.add_argument("input", help="Manual CSV/XLSX export")
    parser.add_argument("output", help="Destination CSV using the frozen template")
    parser.add_argument("--video-id", default="", help="Fallback video_id when export lacks it")
    parser.add_argument("--snapshot-type", default="", help="Fallback snapshot type, e.g. 2h/24h/72h")
    parser.add_argument("--captured-at", default="", help="Fallback ISO-8601 capture time")
    parser.add_argument("--append", action="store_true", help="Append while blocking duplicate snapshot keys")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing normalized output file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.append and args.overwrite:
            raise ValueError("--append and --overwrite are mutually exclusive")
        result = import_snapshots(
            args.input,
            args.output,
            video_id=args.video_id,
            snapshot_type=args.snapshot_type,
            captured_at=args.captured_at,
            append=args.append,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
