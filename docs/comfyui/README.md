# Qwen 3D Character Texture Generator (GGUF v2)

ComfyUI 上で、**3Dキャラクターを複数カメラから撮影した画像をまとめて処理し、リファレンス画像の配色・質感を参照しながら、テクスチャ生成用のマルチビュー画像を生成するワークフロー**です。

主に ViewTexForge から出力した `clay` / `depth` / `mask` 画像群を入力し、Qwen Image Edit 2511 を中心に、Depth / Canny / Inpaint の3系統の DiffSynth ControlNet を併用して形状を維持しながら外観を生成します。

生成後は NVIDIA RTX Video Super Resolution で高解像度化し、元のカメラ単位へ再分割します。さらに **Albedo Mode** を有効にすると、Marigold IID の appearance / lighting 推定を使って、生成画像からライティング成分を抑えた Albedo 相当の画像を抽出して保存します。

---

## Required Models

このワークフローでは、以下のモデルを使用します。

### Qwen Image Edit

- `qwen-image-edit-2511-Q8_0.gguf`
- `qwen_2.5_vl_7b_fp8_scaled.safetensors`
- `qwen_image_vae.safetensors`
- `Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors`

### DiffSynth ControlNet

- `qwen_image_depth_diffsynth_controlnet.safetensors`
- `qwen_image_canny_diffsynth_controlnet.safetensors`
- `qwen_image_inpaint_diffsynth_controlnet.safetensors`

### Albedo Mode

Albedo Mode を使用する場合は、以下の Marigold IID モデルも使用します。

- `prs-eth/marigold-iid-appearance-v1-1`
- `prs-eth/marigold-iid-lighting-v1-1`

Marigold のモデルは `ComfyUI-Marigold` から Hugging Face 経由で取得されます。

## Model Storage Location

```text
📂 ComfyUI/
├── 📂 models/
│   ├── 📂 vae/
│   │   └── qwen_image_vae.safetensors
│   ├── 📂 loras/
│   │   └── Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
│   ├── 📂 diffusion_models/
│   │   └── qwen-image-edit-2511-Q8_0.gguf
│   ├── 📂 text_encoders/
│   │   └── qwen_2.5_vl_7b_fp8_scaled.safetensors
│   └── 📂 model_patches/
│       ├── qwen_image_depth_diffsynth_controlnet.safetensors
│       ├── qwen_image_canny_diffsynth_controlnet.safetensors
│       └── qwen_image_inpaint_diffsynth_controlnet.safetensors
```

---

## Workflow Overview

```text
ViewTexForge output
  ├─ clay/*.png
  ├─ depth/*.png
  └─ mask/*.png
        ↓
Load image lists
        ↓
Auto-detect view count / build multi-view grid
        ↓
Build multi-view grids
        ↓
Resize to Qwen working resolution
        ↓
Qwen Image Edit 2511 (GGUF)
  ├─ Reference image
  ├─ Depth ControlNet
  ├─ Canny ControlNet
  └─ Inpaint ControlNet + mask
        ↓
4-step generation
        ↓
RTX Video Super Resolution (ULTRA)
        ↓
Downscale / split back to individual views
        ↓
Albedo Mode
  ├─ OFF → generated images directly
  └─ ON  → Marigold IID → PBR Extractor → Albedo
        ↓
Save images
```

---

# 1. What This Workflow Does

このワークフローの目的は、**3Dモデルの複数ビュー画像を、形状をできるだけ維持したままリファレンス画像に近いカラー・テクスチャ表現へ変換すること**です。

入力として以下を使用します。

- Clay / Render image
- Depth image
- Mask image
- Reference image

複数カメラから取得した画像は一度グリッド画像にまとめられ、Qwen Image Edit に1枚の画像として渡されます。

Qwen には以下の情報を同時に与えます。

- 元のマルチビュー画像
- リファレンス画像
- Depth ControlNet
- Canny ControlNet
- Inpaint ControlNet
- Geometry Mask

