# Notices for adversarial-pr-review

Unless noted below, this skill is licensed under the repository MIT License.

## Qiita article

- Title: ベテランエンジニアのPRレビュー187件を分類してみたら、バグは5件に1件しか指摘されていなかった
- Author: `@ktdatascience`
- Published: 2026-08-26
- Source: <https://qiita.com/ktdatascience/items/02b6b45e2ca7d34ad146>
- Reviewed: 2026-08-30

The article was used as an attributed conceptual reference for organizing review
domains, treating review as broader than bug detection, and considering reusable
checklist candidates. This implementation does not rely on a redistribution
license for the article or its underlying data.

No article text or 187-comment dataset is copied into this repository. The
article's reported percentages are not treated as universal benchmarks, quality
targets, or empirical claims about other repositories. The A0-A4 adversarial
model, evidence workflow, safety boundaries, schemas, examples, and evals are
independently written for this skill.

No endorsement by the author or Qiita is implied.

## Atsumell article

- Title: AIコードレビューのやり方｜7つの確認点
- Publisher / author shown on page: 株式会社Atsumell
- Published: 2026-08-27
- Source: <https://www.atsumell.com/blog/ai-code-review-seven-checkpoints>
- Reviewed: 2026-08-30

The article was used as an attributed conceptual reference for the review
contract and human-approval boundary added to this skill.

### Adapted concepts

- Combining the code diff with explicit review criteria.
- Stating acceptance criteria and forbidden outcomes.
- Treating declared impact as an input to review.
- Preserving evidence provenance for reported test results.
- Reviewing stop conditions, recovery paths, and responsibility handoff.
- Separating AI review and gate recommendations from human approval.

### Material modifications

- Defining `sufficient`, `partial`, and `missing` specification states, and
  continuing non-specification review when criteria are incomplete.
- Recording contract-source provenance and separating declared requirements
  from inferred invariants.
- Separating `declared_impact` from `discovered_impact`.
- Classifying test evidence as `claimed`, `observed`, or `executed`.
- Separating gate recommendations from `NOT GRANTED` approval status and
  integrating the contract with the existing A0-A4 levels, depth, finding
  schema, and safety boundaries.

No article text or media is redistributed. No article license is asserted here.
No endorsement by 株式会社Atsumell is implied.
