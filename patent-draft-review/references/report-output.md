# 专利审核报告

只审稿也交报告。网页标题和文件名统一使用「专利审核报告」，文件名可加案件名。以同一稿件版本组织概览、意见、逐图覆盖、图文证据、独立项检索和交付状态。不同版本或案件分别出表。先核对原件再填数据。模板负责展示和结构校验，证据是否可靠由审稿人核查。

视觉与交互以 [DESIGN.md](../DESIGN.md) 为唯一设计规范，具体数值在包内 CSS。扩展字段和输入模板见 [数据与组件](template-schema.md)，复审反馈核实及浏览器验收见 [复审与验收](report-validation.md)。本文件负责内容组织与基础字段，不另外维护一套版式。

## 填表顺序

1. **概览与覆盖。** 首屏先让读者知道本轮结论、哪些决定受影响、建议找谁核对及下一步。优先待办按实际阅读顺序列一至四项，每项链接到原意见。角色写建议分工，责任人未确定时标为「待定」。紧接结论列最关键的缺口，完整覆盖放在审核范围。逐项列研发交底、权利要求、说明书、附图、摘要、申请信息和独权检索。审阅覆盖与问题处置状态分开。
2. **逐图与图文矩阵。** 先列本轮范围内的各图及实际查看状态。每个独权关键限定、每条有疑点的从属引用路径或项内分支各占至少一行。保留权项原句、说明书定位、图号、页码、可见关系或未能核查原因、支持状态及关联意见。工况按区间、端点或初始状态分行。把触发条件写在核查限定，在核查说明中按前态、动作、后态记录原文明确的内容和待确认项。未见于图和图未实看分别写清。
3. **独立项检索。** 每个独立项分别记录新颖性和创造性。写检索来源、实际范围、文献原文位置、日期核查及局限，未执行时写原因和下一步。图文矩阵的本案材料与现有技术证据分开。
4. **逐条意见。** 用稳定编号串联摘要、原文、证据和后续复核。先给一句摘要，再按「原文与位置 → 具体问题 → 对应图证 → 适用阶段和改法 → 可展开的法律依据」组织。法律类别在折叠时仍可见。区分待核事项、优先级、法律判断和处理进度。相关图文、附图只使用已显式关联该编号的记录。深链接保留编号和返回入口。适用程序及关键限制写在改法旁，阅读说明只作补充。原文未明确时，写需确认的具体事实和条件。
5. **交付和复核状态。** 分开登记报告和 Word 双版本的文件交付、人工复核及说明。未指定人工复核人就如实写明，文件已生成不能标为已完成复核。Word 未要求时标为「未要求」。需要 Word 时按同一可编辑基线生成两份正文一致的文档。

## 生成离线报告

在 Skill 目录下运行，输入为 UTF-8 JSON，输出为新的本地 HTML 文件。Python 3.10 或更高版本，无需额外安装 HTML 依赖。

```text
python scripts/render_review.py 审核数据.json --output 案件名_专利审核报告.html
```

字段默认为非空字符串。需要填来源、页码但缺证据时，用「未提供」「无页码，见图3」等事实描述。列表允许为空时，覆盖项需说明本轮为何没有对应记录。

| 字段 | 内容 |
| --- | --- |
| `schema_version` | 新报告填整数 `3`。 |
| `title, version, stage, conclusion` | 案件名、稿件版本、审稿阶段及一句结论。阶段写申请前、审查中、授权公告后或经核实的具体程序。 |
| `phase` | 结构化阶段 `before_filing`（申请前）、`pending`（审查中）、`granted`（授权公告后）、`unknown`（待核）。与展示用的 `stage` 保持一致。 |
| `actions[]` | `issue,impact,role,next`。按阅读顺序最多四项，引用现有且状态为 `pending` 的意见，编号不得重复。有待确认意见时至少一项。每项用一句话说清下一步核对什么。 |
| `gaps[]` | `section,note`。最多三项，`section` 对应 `coverage` 中 `missing`、`partial` 或 `unread` 的分项，不得重复。存在这类分项时至少一项。 |
| `coverage[]` | `section,status,note`。板块 `disclosure,claims,description,drawings,abstract,filing,search` 各一项。状态 `reviewed,partial,unread,missing,na` 对应已审、部分核对、未核读、缺材料、不适用。 |
| `figures[]` | `figure,page,visual_status,observation,issues`。逐图记录。同一图号可在不同页出现。 |
| `evidence[]` | `claim,path,feature,quote,description,figure,page,visual_status,observation,support_status,issues`。原文写在 `quote`，说明书位置及记载写在 `description`。支持状态 `supported,partial,gap,unverified,na` 对应有支持、部分支持、缺口、待核、不适用。 |
| `search[]` | 每个独立项一条 `claim,scope,novelty,inventiveness`。`scope` 记来源和范围。`novelty` 与 `inventiveness` 均为 `{status,basis}`，状态 `reviewed,partial,not_run`。 |
| `issues[]` | `id,section,title,status,priority,summary,confirmation,problem,originals,legal,edits`。处理状态 `pending,adopted,rejected,resolved`，优先级 `high,medium,low`。`summary` 一句话交代要核实的事项及其影响，`problem` 保留技术和证据细节。`confirmation` 取 `technical,evidence,search,writing,decision,none`，分别表示待研发确认、待补证据、待检索比对、文稿校订、待决定、无待核事项。 |
| `deliverables[]` | `name,status,note`。状态 `ready,pending,not_requested,unavailable` 对应已交付、待完成、未要求、未生成。已交的 Word 可用 `file` 填同目录 DOCX 文件名。 |

