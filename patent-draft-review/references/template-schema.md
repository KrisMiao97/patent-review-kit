# 模板数据与组件

新报告使用 schema 4，基础字段见 [报告输出](report-output.md)，必须增加下述因果核查记录。旧数据 1／2／3 可生成，但缺少本项记录时首页明确显示“技术因果必查未完成”，不得作为本项已通过的报告。字段均为纯文本或结构化数组，生成器统一转义；不接收任意 HTML、脚本或远程图像。

## 因果必查数据

`causal_review` 含 `applicability,scope,targets,problems,chains`。`applicability` 为 `functional`。仅对不主张功能的外观等材料可填 `not_applicable`，在 `scope` 解释理由，并将三个数组留空。`claim_index[]`、`search[]`、`evidence[]` 或 `amendment_options[]` 任一含权项记录时，校验拒绝整案标为不适用。缺件按功能性报告记录未取材料和影响。

- `scope` 写明本轮原稿版本、实际核查范围及局限。
- `targets[]` 每条有稳定 `id`、原文权项名 `claim`、累计及备选路径 `path`、`kind`（`independent,dependent,unavailable`）。包含全部独权及需判断新增效果的从属路径。没有权项时用 `unavailable` 明确材料缺失。`claim_index[].claim`、`search[].claim` 和 `targets[].claim` 使用同一编号写法。速览或检索任一列为独权的，因果记录须有对应独立路径，登记的每条路径至少有一条对应链。不同栏目对同一权项的类型矛盾时拒绝生成。
- `problems[]` 每条有 `id,statement,location`：背景／发明内容／效果／用户目标中待核的问题及其出处。逐项提取，不因为没有现成方案而漏掉问题。原文缺失时明确待取得对象。
- `chains[]` 每条有 `id,target_id,problem_id`，对应已登记的权项路径与问题。所有目标和问题至少对应一条链；同一权项的多个问题及备选路径可有多条链。
- 每条链必填非空文本 `scenario,failure,cause,features,mechanism,effect,limits,countercheck,next_action`，分别为工况、故障／待改进现象、原因、当前权项特征、作用过程、效果、成立边界、反向核查、下一步。依[输入信息、方案选型与效果精度](causal-review.md#输入信息方案选型与效果精度)填写其适用环节及出处。不涉及某一步时说明原因。缺失信息写具体缺口，不能编造。
- `status` 为 `supported,partial,gap,contradicted`；`critical` 为布尔值，表示是否影响独权、核心问题或核心效果。独权或权项缺失目标的未决链必须为关键。
- `evidence[]` 每条含 `link,kind,location,quote,reason`。`link` 为 `problem,mechanism,effect`，三个环节各至少一条。`kind` 为 `document,inference,test,assumption`。写清可复核位置、原文／数据或明确缺件说明，以及该依据支持什么。推断记录事实前提和推理；原稿效果主张不能自证效果。缺件记录用 `assumption`，不得写成事实。
- `gaps[]` 是具体未决缺口文本数组，`issues[]` 关联现有意见。`supported` 不得含缺口或待验证假设；其他状态必须列缺口，并至少关联一项 `pending` 或 `adopted` 意见。关键缺口至少关联一项高优先级未解决意见。

首页缺口提示和对应关系章节由同一数据生成，不受最多四项待办或三项材料缺口的限制。每条未决链均显示具体缺口，详细记录保持展开，打印及无脚本可读。自动校验只检查字段、覆盖、状态和关联，不检查原文真实性及因果推理质量；后者按 [因果必查](causal-review.md) 回到原件核查。

## 可直接填写的输入模板

复制 `examples/template-input.json` 后逐项换成已核实的案件事实。例中是虚构种苗箱，仅演示格式，不是可复用法律结论。执行：

```text
python scripts/render_review.py examples/template-input.json --output 新报告.html
```

输出必须是新文件，不覆盖已有交付。程序只需 Python 3.10+ 标准库；CSS、JS 和附图均内嵌到单个 HTML。

## 扩展字段

| 字段 | 结构与用途 | 无此字段时 |
| --- | --- | --- |
| `meta[]` | `{label,text}`，如报告修订、审阅立场、法域、申请人及来源、整理人。不得与固定字段审核版本／审核阶段／人工复核重名。 | 只展示固定字段。 |
| `reviewer` | 人工复核人、日期和状态的事实文本，不以文件已生成推定已复核。 | 显示“未指定，待复核”。 |
| `conclusions[]` | `{label,text}`，将 `conclusion` 完整含义拆为易读段落。须保留范围与局限。 | 展示原 `conclusion`。 |
| `reading_guide[]` | 补充阅读说明的文本段落。程序自动说明编号用途和统一处理进度。 | 保留通用说明。 |
| `technology[]` | 技术方案的完整说明段落，写安装位置、动作、方向、作用和来源。 | 有权项路径时仅展示路径区。 |
| `claim_index[]` | `{claim,kind,claim_type,path,summary}`。`kind` 为显示用类型及引用说明。功能性新报告填写结构化 `claim_type`，取 `independent` 或 `dependent`。旧记录可从明确的中英文 `kind` 标签、已登记的同名检索或因果目标核对类型。来源矛盾或类型无法确定时列明权项，补 `claim_type`。每个权项只出现一次，多条择一路径写入 `path`。 | 旧记录仍可输出不含速览的报告。新报告有原文时先登记全部权项，生成器无法识别所有输入栏目均未列出的原文权项。 |
| `claim_path_note` | 解释该案的继承和替代路径。 | 显示通用累计限定说明。 |
| `context_issues[]` | 适用于全篇的现有意见编号，列在速览说明里。 | 不额外关联。 |
| `conditions_intro` | 工况表的适用范围和原文边界。 | 显示通用工况说明。 |
| `conditions[]` | `{condition,behavior,source,issues}`。`behavior` 写触发前状态、动作、后续状态与未明示部分；`issues` 显式关联意见。 | 省去整个工况章节及导航入口。 |
| `references[]` | `{id,title,note,url}`。`title` 含完整公开号、主体、日期及文献性质；`note` 含实际核读位置、公开内容和资格边界。 | 不生成独立文献目录，已有检索正文仍保留。 |
| `issues[].reference_ids[]` | 引用 `references[].id`；该条意见先展示文献身份，再跳到文献与日期记录。 | 无附加文献入口。 |
| `search_common` | 已实际执行的共同范围、日期、词式及局限。 | 使用原独权行内 `scope`。 |
| `search[].focus` | 每项独权的检索重点。有一项填写则所有独权行都要填，并同时填 `search_common`。原 `scope` 仍存源数据供复核，展示范围由 `search_common + focus` 承担，人工核对不能删掉必要限制。 | 表头保持“检索来源及范围”，展示 `scope`。 |
| `search_log[]` | `{label,text}`，日期、来源、分类、检索式、命中、实际核读和复核记录；未知如实填写。 | 不补造记录表。 |
| `figure_notes[]` | `{label,text,source}`，标号冲突等补充核查记录。 | 只展示逐图表与原图。 |
| `drawing_pages[]` | `{file,label,source}`，输入 JSON 所在目录内的 PNG/JPEG 相对路径、图号标签、原件版本与页码。禁止路径越界和活动 SVG。每张最多 16 MiB、合计 64 MiB；优先在保真前提下压缩并目视复核。 | 不生成原图占位；附图覆盖状态仍应说明是否已实际核读。 |
| `deliverables[].review` | 每份文件的人工复核状态。未要求的文件可写“不适用（本轮未交付）”。 | “未记录人工复核完成”。 |

## 单一来源与展示规则

### 三档候选扩展

v0.5.2 沿用 schema 3 的可选 `amendment_options[]`，v0.6.0 同样支持在 schema 4 中使用，没有候选的旧数据照常生成。有候选时使用下列字段。各候选和来源使用分类型、无歧义编码的锚点，可见编号仍由 `id` 给出。字段全部转义为文本。可复现示例见 `examples/amendment-input.json`。

每条包含以下字段。

- `id,title,target,dependency,text,scope_change,condition,sync` 分别记录编号、标题、修改落点、直接引用和累计路径、完整候选文字、范围变化、采纳条件、同步位置。`id` 遵循意见编号格式，`text` 的换行保留。替代独权应写完整权项，从属候选应写完整引用句。
- `tier` 为 `clarify`（保守澄清）、`balanced`（平衡限定）、`fallback`（收窄后备）。`issues[]` 关联现有意见。`applicability` 沿用改法的 `kind,note` 结构。
- `candidate_check` 含 `kind,status,note`。`kind` 取 `dependent_claim,independent_claim,wording`；`status` 取 `complete,pending`。收窄后备只接受已核对完整的独立项或从属项。`note` 记录逐句核查对象及边界，不以勾选状态替代全文核读。
- `scope_check` 含 `effect,reason,abandoned_coverage,product_impact`。`effect` 取 `unchanged,narrowed,broadened,uncertain`；明确收窄或扩大的候选不能标为 `clarify`。无法确定时填写 `uncertain` 并说明待核事项，不强行选“未变化”。各文字字段非空，确实不适用时写原因。
- `claim_actions[]` 含 `target,action,reason`，至少一条。`action` 取 `retain,replace,add,remove`。逐项说明采纳后的原权项与候选关系、基准版本及并存条件；同一 `target` 不重复。该表仅是待采纳安排，不改变 Word 导出状态。
- `embodiments[]` 含稳定 `id` 与显示用 `label`。`id` 与候选编号格式相同且内部唯一；没有已定位实施例时可为空。
- `embodiment_conflicts[]` 含 `left,right,reason`，引用两个不同的实施例编号；同一对不可重复。无已发现互斥关系时显式填 `[]`，不表示已经排除所有潜在矛盾。
- `sources[]` 含 `id,kind,location,quote,observation,embodiment,embodiment_ids`。`kind` 为 `description,drawing,claim`。`embodiment` 是解释文本，`embodiment_ids` 引用本候选实施例编号。权项或尚未归属的来源可填空数组。说明书摘录保留原句，图证 `quote` 可写原图题或原标号，`observation` 单独记录可见关系与限制。引用图题时，位置同时写图号、图题所在段及观察涉及的标号。来源编号在候选内部唯一。
- 来源明确允许跨例组合时，填 `sources[].combination_guidance`。其 `embodiment_ids` 列出原文允许一起采用的至少两个编号，这些编号须属于该来源的 `embodiment_ids`。`relation` 写明原文连接哪些特征及适用条件。说明分别适用于多个实施例时可保留全部来源归属，只有原文明确允许组合时才填写指引。
- `features[]` 含 `id,text,role,status,source_ids,claim_source_ids`。`role` 说明继承、澄清或加入，`status` 为 `supported,partial,gap,unverified`。`source_ids` 只允许说明书／附图，`claim_source_ids` 只允许权项；二者都显式提供，未列来源填 `[]`。标记特征 `supported` 时至少有一条对应的正文／图证，权项路径不代替组合依据。组合重要的继承关系也须列出。
- `combination` 含 `status,embodiment,source_ids,reasoning,omitted_features,counterevidence,figure_check,mode,embodiment_ids,guidance_source_ids`。保留原有的状态、时序、组合理由、省略和反证分析；新增 `mode` 为 `same_embodiment,explicit_combination,unresolved`。组合来源及指引只允许正文／图证，指引必须包含在组合来源中。缺少图或图无关时在 `figure_check` 说明，文字证据可以单独支持。

标记组合 `supported` 时，全部特征均须 `supported`，组合来源须覆盖逐特征正文／图证。每条来源至少适用于一个所选实施例，另行适用的未选例可以保留在来源记录中。`same_embodiment` 只选一个稳定编号。`explicit_combination` 至少选两个，每条 `guidance_source_ids` 对应的来源都须填 `combination_guidance`，其中的编号须在所选实施例内。各条指引须能将全部所选实施例连成一组。只有 E1–E2 和 E3–E4 两条指引时，两组分别记录。选入已登记互斥的两例或仍为 `unresolved` 时拒绝 `supported`。部分支持和缺口保留待核候选。原文对特征、适用条件和整体组合的支持由审稿人核对。

交付时使用本包生成器，以便检查指引中的具体组合关系，并在报告中展示原文出处。

- 意见与权项、附图的关系只在 `evidence[].issues` 和 `figures[].issues` 填一次。图证数量、卡片关联区和速览关联编号从这些记录产生。不要另外填写“关联总数”。
- 同一意见的屏幕计数与打印计数均由同一个 `Counter` 结果生成。HTML 会有重复显示值，这是展示副本；改关系后重新生成即可。
- 筛选器只提供实际记录存在的值。覆盖分项没有意见时显示文字和原因，不能指向不存在的筛选值。
- 技术要点只在路径区详细显示；速览不重复完整要点和意见标题。每个编号链接有完整可访问名称，点开即能读到标题。
- 原始引用不替换术语、不“润色”英文。生成器仅做 HTML 转义和少量短引用防断行，文本内容保持不变。
- 数据为空时给出范围说明；不从“零意见”推断“无风险”。`claim_index` 是人工核实清单，不因证据表恰有若干行就推断已覆盖全部权项。

## 迁移既有案件

v0.6.1 沿用 schema 4。补正被拒的数据时，先回原文查漏项或类型，补足独立路径和对应链。旧 `kind` 无法归类时只补 `claim_type` 即可消除类型歧义。旧数据 1／2／3 缺因果记录时沿用未完成提示，可阅读旧报告。

v0.5.1 的同一实施例候选沿用原字段。已有跨实施例候选标为 `supported` 时，逐条核对 `guidance_source_ids` 的原文并补录 `combination_guidance`。原文只分别描述各例，或多条指引之间缺少连接时，按实际证据保留部分支持或缺口。

v0.5.0 的已有候选需要补齐完整性、范围、采纳安排、实施例编号／互斥关系、来源归属和权项路径等记录。先保留旧数据，再回到原件核对；不能按名称相似就批量认定同属实施例，也不能自动把组合状态升为有依据。旧候选缺字段时新版拒绝生成并指出字段路径。未使用候选字段的 schema 1／2／3、以及 schema 3 的空候选数组继续兼容。

将原本写在临时生成脚本中的概览段落、路径、工况、文献索引、图片和复核状态移入对应字段。直接生成并比对原始摘录、判断对象、关系数量及图像哈希。不要把旧脚本的后处理替换继续串在新版输出之后。旧交付保留，样板单独命名。
