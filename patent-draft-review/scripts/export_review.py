"""Build annotated and clean Word copies from a verified patent review plan."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import sys
from tempfile import TemporaryFile
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph


WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
REVIEW_NAMESPACES = (WORD_NS, "{http://schemas.microsoft.com/office/word/2010/wordml}")
STATUS_LABELS = {
    "adopted": "本轮采纳",
    "pending": "待确认",
    "rejected": "未采纳",
    "resolved": "已解决",
}
REVIEW_MARKS = {
    "ins", "del", "delText", "delInstrText", "moveFrom", "moveTo",
    "moveFromRangeStart", "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd",
    "cellIns", "cellDel", "cellMerge", "numberingChange", "tblPrExChange",
    "conflictIns", "conflictDel",
    "commentRangeStart", "commentRangeEnd", "commentReference",
}


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"修改计划中存在重复字段 {key}")
        result[key] = value
    return result


def check_source_package(raw):
    """Require a finalized source before creating a second review layer."""
    with ZipFile(io.BytesIO(raw)) as package:
        for name in package.namelist():
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            if name.rsplit("/", 1)[-1].lower().startswith("comments"):
                raise ValueError("原稿已有 Word 批注。请先另存一份已处理旧批注的基线，再生成本轮文档。")
            root = ElementTree.fromstring(package.read(name))
            for element in root.iter():
                if not element.tag.startswith(REVIEW_NAMESPACES):
                    continue
                local_name = element.tag.rsplit("}", 1)[-1]
                custom_xml_revision = local_name.startswith("customXml") and local_name.endswith(("RangeStart", "RangeEnd"))
                if local_name in REVIEW_MARKS or local_name.endswith("PrChange") or custom_xml_revision:
                    raise ValueError("原稿含批注或跟踪修订。请先另存一份已处理旧标记的基线。")
                if local_name == "trackRevisions" and element.get(WORD_NS + "val", "true") not in {
                    "0", "false", "off",
                }:
                    raise ValueError("原稿开启了跟踪修订。请在另存的基线中关闭跟踪修订。")
                if local_name == "documentProtection" and element.get(WORD_NS + "enforcement") in {
                    "1", "true", "on",
                }:
                    raise ValueError("原稿启用了编辑保护。请使用有权编辑的副本作为基线。")


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} 必须是非空文字")
    return value


def locate(paragraphs, number, quote, label):
    if type(number) is not int or not 1 <= number <= len(paragraphs):
        raise ValueError(f"{label} 的正文段号超出 1 至 {len(paragraphs)}")
    quote = required_text(quote, label + "的原文片段")
    text = paragraphs[number - 1].text
    start = text.find(quote)
    if start < 0:
        raise ValueError(f"{label} 的原文片段不在第 {number} 段")
    if text.find(quote, start + 1) >= 0:
        raise ValueError(f"{label} 的原文片段在第 {number} 段出现多次，请扩大定位片段")
    return start, start + len(quote)


def compile_plan(plan, paragraphs):
    if not isinstance(plan, dict) or not isinstance(plan.get("issues"), list):
        raise ValueError("修改计划必须含 issues 数组")
    replacements, insertions = {}, {}
    ids = set()
    for issue in plan["issues"]:
        if not isinstance(issue, dict):
            raise ValueError("issues 中的每条意见必须是对象")
        issue_id = required_text(issue.get("id"), "意见编号")
        if issue_id in ids:
            raise ValueError(f"意见编号 {issue_id} 重复")
        ids.add(issue_id)
        required_text(issue.get("problem"), issue_id + "的问题")
        required_text(issue.get("reference_fix"), issue_id + "的补充参考改法")
        status = issue.get("status")
        if not isinstance(status, str) or status not in STATUS_LABELS:
            raise ValueError(f"{issue_id} 的采纳状态无效")
        anchor = issue.get("anchor")
        if not isinstance(anchor, dict):
            raise ValueError(f"{issue_id} 缺少原文定位")
        locate(paragraphs, anchor.get("paragraph"), anchor.get("quote"), issue_id)
        edits = issue.get("edits", [])
        if not isinstance(edits, list):
            raise ValueError(f"{issue_id} 的 edits 必须是数组")
        if status != "adopted":
            continue
        if not edits:
            raise ValueError(f"{issue_id} 已采纳，但没有可执行修改")
        for edit in edits:
            if not isinstance(edit, dict):
                raise ValueError(f"{issue_id} 的修改必须是对象")
            number = edit.get("paragraph")
            start, end = locate(paragraphs, number, edit.get("before"), issue_id + "的修改")
            if ("after" in edit) == ("insert_after" in edit):
                raise ValueError(f"{issue_id} 每项修改须指定 after 或 insert_after 之一")
            if "after" in edit:
                after = edit["after"]
                if not isinstance(after, str) or "\n" in after or "\r" in after:
                    raise ValueError(f"{issue_id} 的 after 须为单段文字，新增段落请用 insert_after")
                replacements.setdefault(number, []).append((start, end, after))
            else:
                added = edit["insert_after"]
                if not isinstance(added, list) or not added or any(
                    not isinstance(text, str) or not text.strip() or "\n" in text or "\r" in text
                    for text in added
                ):
                    raise ValueError(f"{issue_id} 的 insert_after 必须含一个或多个非空段落")
                if number in insertions:
                    raise ValueError(f"第 {number} 段有多项插入，请按顺序合并为一个 insert_after")
                insertions[number] = added
    for number, spans in replacements.items():
        spans.sort()
        if any(first[1] > second[0] for first, second in zip(spans, spans[1:])):
            raise ValueError(f"第 {number} 段有重叠的已采纳修改，请合并后重新导出")
    return replacements, insertions


def replace_text(paragraph, number, start, end, after):
    # Restrict modifications to text runs whose other XML can stay intact.
    if any(child.tag not in {qn("w:pPr"), qn("w:r")} for child in paragraph._p):
        raise ValueError(f"第 {number} 段有超链接、书签或其他复杂内容，请先在 Word 中处理该段")
    parts = []
    offset = 0
    for run in paragraph.runs:
        stop = offset + len(run.text)
        if offset < end and stop > start:
            if any(child.tag not in {qn("w:rPr"), qn("w:t")} for child in run._r):
                raise ValueError(f"第 {number} 段的修改跨越复杂内容，请先在 Word 中处理该处")
            if offset < stop:
                parts.append((run, max(0, start - offset), min(stop, end) - offset))
        offset = stop
    if not parts:
        raise ValueError(f"第 {number} 段没有可修改的文字")
    for index, (run, left, right) in enumerate(parts):
        run.text = run.text[:left] + (after if index == 0 else "") + run.text[right:]


def apply_edits(paragraphs, replacements, insertions):
    for number, spans in replacements.items():
        for start, end, after in reversed(spans):
            replace_text(paragraphs[number - 1], number, start, end, after)
    for number, strings in insertions.items():
        source = paragraphs[number - 1]
        preceding = source._p
        for text in strings:
            element = OxmlElement("w:p")
            preceding.addnext(element)
            added = Paragraph(element, source._parent)
            added.style = source.style
            added.add_run(text)
            preceding = element


def add_review_comments(document, paragraphs, issues):
    for issue in issues:
        number = issue["anchor"]["paragraph"]
        runs = [run for run in paragraphs[number - 1].runs if run.text.strip()]
        if not runs:
            raise ValueError(f"{issue['id']} 所在第 {number} 段没有可挂载批注的正文")
        note = "\n".join([
            f"{issue['id']}  {STATUS_LABELS[issue['status']]}",
            f"原稿第 {number} 段 · {issue['anchor']['quote']}",
            f"问题：{issue['problem']}",
            f"补充参考改法：{issue['reference_fix']}",
        ])
        document.add_comment([runs[0], runs[-1]], note, author="专利审稿", initials="IP")


def write_pair(source, plan_path, annotated, clean):
    destinations = [annotated, clean]
    if source.suffix.lower() != ".docx" or any(p.suffix.lower() != ".docx" for p in destinations):
        raise ValueError("原稿和两份输出都须使用 .docx")
    resolved = [p.resolve() for p in [source, plan_path, *destinations]]
    if len(set(resolved)) != len(resolved):
        raise ValueError("原稿、计划、批注版和清洁版必须使用不同路径")
    for path in destinations:
        if path.exists() or path.is_symlink():
            raise ValueError(f"输出文件已经存在，请指定新路径：{path}")
        if not path.parent.is_dir():
            raise ValueError(f"输出目录不存在：{path.parent}")
    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_keys)
    digest = plan.get("source_sha256") if isinstance(plan, dict) else None
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise ValueError("修改计划须记录原稿的 source_sha256")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest.lower():
        raise ValueError("原稿与计划记录的版本不一致，请重新核对定位后再导出")
    check_source_package(raw)
    document = Document(io.BytesIO(raw))
    paragraphs = document.paragraphs
    replacements, insertions = compile_plan(plan, paragraphs)
    apply_edits(paragraphs, replacements, insertions)
    with TemporaryFile() as annotated_temp, TemporaryFile() as clean_temp:
        document.save(clean_temp)
        add_review_comments(document, paragraphs, plan["issues"])
        document.save(annotated_temp)
        created = []
        try:
            for path, stream in zip(destinations, [annotated_temp, clean_temp]):
                stream.seek(0)
                with path.open("xb") as output:
                    created.append(path)
                    shutil.copyfileobj(stream, output)
        except BaseException:
            for path in created:
                path.unlink(missing_ok=True)
            raise
    return len(plan["issues"]), sum(issue["status"] == "adopted" for issue in plan["issues"])


def main():
    parser = argparse.ArgumentParser(description="按已确认的审稿计划生成批注版与清洁版 Word")
    parser.add_argument("source", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--annotated", type=Path, required=True)
    parser.add_argument("--clean", type=Path, required=True)
    args = parser.parse_args()
    try:
        comments, adopted = write_pair(args.source, args.plan, args.annotated, args.clean)
    except (ValueError, OSError, BadZipFile, ElementTree.ParseError) as error:
        parser.exit(2, f"导出失败：{error}\n")
    print(f"导出完成。批注 {comments} 条，采纳意见 {adopted} 条。", file=sys.stdout)


if __name__ == "__main__":
    main()
