"""Validate a patent review record and render a self-contained HTML report."""

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path
from string import Template
from urllib.parse import quote, urlsplit


SECTIONS = {
    "disclosure": "技术交底", "claims": "权利要求", "description": "说明书",
    "drawings": "附图", "abstract": "摘要", "filing": "申请信息", "search": "独权检索",
}
COVERAGE = {
    "reviewed": "已核查", "partial": "部分核查", "unread": "未核读",
    "missing": "待材料", "na": "不适用",
}
VISUAL = {
    "seen": "图示可见", "text_only": "仅正文有记载", "unclear": "已看图但无法确认",
    "unread": "附图未核读", "missing": "附图缺失", "na": "不适用",
}
SUPPORT = {
    "supported": "有依据", "partial": "部分有依据", "gap": "依据有缺口",
    "unverified": "待核验", "na": "不适用",
}
SEARCH = {"reviewed": "已核查", "partial": "部分核查", "not_run": "未执行"}
ISSUE = {"pending": "待确认", "adopted": "已采纳", "rejected": "未采纳", "resolved": "已解决"}
PRIORITY = {"high": "高优先级", "medium": "中优先级", "low": "低优先级"}
PHASES = ("before_filing", "pending", "granted", "unknown")
CONFIRMATION = {
    "technical": "待研发确认", "evidence": "待补证据", "search": "待检索比对",
    "writing": "文稿校订", "decision": "待决定", "none": "无待核事项",
}
APPLICABILITY = {
    "current_draft": "当前稿件可考虑",
    "review": "本轮可做的核查",
    "future_draft": "后续新稿参考",
    "procedure_check": "先核对适用程序",
}
GAP_STATUSES = ("missing", "partial", "unread")
ASSESSMENT = {
    "supported": "证据支持该判断",
    "risk": "法律风险待核",
    "drafting": "撰写或保护层次问题",
    "insufficient": "证据不足",
    "legacy": "待补核",
}
DELIVERY = {"ready": "已交付", "pending": "待交付", "not_requested": "本轮未要求", "unavailable": "暂无法交付"}
LABELS = {
    "reviewed": "good", "partial": "warn", "missing": "warn", "unread": "warn",
    "seen": "good", "unclear": "warn", "supported": "good", "gap": "warn",
    "unverified": "warn", "pending": "warn", "resolved": "good", "ready": "good",
    "high": "danger", "medium": "warn", "unavailable": "warn", "risk": "warn",
    "insufficient": "warn", "legacy": "warn",
}
TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "review-report.html"
ISSUE_ID = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,47}\Z")
MAX_INPUT = 2 * 1024 * 1024
MAX_ROWS = 2000
MAX_TEXT = 4000


def unique_fields(pairs):
    fields = {}
    for key, value in pairs:
        if key in fields:
            raise ValueError(f"JSON 字段重复：{key}")
        fields[key] = value
    return fields


def record(value, path, fields=(), choices=None):
    if not isinstance(value, dict):
        raise ValueError(f"{path} 必须是对象")
    for field in fields:
        item = value.get(field)
        if not isinstance(item, str) or not item.strip() or len(item) > MAX_TEXT:
            raise ValueError(f"{path}.{field} 必须是 1–{MAX_TEXT} 字的非空文本")
    for field, options in (choices or {}).items():
        item = value.get(field)
        if not isinstance(item, str) or item not in options:
            raise ValueError(f"{path}.{field} 无效，可选 {', '.join(options)}")
    return value


def rows(data, field):
    value = data.get(field)
    if not isinstance(value, list) or len(value) > MAX_ROWS:
        raise ValueError(f"{field} 必须是最多含 {MAX_ROWS} 行的数组")
    return ((item, f"{field}[{index}]") for index, item in enumerate(value, 1))


def issue_rows(issue, field, path, fields, required=True):
    value = issue.get(field)
    if not isinstance(value, list) or len(value) > MAX_ROWS or (required and not value):
        minimum = 1 if required else 0
        raise ValueError(f"{path}.{field} 必须包含 {minimum}–{MAX_ROWS} 条记录")
    for index, item in enumerate(value, 1):
        item_path = f"{path}.{field}[{index}]"
        yield record(item, item_path, fields), item_path


def validate_source_url(url, path):
    try:
        address = urlsplit(url)
        if (address.scheme not in ("http", "https") or not address.hostname
                or address.username is not None or re.search(r"[\s\\\x00-\x1f\x7f]", url)):
            raise ValueError()
    except ValueError:
        raise ValueError(f"{path}.url 必须是可打开的 HTTP(S) 来源链接") from None


