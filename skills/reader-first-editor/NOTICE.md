# Notices for reader-first-editor

Unless noted below, this skill is licensed under the repository MIT License.

## `coji/natural-japanese`（概念上の参照）

- Source: <https://github.com/coji/natural-japanese>
- Reviewed commit: `0f1cc1c5a4e2aa7590598c88a15c213a60d9545a`
- Copyright: Copyright (c) 2026 coji
- License: MIT License

機械的な候補抽出と文脈に基づく最終判断の分離、genre差の考慮、重い解析の
optional化、コーパスで仮説を反証する考え方を、設計上の先行例として参照した。
この変更では、upstreamのsource code、文書本文、禁止語一覧、corpus、report、
数値thresholdをコピーしていない。AIらしさのscoreや作者分類も取り込んでいない。
`reader-first-editor` は独立した非公式のSkillであり、upstream作者による推奨、提携、
互換性を示すものではない。採否と変更点は
[`docs/related-work-natural-japanese.md`](docs/related-work-natural-japanese.md)に記録する。

## danyuchn/iso-24495-skill

- Source: <https://github.com/danyuchn/iso-24495-skill>
- Reviewed commit: `113656b0a6a6cbeb3b3c2bb7cf3bc29349cb05cf`
- Copyright: Copyright (c) 2026 Dustin Yuchen Teng
- License: MIT License

The skill inherits these design ideas: identify reader and purpose before local
editing; read the complete document first; separate cross-language principles
from language-specific techniques; consider relevant, findable, understandable,
and usable outcomes in that order; treat numeric measures as prompts for review;
and distinguish plain language from Controlled Language.

This implementation materially changes the predecessor by making review the
default, placing semantic preservation first, prohibiting invented operational
details, exposing deletion proposals, adding Japanese-specific discourse and
interaction layers, adding fidelity evals, and avoiding compulsory short
sentences or active voice.

The upstream MIT license is reproduced below:

> MIT License
>
> Copyright (c) 2026 Dustin Yuchen Teng
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

## JTF Japanese Standard Style Guide 4.0

- Title: JTF日本語標準スタイルガイド（翻訳用）第4.0版
- Publisher: Japan Translation Federation (日本翻訳連盟)
- Source: <https://www.jtf.jp/tips/styleguide>
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)

Selected surface-style guidance is summarized and reorganized in
`references/ja/jtf-alignment.md`. The wording and operational hierarchy are
modified for this skill; the guide is not reproduced in bulk.

## Agency for Cultural Affairs

- Title: 文化庁「公用文作成の考え方」
- Source: <https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/pdf/93651301_01.pdf>

The document informs the Japanese syntax and information-structure discussion.
Extensions to technical documents, workplace communication, UI, and reviews are
independent design work and are not presented as government guidance.

## ISO 24495-1

Only publicly described plain-language principles were consulted. No text from
the licensed ISO 24495-1 standard is reproduced. This is an unofficial,
independent skill and does not claim ISO conformance, certification, or
endorsement.

## GiNZA optional integration

- Source: <https://github.com/megagonlabs/ginza>
- Packages: `ginza`, `ja-ginza`
- Reviewed version: `5.2.0`
- License metadata: MIT / MIT License

The skill includes an optional adapter and a synthetic recorded fixture. It
does not bundle GiNZA, spaCy, Sudachi, or the `ja-ginza` model. Users install
those packages separately under their respective licenses.