これにより、単純な Image-to-Image よりも、**元の3D形状・輪郭・奥行き関係を維持したテクスチャ生成**を狙っています。

現在の Positive Prompt は以下の方針です。

```text
image1 のカラーパレットを image2 をもとに入れ替える。
アルベドテクスチャマップ、フラットカラー、完全に無照明、影なし、
指向性照明なし、フラットグレーの背景。
```

Negative Prompt は現在ほぼ空です。

---

# 2. Supported View Counts

入力された Clay 画像の枚数をもとに、複数ビューを1枚のグリッド画像へまとめて Qwen に渡します。

本ワークフローでは、**2 x 2、3 x 3、4 x 4 などの正方グリッドを基本形として想定**しています。

特に推奨する構成は以下です。

| View Count | Grid | Recommendation |
|---:|---:|---|
| 4 | 2 x 2 | **Recommended** |
| 9 | 3 x 3 | **Recommended** |
| 16 | 4 x 4 | Not recommended |

### Recommended: 2 x 2 / 3 x 3

**2 x 2（4 views）と 3 x 3（9 views）が推奨構成です。**

正方形のグリッドは Qwen に入力した際に元画像の縦横比を維持しやすく、各カメラ画像の形状も比較的安定して生成できます。

### 3 x 2 / 4 x 3 Grid

**3 x 2（6 views）や 4 x 3（12 views）でも生成自体は可能**です。

ただし実際のテストでは、Qwen の生成結果でグリッド全体の縦横比が変化しやすく、元画像と比較すると出力サイズや各セルの比率が正確に維持されない場合があります。

そのため、6 views / 12 views は利用可能ではあるものの、現在は推奨構成にはしていません。

### 4 x 4 and Larger

**4 x 4（16 views）以上は実用上推奨していません。**

1枚の生成画像の中へ多数のビューを詰め込むことで、1ビューあたりに割り当てられる生成解像度が不足し、テクスチャのディテールが大きく失われる傾向があります。

16 views 以上でも処理自体は想定していますが、現状ではテクスチャが粗くなり、実用的な品質を得ることが難しいことを確認しています。

> **Recommended:** 2 x 2 / 3 x 3  \n> **Usable but not recommended:** 3 x 2 / 4 x 3  \n> **Not recommended:** 4 x 4 or larger

グリッドの1セルサイズは、最初の Clay 画像の解像度から取得されます。

---

# 3. Required Custom Nodes

## ComfyUI-GGUF

Qwen Image Edit 2511 の GGUF モデル読み込みに必要です。

使用ノード:

```text
LoaderGGUF
```

Repository:

https://github.com/city96/ComfyUI-GGUF

---

## Comfy_KepListStuff

フォルダ内の複数画像をリストとしてロードするために使用します。

使用ノード:

```text
ImageListLoader
List Length
```

Repository:

https://github.com/M1kep/Comfy_KepListStuff

---

## ComfyUI-Easy-Use

画像枚数による条件分岐、数値計算などに使用します。

使用ノード例:

```text
easy simpleMathDual
easy ifElse
easy int
```

Repository:

https://github.com/yolain/ComfyUI-Easy-Use

---

## ComfyUI Impact Pack

可変値を一時的にリスト化するために使用します。

使用ノード:

```text
ImpactMakeAnyList
```

Repository:

https://github.com/ltdrdata/ComfyUI-Impact-Pack

---

## ComfyUI Essentials

Geometry Mask から白領域などを抽出するために使用します。

使用ノード:

```text
MaskFromRGBCMYBW+
```

Repository:

https://github.com/cubiq/ComfyUI_essentials

---

## KJNodes for ComfyUI

Seed をファイル名に変換する処理や、Marigold 前の画像レンジ調整などに使用します。

使用ノード:

```text
SomethingToString
RemapImageRange
```

Repository:

https://github.com/kijai/ComfyUI-KJNodes

---

## ComfyUI-Marigold

Albedo Mode 用の Marigold IID 推定に必要です。

使用ノード:

