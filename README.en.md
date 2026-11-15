# Patent Review Kit

[简体中文](README.md) · [Changelog](CHANGELOG.md) · [Download WorkBuddy v0.6.1](downloads/patent-draft-review-workbuddy-v0.6.1.zip)

Review patent drafts, revised submissions, and published texts in one traceable report. Applicants can review drafting decisions. Product and R&D teams can map technical features and identify evidence gaps when reading a third-party patent.

**Current version v0.6.1.** Trace what technical problem each claim addresses, how its features act on the cause, and what the evidence supports under the stated conditions. The report surfaces critical gaps in its overview.

## What's new in v0.6.1

- A report with claim records cannot mark causal review as inapplicable. Independent claims listed in the claim index or search records must have corresponding causal records.
- Three additional checks cover whether the actual input preserves the required information, whether the disclosure guides the choice of a workable combination, and whether the evidence supports the claimed precision.
- This public update also includes the causal review workflow, three levels of claim amendment options, and checks for combining features across embodiments. See the [changelog](CHANGELOG.md) for upgrade details.

## Account-free synthetic demo

**[Open the interactive report (Chinese)](https://krismiao97.github.io/patent-review-kit/)** · [Inspect the synthetic input](patent-draft-review/examples/template-input.json)

[![Screenshot of the fictional seedling chamber review report](docs/preview.png)](https://krismiao97.github.io/patent-review-kit/)

The fictional seedling chamber turns its lamp on below a light threshold. Open the causal review section to see how the report treats the initial state, the exact threshold, and the lighting effect. Follow **EX-01** from the overview to the cited text, evidence gap, and next step.

The demo runs in your browser without a sign-in, API key, installation, or file upload. For offline use, download the repository and open [`docs/index.html`](docs/index.html). The demo uses fictional data and records no prior-art search.

## What the review delivers

| Use case | Output |
| --- | --- |
| Draft or revision review | Claim dependency paths, source excerpts, supporting evidence, reasons, and conditional edits. |
| Third-party patent review | Jurisdiction, document version, evidence limits, and open questions about product correspondence. |
| Technical problem, solution, and effect | A causal review with conditions, counterexamples, and critical gaps surfaced in the overview. |
| Claim amendment options | Three levels of amendment with scope trade-offs and evidence for combining features. |
| Drawings and operating conditions | Cross-references to claims and drawings, including threshold endpoints, state changes, and exceptions. |
| Independent claim searches | Separate novelty and inventive-step evidence, actual search scope, and gaps. |
| Report delivery | A filterable offline HTML report, plus optional annotated and clean Word copies when the source and review decisions are ready. |

## Get started

1. Copy [`patent-draft-review/`](patent-draft-review/) to your assistant’s skill directory. Keep the internal folder structure.
2. Provide the draft or publication, version, jurisdiction, procedural stage, and any drawings or prior-art material.
3. Ask the assistant to use `patent-draft-review`. For Word output, provide an editable DOCX and specify which changes you have accepted.

> Use patent-draft-review to review this pre-filing draft. Trace the technical problem, claim language, specification, and drawings. Include source locations, conditions for the claimed effects, evidence gaps, and proposed edits in an offline HTML report.

## Rebuild the demo locally

Run from the repository root with Python 3.10+. The HTML renderer uses the standard library.

```sh
python patent-draft-review/scripts/render_review.py patent-draft-review/examples/template-input.json --output demo-local.html
```

Word export requires `python-docx`. See [requirements.txt](requirements.txt), the [Word export guide](patent-draft-review/references/word-output.md), the [report design specification](patent-draft-review/DESIGN.md), and the [template schema](patent-draft-review/references/template-schema.md).

## WorkBuddy

Download the [WorkBuddy v0.6.1 ZIP](downloads/patent-draft-review-workbuddy-v0.6.1.zip). Import it through Skills → Add Skill → Upload Skill, then invoke `patent-draft-review` in a task. [WorkBuddy upload guide](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)
