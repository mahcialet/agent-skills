# 日本語構文解析

状態: planned（未実装）

実文corpusとprovider baselineを先に整備し、必要性を確認した後でoptionalな構造sensorを
評価する。現在、GiNZA、KWJA、その他のparserはSkillの依存に含まれない。

## 役割

parserは文数、dependency distance、modifier depth、条件・否定markerなどの観測値だけを返す。
Agentが原文とcontextを読み、人間がrule変更を承認する。parser outputを可読性のground truth、
RR label、曖昧でないことの証拠として扱わない。

## Safety

- optional dependencyとし、未導入でもSkill全体を継続する。
- parse errorを文章の誤りと判定しない。
- parser、model、version、失敗理由を結果へ記録する。
- hard thresholdだけでFAILまたは改稿を決めない。
- 数値を満たすための機械的な短文化を行わない。
- model downloadやnetwork accessを通常reviewから自動実行しない。

dependencyがない場合は、成功を装わず次のようなavailability resultを返す。

```json
{
  "available": false,
  "reason": "dependency-not-installed",
  "warnings": []
}
```

## 導入順

1. LLM-onlyのcorpus baselineを記録する。
2. GiNZAの現行version、license、Python対応、配布size、offline動作を確認する。
3. sensor output schemaとgraceful fallbackを実装する。
4. 同一corpusでLLM-onlyとLLM-plus-signalsを比較する。
5. RR recall、false positive、unnecessary revision、semantic preservation、provider差、cost、
   parse failure率を評価する。
6. 改善が確認できた場合だけ既定利用を検討する。

KWJAなどの高度なbackendは、coreferenceやdiscourse signalの不足が実文から確認された場合だけ
experimentalに比較し、coreの必須依存にはしない。