def validate_issue_details(issue, path, phase=None):
    list(issue_rows(issue, "originals", path, ("location", "quote")))
    for edit, edit_path in issue_rows(issue, "edits", path, ("location", "operation", "text", "condition", "sync")):
        if phase is not None:
            scope_path = f"{edit_path}.applicability"
            scope = record(edit.get("applicability"), scope_path, ("note",), {"kind": APPLICABILITY})
            if scope["kind"] == "current_draft" and phase in ("granted", "unknown"):
                raise ValueError(f"{scope_path}.kind 与 report.phase 不匹配，请先核对程序")
    legal_path = f"{path}.legal"
    legal = record(issue.get("legal"), legal_path, ("reason",),
                   {"assessment": tuple(key for key in ASSESSMENT if key != "legacy")})
    needs_source = legal["assessment"] in ("supported", "risk")
    for source, source_path in issue_rows(legal, "sources", legal_path, ("name", "provision", "url", "applicability"), needs_source):
        validate_source_url(source["url"], source_path)


def legacy_issue(issue, path):
    record(issue, path, ("location", "reference_fix"))
    return {
        **issue,
        "originals": [{"location": issue["location"], "quote": "旧记录未附逐字原文，待补核。"}],
        "legal": {"assessment": "legacy", "reason": "旧记录未单列法律依据与判断，待补核。", "sources": []},
        "edits": [{
            "location": "拟修改的具体位置待补核",
            "operation": "旧记录的参考改法",
            "text": issue["reference_fix"],
            "condition": "具体采纳条件待补核",
            "sync": "同步修改范围待补核",
        }],
    }


def require_unique(values, field):
    if len(set(values)) != len(values):
        raise ValueError(f"{field} 不得重复")


def check_links(item, path, issue_ids):
    links = item.get("issues")
    if not isinstance(links, list) or len(links) > MAX_ROWS:
        raise ValueError(f"{path}.issues 必须是意见编号数组")
    if any(not isinstance(link, str) or link not in issue_ids for link in links):
        raise ValueError(f"{path}.issues 含未定义的意见编号")
    require_unique(links, f"{path}.issues")


def validate_overview(data, issues):
    pending = {item["id"] for item in issues if item["status"] == "pending"}
    actions = list(rows(data, "actions"))
    if len(actions) > 4 or (pending and not actions):
        raise ValueError("actions 最多列 4 项，有待确认意见时至少列 1 项")
    for item, path in actions:
        record(item, path, ("issue", "impact", "role", "next"))
        if item["issue"] not in pending:
            raise ValueError(f"{path}.issue 必须引用现有的待确认意见")
    require_unique([item["issue"] for item, _ in actions], "actions.issue")
    uncovered = {item["section"] for item in data["coverage"] if item["status"] in GAP_STATUSES}
    gaps = list(rows(data, "gaps"))
    if len(gaps) > 3 or (uncovered and not gaps):
        raise ValueError("gaps 最多列 3 项，存在核查缺口时至少列 1 项")
    for item, path in gaps:
        record(item, path, ("section", "note"))
        if item["section"] not in uncovered:
            raise ValueError(f"{path}.section 必须引用有核查缺口的分项")
    require_unique([item["section"] for item, _ in gaps], "gaps.section")


def validate(data):
    record(data, "report", ("title", "version", "stage", "conclusion"))
    version = data.get("schema_version", 1)
    if type(version) is not int or version not in (1, 2, 3):
        raise ValueError("schema_version 必须是 1、2 或 3，新报告请使用 3")
    phase = None
    if version == 3:
        phase = record(data, "report", choices={"phase": PHASES})["phase"]
    sections = []
    for item, path in rows(data, "coverage"):
        record(item, path, ("note",), {"section": SECTIONS, "status": COVERAGE})
        sections.append(item["section"])
    require_unique(sections, "coverage.section")
    if set(sections) != set(SECTIONS):
        raise ValueError("coverage 必须覆盖七个分项各一次")
    issue_ids = []
    issues = []
    for item, path in rows(data, "issues"):
        record(item, path, ("id", "title", "problem"),
               {"section": SECTIONS, "status": ISSUE, "priority": PRIORITY})
        if not ISSUE_ID.fullmatch(item["id"]):
            raise ValueError(f"{path}.id 必须以字母开头，使用不超过 48 位的字母、数字、点、下划线或连字符")
        issue_ids.append(item["id"])
        if version == 3:
            record(item, path, ("summary",), {"confirmation": CONFIRMATION})
        if version >= 2:
            validate_issue_details(item, path, phase)
        issues.append(item if version >= 2 else legacy_issue(item, path))
    require_unique(issue_ids, "issues.id")
    issue_ids = set(issue_ids)
    if version == 3:
        validate_overview(data, issues)
    for item, path in rows(data, "evidence"):
        record(item, path, ("claim", "path", "feature", "quote", "description", "figure", "page", "observation"),
               {"visual_status": VISUAL, "support_status": SUPPORT})
        check_links(item, path, issue_ids)
    figures = []
    for item, path in rows(data, "figures"):
        record(item, path, ("figure", "page", "observation"), {"visual_status": VISUAL})
        check_links(item, path, issue_ids)
        figures.append((item["figure"], item["page"]))
    require_unique(figures, "figures 的图号和页码组合")
    search_claims = []
    for item, path in rows(data, "search"):
        record(item, path, ("claim", "scope"))
        for field in ("novelty", "inventiveness"):
            record(item.get(field), f"{path}.{field}", ("basis",), {"status": SEARCH})
        search_claims.append(item["claim"])
    require_unique(search_claims, "search.claim")
    deliveries = []
    for item, path in rows(data, "deliverables"):
        record(item, path, ("name", "note"), {"status": DELIVERY})
        if "file" in item:
            record(item, path, ("file",))
            filename = item["file"]
            if item["status"] != "ready" or not filename.lower().endswith(".docx") or re.search(r'[\\/:*?"<>|\x00-\x1f]', filename):
                raise ValueError(f"{path}.file 仅用于已交付的同目录 DOCX 文件名")
        deliveries.append(item["name"])
    require_unique(deliveries, "deliverables.name")
    return validate_extensions({**data, "issues": issues}, issue_ids)


