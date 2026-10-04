# ViewTexForge 設定項目リファレンス

[← README に戻る](../../README.md)

ViewTexForge v1.0 の公開 GUI に表示される主要設定を説明します。

> 初めて使用する場合は、まず初期値のまま [Quick Start](usage.md) を試すことを推奨します。

---

## Save

### Output Directory

Capture / Generated / Texture Merge 結果を保存するルートフォルダです。

初期値:

```text
//ai_texture_capture
```

無効なパス、解決できない Blender 相対パス、アクセスできないパスの場合は処理を停止します。

### Show Explorer

現在の Output Directory を Explorer で開きます。

---

# Capture Settings

## Render Target

### All Renderable

シーン内のレンダリング対象を使用します。

### Selected Only

現在選択している対象のみを Capture します。

初回テストや、特定キャラクターだけを処理したい場合に便利です。

**Default:** `All Renderable`

---

## Output Size

### Qwen Preset

Capture 画像の解像度です。

| Setting | 用途 |
|---|---|
| 1024 x 1024 (Recommended) | 標準 / 推奨 |
| 1280 x 1280 (Balanced) | 解像度を少し上げたい場合 |
| 1536 x 1536 (Detail) | 高詳細 / 処理負荷増加 |

**Default:** `1024 x 1024`

---

## Clay Rendering

### Mode

#### Solid Viewport

Solid Viewport + MatCap を利用した Clay 画像を出力します。

#### Lit Clay Render

グレーの Clay Material とライティングを利用した Render を出力します。

**Default:** `Lit Clay Render`

### Lighting

Lit Clay Render 時に表示されます。

#### Use Existing Lighting

現在の Scene Lighting を使用します。

#### Use Auto Lighting

ViewTexForge が Front / Back / Left / Right / Top の 5 Area Lights を自動生成します。

**Default:** `Use Auto Lighting`

---

## Camera

v1.0 の公開 GUI では Auto Cameras を使用します。

### Camera Layout

#### 2 x 2 (4 Cameras)

```text
Front / Right / Back / Left
```

**Default / Recommended**

#### 3 x 3 (9 Cameras)

Axis-heavy な9方向 Capture を行います。

```text
Front
Right
Back
Left
Top
Bottom
Front-Right (slightly elevated)
Front-Left (slightly elevated)
Lower-Front
```

より多方向から生成・投影情報を取得したい場合に使用します。

### Camera Margin

Auto Camera の framing margin です。

- 小さい値: モデルを画面いっぱいに近づける
- 大きい値: 周囲に余白を増やす

**Default:** `1.05`

Camera は対象 Geometry を各 Camera のローカル2D平面へ投影した bounds をもとに自動 fit されます。

---

## Output Settings

### Output Images

#### Clay

ComfyUI の主要入力となる Clay 画像を出力します。

**Default:** ON

#### Normal

Normal 画像を出力します。

**Default:** ON

#### Depth

ComfyUI 用の normalized Depth 画像を出力します。

**Default:** ON

#### Mask

ComfyUI 用の foreground Mask を出力します。

**Default:** ON

> Capture 実行には Clay / Normal / Depth / Mask のうち少なくとも1つを有効にする必要があります。

Texture Merge 用の `depth_raw` / `geometry_mask` / `camera` データは Capture Contract として別途生成されます。

---

## Lighting Options

`Lit Clay Render + Use Auto Lighting` の場合に利用できます。

### Power Mode

#### Auto

対象モデルの bounding size から Area Light Power を自動計算します。

大きなモデルと小さなモデルで Light Power を手動調整する必要を減らすためのモードです。

**Default:** `Auto`

#### Manual

手動で Light Power を指定します。

Manual の場合のみ **Light Power** が表示されます。

### Light Power

Manual Power Mode 時の Area Light Power。

**Default:** `1000.0`

### Normalize

自動生成 Area Light の Normalize を設定します。

**Default:** ON

### Cast Shadow

自動生成ライトの Shadow を有効にします。

**Default:** OFF

### Exposure

初期値:

```text
Front : 6.0
Back  : 6.0
Left  : 6.0
Right : 6.0
Top   : 8.0
```

### Light Color

自動生成ライトの色。

**Default:** White

### Keep Auto Lights (Debug)

Capture 後も自動生成ライトを Scene に残します。

通常利用では OFF を推奨します。

**Default:** OFF

---

# ComfyUI Settings

## Reference Image

Qwen Image Edit が外観・配色を参照する画像です。

全 Camera View で同じ Reference Image を使用します。

