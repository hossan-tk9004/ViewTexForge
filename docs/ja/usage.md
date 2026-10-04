# ViewTexForge 使い方

[← README に戻る](../../README.md)

このページでは、ViewTexForge v1.0 の基本的な使い方を説明します。

---

## Quick Start - 必須項目だけで実行する

最初は詳細設定を変更せず、初期値を利用することを推奨します。

### 1. ComfyUI を起動

先に ComfyUI を起動します。

既定 URL:

```text
http://127.0.0.1:8188
```

---

### 2. Blender で対象モデルを開く

Texture Merge まで実行する場合は、対象 Mesh に UV が存在することを確認してください。

---

### 3. Output Directory

ViewTexForge 上部の **Save > Output Directory** に出力先を指定します。

既定値:

```text
//ai_texture_capture
```

`//` は Blender ファイルからの相対パスです。

---

### 4. Capture Settings

**Capture Settings** を開きます。

最低限確認する項目:

#### Render Target

- `All Renderable` - シーン内のレンダリング可能な対象を使用
- `Selected Only` - 選択オブジェクトのみを対象にする

#### Camera Layout

- `2 x 2 (4 Cameras)` - **推奨 / 初期値**
- `3 x 3 (9 Cameras)` - より多方向から情報を取得したい場合

最初は `2 x 2 (4 Cameras)` を推奨します。

---

### 5. Reference Image

**ComfyUI Settings** を開き、**Reference Image** にテクスチャ・配色・外観の参考にしたい画像を指定します。

Reference Image は全カメラで共通して使用されます。

---

### 6. ComfyUI Connection

同じ PC で標準設定の ComfyUI を起動している場合、Server URL は初期値のままで構いません。

```text
http://127.0.0.1:8188
```

以下を確認します。

```text
Status: Connected
Workflow Status: Valid
```

---

### 7. Execution Mode

すべてを連続実行する場合:

```text
Capture -> ComfyUI -> Texture Merge
```

を選びます。

---

### 8. Run

**Run Selected Mode** を押します。

ViewTexForge が順番に以下を処理します。

```text
Capture
  ↓
ComfyUI
  ↓
Texture Merge
```

画面下部の **Status** で Current Stage / Overall Progress / Stage Progress を確認できます。

---

## Individual Stage Execution

処理は個別にも実行できます。

| Execution Mode | 内容 |
|---|---|
| Capture only | Capture のみ |
| Capture -> ComfyUI | Capture 後に ComfyUI を実行 |
| Capture -> ComfyUI -> Texture Merge | 全工程を連続実行 |
| ComfyUI only | 最新の有効な Capture を使って ComfyUI のみ実行 |
| ComfyUI -> Texture Merge | ComfyUI 生成後に Texture Merge |
| Texture Merge only | 最新の生成結果を使って Texture Merge のみ実行 |

Capture / ComfyUI / Texture Merge 各セクション内の個別 Run ボタンから直接実行することもできます。

---

## Capture Output

Capture では、選択した通常出力に加えて Texture Merge 用のデータが生成されます。

```text
<Output Directory>/
├─ clay/
│  ├─ view_0001.png
│  └─ ...
├─ normal/
├─ depth/
├─ mask/
├─ raw_depth/
│  ├─ view_0001.exr
│  └─ ...
├─ geometry_mask/
├─ camera/
│  ├─ view_0001.json
│  └─ ...
└─ capture.json
```

`view_0001` は Auto Camera レイアウトの基準となる Front view です。

---

## ComfyUI Generation

ViewTexForge は Capture 出力を同梱ワークフローへ渡し、Reference Image を参照した画像生成を行います。

主に使用される入力:

```text
Clay
Depth
Mask
Reference Image
```

同梱ワークフローでは Qwen Image Edit 2511 と Depth / Canny / Inpaint DiffSynth ControlNet を組み合わせ、元の 3D 形状をできるだけ維持しながら外観を生成します。

生成画像は Output Directory の `generated/` 以下へ保存されます。

詳細は [ComfyUI ワークフロー README](../comfyui/README.md) を参照してください。

---

## Albedo Mode

**Generate Options > Albedo Mode** を有効にすると、生成画像からライティング成分を抑えた Albedo 相当の画像を抽出する処理を追加します。

Albedo Source:

- `appearance`
- `lighting` - 初期値

Marigold IID による Albedo 抽出は、厳密な物理ベース Base Color を保証するものではありません。Texture Merge / Baking で扱いやすい結果へ近づけるための実用的な前処理として使用します。

---

## Texture Merge

Texture Merge は、各カメラの生成画像を Camera / Raw Depth / Geometry 情報をもとにモデルへ投影し、UV Texture に統合します。

初期設定では:

```text
Texture Resolution : 2048 x 2048
Material Apply     : Apply to New Material
Depth Tolerance    : Auto
RGB Surface Check  : Local Surface
Small Hole Fill    : Constrained
```

まずは初期値での利用を推奨します。

Texture Merge の詳細設定は [設定項目リファレンス](settings.md) を参照してください。

---

## Recommended First Test

初回確認では次の条件を推奨します。

```text
Render Target     : Selected Only
Qwen Preset       : 1024 x 1024
Clay Rendering    : Lit Clay Render
Lighting          : Use Auto Lighting
Power Mode        : Auto
Camera Layout     : 2 x 2 (4 Cameras)
Reference Image   : 任意の1枚
Albedo Mode       : OFF
Texture Resolution: 2048 x 2048
Material Apply    : Apply to New Material
Execution Mode    : Capture -> ComfyUI -> Texture Merge
```

対象モデルだけを選択した状態で `Selected Only` にすると、初回テスト時の対象範囲を明確にできます。

---

## Troubleshooting Checklist

### ComfyUI に接続できない

- ComfyUI が起動しているか
- Server URL / Port が一致しているか
- `http://127.0.0.1:8188` へ接続可能か

### Workflow Status が Error

- ComfyUI を更新する
- ComfyUI Manager を更新する
- Missing Custom Nodes をインストールする
- 必要モデルの配置を確認する

詳細: [ComfyUI ワークフロー README](../comfyui/README.md)

### Capture が開始されない

- Output Directory が有効か
- Render Target に有効な対象 Object が存在するか
- Clay / Normal / Depth / Mask のうち少なくとも1つが有効か

### Texture Merge が失敗する

- UV Layer が存在するか
- Capture 後に対象 Geometry を変更していないか
- `generated/` に対応する生成画像が存在するか
- Capture / Generated の view_id が対応しているか