def e(value):
    return html.escape(str(value), quote=True)


def reading_text(value):
    # Keep short patent references together without affecting longer paragraphs.
    escaped = e(value)
    return re.sub(r"(?:权(?:利要求)?|图|PDF)[ \t]{0,2}[0-9]{1,4}(?:[–—-][0-9]{1,4})?(?![0-9])", r'<span class="keep">\g<0></span>', escaped)


def chip(status, labels):
    return f'<span class="chip {LABELS.get(status, "neutral")}">{labels[status]}</span>'


def text_cell(value):
    return f'<span class="copy">{reading_text(value)}</span>'


def issue_link(issue_id, label=None):
    return f'<a class="issue-link" href="#issue-{e(issue_id)}">{e(label or issue_id)}</a>'


def issue_links(ids):
    return " ".join(issue_link(issue_id) for issue_id in ids) or "—"


def table(headers, records, empty):
    if not records:
        return f'<p class="empty">{e(empty)}</p>'
    head = "".join(f'<th scope="col" role="columnheader">{e(header)}</th>' for header in headers)
    body = []
    for cells, attributes in records:
        formatted = "".join(
            f'<td role="cell"><span class="cell-label" aria-hidden="true">{e(header)}</span><div>{cell}</div></td>'
            for header, cell in zip(headers, cells)
        )
        body.append(f'<tr role="row"{attributes}>{formatted}</tr>')
    return (f'<table role="table"><thead role="rowgroup"><tr role="row">{head}</tr></thead>'
            f'<tbody role="rowgroup">{"".join(body)}</tbody></table>')


def options(values):
    return "".join(f'<option value="{e(value)}">{e(label)}</option>' for value, label in values)


def evidence_table(evidence):
    body = []
    previous_claim = None
    for item in evidence:
        group = ' class="claim-group-start"' if item["claim"] != previous_claim else ""
        previous_claim = item["claim"]
        body.append(((
            f'<strong>{e(item["claim"])}</strong><small>{e(item["path"])}</small>',
            f'<strong>{e(item["feature"])}</strong><blockquote>{text_cell(item["quote"])}</blockquote>',
            text_cell(item["description"]),
            f'<strong>{e(item["figure"])}</strong><small>{e(item["page"])}</small>'
            f'<p class="copy">{e(item["observation"])}</p>'
            f'{chip(item["visual_status"], VISUAL)} {chip(item["support_status"], SUPPORT)}',
            issue_links(item["issues"]),
        ), f'{group} data-claim="{e(item["claim"])}" data-visual="{e(item["visual_status"])}"'
           f' data-related="{e(" ".join(item["issues"]))}"'))
    return table(("权项与路径", "特征及原文", "说明书依据", "附图与支持判断", "关联意见"),
                 body, "本轮无图文对照行。请查看各分项的覆盖说明。")


def figures_table(figures):
    body = [((
        f'<strong>{e(item["figure"])}</strong><small>{e(item["page"])}</small>',
        f'{chip(item["visual_status"], VISUAL)} <p class="copy">{e(item["observation"])}</p>',
        issue_links(item["issues"]),
    ), f' data-related="{e(" ".join(item["issues"]))}"') for item in figures]
    return table(("图号与页码", "图上核查及限制", "关联意见"), body,
                 "本轮无逐图记录。请查看附图分项的覆盖说明。")


def search_table(search):
    body = []
    for item in search:
        analysis = [f'{chip(item[key]["status"], SEARCH)}<p class="copy">{e(item[key]["basis"])}</p>'
                    for key in ("novelty", "inventiveness")]
        body.append(((f'<strong>{e(item["claim"])}</strong>', text_cell(item.get("focus", item["scope"])), *analysis), ""))
    return table(("独立权利要求", "本项检索重点" if search and "focus" in search[0] else "检索来源及范围", "新颖性", "创造性"), body,
                 "本轮无独立项检索记录。请查看独权检索分项的覆盖说明。")


def original_items(originals):
    locations = {}
    for original in originals:
        locations.setdefault(original["quote"], []).append(original["location"])
    items = []
    for quote_text, places in locations.items():
        other_places = "".join(f'<span class="location">{e(place)}</span>' for place in places[1:])
        items.append(f'<li><span class="location">{e(places[0])}</span>'
                     f'<blockquote class="copy">{e(quote_text)}</blockquote>{other_places}</li>')
    return "".join(items)


