# Spine2Video-NTE-WuWa

> A tool for converting FModel-exported Spine 2D animations from Neverness to Everness (NTE) and Wuthering Waves (WuWa) into MP4 and transparent MOV videos.

---

# 🇯🇵 日本語

## 概要

FModelで書き出した **Neverness to Everness (NTE)** および **Wuthering Waves (鳴潮)** のSpineアセットを自動処理し、キャラクターのSpineアニメーションを動画として書き出すPythonツールです。

Spineデータとテクスチャを自動的に検出し、Spine WebGLを使用してアニメーションをレンダリングします。

## ✨ 主な機能

* 🎮 NTE / 鳴潮に対応
* 🌐 日本語 / Englishに対応
* 📂 FModelのExportフォルダを自動スキャン
* 🔍 Spineアセットを自動検出
* 🖼️ Atlasから必要なテクスチャを自動検索・コピー
* 🦴 `.skel` / `.atlas` を自動生成
* 🎞️ Spineアニメーションをフレーム単位でレンダリング
* 📹 MP4への自動変換
* 🪟 透過背景対応のMOV（ProRes 4444）出力
* ⚡ 複数Workerによる並列処理
* 🔧 FFmpegの自動検出・取得
* 🌐 Playwright / Chromiumの自動セットアップ
* 💾 処理済みアセットを`_done.json`に記録
* ⏭️ 処理済みアセットを自動スキップ
* 🧹 成功した処理の中間ファイルを自動削除
* 🛠️ 部分的な失敗時は中間ファイルを保持

## 📋 必要なもの

* Python 3.x
* FModel
* インターネット接続

以下のPythonパッケージは、不足している場合に自動的にインストールされます。

* `numpy`
* `Pillow`
* `playwright`
* `imageio-ffmpeg`

Playwright用のChromiumも必要に応じて自動インストールされます。

## 🚀 使い方

```bash
python Spine_2D.py
```

起動すると、言語を選択します。

```text
Select language / 言語を選択してください:
  1: Japanese
  2: English
```

次に処理するゲームを選択します。

```text
Which game do you want to process?
  1: NTE
  2: Wuthering Waves (WuWa)
```

初回起動時は、FModelのExport元フォルダと出力先フォルダを指定します。

指定したパスはJSON設定ファイルに保存され、次回以降は自動的に使用されます。

## 📁 入力

FModelからExportしたSpine関連のデータを使用します。

NTEでは`SpineAtlasAsset`と`SpineSkeletonDataAsset`を含むJSONを検索します。

鳴潮では同じJSON内にある`SpineAtlasAsset`と`SpineSkeletonDataAsset`を使用します。

Atlasに記載された画像名をもとに、必要なPNGテクスチャを自動検索します。

`Textures` / `textures`フォルダを優先し、見つからない場合はキャラクターフォルダ以下を再帰的に検索します。

## 🎞️ 出力

アニメーションごとに動画が生成されます。

```text
<AnimationName>.mp4
<AnimationName>_alpha.mov
```

* `.mp4` — 通常再生用動画
* `_alpha.mov` — 透過背景付き動画

透過MOVはProRes 4444 / `yuva444p10le`でエンコードされます。

## 🖥️ レンダリング

Spine WebGLをChromium上で実行し、Playwrightを使用してアニメーションをフレーム単位でレンダリングします。

デフォルト設定:

```python
FPS = 30
CANVAS_DIM = 2500
MARGIN = 1.15
```

アニメーションの長さから必要なフレーム数を自動計算します。

また、アニメーションをサンプリングしてキャラクターのBoundsを取得し、カメラを自動調整します。

## 🪟 透過動画

透過MOVを生成する場合、各フレームを黒背景と白背景の2種類でレンダリングします。

その2つの画像の差分からアルファチャンネルを再構築し、透過画像を生成します。

その後、FFmpegを使用して透過MOVへ変換します。

## ⚡ 並列処理

複数のWorkerによる並列処理に対応しています。

現在の設定:

```python
BROWSER_RESTART_EVERY = 2
N_PARALLEL_WORKERS = 2
```

WorkerごとにChromiumを使用して処理を行います。

一定数のキャラクターを処理するとブラウザを自動的に再起動します。

## 💾 処理済みアセット

正常に処理されたアセットは`_done.json`に記録されます。

例:

```json
{
  "CharacterName__AnimationData": {
    "completed_at": "2026-08-24 12:34:56"
  }
}
```

次回実行時には、すでに処理済みのアセットを自動的にスキップします。

これにより、大量のアセットを何度も処理する必要がありません。

## 🔧 自動セットアップ

不足しているPythonパッケージは自動的にインストールされます。

FFmpegがシステムに存在する場合は、そのFFmpegを使用します。

FFmpegが見つからない場合は`imageio-ffmpeg`を使用してFFmpegを自動取得します。

Playwright用のChromiumも必要に応じて自動インストールされます。

## ⚙️ ゲーム別設定

### Neverness to Everness

```python
SPINE_WEBGL_VERSION = "4.2.39"
PHYSICS_ARG = "spine.Physics.update"
```

### Wuthering Waves

```python
SPINE_WEBGL_VERSION = "4.1.*"
PHYSICS_ARG = ""
```

