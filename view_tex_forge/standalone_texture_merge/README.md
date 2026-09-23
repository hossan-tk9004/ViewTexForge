# Standalone Texture Merge Core v1

Blender 5.1.x / native Windows 用の決定論的Texture Merge Coreです。
ViewTexForge v0.2.1のCamera JSON v2とRaw CAMERA_Zを読み、現在の
BlenderシーンのEVALUATED_RENDER GeometryへGenerated Colorを投影します。
通常の成果物はObjectごとの`basecolor.png`だけです。

## 実行

Blender同梱のPythonとNumPyを使用します。CoreにPillowや追加アドオンの
インストールは不要です。CLIでは独立したBlenderプロセスで実行してください。

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe' `
  --background 'D:/your/project/model.blend' `
  --python-exit-code 1 `
  --python 'D:/RD/AITools/AstraBlender/standalone_texture_merge/run_texture_merge.py' `
  -- --manifest 'D:/your/project/generated_manifest.json' `
     --settings 'D:/your/project/merge_settings.json' `
     --output 'D:/your/project/merged'
```

`--scene SceneName`でシーンを明示できます。`--debug-output`で診断を有効に
できます。設定例は`examples/settings.json`、対応表の例は
`examples/generated_manifest.json`です。例のパスとIDは実データに置換してください。
Pythonからは`run_texture_merge.run(manifest_path, output_root, settings, scene)`を
呼び出せます。返り値は出力PNGの絶対パス一覧です。

Depth toleranceの既定は`AUTO`です。設定例:

```json
{
  "depth_tolerance_mode": "AUTO",
  "depth_sigma_scale_px": 0.65,
  "depth_cutoff_scale_px": 1.7
}
```

固定値が必要な場合だけ`MANUAL`に切り替え、`depth_sigma_m`と
`depth_cutoff_m`を使用してください。Debug reportにはAUTO時のView別
`pixel_footprint_m`、解決後`depth_sigma_m`、`depth_cutoff_m`を記録します。

シーンのメッシュ、UV、マテリアル、Object IDは変更せず、.blendも保存しません。
Geometry取得のため通常のRenderを1回実行するのでRender Resultは更新されます。
一時的に無効にするcompositingと追加ハンドラーは、失敗時も復元・除去します。
Render解像度、engine、modifier、カメラ、frameは変更しません。

## 入力と前提

- Manifestの各`views[]`に`view_id`、`camera_json_path`、`color.path`を指定します。
  camera.jsonとGenerated ColorのパスはManifestからの相対パスまたは絶対パスです。
  Depth／Geometry Maskのパスはそのcamera.jsonから解決します。
- `color_valid_mask: {"path": "...", "resolution": [W,H]}`を任意指定できます。
  省略時は全画素が有効です。黒い色を背景判定に使いません。
- Colorは8/16bit sRGB PNG、Raw DepthはNon-ColorのFLOAT32 EXRのRチャンネル、
  CAMERA_Zはカメラ前方に正のメートル単位、背景0を前提とします。
  Geometry Mask／Color Valid Maskは0/255二値PNG（読み込み後0.5を閾値）です。
- CameraはORTHO、行配列・列ベクトルのmatrix_worldとOpenGL NDC projection_matrix、
  Blender右手系Z-up・カメラ前方-Zです。保存済みprojection_matrixを正本にすることで
  shift、縦横比、pixel aspect、sensor fitを反映します。旧cameras.json形式には対応しません。
- 内部画像はTOP_LEFT、画素中心は(x+0.5,y+0.5)、UVは左下原点です。
  サンプリングはNEAREST（画像端座標に対するfloor）。リサイズやWarpは行いません。
- Generated ColorはすべてCapture pixel gridへ位置合わせ済みであることが前提です。
  `registration`はManifestに保持できますが、Coreは検証・解釈・変換しません。
