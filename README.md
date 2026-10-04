# ViewTexForge

**ViewTexForge** は、Blender 上の 3D モデルから複数視点の画像をキャプチャし、ComfyUI を利用した AI テクスチャ生成、生成画像の 3D モデルへの再投影・統合までを一連の流れで実行するための Blender アドオンです。

> Release: **v1.0**  
> Target: **Blender 5.1.x**

[English README](README_EN.md)

---

## 目次

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Setup](#setup)
- [Quick Start](#quick-start)
- [Camera Layout Recommendation](#camera-layout-recommendation)
- [Output](#output)
- [Settings Reference](#settings-reference)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Changelog](#changelog)
- [License](#license)

---

## Overview

ViewTexForge は、3D キャラクターや 3D モデルに対して、リファレンス画像をもとにしたテクスチャ生成を補助するワークフローを提供します。

基本的な処理は次の 3 ステージで構成されています。

```text
Blender / ViewTexForge
        │
        ├─ 1. Capture
        │    ├─ Clay
        │    ├─ Normal
        │    ├─ Depth
        │    ├─ Mask
        │    └─ Texture Merge 用の Camera / Raw Depth / Geometry Mask
        │
        ▼
ComfyUI
        │
        ├─ 2. AI Texture Generation
        │    └─ Reference Image を参照して各カメラ画像を生成
        │
        ▼
ViewTexForge
        │
        └─ 3. Texture Merge
             └─ 複数カメラの生成画像を UV Texture に統合
```

ViewTexForge から **Capture → ComfyUI → Texture Merge** を連続実行することも、それぞれのステージを個別に実行することもできます。

### Main Features

- 2 x 2（4 Cameras） / 3 x 3（9 Cameras）の Auto Camera Capture
- Clay / Normal / Depth / Mask のマルチビュー出力
- Texture Merge 用 Raw CAMERA_Z / Geometry Mask / Camera Metadata の自動生成
- Lit Clay Render と自動ライティング
- モデルサイズに応じた Auto Light Power
- ComfyUI との HTTP API 連携
- Qwen Image Edit を利用したリファレンスベースの画像生成
- Albedo Mode
- 複数カメラ画像からの Texture Merge
- Capture / ComfyUI / Texture Merge の単独実行・連続実行
- ステージごとの Progress / Status 表示

---

## Requirements

### ViewTexForge

- Blender **5.1.x**
- Windows 環境を基準に開発・確認

### ComfyUI Workflow

同梱ワークフローを使用する場合、主に以下が必要です。

- ComfyUI
- NVIDIA RTX GPU
- Qwen Image Edit 2511 GGUF
- DiffSynth ControlNet（Depth / Canny / Inpaint）
- NVIDIA RTX Video Super Resolution
- Albedo Mode 使用時: Marigold IID

同梱 ComfyUI ワークフローは **8 GB VRAM の NVIDIA RTX GPU で動作確認済み**です。より大きな VRAM を搭載した GPU では、モデルの offload / reload を減らせるため、より快適に動作する可能性があります。

詳細は [ComfyUI ワークフロー README](docs/comfyui/README.md) を参照してください。

---

## Installation

1. GitHub の **Releases** から ViewTexForge v1.0 の ZIP ファイルをダウンロードします。
2. ZIP は展開せず、そのまま Blender から指定します。
3. Blender を起動します。
4. `Edit > Preferences > Add-ons` を開きます。
5. メニューから **Install from Disk...** を選択します。
6. ダウンロードした ViewTexForge の ZIP を指定します。
7. インストール後、**ViewTexForge** を有効にします。
8. 3D Viewport の Sidebar（`N` キー）から **ViewTexForge** タブを開きます。

詳しい初期セットアップは [セットアップガイド](docs/ja/setup.md) を参照してください。

---

## Setup

ViewTexForge のフルワークフローを使用するには、Blender 側のアドオンに加えて ComfyUI のセットアップが必要です。

### 1. ComfyUI

ComfyUI をインストールし、起動できる状態にしてください。ComfyUI には主に以下の導入方法があります。

| 導入方法 | ダウンロード / Repository | 公式セットアップドキュメント |
|---|---|---|
| GitHub / Manual Install | [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI) | [Manual Installation](https://docs.comfy.org/installation/manual_install) |
| Windows Portable | [Download Page](https://docs.comfy.org/installation/comfyui_portable_windows#download-comfyui-portable) | [ComfyUI Portable for Windows](https://docs.comfy.org/installation/comfyui_portable_windows) |
| Desktop | [ComfyUI Download](https://comfy.org/download) | [Comfy Desktop for Windows](https://docs.comfy.org/installation/desktop/windows) |

ComfyUI 自体のインストール・初期設定については、本 README では詳細を扱いません。**使用する導入方法に対応した ComfyUI 公式セットアップドキュメントを参照して、ComfyUI 単体で正常に起動できる状態までセットアップしてください。**

> ViewTexForge 同梱ワークフローは NVIDIA RTX Video Super Resolution を使用するため、標準構成では NVIDIA RTX GPU を前提としています。

ViewTexForge の初期 Server URL は以下です。

```text
http://127.0.0.1:8188
```

### 2. Required Models

現在の同梱ワークフローでは以下のモデルを使用します。

```text
qwen-image-edit-2511-Q8_0.gguf
qwen_2.5_vl_7b_fp8_scaled.safetensors
qwen_image_vae.safetensors
Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
qwen_image_depth_diffsynth_controlnet.safetensors
qwen_image_canny_diffsynth_controlnet.safetensors
qwen_image_inpaint_diffsynth_controlnet.safetensors
```

Albedo Mode を使用する場合は、さらに以下を使用します。

```text
prs-eth/marigold-iid-appearance-v1-1
prs-eth/marigold-iid-lighting-v1-1
```

### Model Storage Location

```text
ComfyUI/
└─ models/
   ├─ vae/
   │  └─ qwen_image_vae.safetensors
   ├─ loras/
   │  └─ Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
   ├─ diffusion_models/
   │  └─ qwen-image-edit-2511-Q8_0.gguf
   ├─ text_encoders/
   │  └─ qwen_2.5_vl_7b_fp8_scaled.safetensors
   └─ model_patches/
      ├─ qwen_image_depth_diffsynth_controlnet.safetensors
      ├─ qwen_image_canny_diffsynth_controlnet.safetensors
      └─ qwen_image_inpaint_diffsynth_controlnet.safetensors
```

Marigold モデルは `ComfyUI-Marigold` から Hugging Face 経由で取得されます。

Custom Nodes、モデルの入手先、VRAM要件、ワークフロー構造については、以下の専用 README にまとめています。

**→ [Qwen 3D Character Texture Generator - ComfyUI Workflow README](docs/comfyui/README.md)**

セットアップ全体の手順は [セットアップガイド](docs/ja/setup.md) を参照してください。

---

## Quick Start

最小限の設定で **Capture → ComfyUI → Texture Merge** を実行する場合は、次の手順で開始できます。

### Before You Start

- ComfyUI を起動しておく
- 対象モデルに使用可能な UV が存在することを確認する
- Texture Merge 後に適用したい対象モデルを Blender で開いておく

### ViewTexForge

1. **Output Directory** を指定します。
2. **Capture Settings** を開きます。
3. 必要に応じて **Render Target** を選択します。
   - `All Renderable`: シーン内のレンダリング対象を使用
   - `Selected Only`: 選択オブジェクトのみを使用
4. **Camera Layout** を選択します。
   - `2 x 2 (4 Cameras)` - 初期値 / 推奨
   - `3 x 3 (9 Cameras)` - より多方向から生成したい場合
5. **ComfyUI Settings** を開き、**Reference Image** を指定します。
6. ComfyUI がローカル既定値以外で起動している場合のみ **Server URL** を変更します。
7. **Execution > Mode** を `Capture -> ComfyUI -> Texture Merge` にします。
8. **Run Selected Mode** を実行します。

その他の設定は、まず初期値のまま試すことを推奨します。

詳しくは [使い方](docs/ja/usage.md) を参照してください。

---

## Camera Layout Recommendation

| Layout | Cameras | Recommendation | Notes |
|---|---:|---|---|
| 2 x 2 | 4 | **Recommended** | 処理負荷と各ビューの生成解像度のバランスが良い |
| 3 x 3 | 9 | **Recommended** | より多方向から情報を取得可能 |

現在の ViewTexForge v1.0 公開 GUI では、Auto Cameras として **4 Cameras / 9 Cameras** を使用します。

ComfyUI ワークフロー側では他のグリッド構成も設計上扱えますが、Qwen での縦横比の安定性や各ビューへ割り当てられる生成解像度を考慮し、ViewTexForge v1.0 では 2 x 2 / 3 x 3 を公開設定としています。

---

## Output

Capture を実行すると、Output Directory 以下に用途別のファイルが生成されます。

```text
<Output Directory>/
├─ clay/
├─ normal/
├─ depth/
├─ mask/
├─ raw_depth/
├─ geometry_mask/
├─ camera/
├─ generated/
├─ merged/
└─ capture.json
```

- `clay` / `depth` / `mask`: 主に ComfyUI 生成用
- `depth_raw` / `geometry_mask` / `camera`: Texture Merge 用
- `generated`: ComfyUI 生成画像
- `merged`: Texture Merge 結果
- `capture.json`: Capture 全体のマニフェスト

---

## Settings Reference

各設定項目の意味、初期値、変更する場面については以下を参照してください。

**→ [設定項目リファレンス](docs/ja/settings.md)**

---

## Troubleshooting

問題が発生した場合は、症状別の確認事項と対処方法をまとめた以下のページを参照してください。

**→ [トラブルシューティング](docs/ja/troubleshooting.md)**

---

## Documentation

- [セットアップガイド](docs/ja/setup.md)
- [使い方](docs/ja/usage.md)
- [設定項目リファレンス](docs/ja/settings.md)
- [トラブルシューティング](docs/ja/troubleshooting.md)
- [更新履歴](docs/ja/changelog.md)
- [ComfyUI ワークフロー README](docs/comfyui/README.md)

---

## Changelog

### v1.0

ViewTexForge 初回公開版。

主な機能:

- Auto Camera によるマルチビュー Capture
- Clay / Normal / Depth / Mask 出力
- Auto Lighting / Auto Light Power
- ComfyUI 連携
- Qwen Image Edit ベースのマルチビュー生成
- Albedo Mode
- Texture Merge
- Capture / ComfyUI / Texture Merge の統合 Execution
- 2 x 2（4 Cameras） / 3 x 3（9 Cameras）レイアウト

開発版を含む詳細な変更履歴は [更新履歴](docs/ja/changelog.md) を参照してください。

---

## License

ViewTexForge は **MIT License** で公開されています。

詳細はリポジトリ内の [LICENSE](LICENSE) を参照してください。

---

*Generated by ChatGPT Sol 5.6*
