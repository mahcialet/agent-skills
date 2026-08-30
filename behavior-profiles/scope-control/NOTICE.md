# Scope Control attribution and license notice

このpackageは、Second Mind Systemsが公開するBehavior ProfilesのScope Controlを参照し、
このrepositoryのBehavior Profile formatと日本語文書方針へadaptしたものである。

## Upstream source

- Repository: <https://github.com/Secondmindsystems/Behavior-Profiles>
- Reviewed and pinned commit: `fffa2863cf20536a9152a943d98deb6653435e17`
- Commit URL:
  <https://github.com/Secondmindsystems/Behavior-Profiles/commit/fffa2863cf20536a9152a943d98deb6653435e17>
- License at pinned commit:
  <https://github.com/Secondmindsystems/Behavior-Profiles/blob/fffa2863cf20536a9152a943d98deb6653435e17/LICENSE>
- Trademark policy at pinned commit:
  <https://github.com/Secondmindsystems/Behavior-Profiles/blob/fffa2863cf20536a9152a943d98deb6653435e17/TRADEMARKS.md>

## Files referenced or adapted

次のpinned revisionのfileを実際に参照またはadaptした。

- `LICENSE`
  - MIT License全文と `Copyright (c) 2026 Second Mind Systems` の著作権表示を保持した。
- `TRADEMARKS.md`
  - Second Mind Systemsの名称・ロゴ、公式性、endorsement、certificationに関する境界を
    参照した。
- `LIMITATIONS.md`
  - security、tamper resistance、compliance、production readiness、cross-model consistency、
    evidence boundaryに関するrepository-levelのclaim ceilingを参照した。
- `BEHAVIOR_PROFILES.md`
  - Skill/capabilityとpersistent conduct layerを分離するconceptを参照した。
- `FORMAT.md`
  - behavior contract、observable、pressure test、completion evidence、bypass、limitationsを
    分離するreference shapeを参照した。
- `products/behavior-profiles/scope-control/BEHAVIOR_PROFILE_SCOPE_CONTROL.md`
  - 上流がauthoritative canonical product artifactとして固定するconduct contract。
- `profiles/scope-control/BEHAVIOR_PROFILE.md`
  - installable representation。開始時のtask boundary、no-touch、authorized actions、done
    condition、stop/flag condition、completion noteのconductを参照した。
- `profiles/scope-control/LIMITATIONS.md`
  - instruction-layerであり、file access、edit、command、commitまたはexternal actionを阻止しない
    というclaim boundaryを参照した。
- `profiles/scope-control/QUICK_TEST.md`
  - no-edit taskとboundary readbackのpressure scenarioを参照した。
- `profiles/scope-control/TRY_IT.md`
  - ACT、DEFER、STOP、expansion pressure、曖昧なauthorityのscenario設計を参照した。
- `tests/fixtures/authorized-execution/fixture.json`
- `tests/fixtures/expansion-pressure/fixture.json`
- `tests/fixtures/ambiguous-authority/fixture.json`
  - supporting scenario、prohibited action、boundary scenarioの観測項目を参照した。
- `harness/profiles/scope-control/suite.json`
- `harness/profiles/scope-control/controls.json`
  - supporting/counterexampleの分離と、synthetic controlを実Agent evidenceと区別する考え方を
    参照した。

Pinned file URLsの基点は次である。

<https://github.com/Secondmindsystems/Behavior-Profiles/tree/fffa2863cf20536a9152a943d98deb6653435e17>

## Modifications

このrepositoryでは、上流文章をbyte-identicalに再配布せず、次の変更を行った。

- 本文を日本語主体で再構成した。
- local canonical frontmatterと、固定された九つのrequired sectionへ変換した。
- 開始scope contract、隣接cleanup禁止、expansion pressure、blocker、completion noteをlocal
  observableとして明示した。
- no-edit、scope expansion、completion note、ambiguous authority、no-touch collisionをlocal
  fixture schemaへ書き直した。
- supporting example、counterexample、boundary exampleと `PASS` / `FAIL` / `CONFUSED` の判定条件を
  local evaluation packageへ追加した。
- 上流のRuntime、enforcement mechanism、qualification結果またはcertification markは取り込んで
  いない。

## Copyright and MIT License

以下は上流の著作権表示およびMIT License全文である。英語原文を保持する。

```text
MIT License

Copyright (c) 2026 Second Mind Systems

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Trademark and relationship statement

MIT LicenseはSecond Mind Systemsの名称またはロゴを、sponsorship、endorsement、certification、
または公式製品を示唆する形で利用する許可を与えない。本packageでは名称を正確な出典表示のため
だけに使用し、上流ロゴを使用しない。

本packageはSecond Mind Systemsの公式製品ではなく、同社によるsponsorship、endorsement、
certificationまたは互換性確認を受けていない。上流が提供していない “Verified Second Mind
Profile” certificationまたはmaturity markを主張しない。上流由来であることの表示は、公式性、
byte identity、structural equivalenceまたはbehavioral equivalenceの主張ではない。

このadaptationに関する変更、fixture、validation、evidenceおよびclaimの責任は、このrepositoryの
maintainerにある。