- すべてのビューは同一の、カメラ非依存のGeometry評価状態と座標系を共有します。
  Capture時と同じframe、単位、modifier状態、render設定、対象シーンを準備してください。
  Coreは現在のシーンを評価し、capture_matrix_worldやcapture frameに巻き戻しません。
- 対象は各camera.jsonの`targets[]`の和集合です。そのObjectを含むビューだけをMergeします。
  `viewtexforge_object_id`で解決し、見つからない場合は記録された`object_name`を使用します。
  名前を変更しIDもない場合は入力側で対応を明示してください。重複IDは曖昧なためエラーです。
- v1はObjectごとに指定された1 UV Layer、0–1の1タイルです。タイル外はラスタライズ範囲外です。
  UDIM、instancerの個別インスタンス列挙、カメラ依存Geometryは対象外です。

完全なInput Contract Validation、geometry_digest照合、hash検証、UV重複検証、
registration確認は将来の別Utilityの責務です。Coreの入力チェックは必要ファイル、
実画像／宣言解像度の一致、対象Object、指定UVの存在を中心とします。
未対応ORTHO以外、欠損した必須field、画像デコード、設定値不正、RENDER取得失敗などの
実行上のエラーは隠さず停止します。未実証のGeometry fallbackはありません。

## Geometry取得の由来

`blender_geometry.py`はViewTexForge v0.2.1の`RenderContractCollector`と
`render_texture_merge_contract_pass`の取得経路を移植しています。
`depsgraph_update_post`／`frame_change_post`で実際の`RENDER` depsgraphのみ受理し、
`evaluated_get(depsgraph)` → `to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)`
→ `calc_loop_triangles()`で抽出します。RENDER graphが得られない場合は停止します。
差分は指定UV名の選択、ID書き込み・Digest生成・Camera再取得の除外です。
出典とライセンスは`THIRD_PARTY.md`を参照してください。

## 汎用v3 WeightとUV統合

World空間の三角形から単位Face Normalを計算します。同一evaluated vertexに接続する
単位三角形法線を等重みで加算して正規化し、UV texelで重心補間後、再正規化します。
Custom／Shading Normal、Rendered Normal、smoothフラグは使いません。
負のdeterminantを持つObject変換では法線の符号を補正して外向きを維持します。

```text
V = normalize(camera.matrix_worldのlocal +Z軸)
a = clamp(dot(average_geometry_normal, V), 0, 1)
g = clamp(12 * dot(face_normal, V), 0, 1)
delta = abs(depth_raw_m - (-camera_local_z) * meters_per_world_unit)
pixel_footprint_m = max(
    2 / (render_width  * abs(projection_matrix[0][0])),
    2 / (render_height * abs(projection_matrix[1][1]))
) * meters_per_world_unit

# AUTO (default)
depth_sigma_m  = pixel_footprint_m * 0.65
depth_cutoff_m = pixel_footprint_m * 1.70

w = view_priority * a^4 * g * exp(-(delta / depth_sigma_m)^2)
```

Depth toleranceは既定で`AUTO`です。保存済みORTHO projection matrixから各Viewの
1pixel相当のworld footprintをメートルで求め、`depth_sigma_scale_px=0.65`、
`depth_cutoff_scale_px=1.70`を掛けます。これによりCaptureのスケールや解像度が変わっても、
許容幅が画像のサンプリング密度に追従します。フレーム外、clip範囲外、Mask無効、
Depth非有限／0以下、`delta >= depth_cutoff_m`ではw=0です。

従来の固定メートル値を使う場合は`depth_tolerance_mode="MANUAL"`にし、
`depth_sigma_m` / `depth_cutoff_m`を指定します。
`OPAQUE_DOUBLE_SIDED_TRIANGLES`はDepth／OcclusionのSurface Policyです。
ColorはGeometry NormalでFacing Gateをかけるため、カメラから見た裏面は寄与0です。
`view_priority`は全Viewデフォルト1.0です。名前がfrontでも特別扱いしません。

