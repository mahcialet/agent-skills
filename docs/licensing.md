# Licensing

このrepositoryのoriginal materialには、rootのMIT Licenseを適用する。他の著作物をadaptまたは
引用するSkillやBehavior Profileには `NOTICE.md` を置き、source repository、copyright holder、
license、確認したpinned revision、実際に参照またはadaptしたfile、継承した要素、material
modificationを記録する。必要なlicense noticeは全文を保持し、公式性、endorsement、互換性を
示さない境界も明記する。

Root [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) は、各packageのnoticeを索引する。
再配布を許可しないtermsのstandardやguidanceをコピーしてはならない。大量引用より、適切な
attribution、要約、独自に記述したoperational ruleを優先する。

Authoritative evidenceがない限り、SkillやBehavior Profileはcertification、official
conformance、compatibility、endorsementを主張しない。Package validatorの成功や少数の
Agent episodeも、これらのclaimを支える証拠にはならない。

状態語の根拠は次のように分ける。

- `structurally validated`: 対象revision、validatorとtestの結果を記録する。
- `observed`: sanitized episodeにhost、version、model、Profile hash、permission、fixture、結果、
  limitationsを記録する。記録外の組合せへ一般化しない。
- `verified`: 明示したscopeとacceptance criteriaに対する検証結果と、人間によるreviewを記録する。

Behavior-changing ruleをcoreへ昇格する場合は、支持例、反例、境界例、既存evalの回帰確認、sourceと
provenanceの確認、人間による明示的なreviewを別途必要とする。どの証拠をcertificationや
official conformanceの根拠として受理できるかは未定義であり、このrepositoryではそのclaimを
行わない。
