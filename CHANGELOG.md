# v0.6.1 试用与发布附件 · 2026-11-16

- Skill 详情加入公开试用入口，描述补充申请前专利审稿的英文表述。
- 公开试用页新增 40 lx 英文示例，展示说明书原句、缺失工况及经研发确认后可采用的改法。
- v0.6.1 Release 提供 WorkBuddy 导入包和种苗箱样稿与附图的直链下载，双语 README 与试用页使用同一组附件。

- Added public trial links to the skill and clarified the pre-filing review use case in its description.
- Added an English 40 lx review note with the source passage, the evidence gap, and an edit conditional on engineering confirmation.
- The v0.6.1 release provides direct downloads for the WorkBuddy import ZIP and the fictional draft with its drawing.

# GitHub 试用入口 · 2026-11-16

新增可下载的虚构种苗箱样稿、图 1 和可逐条对照的预期报告。双语首页集中展示试用和安装方式，Skill 描述补充申请前审稿、返稿复核与说明书支持等触发词。

Added a downloadable fictional seedling-box draft, Figure 1, and an evidence-linked expected report. The bilingual README now surfaces the sample and installation, and the skill description names specific draft-review tasks.

# v0.6.1 · 2026-11-15

本次公开更新从 v0.4.0 升至 v0.6.1，纳入中间版本已实现的因果核查与权项修改候选功能。

- **因果核查必查。** 按背景技术问题、权项特征、作用过程和有证据支持的效果逐项核对，关键缺口关联高优先级意见并在首页显示。
- **两处校验修复。** 权项对照和修改候选也会触发适用性检查。独权覆盖同时核对速览、检索和因果记录，并指出具体漏项或类型冲突。
- **三项证据复核。** 核对输入转换会丢失哪些信息，说明书是否指导选择可实施的组合，以及输出刻度与实测精度各有何依据。
- **权项改法。** 支持保守澄清、平衡限定及收窄后备，记录组合依据、实施例冲突和修改后的权项关系。
- **兼容。** 继续使用 schema 4，建议速览用 `claim_type` 明确类型。旧 schema 1–3 缺少因果记录时仍可生成带“未完成”提示的报告。原有 schema 4 记录如存在漏项或类型歧义，按校验提示回原文补正。
- **验证。** 81 项自动测试通过。同一专利定向复验中，旧版放行的两组异常输入由 v0.6.1 拒绝。公开演示使用虚构种苗箱数据。

This public update moves from v0.4.0 to v0.6.1 and includes the causal review and claim amendment features developed in between.

- **Required causal review.** Connect technical problems, claim features, mechanisms, and supported effects. Surface critical gaps in the report overview.
- **Validation fixes.** Claim evidence and amendment options now prevent a review being marked inapplicable. The renderer cross-checks independent claims across the claim index, search records, and causal targets.
- **Three evidence checks.** Examine information lost during input transformations, guidance for choosing workable combinations, and the evidence available for actual precision.
- **Claim amendment options.** Record conservative clarification, balanced limitations, and narrower fallback options with support for feature combinations and their effect on scope.
- **Compatibility.** Schema 4 remains current. Use `claim_type` to identify independent and dependent claims. Schema 1–3 reports without causal records can still be rendered with an incomplete-review notice.
- **Verification.** All 81 automated tests passed. A targeted rerun on the same patent confirmed that v0.6.1 rejects two inputs that the preceding version accepted. The public demo uses fictional data.

# v0.4.0 · 专利审稿 / Patent Draft Review

- 支持从申请人或使用方立场审阅稿件、返稿及公开文本，记录法域、程序阶段和版本。
- 报告将意见关联至权项对照、附图和工况，保留筛选、定位和返回路径。文件交付与人工复核分别记录。
- 提供统一的报告设计规范、可填写模板、合成演示和 WorkBuddy 导入包。

- Review drafts, revisions, and published texts from either the applicant’s or downstream user’s perspective.
- Navigate from issues to claim evidence, drawings, and operating conditions. The report tracks delivery and human review separately.
- Includes the report design specification, editable input template, account-free synthetic demo, and WorkBuddy import ZIP.