各UV texelの中心を三角形の重心座標でラスタライズします。三角形のWorld Positionと
Average Normalを補間し、各カメラに投影して加重平均します。UV重複と共有辺は
**最小のevaluated loop_triangle indexを所有者**とする固定ルールです。
triangle順序が同一なら実行順やカメラの寄与によって所有者は変わりません。
退化UV三角形は寄与しません。

ビューはview_idの辞書順で加算し、Dominant Viewの同率時も先のview_idを採用します。
直接観測判定はweight_sum > 1e-5。未観測texelは黒のままです。
SRGB_ENCODEDを標準とし、SCENE_LINEARではsRGB伝達関数で線形化してから平均し、
出力時にsRGBへ戻します。いずれも出力PNGはsRGBで、AgX等のdisplay transformは通しません。

PaddingはUV占有領域の**外側だけ**に4近傍で指定距離まで広げます。内部Hole Fillは
行いません。UV islandは同じmesh edgeと一致する両端UVで接続判定します。
競合時は最短grid距離 → 最小island ID → 最小source pixel indexで決定します。
異なるislandの色は平均しません。直接観測とPaddingの判定は最後まで分離します。

## 構成と出力

| モジュール | 役割 |
|---|---|
| run_texture_merge | CLI／実行順序 |
| dataset_io / settings | Capture・Generated対応表と設定 |
| blender_geometry | ViewTexForgeと同じRENDER Geometry取得 |
| uv_rasterizer | Geometry法線、UVラスタライズ、所有者とisland |
| projection / merge_core | 保存Camera投影、Weight、色空間と統合 |
| uv_padding | 外側Paddingのみ |
| image_io / output_io | 数値を保持する画像入出力、任意Debug |

```text
merged/
  object_<safe-id-prefix>_<sha256-of-object-id>/
    basecolor.png
    debug/                    # debug_output=trueのときだけ生成
      direct_coverage.png     # 8bit二値、直接観測のみ
      padding_area.png        # 8bit二値、外側Paddingのみ
      weight_sum.exr          # float32 R（G/Bも同値）、加工前の重み合計
      dominant_view.npy       # uint32、0=直接観測なし、1以降はreportの対応表
      merge_report.json       # texel数、view統計、方式・対応表
```

ObjectディレクトリはWindowsの禁止文字、予約名、大小文字の衝突を避けるため、
IDの安全なprefixとSHA256を使います。Geometry Digestではありません。
再実行時は同じbasecolorを上書きします。過去のDebugファイルは自動削除しないため、
モード比較には別output directoryを使ってください。
`filled_area.png`や必須reportは出力しません。

メモリには対象1 Object分のUVラスタと全View画像を保持します。2048を標準にし、
高解像度・多数Viewではメモリ使用量に応じて解像度を選んでください。タイル分割や
ストリーミングはこのCoreにはまだありません。

## 検証

純粋Python部分はNumPyとPillowのあるPythonで実行できます（Pillowはテストのみ）。

```text
python -m unittest discover -s standalone_texture_merge/tests -p test_core.py -v
```

Blender統合テストは独立したbackgroundプロセスでのみ実行します。
`tests/blender_integration.py`は新規fixtureシーンで、ViewTexForge v0.2.1とのGeometry配列の
一致、render_levelsの使用、実ExporterのDepth／Mask、8/16bit PNGとEXR、
通常／Debug出力、失敗時の復元を確認します。

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe' `
  --background --factory-startup --python-exit-code 1 `
  --python 'D:/RD/AITools/AstraBlender/standalone_texture_merge/tests/blender_integration.py' `
  -- 'D:/RD/BlenderAddons/ViewTexForge'
```

fixtureと検証結果は新規`diagnostics/texture_merge_core_*`に保存します。
Registration、顔／眉／まつ毛／眼球／肌色等のRepair、Generative AI、完全Validator、
内部Hole Fill、Perspectiveは実装対象に含めていません。