def legal_items(sources):
    return "".join(
        f'<li><a href="{e(source["url"])}" target="_blank" rel="noopener">'
        f'{e(source["name"])} · {e(source["provision"])}</a>'
        f'<p class="copy">{e(source["applicability"])}</p></li>'
        for source in sources
    )


def edit_scope(edit, structured):
    if not structured:
        return '<p class="stage-note"><b>适用阶段待补核</b> 此建议来自旧记录。</p>'
    scope = edit["applicability"]
    return f'<p class="stage-note"><b>{APPLICABILITY[scope["kind"]]}</b> {e(scope["note"])}</p>'


def edit_items(edits, structured):
    return "".join(
        f'<li><strong>{e(edit["location"])}</strong><span class="sub">{e(edit["operation"])}</span>'
        f'{edit_scope(edit, structured)}<p class="copy">{e(edit["text"])}</p>'
        f'<p class="edit-detail"><b>采纳条件</b> {e(edit["condition"])}</p>'
        f'<p class="edit-detail"><b>同步位置</b> {e(edit["sync"])}</p></li>'
        for edit in edits
    )


def related_panel(issue_id, evidence_count, figure_count):
    if not evidence_count and not figure_count:
        return ""
    records = ""
    if evidence_count:
        records += (f'<div class="related-records" data-source="evidence"><h5>{issue_id} 权项对照</h5>'
                    '<p class="related-fallback"><a href="#evidence">查看完整权项对照</a></p></div>')
    if figure_count:
        records += (f'<div class="related-records" data-source="figures" id="figure-records-{issue_id}" tabindex="-1">'
                    f'<h5>{issue_id} 附图核查记录</h5>'
                    '<p class="related-fallback"><a href="#figures">查看完整逐图核查</a></p></div>')
    figure_jump = f'<a href="#figure-records-{issue_id}">直达附图核查 ↓</a>' if figure_count and evidence_count else ""
    back = f'<a class="return-link" href="#issue-{issue_id}">返回摘要 ↑</a>'
    return (f'<details class="related" id="related-{issue_id}" data-issue="{issue_id}" tabindex="-1">'
            f'<summary>{issue_id} 对应图证 <span>{evidence_count} 条权项对照 · {figure_count} 条附图记录</span></summary>'
            f'<div class="related-content"><div class="issue-jumps">{back}{figure_jump}</div>{records}{back}</div></details>')


def issue_card(item, structured, evidence_count, figure_count, references=None, conditions=(), show_status=True):
    issue_id = e(item["id"])
    legal = item["legal"]
    summary = f'<p class="issue-summary">{reading_text(item["summary"])}</p>' if structured else ""
    confirmation = item["confirmation"] if structured else ""
    confirmation_chip = chip(confirmation, CONFIRMATION) if confirmation and confirmation != "none" else ""
    related = related_panel(issue_id, evidence_count, figure_count)
    evidence_jump = f'<a href="#related-{issue_id}">看对应图证</a>' if related else ""
    if item["section"] == "search":
        evidence_jump += '<a href="#search">看独立项检索</a>'
    if any(item["id"] in row["issues"] for row in conditions):
        evidence_jump += '<a href="#conditions">看控制与工况</a>'
    document_key = ""
    if item.get("reference_ids"):
        document_key = '<div class="document-key">本条涉及文献：' + "；".join(
            f'<a href="#ref-{e(id)}">{e(id)} · {e(references[id]["title"])}</a>' for id in item["reference_ids"]) + '</div>'
    # Screen and print use exactly the same source-derived count string.
    counts = f'{evidence_count} 条权项对照 · {figure_count} 条附图记录'
    print_note = (f'<p class="print-evidence-links">{issue_id} 关联图证共 {counts}。'
                  '完整内容见“权利要求对照”和“附图与原图”中标有本意见编号的记录。</p>') if related else ""
    legal_sources = f'<ul>{legal_items(legal["sources"])}</ul>' if legal["sources"] else ""
    status_chip = chip(item["status"], ISSUE) if show_status else ""
    return f'''
<article class="issue" id="issue-{issue_id}" data-section="{item["section"]}" data-status="{item["status"]}" data-confirmation="{confirmation}" data-priority="{item["priority"]}" tabindex="-1">
  <div class="issue-meta"><b>{issue_id}</b>{chip(item["priority"], PRIORITY)}<span>{SECTIONS[item["section"]]}</span>{status_chip}{confirmation_chip}
    <span class="filter-exception" hidden>已定位到筛选条件外的意见</span></div>
  <div class="issue-heading"><h3>{reading_text(item["title"])}</h3></div>{summary}
  <nav class="issue-jumps" aria-label="{issue_id} 小节"><a href="#original-{issue_id}">看原文</a>{evidence_jump}<a href="#edit-{issue_id}">看修改位置</a><a href="#law-{issue_id}">看法律依据</a></nav>
  {document_key}
  <div class="issue-reading">
    <div class="original" id="original-{issue_id}" tabindex="-1"><h4>{issue_id} 原文与位置</h4><ul>{original_items(item["originals"])}</ul></div>
    <div class="finding"><h4>具体问题</h4><p class="copy">{reading_text(item["problem"])}</p></div>
  </div>
  {related}{print_note}
  <div class="edits" id="edit-{issue_id}" tabindex="-1">
    <div class="section-head"><h4>{issue_id} 建议修改位置与改法</h4><a class="return-link" href="#issue-{issue_id}">返回摘要 ↑</a></div>
    <ol>{edit_items(item["edits"], structured)}</ol>
    <a class="return-link" href="#reading-guide">补充阅读：意见和改法的使用说明</a>
  </div>
  <details class="legal" id="law-{issue_id}" tabindex="-1">
    <summary>{issue_id} 法律依据与判断 {chip(legal["assessment"], ASSESSMENT)}</summary>
    <div class="legal-body"><p class="copy">{reading_text(legal["reason"])}</p>{legal_sources}
    <a class="return-link" href="#issue-{issue_id}">返回摘要 ↑</a></div>
  </details>
</article>'''



