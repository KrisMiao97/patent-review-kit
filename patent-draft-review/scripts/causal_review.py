"""Required causal records and visible evidence gaps; no automated merits finding."""
import html
import re

STATUS = {"supported": "因果对应有依据", "partial": "部分有依据", "gap": "关键依据缺失", "contradicted": "现有证据存在矛盾"}
LINKS = {"problem": "问题及原因", "mechanism": "结构与作用过程", "effect": "效果及成立条件"}
KINDS = {"document": "原文事实", "inference": "工程推断", "test": "测试结果", "assumption": "待验证假设"}
ID = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,47}\Z")
CLAIM_TYPES = ("independent", "dependent")
CLAIM_RECORD_SECTIONS = {"search": "独权检索", "claim_index": "权项速览", "evidence": "权项对照", "amendment_options": "权项修改候选"}


def obj(value, path, fields=(), choices=None):
    if not isinstance(value, dict):
        raise ValueError(f"{path} 必须是对象")
    for field in fields:
        text = value.get(field)
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ValueError(f"{path}.{field} 必须填写具体非空文本（最多 4000 字）")
    for field, allowed in (choices or {}).items():
        if not isinstance(value.get(field), str) or value[field] not in allowed:
            raise ValueError(f"{path}.{field} 无效，可选 {', '.join(allowed)}")
    return value


def array(value, path, required=False):
    if not isinstance(value, list) or len(value) > 2000 or (required and not value):
        raise ValueError(f"{path} 必须是{'非空' if required else ''}数组（最多 2000 项）")
    return value


def inventory(value, path, fields, choices=None):
    result = {}
    for row in array(value, path, True):
        obj(row, path, ("id", *fields), choices)
        if not ID.fullmatch(row["id"]) or row["id"] in result:
            raise ValueError(f"{path}.id 格式错误或重复")
        result[row["id"]] = row
    return result


def legacy_claim_type(kind):
    # Read the type label only. A dependent claim's citation can mention an independent claim.
    label = re.split(r"[,，;；(（]", kind, maxsplit=1)[0].strip()
    english = re.match(r"(independent|dependent)\b", label, re.IGNORECASE)
    if english:
        return english.group(1).lower()
    chinese = re.search(r"(?<!非)(独立|从属)(?:权利要求|权项|项|$)", label)
    return {"独立": "independent", "从属": "dependent"}.get(chinese.group(1)) if chinese else None


def validate_claim_coverage(data, targets):
    search_claims = {row["claim"] for row in data["search"]}
    target_types = {}
    for row in targets.values():
        if row["kind"] in CLAIM_TYPES:
            target_types.setdefault(row["claim"], set()).add(row["kind"])
    for claim, kinds in target_types.items():
        if len(kinds) > 1:
            raise ValueError(f"因果核查对同一权项 {claim} 登记了相互冲突的独立／从属类型")

    required_independent = set(search_claims)
    for position, row in enumerate(data.get("claim_index", []), 1):
        claim = row["claim"]
        label_type = legacy_claim_type(row["kind"])
        if "claim_type" in row:
            path = f"claim_index[{position}] ({claim})"
            explicit_type = obj(row, path, choices={"claim_type": CLAIM_TYPES})["claim_type"]
            if label_type is not None and explicit_type != label_type:
                raise ValueError(f"{path}.claim_type 与速览显示类型 kind 矛盾")
            label_type = explicit_type
        registered_types = target_types.get(claim, set())
        if claim in search_claims:
            registered_types = registered_types | {"independent"}
        if label_type is not None:
            registered_types = registered_types | {label_type}
        if len(registered_types) > 1:
            raise ValueError(f"权项 {claim} 的速览、检索或因果核查类型矛盾")
        if not registered_types:
            raise ValueError(f"权项速览 {claim} 的独立／从属类型不明，请填 claim_type")
        if "independent" in registered_types:
            required_independent.add(claim)

    missing = required_independent - {claim for claim, kinds in target_types.items() if "independent" in kinds}
    if missing:
        names = "、".join(sorted(missing))
        raise ValueError(f"因果核查未覆盖权项速览或独权检索清单中的全部独立权利要求：{names}")