## 🐛 エラー処理

アセットの読み込みエラーやFFmpegによる動画変換エラーを検出して表示します。

MP4変換に失敗した場合、生成済みのPNGフレームは削除せず、そのまま残します。

そのため、失敗した処理を確認して再処理できます。

---

# 🇺🇸 English

## Overview

**Spine2Video-NTE-WuWa** is a Python tool for automatically processing **Spine assets exported from FModel** for **Neverness to Everness (NTE)** and **Wuthering Waves (WuWa)**.

It automatically detects Spine data and textures, renders animations using Spine WebGL, and converts them into video files.

## ✨ Features

* 🎮 NTE / Wuthering Waves support
* 🌐 Japanese / English interface
* 📂 Automatically scans FModel export folders
* 🔍 Automatically detects Spine assets
* 🖼️ Automatically finds and stages textures referenced by the Atlas
* 🦴 Automatically generates `.skel` / `.atlas` files
* 🎞️ Renders Spine animations frame-by-frame
* 📹 Automatically converts animations to MP4
* 🪟 Transparent MOV output using ProRes 4444
* ⚡ Parallel processing with multiple workers
* 🔧 Automatic FFmpeg detection and setup
* 🌐 Automatic Playwright / Chromium setup
* 💾 Records completed assets in `_done.json`
* ⏭️ Automatically skips already processed assets
* 🧹 Removes intermediate files after successful processing
* 🛠️ Keeps intermediate files when processing partially fails

## 📋 Requirements

* Python 3.x
* FModel
* Internet connection

The following Python packages are automatically installed if they are missing:

* `numpy`
* `Pillow`
* `playwright`
* `imageio-ffmpeg`

Chromium for Playwright is also automatically installed when required.

## 🚀 Usage

```bash
python Spine_2D.py
```

First, select your language:

```text
Select language / 言語を選択してください:
  1: Japanese
  2: English
```

Then select the game:

```text
Which game do you want to process?
  1: NTE
  2: Wuthering Waves (WuWa)
```

On the first run, you will be asked to provide the FModel export source folder and the output folder.

These paths are saved to a JSON configuration file and automatically reused on subsequent runs.

## 📁 Input

The tool uses Spine-related data exported from FModel.

For NTE, it searches for JSON files containing `SpineAtlasAsset` and `SpineSkeletonDataAsset`.

For Wuthering Waves, it uses `SpineAtlasAsset` and `SpineSkeletonDataAsset` data from the same JSON file.

Textures are automatically searched using the image names referenced by the Atlas.

The `Textures` / `textures` directories are checked first. If the texture is not found there, the character directory is searched recursively.

## 🎞️ Output

A video is generated for each animation.

```text
<AnimationName>.mp4
<AnimationName>_alpha.mov
```

* `.mp4` — Normal playback video
* `_alpha.mov` — Transparent video with an alpha channel

Transparent MOV files are encoded using ProRes 4444 / `yuva444p10le`.

## 🖥️ Rendering

Spine WebGL runs inside Chromium through Playwright and renders animations frame-by-frame.

Default settings:

```python
FPS = 30
CANVAS_DIM = 2500
MARGIN = 1.15
```

The required number of frames is automatically calculated from the animation duration.

The camera is also automatically fitted by sampling the animation and calculating the character bounds.

## 🪟 Transparent Video

When transparent MOV output is enabled, each frame is rendered against both black and white backgrounds.

The difference between the two renders is used to reconstruct the alpha channel.

The resulting frames are then encoded into a transparent MOV using FFmpeg.

## ⚡ Parallel Processing

The tool supports parallel processing using multiple workers.

Current settings:

```python
BROWSER_RESTART_EVERY = 2
N_PARALLEL_WORKERS = 2
```

Each worker uses Chromium to process its assigned assets.

The browser is automatically restarted after processing a certain number of characters.

## 💾 Processing Manifest

Successfully processed assets are recorded in `_done.json`.

Example:

```json
{
  "CharacterName__AnimationData": {
    "completed_at": "2026-08-24 12:34:56"
  }
}
```

On subsequent runs, assets that have already been processed are automatically skipped.

This allows large collections to be processed without rendering the same assets repeatedly.

## 🔧 Automatic Setup

Missing Python packages are automatically installed.

If FFmpeg is already available on the system, the existing installation is used.

If FFmpeg cannot be found, an FFmpeg executable is automatically obtained through `imageio-ffmpeg`.

Chromium for Playwright is also automatically installed when required.

## ⚙️ Game-specific Settings

### Neverness to Everness

```python
SPINE_WEBGL_VERSION = "4.2.39"
PHYSICS_ARG = "spine.Physics.update"
```

### Wuthering Waves

```python
SPINE_WEBGL_VERSION = "4.1.*"
PHYSICS_ARG = ""
```

## 🐛 Error Handling

Asset loading errors and FFmpeg encoding errors are detected and reported.

If MP4 encoding fails, the generated PNG frame sequence is kept instead of being deleted.

This allows failed output to be inspected and processed again.

---

## ⚠️ Disclaimer

This project is intended for processing assets that you have exported yourself using tools such as FModel.

Please make sure that your use of extracted assets complies with the terms of service and applicable rights of the respective games and services.