def report_title(title):
    name = re.sub(r"\s*[｜|·]?\s*[Bb]\s*版\s*证据矩阵\s*$", "", title).strip()
    if not name:
        return "专利审核报告"
    return name if "专利审核报告" in name else f"{name}｜专利审核报告"


def validate_extensions(data, issue_ids):
    """Optional presentation data; never infer technical relationships from prose."""
    definitions = {
        "meta": ("label", "text"), "conclusions": ("label", "text"),
        "claim_index": ("claim", "kind", "path", "summary"),
        "conditions": ("condition", "behavior", "source"),
        "references": ("id", "title", "note", "url"),
        "search_log": ("label", "text"),
        "figure_notes": ("label", "text", "source"),
        "drawing_pages": ("file", "label", "source"),
    }
    for field, fields in definitions.items():
        if field not in data:
            continue
        for item, path in rows(data, field):
            record(item, path, fields)
            if field == "conditions":
                check_links(item, path, issue_ids)
            if field == "references":
                if not ISSUE_ID.fullmatch(item["id"]):
                    raise ValueError(f"{path}.id 的格式与意见编号相同")
                validate_source_url(item["url"], path)
            if field == "drawing_pages":
                image = Path(item["file"])
                if image.is_absolute() or ".." in image.parts or ":" in item["file"]:
                    raise ValueError(f"{path}.file 必须是输入目录内的相对图片路径")
                if image.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                    raise ValueError(f"{path}.file 只接受 PNG 或 JPEG 原图")
    for field, key in (("meta", "label"), ("claim_index", "claim"), ("references", "id")):
        require_unique([row[key] for row in data.get(field, [])], field + "." + key)
    for field in ("technology", "reading_guide"):
        if field in data:
            values = data[field]
            if not isinstance(values, list) or len(values) > 100:
                raise ValueError(f"{field} 必须是最多 100 段的文本数组")
            for value in values:
                record({"text": value}, field, ("text",))
    for field in ("search_common", "conditions_intro", "claim_path_note", "reviewer"):
        if field in data:
            record(data, "report", (field,))
    if "context_issues" in data:
        check_links({"issues": data["context_issues"]}, "context_issues", issue_ids)
    reference_ids = {row["id"] for row in data.get("references", [])}
    for item, path in rows(data, "issues"):
        if "reference_ids" in item:
            check_links({"issues": item["reference_ids"]}, path + ".reference_ids", reference_ids)
    focuses = ["focus" in row for row in data["search"]]
    if any(focuses) and (not all(focuses) or not data.get("search_common")):
        raise ValueError("使用 focus 时每项检索均须填写 focus，另填 search_common 保留共同范围")
    for item, path in rows(data, "search"):
        if "focus" in item:
            record(item, path, ("focus",))
    for item, path in rows(data, "deliverables"):
        if "review" in item:
            record(item, path, ("review",))
    return data


def section(section_id, title, content, classes=""):
    return (f'<section id="{section_id}" class="section {classes}" aria-labelledby="{section_id}-title">'
            f'<h2 id="{section_id}-title">{title}</h2>{content}</section>')


def details(panel_id, title, content, extra=""):
    return (f'<details class="review-extra {extra}" id="{panel_id}" tabindex="-1">'
            f'<summary><h3>{title}</h3></summary>{content}</details>')


def paragraphs(values):
    return "".join(f'<p class="copy">{reading_text(text)}</p>' for text in values)


def filter_control(field_id, label, all_label, mapping, values):
    present = set(values)
    choices = [(key, value) for key, value in mapping.items() if key in present]
    hidden = " hidden" if len(choices) < 2 else ""
    return (f'<label{hidden}>{label}<select id="{field_id}"><option value="">{all_label}</option>'
            f'{options(choices)}</select></label>')


