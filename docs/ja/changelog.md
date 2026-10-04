# ViewTexForge 更新履歴

[← README に戻る](../../README.md)

## v1.0 - Initial Public Release

GitHub 公開向け初回リリース。

主な機能:

- Blender 5.1.x 対応
- Auto Camera 2 x 2（4 Cameras） / 3 x 3（9 Cameras）
- Clay / Normal / Depth / Mask Capture
- Raw CAMERA_Z / Geometry Mask / Camera Metadata
- Auto Lighting
- Auto / Manual Light Power
- ComfyUI HTTP API Integration
- Bundled Qwen Image Edit Workflow
- Albedo Mode
- Integrated Texture Merge
- 6種類の Execution Mode
- Modal Capture / Texture Merge Progress
- Output Directory Validation
- Status / Progress UI

---

# Development History

以下は v1.0 公開までの開発版履歴です。

## v1.0.0

- Auto / Manual Power Mode を追加。
- Auto を既定値とし、対象 bounds と auto-light rig scale から Area Light Power を自動計算。
- モデルサイズに応じた squared size relationship と safety clamp を使用。
- Manual 時のみ Light Power を表示。

## v0.5.17

- Render Target の radio choices と標準 option rows の実効幅を統一。
- Reference Image preview を拡大。

## v0.5.16

- Render Target を横一列の radio-style UI に変更。
- Reference Image を label + path / thumbnail のコンパクトな2行構成に変更。
- ComfyUI panel から Workflow 選択を非表示化し、同梱 workflow を固定使用。

## v0.5.15

- Release GUI / defaults を整理。
- Capture / ComfyUI / Texture Merge Settings は表示し、二次オプションを折りたたみ化。
- Clay Rendering 既定値を Lit Clay Render + Auto Lighting に変更。
- Camera mode を release workflow では Auto Cameras に固定。
- Camera Layout を 2 x 2（4 Cameras） / 3 x 3（9 Cameras）に限定。
- Albedo Source は Albedo Mode ON 時のみ表示。
- Texture Merge visibility を Strict Ray に固定。
- Advanced に Depth Tolerance / RGB Surface Check / Small Hole Fill / tuning settings を整理。

## v0.5.14

- Output Directory validation を Capture / ComfyUI / Texture Merge / Show Explorer に追加。
- Capture を modal incremental operation 化し、view/pass progress を表示。
- Texture Merge を modal incremental operation 化し、各処理 progress を表示。
- Execution が Capture / Texture Merge の modal stage を待機し、Overall Progress へ反映。
- failure / cancellation 時の runtime lock 解放を改善。

## v0.5.12

- 9-camera の Front-Right / Front-Left を pitch +15° へ調整。
- Lower-Front は pitch -30° を維持。

## v0.5.11

- 9-camera layout を axis-heavy validation set に変更。
- Front / Right / Back / Left / Top / Bottom / Front-Right / Front-Left / Lower-Front。

## v0.5.10

- 9-camera layout を左右対称構成へ調整。
- Front + upper diagonal 4 views + lower diagonal 4 views を検証。

## v0.5.9

- 一時的な 8-camera validation mode を legacy 9-camera mode へ置換。
- Auto Camera layouts を 4 / 6 / 9 / 12 / 16 として検証。

## v0.5.8

- 4 / 6 / 8 / 12 / 16 camera layouts を検証用に追加。
- Legacy 8-view horizontal ring / 16-view angle set を復元。

## v0.5.7

- Auto Camera orthographic fitting を各 camera local 2D plane 上の evaluated target geometry bounds 基準へ変更。
- Oblique view が小さく写る原因だった cube/AABB based ortho-scale floor を撤廃。
- Camera Margin を projected fit に適用。

## v0.5.6

- 4 / 6 / 12 cameras の 2 x 2 / 3 x 2 / 4 x 3 tiling を実装・検証。
- capture.json に grid_columns / grid_rows を追加。

## v0.5.5

- ComfyUI 向け `mask` を RGB 8-bit pure black/white に変更。
- ComfyUI 向け `depth` を RGB 8-bit に変更。
- Texture Merge 用 `depth_raw` / `geometry_mask` は変更せず維持。

## v0.5.0

- Auto Cameras の multi-view layouts を拡張。
- Capture output を `clay / normal / depth / mask / raw_depth / geometry_mask / camera` の用途別 folder へ整理。
- `view_XXXX` 命名に統一。
- `capture.json` manifest を追加。
- stale view files の cleanup を追加。

## v0.4.0

- Standalone Texture Merge Core v1 を統合。
- Capture / ComfyUI / Texture Merge settings を collapsible section 化。
- 6種類の unified Execution mode を追加。
- shared Status / overall / stage progress を追加。
- ComfyUI generated manifest を Texture Merge 対応へ拡張。

## v0.3.4

- ComfyUI workflow selection を main panel から非表示化。
- Texture Merge Contract / ComfyUI Input Mapping を main panel から非表示化。
- Show Explorer を追加。
- ComfyUI progress 表示を改善。

## v0.3.3

- Capture folder / view_id を `view_0001`, `view_0002`, ... の canonical numeric ID に統一。
- `view_0001` を Front として固定。
- ComfyUI capture discovery で contiguous view IDs を検証。

## v0.3.2

- 複数 Camera folder の `clay.png / depth.png / mask.png` upload filename collision を修正。
- View ordinal / view_id を含む upload filename に変更。

## v0.3.1

- Bundled ComfyUI API workflow を `workflows/` へ配置。
- `_meta.title` ベースの ViewTexForge workflow contract を追加。
- workflow startup / change / generation before submit 時の validation を追加。

## v0.3.0

- ViewTexForge → ComfyUI generation integration を追加。
- Server URL / connection monitor / Reference Image / Seed Mode を追加。
- HTTP polling based progress を追加。
- Generated image download / generated manifest を追加。

## v0.2.1

- Raw CAMERA_Z を METERS に統一。
- Geometry Mask / Raw Depth を material alpha / AA 非依存の geometry rasterization に変更。
- Camera JSON v2 の座標系 metadata を拡張。
- Geometry Digest serialization を `VTFGEOM1_LE_F64_U64` に統一。

## v0.2.0

- Camera JSON format_version 2。
- capture_id を追加。
- ORTHO projection_matrix を追加。
- Raw CAMERA_Z EXR を追加。
- geometry_mask.png を追加。
- EVALUATED_RENDER Geometry Digest を追加。

## v0.1.14

- `depth_space = CAMERA_Z` metadata を camera.json に追加。

## v0.1.13

- Auto4 framing と output resolution / aspect fitting を修正。
- Camera Margin を Auto Cameras 専用に整理。

## v0.1.12

- Camera Margin control を追加。

## v0.1.11

- Auto lights の Cast Shadow option を追加。
- Auto camera framing を target cube bounds 基準へ改善。

## v0.1.10

- Auto light exposure を Blender `Light.exposure` へ反映。
- Light Power / Normalize / directional Exposure を UI に追加。
- Auto light placement を target bounds の longest axis 基準 cube へ変更。

## v0.1.9

- Keep Auto Lights (Debug) を追加。

## v0.1.8

- Auto light placement を target bounding-box faces 基準へ変更。
- Square Area Light / Normalize を採用。

## v0.1.3

- Blender 5.1 compositor / File Output API 対応。
- Qwen output size presets を追加。
- Viewport Camera preview overlay を追加。
- Solid Viewport / Lit Clay Render を追加。
- Existing Lighting / Auto 5-area-light rig を追加。

## v0.1.2

- Blender version compatible Eevee engine selection を追加。
- Version display を ViewTexForge panel に追加。