def validate_causal(data):
    review = data.get("causal_review")
    if review is None and data.get("schema_version", 1) < 4:
        return
    obj(review, "causal_review", ("scope",), {"applicability": ("functional", "not_applicable")})
    if review["applicability"] == "not_applicable":
        # Only nonfunctional material (e.g. design appearance) may use this route.
        for key in ("targets", "problems", "chains"):
            if array(review.get(key), "causal_review." + key):
                raise ValueError("不适用的因果核查不得同时记录功能性目标、问题或因果链")
        claim_records = [label for field, label in CLAIM_RECORD_SECTIONS.items() if data.get(field)]
        if claim_records:
            raise ValueError(f"已有权项记录（{'、'.join(claim_records)}），不能将功能性因果必查整体标为不适用")
        return
    targets = inventory(review.get("targets"), "causal_review.targets", ("claim", "path"),
                        {"kind": ("independent", "dependent", "unavailable")})
    problems = inventory(review.get("problems"), "causal_review.problems", ("statement", "location"))
    target_keys = [(t["claim"], t["path"]) for t in targets.values()]
    if len(target_keys) != len(set(target_keys)):
        raise ValueError("因果核查的权项及路径不得重复")
    validate_claim_coverage(data, targets)
    issues = {x["id"]: x for x in data["issues"]}
    chains = inventory(review.get("chains"), "causal_review.chains",
                       ("target_id", "problem_id", "scenario", "failure", "cause", "features",
                        "mechanism", "effect", "limits", "countercheck", "next_action"), {"status": STATUS})
    covered_targets, covered_problems = set(), set()
    for cid, row in chains.items():
        path = "causal_review.chains." + cid
        if row["target_id"] not in targets or row["problem_id"] not in problems:
            raise ValueError(f"{path} 指向不存在的权项路径或技术问题")
        covered_targets.add(row["target_id"])
        covered_problems.add(row["problem_id"])
        if type(row.get("critical")) is not bool:
            raise ValueError(f"{path}.critical 必须明确是否影响核心问题或效果")
        evidence = array(row.get("evidence"), path + ".evidence", True)
        for item in evidence:
            obj(item, path + ".evidence", ("location", "quote", "reason"), {"link": LINKS, "kind": KINDS})
        if {e["link"] for e in evidence} != set(LINKS):
            raise ValueError(f"{path} 必须分别记录问题、作用过程和效果的依据或假设")
        gaps = array(row.get("gaps"), path + ".gaps")
        for gap in gaps:
            obj({"gap": gap}, path, ("gap",))
        linked = array(row.get("issues"), path + ".issues")
        if any(not isinstance(x, str) or x not in issues for x in linked) or len(linked) != len(set(linked)):
            raise ValueError(f"{path}.issues 有悬空或重复意见编号")
        if row["status"] == "supported":
            if gaps or any(x["kind"] == "assumption" for x in evidence):
                raise ValueError(f"{path} 有缺口或待验证假设，不能标为因果对应有依据")
        else:
            if not gaps or not linked:
                raise ValueError(f"{path} 必须明确具体缺口，并关联未解决的审核意见")
            unresolved = [issues[x] for x in linked if issues[x]["status"] in ("pending", "adopted")]
            if not unresolved:
                raise ValueError(f"{path} 因果缺口仍在，关联意见不能全部标为已解决或未采纳")
            if targets[row["target_id"]]["kind"] in ("independent", "unavailable") and not row["critical"]:
                raise ValueError(f"{path} 独立项或材料缺失的因果缺口必须标为关键")
            if row["critical"] and not any(x["priority"] == "high" for x in unresolved):
                raise ValueError(f"{path} 关键依据缺失必须关联高优先级未解决意见")
    if covered_targets != set(targets) or covered_problems != set(problems):
        raise ValueError("因果必查未逐项覆盖全部已登记权项路径和背景技术问题")


def esc(value):
    return html.escape(str(value), quote=True)


def anchor(cid):
    return "causal-chain-" + cid.encode("utf8").hex()