def claim_index(data):
    index = data.get("claim_index", [])
    if not index:
        # An evidence table is not proof that all claims have been reviewed.
        return ""
    titles = {item["id"]: item["title"] for item in data["issues"]}
    related = {row["claim"]: [] for row in index}
    for row in data["evidence"]:
        if row["claim"] in related:
            related[row["claim"]].extend(row["issues"])
    body = []
    for row in index:
        links = " ".join(
            f'<a href="#issue-{e(id)}" title="{e(titles[id])}" aria-label="{e(id + " " + titles[id])}">{e(id)}</a>'
            for id in dict.fromkeys(related[row["claim"]])) or "未单列关联意见"
        body.append(((reading_text(row["claim"]), reading_text(row["kind"]), links), ""))
    context = (f'<p>全篇另需核对：{issue_links(data["context_issues"])}。</p>'
               if data.get("context_issues") else "")
    return details("claim-overview", f'{len(index)} 项权利要求与关联意见速览',
                   '<p>关联意见据“权利要求对照”逐行汇总。编号链接可查看完整标题、证据和建议。'
                   '未列关联意见不表示已排除风险；本表不单独作侵权或无效结论。</p>' + context +
                   '<div class="table-wrap">' + table(("权利要求", "类型及引用", "关联意见"), body, "") + '</div>',
                   "overview-extra")


def technology_section(data):
    content = paragraphs(data.get("technology", []))
    if data.get("claim_index"):
        note = data.get("claim_path_note", "从属项继承其实际引用路径中的全部限定，再增加自身限定。兄弟项不自动组合；择一引用按各条路径分别核对。")
        items = "".join(f'<li><strong>{reading_text(row["claim"])}</strong> {reading_text(row["summary"])}'
                        f'<small>路径：{e(row["path"])}</small></li>' for row in data["claim_index"])
        content += details("claim-paths", "查看权利要求路径与技术要点", paragraphs([note]) + f'<ul>{items}</ul>')
    return content


def drawing_gallery(data, source_folder):
    import base64
    figures = []
    total = 0
    root = source_folder.resolve()
    for row in data.get("drawing_pages", []):
        image = (root / row["file"]).resolve()
        if not image.is_relative_to(root):
            raise ValueError("附图路径不得越过输入数据目录")
        with image.open("rb") as stream:
            payload = stream.read(16 * 1024 * 1024 + 1)
        total += len(payload)
        if len(payload) > 16 * 1024 * 1024 or total > 64 * 1024 * 1024:
            raise ValueError("附图单张最多 16 MiB，合计最多 64 MiB；请先保真压缩后再核对可读性")
        if payload.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif payload.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        else:
            raise ValueError(f"不是有效的 PNG/JPEG 图片：{row['file']}")
        src = "data:" + mime + ";base64," + base64.b64encode(payload).decode("ascii")
        caption = e(row["label"] + " · " + row["source"])
        figures.append(f'<figure><img src="{src}" alt="{caption}"><figcaption>{caption}</figcaption></figure>')
    if not figures:
        return ""
    return '<div id="drawing-pages" tabindex="-1"><h3>内嵌原图</h3><div class="review-gallery">' + "".join(figures) + '</div></div>'