每条意见的结构化字段按下表填写。

| 字段 | 内容 |
| --- | --- |
| `originals[]` | 至少一条，每条含 `location,quote`。位置写到 PDF 页码、权项分句、说明书段落、图号或其他可复核位置。每段原文分别对应其出处。缺材料时写明待核部位与未取得原因。 |
| `legal` | `assessment,reason,sources`。`assessment` 取 `supported`（判断有依据）、`risk`（存在风险待核）、`drafting`（一般撰写问题）、`insufficient`（证据不足）。`reason` 写出证据和结论之间的关系。后两类没有来源时显式填 `sources: []`，并在 `reason` 说明理由。 |
| `legal.sources[]` | `name,provision,url,applicability`。写来源全名、条款或节号、官方链接和适用理由。裁判的 `provision` 写案号及对应裁判段落，`applicability` 写可类比的边界。链接须为 HTTP(S)。`supported` 和 `risk` 至少列一条来源。 |
| `edits[]` | 至少一条，每条含 `location,operation,applicability,text,condition,sync`。依次写目标位置、具体动作、适用阶段、候选文字、采纳条件、同步位置。条件或同步项不适用时写明「无额外条件」或「无需同步」及理由。 |
| `edits[].applicability` | `kind,note`。`kind` 取 `current_draft`（当前稿件可考虑）、`review`（本轮可做的核查）、`future_draft`（后续新稿参考）、`procedure_check`（先核对适用程序）。授权后或阶段待核时不允许填 `current_draft`。在 `note` 写清范围和限制，例如把授权后待核的权项建议与后续新稿的说明书改写分开。 |

旧数据未填 `schema_version` 或填 `1` 时，保留原意见的 `location`、`problem` 和 `reference_fix`。版本 `2` 保留原文、法律判断和改法结构。两版缺失的适用阶段显示为待补核，首页保留待确认意见链接。返稿复核时逐条查证后补录为 `3`，沿用意见编号和处理记录。

`visual_status` 取 `seen,text_only,unclear,unread,missing,na`，对应图上可见、仅正文记载、图已看但辨识不足、未实看、图未取得、不适用。以具体限定或逐图核对项为单位填写。`issues` 在图和矩阵行中为意见编号列表，无关联时写空列表。编号可用 `R-01`。报告中的 Word 下载链接须指向实际存在的同目录 DOCX。生成完成后核对交付状态再分享。

无法运行脚本或写 HTML 时，按同一组字段交 Markdown，保留覆盖状态、页码和编号。图文矩阵表头可用「权项及路径｜核查限定｜权项原文｜说明书位置｜图号及页码｜图示状态及说明｜支持判断｜意见号」。

## 交付验收

- 打开实际交付文件，在桌面、窄屏、手机和打印预览检查标题、正文密度、顺序和可读性。手机上的证据表应显示带字段标签的纵向卡片。打印检查全部意见和证据能否呈现。
- 走两条阅读路径。项目负责人从结论和缺口看到优先待办及下一步。复核人员从首页或带筛选的证据表进入同一意见，查看关联图文和附图，返回摘要或用浏览器后退。若定位到筛选条件外的意见，应有提示且原筛选与展开状态保留。
- 在手机上用意见深链接打开改法，确认意见编号、修改落点和适用阶段先于候选文字。检查长标题、短权项编号的换行与证据空状态。模板校验通过后仍需核对源证据。
- 查清关键独权限定和重点从属分支有无漏行。已取得的关键图若未实看，标出图号、页码和原因。关键阈值或故障的工况逐行回看出处。
- 逐条核对引文和出处、法条或裁判的精确位置和适用范围，以及每项改法的动作、目标位置、条件和同步范围。把待确认、已采纳和已解决分开。无检索时仍记录独立项和未执行原因。
- Word 已要求时核验两份文件及正文、批注、修订标记。若暂未生成，仍交报告，在交付状态写明缺少的材料或工具。
