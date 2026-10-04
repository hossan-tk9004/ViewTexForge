# トラブルシューティング

ViewTexForge の使用中に問題が発生した場合は、まずこのページを確認してください。

ViewTexForge は **Blender / Capture / ComfyUI / Texture Merge** をまたいで処理するため、エラーが発生したステージを切り分けると原因を特定しやすくなります。

## 目次

- [Blender / Add-on](#blender--add-on)
- [Output Directory](#output-directory)
- [Capture](#capture)
- [ComfyUI Connection](#comfyui-connection)
- [ComfyUI Workflow / Models](#comfyui-workflow--models)
- [Generation](#generation)
- [Texture Merge](#texture-merge)
- [Performance / VRAM](#performance--vram)
- [問題が解決しない場合](#問題が解決しない場合)

---

## Blender / Add-on

### ViewTexForge が Blender に表示されない

**確認事項**

1. 対応バージョンの Blender **5.1.x** を使用しているか確認してください。
2. `Edit > Preferences > Add-ons` で **ViewTexForge** が有効になっているか確認してください。
3. 3D Viewport で `N` キーを押し、Sidebar の **ViewTexForge** タブを確認してください。
4. インストール後に表示されない場合は Blender を再起動してください。

### アドオン有効化時に Python エラーが表示される

Blender の **System Console** に表示される Traceback を確認してください。

ViewTexForge のファイルが欠けている場合は、一度アドオンを削除し、配布 ZIP から再インストールしてください。

---

## Output Directory

### Output Directory のエラーが表示される

ViewTexForge は Capture / ComfyUI / Texture Merge の実行前に、出力先が存在し、書き込み可能かを確認します。

**確認事項**

- **Output Directory** が空欄になっていないか
- 書き込み権限のあるフォルダを指定しているか
- ファイルそのものではなくフォルダを指定しているか
- `//` から始まる Blender 相対パスを使用している場合、`.blend` ファイルを保存済みか

迷った場合は、まずローカルドライブ上に新しい空フォルダを作成し、そのフォルダを指定してください。

---

## Capture

### Capture を開始できない

**確認事項**

- `Render Target` が `Selected Only` の場合、対象オブジェクトを選択しているか
- 対象オブジェクトが Render 無効になっていないか
- Clay / Normal / Depth / Mask の出力項目がすべて無効になっていないか
- Output Directory が有効か

Capture 対象として使用できるオブジェクトが見つからない場合、Capture は開始できません。

### Selected Only で意図したモデルが出力されない

`Selected Only` は、実行時に選択されている対応オブジェクトだけを Capture 対象にします。

Capture を実行する直前に、必要なオブジェクトがすべて選択されていることを確認してください。

### モデルがカメラからはみ出す / 小さすぎる

Auto Cameras は対象の evaluated geometry を各カメラへ投影し、投影範囲を基準に Orthographic Camera をフィットします。

まず **Camera Margin** を調整してください。

- はみ出す場合: Margin を大きくする
- モデルが小さすぎる場合: Margin を小さくする

極端に離れた不要オブジェクトが Capture 対象に含まれていないかも確認してください。

### Clay が明るすぎる / 暗すぎる

`Lighting Mode` が **Auto** の場合、ViewTexForge が対象サイズからライト強度を計算します。

意図した結果にならない場合は、対象オブジェクトのスケールや Capture 対象を確認してください。必要に応じて Lighting Mode を Manual 側へ切り替え、Light Power を調整してください。

### Camera Metadata の作成で失敗する

Texture Merge 用 Capture では、Camera JSON / Raw CAMERA_Z / Geometry Mask などの整合性チェックを行います。

失敗した場合は Blender の **System Console** を確認してください。Camera JSON の contract error に詳細が記録される場合もあります。

---

## ComfyUI Connection

### ComfyUI に接続できない

初期設定の Server URL は以下です。

```text
http://127.0.0.1:8188
```

**確認事項**

1. ComfyUI が起動しているか
2. ブラウザから ComfyUI を開けるか
3. ViewTexForge の **Server URL** が ComfyUI のアドレスと一致しているか
4. ComfyUI を別ポートで起動している場合、そのポート番号を指定しているか

ViewTexForge は ComfyUI の `/system_stats` エンドポイントを使用して接続状態を確認します。

### ComfyUI が起動しているのに Connection Failed になる

ComfyUI を `127.0.0.1:8188` 以外で起動している場合は、実際の URL を ViewTexForge に設定してください。

また、Firewall / セキュリティソフト / ネットワーク設定によってローカル HTTP 通信が遮断されていないか確認してください。

---

## ComfyUI Workflow / Models

### Workflow Error が表示される

ViewTexForge は同梱された ComfyUI API Workflow の必要ノードを **ノード ID ではなく `_meta.title`** で検出します。

必要な契約ノードが欠けている、重複している、または想定したノード型と異なる場合、Workflow Validation Error になります。

通常の v1.0 利用では同梱 Workflow をそのまま使用してください。

詳細なエラーは Blender の **System Console** に表示されます。

### Missing Nodes が表示される

同梱 Workflow には複数の Custom Nodes と比較的新しい ComfyUI Core ノードが必要です。

1. ComfyUI を比較的新しいバージョンへ更新してください。
2. ComfyUI Manager から **Install Missing Custom Nodes** を実行してください。
3. 必要な Custom Nodes をインストールしてください。
4. ComfyUI を再起動してください。

必要な Custom Nodes の一覧は [ComfyUI ワークフロー README](../comfyui/README.md) を参照してください。

### Model not found / モデルが読み込めない

モデル名と配置先を確認してください。

主な配置先は以下です。

```text
ComfyUI/
└─ models/
   ├─ vae/
   ├─ loras/
   ├─ diffusion_models/
   ├─ text_encoders/
   └─ model_patches/
```

必要モデルと正確な配置先は [ComfyUI ワークフロー README](../comfyui/README.md) を確認してください。

モデルを追加した後は ComfyUI を再起動するか、必要に応じてモデル一覧を再読み込みしてください。

### Reference Image のエラーが表示される

ComfyUI Generation には有効な **Reference Image** が必要です。

- ファイルが存在するか
- ViewTexForge から正しい画像を選択しているか
- 画像を移動・削除した後に古いパスが残っていないか

を確認してください。

---

## Generation

### ComfyUI Generation が開始されない

以下を順番に確認してください。

1. Capture が正常に完了している
2. Output Directory 内に `clay` / `depth` / `mask` が存在する
3. ComfyUI が起動している
4. Server URL が正しい
5. Reference Image が設定されている
6. Workflow に Missing Nodes がない
7. 必要モデルがすべて配置されている

### 生成画像の視点順が合わない

`clay` / `depth` / `mask` は同じ Camera 順で対応している必要があります。

ViewTexForge が生成したフォルダをそのまま使用し、手動でファイル名や並び順を変更しないことを推奨します。

### 生成結果の形状が大きく崩れる

同梱 Workflow は Depth / Canny / Inpaint ControlNet を使用して形状維持を補助しますが、AI生成のため完全な形状一致は保証されません。

まず以下を確認してください。

- Capture 元の Clay / Depth / Mask が正常か
- Reference Image が対象キャラクターと大きく矛盾していないか
- 2 x 2 または 3 x 3 の推奨 Camera Layout を使用しているか

### 4 / 9 Cameras 以外を使いたい

ViewTexForge v1.0 の公開 GUI では **2 x 2（4 Cameras）** と **3 x 3（9 Cameras）** をサポート対象としています。

同梱 ComfyUI Workflow 自体には他の View 数に関する処理が含まれる場合がありますが、ViewTexForge v1.0 では公開設定として扱いません。

---

## Texture Merge

### Texture Merge を開始できない

Texture Merge には Capture と ComfyUI Generation の両方で生成されるデータが必要です。

主に以下を確認してください。

- `camera/` に Camera JSON が存在する
- `generated/` に生成画像が存在する
- Generated Manifest の各 View に Camera JSON と Generated Image の対応情報が存在する
- Capture 後に対象オブジェクトを削除・置換していない
- 対象オブジェクトに使用可能な UV が存在する

### Camera JSON not found が表示される

Texture Merge が参照している Camera JSON が見つかりません。

Capture を再実行し、その後 ComfyUI Generation を実行してから Texture Merge を行ってください。

Output Directory 内の `camera/` ファイルを手動で移動・削除しないでください。

### Generated color not found が表示される

ComfyUI の生成画像が見つからない、または Manifest に記録されたパスと一致していません。

ComfyUI Generation を再実行し、`generated/` の内容を確認してください。

### Specified UV Layer not found / UV 関連エラーが表示される

Texture Merge 対象には UV が必要です。

- 対象 Mesh に UV Map が存在するか
- Capture 後に UV Layer を削除・リネームしていないか
- Capture 時と Texture Merge 時で対象 Geometry / UV が大きく変わっていないか

を確認してください。

### Target Object not found が表示される

Capture 時に記録された対象オブジェクトを現在の Scene から特定できません。

Capture 後に対象オブジェクトを削除・置換・大きく構成変更した場合は、**Capture からやり直す**ことを推奨します。

### Texture Merge の結果に未塗り領域が残る

全 Camera から観測できない UV 領域は、設定によって未解決領域として残る場合があります。

まず Camera Layout を 3 x 3（9 Cameras）へ増やして改善するか確認してください。

Advanced Settings の Fill / Surface Sample を変更する場合は、初期値から一度に大きく変更せず、結果を確認しながら調整してください。

### Texture Merge 後に継ぎ目や視点差が目立つ

複数 Camera の生成結果そのものに色・陰影・ディテール差がある場合、Merge 後にも差が残ることがあります。

- Albedo Mode を試す
- Reference Image と Prompt を見直す
- Capture / Generation の出力を各 View ごとに確認する
- Camera Layout を 3 x 3 にする

などを検討してください。

---

## Performance / VRAM

### CUDA Out of Memory / VRAM 不足が発生する

同梱 ComfyUI Workflow は **8 GB VRAM の NVIDIA RTX GPU で動作確認済み**ですが、同時に使用している GPU アプリケーションや環境によって利用可能 VRAM は変化します。

必要に応じて以下を試してください。

- 他の GPU 使用アプリケーションを終了する
- ComfyUI の Low VRAM / model offload を利用する
- Albedo Mode を OFF にする
- RTX Video Super Resolution の負荷を下げる
- Marigold の設定を軽くする
- より低 bit の Qwen GGUF を使用する

詳細は [ComfyUI ワークフロー README](../comfyui/README.md) の VRAM Requirements を参照してください。

### 生成が非常に遅い

8 GB VRAM 環境では、モデルの CPU RAM への offload や再ロードが発生するため、高 VRAM 環境より処理に時間がかかる場合があります。

特に Albedo Mode は Marigold Appearance / Lighting の追加処理を行うため、OFF の場合より時間がかかります。

---

## 問題が解決しない場合

問題を報告する際は、可能であれば以下の情報を添えてください。

- ViewTexForge のバージョン
- Blender のバージョン
- ComfyUI の導入方式（Desktop / Portable / Manual）
- GPU と VRAM 容量
- 実行した Mode
- エラーメッセージ
- Blender System Console の Traceback / ViewTexForge ログ
- ComfyUI Console のエラー
- 問題が発生したステージ（Capture / ComfyUI / Texture Merge）

問題の切り分けでは、最初から統合実行するのではなく、

```text
Capture only
    ↓
ComfyUI only
    ↓
Texture Merge only
```

の順に個別実行すると、どのステージで問題が起きているか確認しやすくなります。