def render(data, folder, source_folder=None):
    source_folder = source_folder or folder
    coverage = {row["section"]: row for row in data["coverage"]}
    issues = sorted(data["issues"], key=lambda row: tuple(PRIORITY).index(row["priority"]))
    pending = [row for row in issues if row["status"] == "pending"]
    structured = data.get("schema_version") == 3
    evidence_counts = Counter(id for row in data["evidence"] for id in row["issues"])
    figure_counts = Counter(id for row in data["figures"] for id in row["issues"])
    section_counts = Counter(row["section"] for row in issues)
    meta = [{"label": "审核版本", "text": data["version"]}, {"label": "审核阶段", "text": data["stage"]}]
    meta += data.get("meta", [])
    meta += [{"label": "人工复核", "text": data.get("reviewer", "未指定，待复核")}]
    if len({row["label"] for row in meta}) != len(meta):
        raise ValueError("meta 不得重复审核版本、审核阶段或人工复核字段")
    metadata = "".join(f'<div><dt>{e(row["label"])}</dt><dd>{e(row["text"])}</dd></div>' for row in meta)
    conclusions = data.get("conclusions")
    conclusion = ('<div class="conclusion-points">' + "".join(
        f'<p><b>{e(row["label"])}</b>{reading_text(row["text"])}</p>' for row in conclusions) + '</div>'
        if conclusions else paragraphs([data["conclusion"]]))
    claims = claim_index(data)
    if claims:
        conclusion += '<p class="overview-links"><a href="#claim-overview">查看权利要求与关联意见速览 ↓</a></p>'
    priority = "".join(
        f'<li><a class="action-link" href="#issue-{e(row["issue"])}"><b>{e(row["issue"])}</b><span>'
        f'<strong>{reading_text(row["impact"])}</strong><small>{e(row["role"])} · {reading_text(row["next"])}</small></span></a></li>'
        for row in data["actions"]) if structured else "".join(
            f'<li>{issue_link(row["id"], row["id"] + " · " + row["title"])}</li>' for row in pending[:4])
    gaps = data["gaps"] if structured else [row for row in coverage.values() if row["status"] in GAP_STATUSES][:3]
    gaps_html = "".join(f'<li><b>{SECTIONS[row["section"]]}</b>{e(row["note"])}</li>' for row in gaps)
    guide_text = ["意见编号用于稳定关联证据，处理顺序以优先级和待办为准。待核事项、处理进度和法律判断分别记录。"]
    statuses = set(row["status"] for row in issues)
    if len(statuses) == 1:
        guide_text.append(f'本轮 {len(issues)} 条意见的处理进度均为“{ISSUE[next(iter(statuses))]}”。')
    guide_text += data.get("reading_guide", [])
    guide = details("reading-guide", "如何阅读意见和候选改法", paragraphs(guide_text) +
                    '<a class="return-link" id="guide-return" href="#overview" hidden>返回来源意见</a>', "overview-extra")
    overview = (f'<section id="overview" class="overview" aria-labelledby="overview-title"><div class="panel summary">'
                f'<h2 id="overview-title">审核概览</h2>{conclusion}<div class="gaps"><div class="section-head">'
                '<h3>目前缺什么</h3><a href="#delivery">查看审核范围</a></div>'
                f'<ul>{gaps_html or "<li>覆盖记录未标注待核缺口。</li>"}</ul></div></div>'
                '<aside class="panel priority" aria-labelledby="priority-title"><h2 id="priority-title">优先待办</h2>'
                '<p class="reading-note">按本轮建议处理顺序排列，编号用于关联证据。</p>'
                f'<ul>{priority or "<li>本轮没有标记为待确认的意见。</li>"}</ul></aside>{guide}{claims}</section>')
    chapters = [("overview", "审核概览", overview)]
    technology = technology_section(data)
    if technology:
        chapters.append(("mechanism", "技术与路径", section("mechanism", "技术与路径", technology)))
    filters = '<div class="toolbar" hidden><label class="search-control">查找意见<input id="issue-query" type="search" placeholder="编号、关键词或原文"></label>'
    for field, label, all_label, mapping, key in (
        ("section", "分项", "全部分项", SECTIONS, "section"), ("issue", "处理进度", "全部进度", ISSUE, "status"),
        ("priority", "优先级", "全部优先级", PRIORITY, "priority"),
        ("confirmation", "待核事项", "全部待核事项", CONFIRMATION, "confirmation")):
        filters += filter_control(field + "-filter", label, all_label, mapping, [row.get(key, "") for row in issues])
    filters += '<button id="reset-issues" type="button">重置筛选</button><output id="issue-count" aria-live="polite"></output></div>'
    reference_by_id = {row["id"]: row for row in data.get("references", [])}
    cards = "".join(issue_card(row, structured, evidence_counts[row["id"]], figure_counts[row["id"]],
                              reference_by_id, data.get("conditions", []), len(statuses) > 1) for row in issues)
    issue_content = ('<p class="intro">按原文、问题、对应图证和修改建议阅读；法律依据可在每条意见内展开。</p>' + filters +
                     '<p class="empty filter-empty" id="issue-empty" hidden>没有符合当前筛选条件的意见，请调整条件。</p>' +
                     f'<div class="issue-list">{cards or "<p class=empty>本轮未单列审核意见，请查看覆盖范围与限制。</p>"}</div>')
    chapters.append(("issues", "审核意见", section("issues", "审核意见", issue_content)))
    evidence_filters = '<div class="toolbar" hidden>'
    claim_names = dict.fromkeys(row["claim"] for row in data["evidence"])
    evidence_filters += filter_control("claim-filter", "权利要求", "全部权项", {name: name for name in claim_names}, claim_names)
    evidence_filters += filter_control("visual-filter", "图示状态", "全部图示状态", VISUAL, [row["visual_status"] for row in data["evidence"]])
    evidence_filters += '<button id="reset-evidence" type="button">重置筛选</button><output id="evidence-count" aria-live="polite"></output></div>'
    evidence = ('<p class="intro">逐行保留权项原文、说明书位置、附图观察和支持判断。同一权项的不同分支分别记录。</p>' + evidence_filters +
                '<p class="empty filter-empty" id="evidence-empty" hidden>没有符合当前筛选条件的权项记录。</p>' +
                '<div class="table-wrap">' + evidence_table(data["evidence"]) + '</div>')
    chapters.append(("evidence", "权利要求对照", section("evidence", "权利要求对照", evidence, "matrix")))
    figures = '<p class="intro">“图示可见”只表示下列观察已经核读；未在图中显示的事实另行核实。</p>'
    figures += '<div class="table-wrap">' + figures_table(data["figures"]) + '</div>'
    if data.get("figure_notes"):
        records = [((reading_text(row["label"]), reading_text(row["text"]), reading_text(row["source"])), "") for row in data["figure_notes"]]
        figures += details("figure-notes", "附图与标号补充记录", '<div class="table-wrap">' + table(("核对项", "记录与建议", "位置"), records, "") + '</div>')
    figures += drawing_gallery(data, source_folder)
    chapters.append(("figures", "附图与原图", section("figures", "附图与原图", figures, "figure-table")))
    if data.get("conditions"):
        rows_html = [((reading_text(row["condition"]), reading_text(row["behavior"]),
                       reading_text(row["source"]) + '<p>' + issue_links(row["issues"]) + '</p>'), "") for row in data["conditions"]]
        conditions = paragraphs([data.get("conditions_intro", "按触发条件、动作和后续状态核对；未公开的阈值和恢复条件须明确标注。")])
        conditions += '<div class="table-wrap">' + table(("工况", "触发、动作与后续状态", "原文位置与意见"), rows_html, "") + '</div>'
        chapters.append(("conditions", "控制与工况", section("conditions", "控制与工况", conditions)))
    search = '<p class="intro">记录检索范围与限制，再按独立权利要求分别说明证据和初检判断。</p>'
    if reference_by_id:
        search += '<div id="reference-patents"><h3>对比文献与日期</h3><ul class="reference-list">' + "".join(
            f'<li id="ref-{e(row["id"])}" tabindex="-1"><b>{e(row["id"])} · {e(row["title"])}</b>'
            f'<p class="copy">{reading_text(row["note"])}</p><a href="{e(row["url"])}" target="_blank" rel="noopener">核对公开原文</a></li>'
            for row in reference_by_id.values()) + '</ul></div>'
    if data.get("search_common") or data.get("search_log"):
        search += '<div class="search-scope" id="search-scope"><h3>共同检索范围与局限</h3>' + paragraphs([data["search_common"]] if data.get("search_common") else [])
        if data.get("search_log"):
            records = [((e(row["label"]), reading_text(row["text"])), "") for row in data["search_log"]]
            search += details("search-log", "查看检索记录及待补项目", '<div class="table-wrap">' + table(("记录项", "本次记录与缺口"), records, "") + '</div>')
        search += '</div>'
    search += '<h3>独立权利要求的检索判断</h3><div class="table-wrap claim-search">' + search_table(data["search"]) + '</div>'
    chapters.append(("search", "现有技术", section("search", "现有技术", search, "search-table")))
    coverage_html = []
    for key, label in SECTIONS.items():
        row = coverage[key]
        if section_counts[key]:
            name = f'<a class="section-link" href="#issues" data-filter-section="{key}">{label}</a>'
            note = ""
        else:
            name = f'<span class="section-link" data-coverage-section="{key}">{label}</span>'
            note = "本分项未单列审核意见。" if row["status"] == "reviewed" else ""
        coverage_note = f'<small class="coverage-note">{note}</small>' if note else ""
        coverage_html.append(f'<div class="coverage-row"><div>{name}<small>{e(row["note"])}</small>'
                             f'{coverage_note}</div>{chip(row["status"], COVERAGE)}</div>')
    delivery_rows = []
    for row in data["deliverables"]:
        name = e(row["name"])
        if "file" in row:
            if not (folder / row["file"]).is_file():
                raise ValueError(f'已交付文档不存在于报告目录：{row["file"]}')
            name = f'<a href="{quote(row["file"])}" download>{name}</a>'
        delivery_rows.append(((name, chip(row["status"], DELIVERY), e(row.get("review", "未记录人工复核完成")), text_cell(row["note"])), ""))
    delivery = '<div class="coverage">' + "".join(coverage_html) + '</div><div class="table-wrap delivery-table">'
    delivery += table(("交付项", "文件交付", "人工复核", "说明"), delivery_rows, "本轮无文档交付记录。") + '</div>'
    chapters.append(("delivery", "范围与交付", section("delivery", "范围与交付", delivery)))
    navigation = "".join(f'<a href="#{id}">{title}</a>' for id, title, _ in chapters)
    return Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
        title=e(report_title(data["title"])), metadata=metadata, navigation=navigation,
        body="\n".join(content for _, _, content in chapters),
        styles=(TEMPLATE.parent / "review-report.css").read_text(encoding="utf-8"),
        script=(TEMPLATE.parent / "review-report.js").read_text(encoding="utf-8"))



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="UTF-8 审稿记录 JSON")
    parser.add_argument("--output", required=True, type=Path, help="离线 HTML 报告的新文件路径")
    args = parser.parse_args()
    try:
        with args.input.open("rb") as stream:
            raw = stream.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError("审稿记录不可超过 2 MiB")
        data = validate(json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_fields))
        if args.output.suffix.lower() != ".html":
            raise ValueError("输出文件扩展名应为 .html")
        content = render(data, args.output.parent, args.input.parent).encode("utf-8")
        with args.output.open("xb") as output:
            output.write(content)
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"无法生成报告：{error}\n")
    print(f"已生成离线专利审核报告：{args.output}")


if __name__ == "__main__":
    main()
