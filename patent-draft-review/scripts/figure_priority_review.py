"""Check the recorded figure cross-check and impact-based priority in schema 5."""


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 必须填写")
    return value


def objects(value, field):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{field} 必须是对象数组")
    return value


def issue_priority(impact):
    if not isinstance(impact, dict):
        raise ValueError("每条意见须记录 impact")
    claim, effect = impact.get("claim"), impact.get("effect")
    if claim not in ("none", "local", "material") or effect not in ("none", "local", "core"):
        raise ValueError("impact.claim 或 impact.effect 未归类")
    text(impact.get("reason"), "impact.reason")
    if claim == "material":
        text(impact.get("claim_target"), "impact.claim_target")
    if effect == "core":
        text(impact.get("effect_target"), "impact.effect_target")
    if claim == "material" or effect == "core":
        return "high"
    return "medium" if claim == "local" or effect == "local" else "low"


def validate_figure_priority(data):
    audit = data.get("figure_audit")
    if not isinstance(audit, dict):
        raise ValueError("新版报告必须有 figure_audit")
    views = objects(audit.get("views"), "figure_audit.views")
    legend = objects(audit.get("legend"), "figure_audit.legend")
    status = audit.get("status")
    if status not in ("checked", "partial", "not_applicable"):
        raise ValueError("figure_audit.status 必须为 checked、partial 或 not_applicable")
    expected = {(row["figure"], row["page"]): row["visual_status"] for row in data["figures"]}
    drawing_coverage = next(row["status"] for row in data["coverage"] if row["section"] == "drawings")
    issues = {issue["id"]: issue for issue in data["issues"]}
    for issue in issues.values():
        if issue_priority(issue.get("impact")) != issue["priority"]:
            raise ValueError(f"意见 {issue['id']} 的优先级与权项、效果影响不符")
    if status == "not_applicable":
        text(audit.get("reason"), "figure_audit.reason")
        if expected or views or legend or data.get("drawing_pages") or drawing_coverage != "na":
            raise ValueError("已有图件、图件缺口或附图记录时不能标为不适用")
        return
    if not views or drawing_coverage == "na":
        raise ValueError("有附图任务时须建立逐图核对记录")
    if status == "partial":
        text(audit.get("reason"), "figure_audit.reason")
        if drawing_coverage == "reviewed":
            raise ValueError("逐图核对未齐时，附图覆盖不能标为已核查")
    elif drawing_coverage != "reviewed":
        raise ValueError("逐图核对为已完成时，附图覆盖须与之对应")
    legend_by_mark = {}
    for row in legend:
        mark = text(row.get("mark"), "legend.mark")
        text(row.get("name"), "legend.name")
        text(row.get("source"), "legend.source")
        if mark in legend_by_mark:
            raise ValueError(f"标号 {mark} 的说明书定义应合并列出，冲突在意见中说明")
        legend_by_mark[mark] = row
    seen, used_marks = set(), set()
    for view in views:
        figure = text(view.get("figure"), "views.figure")
        page = text(view.get("page"), "views.page")
        key = (figure, page)
        if key not in expected or key in seen:
            raise ValueError(f"逐图核对缺少对应图号和页码或出现重复: {figure} / {page}")
        seen.add(key)
        text(view.get("description_ref"), "views.description_ref")
        marks = objects(view.get("marks"), "views.marks")
        state = view.get("status")
        if state != "checked":
            if state not in ("missing", "unread", "unreadable") or status == "checked" or marks:
                raise ValueError(f"{figure} 缺图或未看清时不能标全案已核对或填写看到的标号")
            text(view.get("reason"), "views.reason")
            continue
        if expected[key] not in ("seen", "unclear"):
            raise ValueError(f"{figure} 的标号核对须基于实际看图记录")
        if not marks:
            text(view.get("reason"), "无标号图的核对说明")
        targets = set()
        for mark in marks:
            mark_id = text(mark.get("mark"), "marks.mark")
            target = text(mark.get("target"), "marks.target")
            if target in targets:
                raise ValueError(f"{figure} 重复记录同一引注位置: {target}")
            targets.add(target)
            state = mark.get("status")
            if state not in ("match", "suspect", "unclear", "text_label"):
                raise ValueError(f"{figure} 标号 {mark_id} 状态无效")
            ref = mark.get("legend_mark")
            if ref is not None:
                ref = text(ref, "marks.legend_mark")
                if ref not in legend_by_mark:
                    raise ValueError(f"{figure} 关联的说明书标号 {ref} 未登记")
                used_marks.add(ref)
            if state == "match" and ref != mark_id:
                raise ValueError(f"{figure} 标号 {mark_id} 与说明书记载不同，不能标一致")
            if state != "match":
                text(mark.get("note"), "marks.note")
            if (state == "suspect" or "issue" in mark) and (not isinstance(mark.get("issue"), str) or mark["issue"] not in issues):
                raise ValueError(f"{figure} 标号 {mark_id} 疑点须关联一条意见")
    if seen != set(expected):
        raise ValueError("附图说明、正文所引和实际看到的视图须在逐图核对中逐一登记")
    for mark in set(legend_by_mark) - used_marks:
        text(legend_by_mark[mark].get("not_located_reason"), f"说明书标号 {mark} 未找到对应图的原因")