```text
MarigoldModelLoader
MarigoldDepthEstimation_v2
```

Repository:

https://github.com/kijai/ComfyUI-Marigold

---

## ComfyUI-TextureAlchemy

Marigold appearance / lighting 出力から Albedo 等の PBR マップを抽出します。

使用ノード:

```text
PBRExtractor
PBRSplitter
```

Repository:

https://github.com/amtarr/ComfyUI-TextureAlchemy

---

## NVIDIA RTX Nodes for ComfyUI

生成画像のアップスケールに使用します。

使用ノード:

```text
RTXVideoSuperResolution
```

Repository:

https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI

このワークフローでは以下を使用しています。

```text
Quality: ULTRA
Resize type: target dimensions
```

NVIDIA RTX GPU が必要です。

---

# 4. ComfyUI Built-in / Recent Core Nodes

このワークフローでは比較的新しい ComfyUI Core ノードも使用しています。

例:

```text
TextEncodeQwenImageEditPlus
FluxKontextMultiReferenceLatentMethod
ModelPatchLoader
QwenImageDiffsynthControlnet
ResizeImageMaskNode
SplitImageToTileList
ImageGrid
GetImageSize
GetItemFromList
StringConcatenate
ComfyMathExpression
CFGNorm
ComfySwitchNode
```

そのため、**古い ComfyUI ではワークフローを開いても Missing Node になる可能性があります。**

まず ComfyUI 本体を比較的新しいバージョンへ更新することを推奨します。

## KayTool

数値を整数へ変換するために使用します。

使用ノード:

```text
To_Int
```

Repository:

https://github.com/kk8bit/KayTool

ComfyUI Manager では `kaytool` で検索してインストールできます。

Missing Node が残る場合は ComfyUI Manager の **Install Missing Custom Nodes** も使用してください。

---

# 5. Input Folder Structure

このワークフローは ViewTexForge から以下のフォルダを受け取る設計です。

```text
<output root>/
├─ clay/
│  ├─ view_000.png
│  ├─ view_001.png
│  └─ ...
├─ depth/
│  ├─ view_000.png
│  ├─ view_001.png
│  └─ ...
├─ mask/
│  ├─ view_000.png
│  ├─ view_001.png
│  └─ ...
└─ generated/
```

実際のファイル名は固定ではありませんが、各フォルダ内では **同じカメラ順序** で並んでいる必要があります。

`ImageListLoader` は現在以下の設定です。

```text
file_filter = *.png
sort_method = numerical
```

したがって、ファイル名にはカメラ順を判断できる数値を含めることを推奨します。

---

# 6. Reference Image

Reference Image は以下のノードから入力されます。

```text
ViewTexForge_input_ReferenceImage
```

Qwen Image Edit には、

```text
image1 = multi-view source image
image2 = reference image
```

として渡されています。

主な用途は、**3Dモデル側の形状を保持しながら、リファレンス側のカラー・デザイン情報を転写すること**です。

---

# 7. Multi-view Grid Generation

Clay / Depth / Mask はそれぞれ独立してグリッド化されます。

```text
Clay  → ImageGrid
Depth → ImageGrid
Mask  → ImageGrid
```

各グリッドは同じセル幅・セル高さ・列数を使用するため、同じカメラが同じ位置に配置されます。

この対応関係が Depth / Canny / Inpaint ControlNet の整合性に重要です。

---

# 8. Qwen Processing Resolution

カメラ枚数から処理解像度を切り替えています。

```text
4 views  → 1024 x 1024
6 views  → 1248 x 832
12 views → 1152 x 864
```

すべて Bicubic でリサイズされます。

このワークフローでは `FluxKontextImageScale` は使用しておらず、**アスペクト比を明示的に管理した通常の Resize Image/Mask を使用しています。**

---

# 10. ControlNet Structure

ControlNet は以下の順に Model Patch として適用されます。

```text
Qwen Image Edit model
  ↓
Depth DiffSynth ControlNet
  ↓
Canny DiffSynth ControlNet
  ↓
Inpaint DiffSynth ControlNet
  ↓
CFG Norm
  ↓
KSampler
```