def causal_overview(data):
    review = data.get("causal_review")
    if review is None:
        return ('<div id="causal-overview" class="causal-alert"><b>技术因果必查未完成</b>'
                '<p>本报告沿用旧版数据，尚未记录问题、结构与效果的因果对应。旧记录可阅读，不能据此认定技术方案已通过本项核查；返稿须回到原件补核。</p></div>')
    if review["applicability"] == "not_applicable":
        return '<div id="causal-overview" class="causal-alert"><b>因果必查适用范围</b><p>' + esc(review["scope"]) + '</p></div>'
    incomplete = [r for r in review["chains"] if r["status"] != "supported"]
    if not incomplete:
        return ('<div id="causal-overview" class="causal-alert"><b>已逐项记录技术因果依据</b>'
                '<p>判断仅适用于所列权项、工况与效果，不代表已经实测、可以授权或其他审核项目通过。'
                '<a href="#causal-review">核对依据与条件</a></p></div>')
    items = ''.join('<li><a href="#' + anchor(r["id"]) + '">' + esc(r["id"]) + '</a> · '
                    + ('关键：' if r["critical"] else '') + '；'.join(esc(x) for x in r["gaps"]) + '</li>' for r in incomplete)
    return ('<div id="causal-overview" class="causal-alert"><b>技术因果对应尚未成立或仍有缺口</b>'
            '<p>以下依据缺口需要先明确，不能仅通过补全结构文字或缩小效果表述认定问题已解决。</p><ul>' + items + '</ul></div>')


def causal_section(data):
    review = data.get("causal_review")
    if not review or review["applicability"] != "functional":
        return ""
    targets = {x["id"]: x for x in review["targets"]}
    problems = {x["id"]: x for x in review["problems"]}
    cards = []
    labels = (("scenario", "使用工况"), ("failure", "故障或待改进现象"), ("cause", "原因及待证环节"),
              ("features", "当前权项的结构、步骤或条件"), ("mechanism", "怎样作用于原因"),
              ("effect", "能够支持的效果"), ("limits", "成立条件及边界"), ("countercheck", "反向核查与相反证据"))
    for row in review["chains"]:
        target, problem = targets[row["target_id"]], problems[row["problem_id"]]
        body = ''.join('<dt>' + label + '</dt><dd>' + esc(row[key]) + '</dd>' for key, label in labels)
        evidence = ''.join('<li><b>' + LINKS[x["link"]] + ' · ' + KINDS[x["kind"]] + '</b><p>'
                           + esc(x["location"]) + '</p><blockquote>' + esc(x["quote"]) + '</blockquote><p>'
                           + esc(x["reason"]) + '</p></li>' for x in row["evidence"])
        gaps = ''.join('<li>' + esc(g) + '</li>' for g in row["gaps"])
        links = ' '.join('<a href="#issue-' + esc(i) + '">' + esc(i) + '</a>' for i in row["issues"])
        cards.append('<article class="causal-chain" id="' + anchor(row["id"]) + '" tabindex="-1"><h3>'
                     + esc(row["id"]) + ' · ' + STATUS[row["status"]] + '</h3><p><b>' + esc(target["claim"])
                     + '</b> · ' + esc(target["path"]) + '</p><p><b>所回应的问题：</b>' + esc(problem["statement"])
                     + '</p><p class="reading-note">问题出处：' + esc(problem["location"]) + '</p><dl class="causal-facts">'
                     + body + '</dl><h4>分环节依据</h4><ol>' + evidence + '</ol><h4>缺口与下一步</h4>'
                     + ('<ul>' + gaps + '</ul>' if gaps else '<p>本行未记录未决缺口；仍限于上述条件。</p>')
                     + '<p>' + esc(row["next_action"]) + '</p><p>' + links + '</p></article>')
    return ('<section id="causal-review" class="panel" aria-labelledby="causal-review-title"><h2 id="causal-review-title">'
            '技术问题、方案与效果</h2><p>' + esc(review["scope"]) + '</p>' + ''.join(cards) + '</section>')
