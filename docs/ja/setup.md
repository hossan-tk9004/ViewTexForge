# ViewTexForge セットアップガイド

[← README に戻る](../../README.md)

このページでは、ViewTexForge v1.0 を Blender に導入し、同梱 ComfyUI ワークフローを実行できる状態にするまでのセットアップを説明します。

---

## 1. ViewTexForge のインストール

### Requirements

- Blender 5.1.x
- ViewTexForge v1.0 Release ZIP

### Install

1. GitHub の **Releases** から ViewTexForge v1.0 の配布用 ZIP をダウンロードします。
2. ZIP は展開しません。
3. Blender を起動します。
4. `Edit > Preferences > Add-ons` を開きます。
5. メニューから **Install from Disk...** を選択します。
6. ViewTexForge の ZIP を指定します。
7. インストールされた **ViewTexForge** を有効にします。
8. 3D Viewport で `N` キーを押し、Sidebar の **ViewTexForge** タブを確認します。

---

## 2. ComfyUI の導入

フルワークフローの `ComfyUI` ステージを使用する場合は ComfyUI が必要です。

ComfyUI には主に以下の導入方法があります。環境に合わせていずれかを選択してください。

| 導入方法 | ダウンロード / Repository | 公式セットアップドキュメント |
|---|---|---|
| GitHub / Manual Install | [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI) | [Manual Installation](https://docs.comfy.org/installation/manual_install) |
| Windows Portable | [Download Page](https://docs.comfy.org/installation/comfyui_portable_windows#download-comfyui-portable) | [ComfyUI Portable for Windows](https://docs.comfy.org/installation/comfyui_portable_windows) |
| Desktop | [ComfyUI Download](https://comfy.org/download) | [Comfy Desktop for Windows](https://docs.comfy.org/installation/desktop/windows) |

ComfyUI 自体のインストール方法や初期設定は、**各導入方法に対応した ComfyUI 公式セットアップドキュメントを参照してください。** ViewTexForge の設定へ進む前に、ComfyUI 単体で正常に起動できることを確認してください。

> 同梱ワークフローは NVIDIA RTX Video Super Resolution を使用するため、標準構成では NVIDIA RTX GPU を前提としています。Windows + NVIDIA RTX 環境では、Portable版またはDesktop版が導入しやすい選択肢です。

ViewTexForge の既定 Server URL:

```text
http://127.0.0.1:8188
```

別ポートや別PCの ComfyUI を使用する場合は、ViewTexForge の **ComfyUI Settings > Server URL** を変更してください。

---

## 3. ComfyUI を更新する

同梱ワークフローでは比較的新しい ComfyUI Core ノードを使用します。

古い ComfyUI では Missing Node が発生する可能性があるため、以下を推奨します。

1. ComfyUI を比較的新しいバージョンへ更新
2. ComfyUI Manager を更新
3. 同梱ワークフローを ComfyUI で開く
4. **Install Missing Custom Nodes** を実行
5. 不足している Custom Nodes をインストール
6. ComfyUI を再起動

---

## 4. Required Models

### Qwen Image Edit

```text
qwen-image-edit-2511-Q8_0.gguf
qwen_2.5_vl_7b_fp8_scaled.safetensors
qwen_image_vae.safetensors
Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
```

### DiffSynth ControlNet

```text
qwen_image_depth_diffsynth_controlnet.safetensors
qwen_image_canny_diffsynth_controlnet.safetensors
qwen_image_inpaint_diffsynth_controlnet.safetensors
```

### Albedo Mode

Albedo Mode を使用する場合:

```text
prs-eth/marigold-iid-appearance-v1-1
prs-eth/marigold-iid-lighting-v1-1
```

Marigold モデルは `ComfyUI-Marigold` から Hugging Face 経由で取得されます。

---

## 5. Model Storage Location

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

モデルの入手先を含む詳細は以下を参照してください。

**→ [ComfyUI ワークフロー README](../comfyui/README.md)**

---

## 6. Required Custom Nodes

同梱ワークフローでは主に以下の Custom Nodes を使用します。

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

詳細な用途と各 Repository は [ComfyUI ワークフロー README](../comfyui/README.md) を参照してください。

---

## 7. Hardware Guideline

同梱 ComfyUI ワークフローは **8 GB VRAM の NVIDIA RTX GPU で動作確認済み**です。

| VRAM | 目安 |
|---:|---|
| 8 GB | 動作確認済み / 基準環境 |
| 12 GB | より余裕あり |
| 16 GB | 高い余裕あり |
| 24 GB+ | 高解像度処理や追加モデルにも余裕 |

System RAM の目安:

```text
32 GB minimum recommended
64 GB preferred for low-VRAM operation
```

NVIDIA RTX Video Super Resolution を同梱ワークフローで使用するため、標準構成では NVIDIA RTX GPU を前提とします。

---

## 8. ViewTexForge と ComfyUI の接続確認

1. ComfyUI を起動します。
2. Blender で ViewTexForge を開きます。
3. **ComfyUI Settings** を展開します。
4. **Server URL** を確認します。
5. `Status: Connected` になることを確認します。
6. `Workflow Status: Valid` になることを確認します。

接続できない場合は、ComfyUI が起動していること、URL / Port が一致していることを確認してください。

---

## 9. Texture Merge を使用する前の準備

Texture Merge は、Capture 時の Camera / Raw Depth / Geometry 情報を使用して、生成画像を UV Texture へ統合します。

主な前提:

- 対象 Mesh に UV Layer が存在する
- 現在の v1 Core は 0-1 範囲の単一 UV タイルを前提とする
- Capture 後に対象 Geometry を大きく変更しない
- Capture と Merge で対応する対象 Object を維持する

通常は ViewTexForge の統合 Execution を利用すれば、必要な Manifest や中間ファイルは自動的に生成されます。

---

## 10. Setup Complete

以上で基本セットアップは完了です。

次は [使い方](usage.md) の **Quick Start** から実行してください。