## Depth

入力:

```text
Depth grid
```

目的:

- キャラクターの立体形状維持
- パーツの前後関係維持
- シルエットの崩壊抑制

## Canny

Clay grid から Canny を生成します。

```text
low_threshold  = 0.05
high_threshold = 0.20
```

目的:

- 輪郭保持
- 顔・衣装・アクセサリ境界保持
- カメラごとの差異を抑える

## Inpaint

Mask grid から白色領域を抽出して Inpaint ControlNet に渡します。

```text
threshold R = 0.15
threshold G = 0.15
threshold B = 0.15
```

目的:

- Geometry Mask を利用した生成対象領域の制御
- 背景や非対象領域への不要な生成を抑える

---

# 11. Qwen Sampling Settings

現在の主要設定です。

```text
Model      : qwen-image-edit-2511-Q8_0.gguf
LoRA       : Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
Steps      : 4
CFG        : 1.0
Sampler    : Euler
Scheduler  : Simple
Denoise    : 1.0
Aura shift : 3.0
CFG Norm   : 1.0
```

Lightning 4-step LoRA を前提にしているため、通常の Qwen Image Edit よりかなり少ない Steps で生成します。

`ModelSamplingAuraFlow` は `shift = 3.0`、`sampling = flow` です。

`CFGNorm` は strength 1.0 / pre_cfg false で適用されています。

---

# 12. Reference Latent Method

Positive / Negative の両方に以下を適用しています。

```text
FluxKontextMultiReferenceLatentMethod
reference_latents_method = index_timestep_zero
```

このノードは Qwen Image Edit Plus が持つ複数参照画像の latent の扱いを指定するために使用されています。

ComfyUI 公式の Qwen Image Edit 2511 テンプレートでは、再パッケージされたモデルではこの設定が必要になる場合がある旨が示されています。

---

# 12. RTX Video Super Resolution

Qwen の生成結果は RTX Video Super Resolution へ渡されます。

設定:

```text
Quality = ULTRA
```

アップスケール先の解像度は、元のタイルサイズとグリッドサイズから計算されます。

その後、0.5 倍 Bicubic リサイズを行い、`SplitImageToTileList` で各カメラ画像へ戻します。

つまりこの部分は、

```text
Qwen output
    ↓
RTX VSR high-resolution upscale
    ↓
0.5x resize
    ↓
individual camera tiles
```

という構成です。

---

# 14. Albedo Mode

以下の Boolean ノードで切り替えます。

```text
ViewTexForge_input_AlbedoMode
```

## OFF

RTX VSR 後に分割された画像を、そのまま Generated Image として保存します。

## ON

分割後画像を Marigold に入力します。

```text
Generated image
  ↓
Remap Image Range
  ├─ Marigold IID Appearance
  └─ Marigold IID Lighting
        ↓
PBR Extractor
        ↓
PBR Splitter
        ↓
Albedo
```

PBR Extractor の設定:

```text
albedo_source      = lighting
gamma_albedo       = 0.45
gamma_metal_rough  = 2.0
gamma_lighting_ao  = 0.45
```

最終的には PBR Splitter の Albedo 出力だけを保存しています。

---

# 15. Marigold Settings

Appearance / Lighting の両方で以下の設定です。

```text
seed                  = 123
denoise_steps         = 12
ensemble_size         = 4
scheduler             = DDIMScheduler
use_taesd_vae         = false
keep_model_loaded     = false
```

`keep_model_loaded = false` なので、Marigold 推定後はモデルを常駐させない構成です。

VRAM を節約する一方、複数回実行時にはモデル再ロードによる時間増加が発生します。

---

# 15. Output

保存ノード:

```text
ViewTexForge_output_GeneratedImage
```

出力フォルダ名:

```text
ViewTexForge_output/
```

ファイル名プレフィックス:

```text
generated_<seed>
```

Seed が 18 の場合の例:

```text
ViewTexForge_output/generated_18_00001_.png
ViewTexForge_output/generated_18_00002_.png
...
```

実際の連番部分は ComfyUI の SaveImage の命名規則に依存します。

---

# 16. VRAM Requirements

このワークフローは **8 GB VRAM 環境での動作を前提に設計しており、実際に 8 GB VRAM の NVIDIA RTX GPU で動作確認済み**です。

Qwen Image Edit 2511 Q8 GGUF、Qwen VL Text Encoder、3種類の ControlNet、RTX VSR、さらに Albedo Mode では Marigold を使用する比較的重い構成ですが、モデルのロード / アンロードや offload を利用することで 8 GB VRAM 環境でも実行できます。

## VRAM Guideline

| VRAM | Evaluation |
|---:|---|
| 8 GB | **動作確認済み / 本ワークフローの基準環境** |
| 12 GB | より余裕があり、モデル切替や生成処理が快適 |
| 16 GB | 高い余裕があり、offload の頻度低下や処理安定性の向上が期待できる |
| 24 GB+ | 非常に余裕があり、高解像度処理や他モデル併用でも快適 |

つまり、**12 GB 以上は必須要件ではありません。8 GB VRAM での実行を想定したワークフローです。**

VRAM が多い環境ほど、CPU offload やモデル再ロードの頻度を減らせるため、一般的には処理速度や操作時の快適性が向上します。

特に VRAM を使用しやすい箇所:

1. Qwen Image Edit 2511
2. Qwen 2.5 VL 7B Text Encoder
3. 3つの DiffSynth ControlNet
4. RTX Video Super Resolution ULTRA
5. Marigold appearance / lighting

### 8 GB VRAM 環境での補足

- 本ワークフローは 8 GB VRAM で動作確認済みです。
- ComfyUI / PyTorch 側のモデル管理により、必要に応じて CPU RAM への offload が発生します。
- 高VRAM環境と比べると、モデル切替や再ロードに時間がかかる場合があります。
- 同時に他の GPU アプリケーションを多数起動している場合は、利用可能な VRAM が減るため注意してください。
- Albedo Mode では Marigold の追加ロードが発生するため、OFF 時より処理時間が増えます。

### さらに VRAM 使用量を抑えたい場合

必要に応じて以下を検討できます。

- ComfyUI の Low VRAM / model offload を利用する
- Albedo Mode を OFF にする
- RTX VSR を一時的に無効化する
- RTX VSR Quality を ULTRA から HIGH / MEDIUM に下げる
- Marigold の `ensemble_size` を下げる
- Marigold の `keep_model_loaded = false` を維持する
- Qwen のより低bitな GGUF を使用する

---

# 18. Hardware Requirements

## GPU

推奨:

```text
NVIDIA RTX GPU
```

RTX Video Super Resolution ノードを使用するため、NVIDIA RTX 環境を前提としています。

RTX VSR を使用しない構成へ変更する場合、Qwen / Marigold 側の対応範囲内で他GPU環境を検討できますが、この README では未検証です。

## System RAM

GGUF モデルの CPU offload を考慮すると、VRAM だけでなくシステムRAMも重要です。

推奨目安:

```text
32 GB minimum recommended
64 GB preferred for low-VRAM operation
```

特に 8～12 GB VRAM 環境では、CPU RAM にモデルが退避されるためメインメモリに余裕がある方が安定します。

---

# 19. Recommended Installation Procedure

1. ComfyUI を最新版に近い状態へ更新する
2. ComfyUI Manager を更新する
3. この workflow JSON を読み込む
4. `Install Missing Custom Nodes` を実行する
5. 上記の Custom Nodes をインストールする
6. 必要な Qwen / LoRA / ControlNet / VAE / Text Encoder を配置する
7. ComfyUI を再起動する
8. Missing Node がないことを確認する
9. ViewTexForge から `clay` / `depth` / `mask` を出力する
10. Folder Path を指定する
11. Reference Image を設定する
12. Seed / Albedo Mode を設定する
13. Queue Prompt を実行する