フルワークフローでは設定が必要です。

---

## Server URL

ComfyUI Server の Base URL。

**Default:**

```text
http://127.0.0.1:8188
```

### Status

ComfyUI との接続状態を表示します。

```text
Connected
Checking...
Connection Failed
Unknown
```

### Workflow Status

同梱 Workflow が ViewTexForge から操作可能な状態か検証します。

```text
Valid
Checking...
Error
Unknown
```

公開 GUI では Workflow 選択は表示せず、同梱 Workflow を使用します。

---

## Generate Options

### Albedo Mode

ON の場合、ComfyUI 生成後に Marigold IID を利用し、ライティング成分を抑えた Albedo 相当画像を生成します。

**Default:** OFF

### Albedo Source

Albedo Mode ON 時のみ表示されます。

- `appearance`
- `lighting`

**Default:** `lighting`

### Seed Mode

#### Fixed

Base Seed をそのまま使用します。

#### Increment

Workflow batch ごとに Base Seed を increment します。

#### Random

ViewTexForge が実行時に Random Seed を決定します。

**Default:** `Fixed`

### Base Seed

Fixed / Increment で使用する Base Seed。

**Default:** `18`

---

# Texture Merge Settings

## Texture Resolution

出力 Base Color Texture の解像度。

```text
1024 x 1024
2048 x 2048
4096 x 4096
```

**Default:** `2048 x 2048`

### Material Apply

#### Do Not Apply

Texture File のみ保存し、Blender Material は変更しません。

#### Apply to Current Material

現在の Material の Base Color 接続を置き換えます。

#### Apply to New Material

現在の Material を複製し、新しい Material に merged Base Color を接続して Object へ適用します。

**Default:** `Apply to New Material`

---

## Texture Merge Options

### Merge Output Folder

Output Directory 以下に作成する Texture Merge 出力フォルダ。

**Default:**

```text
merged
```

---

## Advanced

通常は初期値を推奨します。

### Depth Tolerance

#### Auto

Capture pixel footprint から View ごとの Depth tolerance を自動計算します。

**Default:** `Auto`

Auto values:

```text
Depth Sigma Scale  : 0.65 px
Depth Cutoff Scale : 1.70 px
```

#### Manual

メートル単位で明示値を使用します。

Default manual values:

```text
Depth Sigma  : 0.0012 m
Depth Cutoff : 0.003 m
```

---

### RGB Surface Check

#### Off

従来の nearest-pixel sampling を使用します。

#### Local Surface

RGB pixel center が同じ local mesh surface に対応することを要求し、境界や遮蔽付近で誤った色を拾いにくくします。

**Default:** `Local Surface`

### RGB Boundary Guard (capture px)

Silhouette / occlusion boundary 周辺の guard 幅。

`-1` の場合は generation scale から自動導出します。

**Default:** `-1`

---

### Small Hole Fill

#### Off

未観測 UV texel をそのまま残します。

#### Constrained

小さく局所的で、周囲との色差が小さい Hole のみ制約付きで補完します。

**Default:** `Constrained`

Advanced defaults:

```text
Fill Vertex Group     : empty
Max Hole Area         : 8 texels
Max Surface Distance  : 0.002
Min Source Weight     : 0.05
Max Source Color Range: 0.18
```

---

### Merge Tuning

#### Facing Exponent

Camera facing weight の指数。

**Default:** `4.0`

#### Face Gate Gain

Face normal による gate の強さ。

**Default:** `12.0`

#### Padding Radius

UV island の外側へ色を拡張する Padding 距離。

**Default:** `16`

#### PNG Bit Depth

- 8 bit
- 16 bit

**Default:** `8 bit`

#### Debug Output

Texture Merge の診断用画像・report を出力します。

**Default:** OFF

---

# Execution

## Mode

| Mode | 処理 |
|---|---|
| Capture only | Capture |
| Capture -> ComfyUI | Capture → ComfyUI |
| Capture -> ComfyUI -> Texture Merge | Capture → ComfyUI → Texture Merge |
| ComfyUI only | ComfyUI |
| ComfyUI -> Texture Merge | ComfyUI → Texture Merge |
| Texture Merge only | Texture Merge |

**Default:** `Capture -> ComfyUI -> Texture Merge`

### Run Selected Mode

選択した Execution Mode を実行します。

---

# Status

Status セクションは常に表示されます。

### Current Stage

現在実行中の Stage。

### Overall Progress

Execution 全体の進行状況。

### Stage Progress

現在 Stage の進行状況。

### Status Message

現在処理している内容や結果を表示します。
