# 逐特征现有技术证据

v0.6.3 对所有受支持的 schema 1 至 5 执行同一规则。新颖性或创造性标为 `reviewed` 前，须填写以下证据。生成器检查记录完整性、引用关系及状态一致性，审稿人回原件核实技术含义和法律判断。

## 特征清单与文献方案

每项 `search[]` 的 `features[]` 至少一条，填写唯一 `id`、`text`、`claim_location`。保留权项原句及具体分句位置，包含继承限定、位置、连接、动作、条件和特征间的配合关系。择一方案按实际路径记录。清单完整性须对照原权项复核，程序无法发现输入中从未登记的原文特征。

`comparisons[]` 每条代表单篇文献中的一套实际技术方案。

| 字段 | 内容 |
| --- | --- |
| `id` | 本独权内唯一方案编号，例如 D1-S1 |
| `reference_id` | 引用现有 `references[]` 中的文献 ID，文献目录保留公开号或资料身份、版本、公开日、链接及核读范围 |
| `scheme` | 实施例或技术方案身份。不同且无组合依据的实施例分别登记 |
| `eligibility` | 公开日期与本案有效日期的具体比较、资格及适用法域。资格未核实时保留部分核查 |
| `features[]` | 对本独权全部已登记特征各填一条，禁止漏项、重复或引用未知特征 |
| `combination` | 本单篇方案的完整组合核对 |

每条 `comparisons[].features[]` 填 `feature_id`、`status`、`reason`。`status` 的要求如下。

| 状态 | 必填证据 |
| --- | --- |
| `disclosed` | `location` 给到该文献的页、段、项或图中区域，`quote` 保存原文或图中可见关系，`reason` 解释为何对应本特征，包括异名、条件和配合关系 |
| `not_disclosed` | `location` 定位最接近的相关记载，`quote` 摘录该记载，`checked_scope` 写清实际核读范围，`reason` 说明该范围内缺少哪项内容或存在何种结构差异。无相关记载时如实记录可复核的全文范围和实际核读结果，禁止编造引文 |
| `unverified` | `reason` 说明缺什么、需要回查何处。参与已核查判断的方案不得含此状态 |

`not_disclosed` 表达限定文献和核读范围内的发现。只做关键词检索、未取得原件或尚未核读的内容使用 `unverified`。

`combination` 含 `status` 与 `reason`。`complete` 和 `incomplete` 另填 `location`，分别定位共同公开的依据或缺失组合的相关位置。`complete` 要求本方案全部特征均为 `disclosed`，并由审稿人核实它们共同出现及协作的条件。`incomplete` 说明缺失特征或无法组合的原因。尚未核实整体组合时填 `unverified`。

## 新颖性

`novelty` 保留 `status,basis`。标为 `reviewed` 时另填 `result`。

- `complete_combination_found` 表示至少一个已登记单篇方案的 `combination.status` 为 `complete`。
- `not_found_in_scope` 表示本轮已登记方案中均未发现完整组合。`basis` 须保留检索范围和局限。

已核查的新颖性要求所有所列候选方案均完成逐特征和完整组合核对。D1 公开 A、B，D2 公开 C 时，各自登记缺失项。即使两套方案来自同篇文献，也须核对该文献中实际存在的组合依据。

## 创造性

`inventiveness` 保留 `status,basis`。标为 `reviewed` 时增加以下字段。

| 字段 | 内容 |
| --- | --- |
| `starting_comparison_id` | 已登记的起点方案编号 |
| `difference_ids` | 区别特征 ID 数组，须与起点方案记录为 `not_disclosed` 的特征一致 |
| `effect` | 区别特征产生的有依据效果及成立条件 |
| `technical_problem` | 由上述区别及效果确定的实际技术问题 |
| `combination` | 结合依据或缺乏依据的核查记录 |

如果各个部件均能在起点找到，但整体关系不同，将缺失的配合关系、工况或顺序纳入特征清单和区别特征。须按实际起点解释其余共同特征。

`inventiveness.combination` 填 `status,reason,evidence[]`。

- `supported` 时，`evidence[]` 必须覆盖全部区别特征。每条包含 `comparison_id,feature_ids,location,quote,reason`。被引用方案须完成核对，并公开该条关联的区别特征。`reason` 写出技术启示或改进动机、作用关联、兼容条件及相反证据的处理，避免只列文献号或相似度。
- `unsupported` 时，填写 `checked_scope`，具体说明核读了哪些文献、哪些组合路径及为何没有获得适用的结合依据。已有反向证据也放入 `evidence[]`。无可定位证据时可保留空数组，说明检索局限，审稿人复核结论强度。
- `not_needed` 用于起点已完整公开全部特征及组合，`difference_ids` 和 `evidence` 均为空，并写明无需新增组合的原因。

已核查表示所记录范围内的审查步骤完成。具体新颖性、创造性结论仍须结合适用规则写入 `basis`，保留日期资格、检索覆盖和事实边界。

## 旧数据与交付

既有 `partial`、`not_run` 记录可沿用，无需编造完整证据。开始填写结构化对照时，缺失项使用 `unverified` 并写明缺口。含 `reviewed` 的旧记录缺少必填证据时，生成器指出字段路径并停止输出。回原件补齐，或将实际未完成的判断改为 `partial`，同步检索覆盖和首页缺口。程序不自动改写原有状态或结论。

已有证据表、文献目录和原文意见继续保留。本节数据在 HTML 的现有技术章节展开显示，包含特征原文、位置、逐文献对应、完整组合和创造性结合依据。字段按纯文本转义，打印可读。

虚构填写示例为 `examples/search-evidence-input.json`。运行 `python scripts/render_review.py examples/search-evidence-input.json --output abc-review.html` 生成报告。A、B、C 的数据仅用于结构和流程验证。