---

# 20. Important Notes

## Camera Order

Clay / Depth / Mask の並び順は完全に一致させてください。

たとえば、

```text
clay/view_000.png
depth/view_000.png
mask/view_000.png
```

がすべて同じカメラである必要があります。

---

## Number of Images

現在は主に以下を想定しています。

```text
4 views
6 views
12 views
```

View 数を追加する場合は、以下も追加・変更する必要があります。

- Grid columns
- Grid rows
- Qwen processing resolution
- Output split size

---

## Albedo Extraction

Marigold IID による Albedo は、厳密な物理ベースの Base Color を保証するものではありません。

生成画像から照明・陰影成分をできるだけ分離し、後工程の Texture Merge / Baking で利用しやすい画像へ近づけるための処理として使用しています。

---

# 21. Main ViewTexForge API Nodes

ViewTexForge 側から操作することを想定して、以下のノードタイトルが付けられています。

```text
ViewTexForge_input_ReferenceImage
ViewTexForge_input_NegativePrompt
ViewTexForge_input_PositivePrompt
ViewTexForge_input_Seed
ViewTexForge_input_OutputDirName
ViewTexForge_input_OutputFilePrefix
ViewTexForge_input_SourceImageFolderPath
ViewTexForge_input_DepthImageFolderPath
ViewTexForge_input_MaskImageFolderPath
ViewTexForge_input_AlbedoMode
ViewTexForge_input_AlbedoSource

ViewTexForge_output_GeneratedImage
```

この命名を利用することで、Blender 側から ComfyUI API workflow JSON を検索し、必要なパラメータだけを差し替える構成にできます。

---

# 22. Dependencies Summary

## Models

```text
qwen-image-edit-2511-Q8_0.gguf
qwen_2.5_vl_7b_fp8_scaled.safetensors
qwen_image_vae.safetensors
Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
qwen_image_depth_diffsynth_controlnet.safetensors
qwen_image_canny_diffsynth_controlnet.safetensors
qwen_image_inpaint_diffsynth_controlnet.safetensors
prs-eth/marigold-iid-appearance-v1-1
prs-eth/marigold-iid-lighting-v1-1
```

## Custom Nodes

```text
ComfyUI-GGUF
Comfy_KepListStuff
ComfyUI-Easy-Use
ComfyUI-Impact-Pack
ComfyUI_essentials
ComfyUI-KJNodes
KayTool
ComfyUI-Marigold
ComfyUI-TextureAlchemy
Nvidia_RTX_Nodes_ComfyUI
```

加えて、最新の ComfyUI Core が必要です。

---

# 23. Source / Reference Links

ComfyUI:

https://github.com/Comfy-Org/ComfyUI

Qwen Image models for ComfyUI:

https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI

Qwen Image Edit 2511 GGUF:

https://huggingface.co/unsloth/Qwen-Image-Edit-2511-GGUF

Qwen Image DiffSynth ControlNets:

https://huggingface.co/Comfy-Org/Qwen-Image-DiffSynth-ControlNets

Qwen Image Lightning:

https://huggingface.co/lightx2v/Qwen-Image-Lightning

ComfyUI GGUF:

https://github.com/city96/ComfyUI-GGUF

ComfyUI Marigold:

https://github.com/kijai/ComfyUI-Marigold

TextureAlchemy:

https://github.com/amtarr/ComfyUI-TextureAlchemy

KayTool:

https://github.com/kk8bit/KayTool

NVIDIA RTX Nodes:

https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI

---

# 24. Workflow Version Notes

README generated from:

```text
Qwen_3DCharacterTexture_generator_ggfu_v2.json
```

解析対象の workflow では、Qwen 2511 / GGUF / DiffSynth ControlNet / RTX VSR / Marigold Albedo extraction を組み合わせています。

今後 workflow のノード構成・モデル名・入力ノード名を変更した場合は、この README の Dependencies / Workflow Structure も合わせて更新してください。
