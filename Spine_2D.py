import importlib
import shutil
import subprocess
import sys


def _ensure_package(module_name: str, pip_name: str = None):
    """モジュールが無ければpipで自動インストールしてからimportする"""
    try:
        return importlib.import_module(module_name)
    except ImportError:
        pip_name = pip_name or module_name
        print(f"[setup] {pip_name} が見つからないのでインストールします... / installing {pip_name} ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", pip_name], check=True)
        return importlib.import_module(module_name)


_ensure_package("numpy")
_ensure_package("PIL", "pillow")
_ensure_package("playwright")

import base64
import gc
import http.server
import io
import json
import socket
import socketserver
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright


def _ensure_playwright_browser():
    """Playwright用のChromiumが入ってなければ自動でインストールする"""
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True, capture_output=True,
        )
    except Exception as e:
        print(f"[setup warning] playwright install chromium に失敗した可能性: {e}")


def _ensure_ffmpeg() -> str:
    """システムにffmpegが無ければ imageio-ffmpeg 経由で自動取得する。
    戻り値: 使用するffmpeg実行ファイルへのパス(文字列)"""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    print("[setup] システムにffmpegが見つからないので imageio-ffmpeg 経由で自動取得します... "
          "/ ffmpeg not found on system, fetching via imageio-ffmpeg ...")
    imageio_ffmpeg = _ensure_package("imageio_ffmpeg", "imageio-ffmpeg")
    return imageio_ffmpeg.get_ffmpeg_exe()


# ---------- -2. 言語選択 (日本語 / English) ----------

LANG = None  # "ja" または "en"


def choose_language() -> str:
    print("Select language / 言語を選択してください:")
    print("  1: Japanese")
    print("  2: English")
    while True:
        choice = input("番号を入力 / Enter number [1/2]: ").strip()
        if choice in ("1", "ja", "JA", "Japanese"):
            return "ja"
        if choice in ("2", "en", "EN", "English"):
            return "en"
        print("  -> 1か2で入力してください。 / Please enter 1 or 2.")


def t(ja: str, en: str) -> str:
    """LANGに応じて日本語/英語のメッセージを返す"""
    return ja if LANG == "ja" else en


# ---------- -1. モード選択(NTE / 鳴潮) ----------

MODE = None  # "nte" または "wuwa"


def choose_mode() -> str:
    print(t("どちらを処理しますか?", "Which game do you want to process?"))
    print("  1: NTE")
    print(t("  2: 鳴潮(Wuthering Waves)", "  2: Wuthering Waves (WuWa)"))
    while True:
        choice = input(t("番号を入力 [1/2]: ", "Enter number [1/2]: ")).strip()
        if choice in ("1", "nte", "NTE"):
            return "nte"
        if choice in ("2", "wuwa", "WuWa", "WUWA", "鳴潮"):
            return "wuwa"
        print(t("  -> 1か2で入力してください。", "  -> Please enter 1 or 2."))


# ---------- 0. 設定(json保存、フォルダ自動生成) ----------

CONFIG_PATH = None
SOURCE_ROOT = Path("")
OUTPUT_ROOT = Path("")


def load_or_create_config():
    global SOURCE_ROOT, OUTPUT_ROOT

    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            SOURCE_ROOT = Path(cfg["source_root"])
            OUTPUT_ROOT = Path(cfg["output_root"])
            OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
            return
        except (json.JSONDecodeError, KeyError, OSError) as e:
            print(t(f"[警告] {CONFIG_PATH} の読み込みに失敗、初回設定をやり直す: {e}",
                     f"[Warning] Failed to read {CONFIG_PATH}, redoing first-run setup: {e}"))

    print(t(f"初回実行のようです。設定ファイル({CONFIG_PATH.name})が無いのでパスを入力してください。",
             f"Looks like this is a first run. No config file ({CONFIG_PATH.name}) found, please enter paths."))
    print(t("(何も入力せずEnterのみなら [ ] 内のデフォルト値を使います。デフォルトが空の項目は入力必須です)",
             "(Press Enter with nothing typed to use the default in [ ]. Fields with an empty default are required.)"))

    while True:
        src_in = input(t(f"FModel書き出し元フォルダのパス [{SOURCE_ROOT}]: ",
                          f"Path to the FModel export source folder [{SOURCE_ROOT}]: ")).strip().strip('"')
        if src_in:
            SOURCE_ROOT = Path(src_in)
            break
        if str(SOURCE_ROOT):
            break
        print(t("  -> 空にはできません。パスを入力してください。", "  -> Cannot be empty. Please enter a path."))

    while True:
        out_in = input(t(f"保存先フォルダのパス [{OUTPUT_ROOT}]: ",
                          f"Path to the output folder [{OUTPUT_ROOT}]: ")).strip().strip('"')
        if out_in:
            OUTPUT_ROOT = Path(out_in)
            break
        if str(OUTPUT_ROOT):
            break
        print(t("  -> 空にはできません。パスを入力してください。", "  -> Cannot be empty. Please enter a path."))

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    save_config()
    print(t(f"設定を {CONFIG_PATH} に保存した。次回からはこのファイルの値が自動で使われる。",
             f"Saved settings to {CONFIG_PATH}. These values will be used automatically from now on."))


def save_config():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps({"source_root": str(SOURCE_ROOT), "output_root": str(OUTPUT_ROOT)},
                    ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


SPINE_WEBGL_VERSION = None
PHYSICS_ARG = None
FFMPEG_BIN = "ffmpeg"  # main()冒頭で_ensure_ffmpeg()により実際のパスに更新される

FPS = 30
CANVAS_DIM = 2500
BATCH_SIZE = max(2, int(20 * (1200 / CANVAS_DIM) ** 2))
MARGIN = 1.15
MAKE_VIDEO = True
MAKE_ALPHA_MOV = True
SHOW_BROWSER_LOGS = False
LOAD_TIMEOUT_MS = 600000


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


HTTP_PORT = None
DONE_MANIFEST_NAME = "_done.json"


def done_manifest_path() -> Path:
    return OUTPUT_ROOT / DONE_MANIFEST_NAME


def load_done_manifest() -> dict:
    p = done_manifest_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_done_manifest(manifest: dict):
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    done_manifest_path().write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def try_extract_spine_pair(atlas_json_path: Path):
    try:
        with open(atlas_json_path, "r", encoding="utf-8") as f:
            atlas_data = json.load(f)
        atlas_entry = next((d for d in atlas_data if d.get("Type") == "SpineAtlasAsset"), None)
        if atlas_entry is None:
            return None
        atlas_raw = atlas_entry["Properties"]["RawData"]
        if not isinstance(atlas_raw, str):
            return None
        data_json_path = atlas_json_path.parent / f"{atlas_json_path.stem}_Data.json"
        if not data_json_path.exists():
            return None
        with open(data_json_path, "r", encoding="utf-8") as f:
            skel_data = json.load(f)
        skel_entry = next((d for d in skel_data if d.get("Type") == "SpineSkeletonDataAsset"), None)
        if skel_entry is None:
            return None
        skel_raw = skel_entry["Properties"]["RawData"]
        if not isinstance(skel_raw, list):
            return None
        return atlas_raw.replace("\\n", "\n"), bytes(bytearray(skel_raw))
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, UnicodeDecodeError, OSError):
        return None


def try_extract_spine_json(json_path: Path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        atlas_entry = next((d for d in data if d.get("Type") == "SpineAtlasAsset"), None)
        skel_entry = next((d for d in data if d.get("Type") == "SpineSkeletonDataAsset"), None)
        if atlas_entry is None or skel_entry is None:
            return None
        atlas_raw = atlas_entry["Properties"]["rawData"]
        skel_raw = skel_entry["Properties"]["rawData"]
        if not isinstance(atlas_raw, str) or not isinstance(skel_raw, list):
            return None
        return atlas_raw.replace("\\n", "\n"), bytes(bytearray(skel_raw))
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, UnicodeDecodeError, OSError):
        return None


def atlas_page_images(atlas_text: str):
    lines = atlas_text.splitlines()
    images = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or ":" in s:
            continue
        prev_blank = (i == 0) or (lines[i - 1].strip() == "")
        next_is_size = (i + 1 < len(lines)) and lines[i + 1].strip().startswith("size:")
        if prev_blank and next_is_size:
            images.append(s)
    return images


def find_png(char_dir: Path, image_name: str):
    stem = Path(image_name).stem
    for tex_dir_name in ("Textures", "textures"):
        tex_dir = char_dir / tex_dir_name
        if tex_dir.is_dir():
            hit = list(tex_dir.glob(f"{stem}.png"))
            if hit:
                return hit[0]
            mip_hits = sorted(tex_dir.glob(f"{stem}_MIP*.png"))
            if mip_hits:
                return mip_hits[0]
    hit = list(char_dir.rglob(f"{stem}.png"))
    if hit:
        return hit[0]
    mip_hits = sorted(char_dir.rglob(f"{stem}_MIP*.png"))
    return mip_hits[0] if mip_hits else None


def stage_textures(atlas_text: str, images: list, char_dir: Path, stem: str, out_dir: Path):
    lines = atlas_text.splitlines()
    copied = []
    missing = []
    for img in images:
        src = find_png(char_dir, img)
        if src is None:
            missing.append(img)
            continue
        new_name = f"{stem}__{src.name}"
        dest = out_dir / new_name
        if not dest.exists():
            shutil.copy2(src, dest)
        copied.append(dest)
        for i, line in enumerate(lines):
            if line.strip() == img:
                lines[i] = new_name
    return "\n".join(lines), copied, missing


def extract_all(done_manifest: dict):
    entries = []
    if not SOURCE_ROOT.exists():
        print(t(f"見つからない: {SOURCE_ROOT}", f"Not found: {SOURCE_ROOT}"))
        return entries

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for json_path in SOURCE_ROOT.rglob("*.json"):
        if MODE == "nte":
            if json_path.stem.endswith("_Data"):
                continue
            if json_path.parent.name.lower() == "textures":
                continue
            result = try_extract_spine_pair(json_path)
        else:
            result = try_extract_spine_json(json_path)

        if result is None:
            continue
        atlas_text, skel_bytes = result
        char_dir = json_path.parent
        stem = json_path.stem
        manifest_key = f"{char_dir.name}__{stem}"

        if manifest_key in done_manifest:
            print(t(f"[スキップ] {manifest_key} : 完了マーカーあり(処理済み)",
                     f"[Skipped] {manifest_key} : already has a completion marker"))
            continue

        images = atlas_page_images(atlas_text)
        out_dir = OUTPUT_ROOT / char_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)

        new_atlas_text, pngs, missing = stage_textures(atlas_text, images, char_dir, stem, out_dir)

        if not pngs:
            print(t(f"[スキップ] {json_path.relative_to(SOURCE_ROOT)} : テクスチャが見つからない ({', '.join(images)})",
                     f"[Skipped] {json_path.relative_to(SOURCE_ROOT)} : no textures found ({', '.join(images)})"))
            continue
        if missing:
            print(t(f"[注意] {json_path.relative_to(SOURCE_ROOT)} : 見つからないテクスチャ {missing}",
                     f"[Note] {json_path.relative_to(SOURCE_ROOT)} : missing textures {missing}"))

        skel_name, atlas_name = f"{stem}.skel", f"{stem}.atlas"
        (out_dir / skel_name).write_bytes(skel_bytes)
        (out_dir / atlas_name).write_text(new_atlas_text, encoding="utf-8")

        entries.append((char_dir.name, skel_name, atlas_name, manifest_key))
        print(t(f"[抽出OK] {manifest_key} : png x{len(pngs)}",
                 f"[Extracted OK] {manifest_key} : {len(pngs)} png(s)"))

    return entries


HARNESS_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://unpkg.com/@esotericsoftware/spine-webgl@__SPINE_VERSION__/dist/iife/spine-webgl.js"></script>
</head><body style="margin:0">
<canvas id="canvas" width="__DIM__" height="__DIM__"></canvas>
<script>
window.ready = false;
window.loadError = null;
window.animNames = [];

window.addEventListener('error', (e) => {
  window.loadError = 'window.onerror: ' + e.message;
  console.error('CAUGHT', e.message, e.filename, e.lineno);
});

if (typeof spine === 'undefined') {
  window.loadError = 'spine-webgl script did not load (CDN blocked/offline?)';
}

const canvas = document.getElementById("canvas");
const gl = canvas.getContext("webgl", {alpha: true, premultipliedAlpha: false, preserveDrawingBuffer: true, antialias: true});
if (!gl) {
  window.loadError = 'WebGL context could not be created';
}
let renderer, assetManager;
if (gl && typeof spine !== 'undefined') {
  renderer = new spine.SceneRenderer(canvas, gl, true);
  assetManager = new spine.AssetManager(gl, "");
  assetManager.loadBinary("__SKEL__");
  assetManager.loadTextureAtlas("__ATLAS__");
}

let skeleton, animations = {};

function poll() {
  if (window.loadError) return;
  if (!assetManager) { setTimeout(poll, 30); return; }
  if (assetManager.hasErrors && assetManager.hasErrors()) {
    window.loadError = 'asset load error: ' + JSON.stringify(assetManager.getErrors());
    return;
  }
  if (assetManager.isLoadingComplete()) {
    const atlas = assetManager.get("__ATLAS__");
    const atlasLoader = new spine.AtlasAttachmentLoader(atlas);
    const skeletonBinary = new spine.SkeletonBinary(atlasLoader);
    const skeletonData = skeletonBinary.readSkeletonData(assetManager.get("__SKEL__"));
    skeleton = new spine.Skeleton(skeletonData);
    skeletonData.animations.forEach(a => { animations[a.name] = a; window.animNames.push(a.name); });

    skeleton.setToSetupPose();
    skeleton.updateWorldTransform(__PHYSICS__);

    console.log('SLOTS(draw order): ' + skeleton.slots.map((s, i) => {
      const att = s.getAttachment();
      return `#${i}:${s.data.name}=[${att ? att.name : 'null'}]/blend=${s.data.blendMode}`;
    }).join(' | '));

    window.ready = true;
  } else {
    setTimeout(poll, 30);
  }
}
if (gl && typeof spine !== 'undefined') poll();

const HIDE_SLOT_KEYWORDS = ['数字', '数据', 'shuju'];
const DEBUG_HIDE_ALL_SCREEN_BLEND = true;
function hideDebugSlots() {
  skeleton.slots.forEach(s => {
    const nameHit = HIDE_SLOT_KEYWORDS.some(kw => s.data.name.includes(kw));
    const screenHit = DEBUG_HIDE_ALL_SCREEN_BLEND && s.data.blendMode === 3;
    if (nameHit || screenHit) {
      s.setAttachment(null);
    }
  });
}

window.renderFrame = function(animName, time, bgR, bgG, bgB) {
  const anim = animations[animName];
  skeleton.setToSetupPose();
  anim.apply(skeleton, 0, time, false, null, 1, spine.MixBlend.setup, spine.MixDirection.mixIn);
  hideDebugSlots();
  skeleton.updateWorldTransform(__PHYSICS__);
  gl.clearColor(bgR, bgG, bgB, 1);
  gl.clear(gl.COLOR_BUFFER_BIT);
  renderer.begin();
  renderer.drawSkeleton(skeleton, false);
  renderer.end();
  return canvas.toDataURL("image/png");
};

window.renderFrameBatch = function(animName, startFrame, count, fps, needAlpha) {
  const anim = animations[animName];
  const blackUrls = [];
  const whiteUrls = [];
  for (let k = 0; k < count; k++) {
    const t = (startFrame + k) / fps;
    skeleton.setToSetupPose();
    anim.apply(skeleton, 0, t, false, null, 1, spine.MixBlend.setup, spine.MixDirection.mixIn);
    hideDebugSlots();
    skeleton.updateWorldTransform(__PHYSICS__);

    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    renderer.begin();
    renderer.drawSkeleton(skeleton, false);
    renderer.end();
    blackUrls.push(canvas.toDataURL("image/png"));

    if (needAlpha) {
      gl.clearColor(1, 1, 1, 1);
      gl.clear(gl.COLOR_BUFFER_BIT);
      renderer.begin();
      renderer.drawSkeleton(skeleton, false);
      renderer.end();
      whiteUrls.push(canvas.toDataURL("image/png"));
    }
  }
  return { black: blackUrls, white: whiteUrls };
};

window.getAnimDuration = function(animName) {
  return animations[animName].duration;
};

window.fitCameraToAnim = function(animName, samples) {
  const anim = animations[animName];
  const n = Math.max(1, samples || 20);
  const offset = new spine.Vector2(), size = new spine.Vector2();
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (let i = 0; i <= n; i++) {
    const t = (anim.duration * i) / n;
    skeleton.setToSetupPose();
    anim.apply(skeleton, 0, t, false, null, 1, spine.MixBlend.setup, spine.MixDirection.mixIn);
    hideDebugSlots();
    skeleton.updateWorldTransform(__PHYSICS__);
    skeleton.getBounds(offset, size, []);
    minX = Math.min(minX, offset.x);
    minY = Math.min(minY, offset.y);
    maxX = Math.max(maxX, offset.x + size.x);
    maxY = Math.max(maxY, offset.y + size.y);
  }
  const width = maxX - minX, height = maxY - minY;
  renderer.camera.position.set(minX + width / 2, minY + height / 2, 0);
  const squareDim = Math.max(width, height) * __MARGIN__;
  renderer.camera.viewportWidth = squareDim;
  renderer.camera.viewportHeight = squareDim;
  renderer.camera.update();
};
</script>
</body></html>
"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve_output_root(port: int):
    def handler(*a, **kw):
        return QuietHandler(*a, directory=str(OUTPUT_ROOT), **kw)
    httpd = ThreadingHTTPServer(("localhost", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def decode_frame_rgb(data_url: str) -> np.ndarray:
    png_bytes = base64.b64decode(data_url.split(",", 1)[1])
    return np.array(Image.open(io.BytesIO(png_bytes)).convert("RGB"), dtype=np.float32)


def compose_alpha_from_black_white(black_arr: np.ndarray, white_arr: np.ndarray) -> Image.Image:
    ALPHA_FLOOR = 48.0
    ALPHA_CUTOFF = 40.0
    diff = white_arr - black_arr
    alpha = 255.0 - np.clip(diff.max(axis=2), 0.0, 255.0)
    alpha_safe = np.maximum(alpha, ALPHA_FLOOR)
    color = np.clip(black_arr * 255.0 / alpha_safe[..., None], 0.0, 255.0)
    alpha = np.where(alpha < ALPHA_CUTOFF, 0.0, alpha)
    rgba = np.dstack([color, alpha]).astype(np.uint8)
    return Image.fromarray(rgba, mode="RGBA")


def opaque_rgba_from_black(black_arr: np.ndarray) -> Image.Image:
    alpha = np.full(black_arr.shape[:2], 255.0, dtype=np.float32)
    rgba = np.dstack([black_arr, alpha]).astype(np.uint8)
    return Image.fromarray(rgba, mode="RGBA")


def cleanup_keep_only_deliverables(out_dir: Path):
    for item in out_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        elif item.suffix.lower() != ".mp4" and not item.name.endswith("_alpha.mov"):
            item.unlink(missing_ok=True)


def encode_outputs(rgba_pattern: str, out_dir: Path, name: str, canvas_dim: int):
    mp4_path = out_dir / f"{name}.mp4"
    r1 = subprocess.run([
        FFMPEG_BIN, "-y",
        "-f", "lavfi", "-i", f"color=black:s={canvas_dim}x{canvas_dim}:r={FPS}",
        "-framerate", str(FPS), "-i", rgba_pattern,
        "-filter_complex", "[0:v][1:v]overlay=shortest=1:format=auto,format=yuv420p,pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-crf", "15", "-preset", "slow",
        "-movflags", "+faststart",
        str(mp4_path)
    ], check=False, capture_output=True)
    mp4_ok = mp4_path.exists() and mp4_path.stat().st_size > 1024 and r1.returncode == 0
    if not mp4_ok:
        mp4_path.unlink(missing_ok=True)
        print(f"    [ffmpeg mp4 " + t("エラー", "error") + f"] {name} : {r1.stderr.decode(errors='ignore')[-800:]}")

    mov_ok = False
    if MAKE_ALPHA_MOV:
        mov_path = out_dir / f"{name}_alpha.mov"
        r2 = subprocess.run([
            FFMPEG_BIN, "-y", "-framerate", str(FPS),
            "-i", rgba_pattern,
            "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
            str(mov_path)
        ], check=False, capture_output=True)
        mov_ok = mov_path.exists() and mov_path.stat().st_size > 1024 and r2.returncode == 0
        if not mov_ok:
            mov_path.unlink(missing_ok=True)
            print(f"    [ffmpeg mov " + t("(透過)エラー", "(alpha) error") + f"] {name} : {r2.stderr.decode(errors='ignore')[-800:]}")

    return mp4_ok, mov_ok


def process_batch_result(result: dict, count: int, frame_dir: Path, start_idx: int):
    for k in range(count):
        black_arr = decode_frame_rgb(result["black"][k])
        if MAKE_ALPHA_MOV:
            white_arr = decode_frame_rgb(result["white"][k])
            rgba_img = compose_alpha_from_black_white(black_arr, white_arr)
            del white_arr
        else:
            rgba_img = opaque_rgba_from_black(black_arr)
        rgba_img.save(frame_dir / f"frame_{start_idx + k:04d}.png")
        del black_arr, rgba_img
    del result
    gc.collect()


def render_character(page, char_dir_name, skel_name, atlas_name):
    out_dir = OUTPUT_ROOT / char_dir_name
    harness_path = out_dir / "_harness.html"
    html = (HARNESS_TEMPLATE
            .replace("__SPINE_VERSION__", SPINE_WEBGL_VERSION)
            .replace("__SKEL__", skel_name)
            .replace("__ATLAS__", atlas_name)
            .replace("__DIM__", str(CANVAS_DIM))
            .replace("__MARGIN__", str(MARGIN))
            .replace("__PHYSICS__", PHYSICS_ARG))
    harness_path.write_text(html, encoding="utf-8")

    page.goto(f"http://localhost:{HTTP_PORT}/{char_dir_name}/_harness.html")
    try:
        page.wait_for_function(
            "() => window.ready === true || window.loadError !== null",
            timeout=LOAD_TIMEOUT_MS,
        )
    except Exception:
        load_error = page.evaluate("window.loadError")
        raise RuntimeError(t(f"読み込みタイムアウト({LOAD_TIMEOUT_MS / 1000:.0f}秒)。window.loadError={load_error!r}",
                              f"Load timed out ({LOAD_TIMEOUT_MS / 1000:.0f}s). window.loadError={load_error!r}"))

    load_error = page.evaluate("window.loadError")
    if load_error:
        raise RuntimeError(t(f"読み込み失敗: {load_error}", f"Load failed: {load_error}"))

    anim_names = page.evaluate("window.animNames")
    all_ok = True

    for anim in anim_names:
        duration = page.evaluate("(a) => window.getAnimDuration(a)", anim)
        if not duration or duration <= 0:
            continue
        page.evaluate("([a, s]) => window.fitCameraToAnim(a, s)", [anim, 20])
        n_frames = max(1, int(duration * FPS))
        frame_dir = out_dir / "frames" / anim
        frame_dir.mkdir(parents=True, exist_ok=True)

        idx = 0
        t_start = time.time()
        batch_ranges = [(start, min(BATCH_SIZE, n_frames - start)) for start in range(0, n_frames, BATCH_SIZE)]

        def render_batch(start, count):
            return page.evaluate(
                "([a, s, c, fps, na]) => window.renderFrameBatch(a, s, c, fps, na)",
                [anim, start, count, FPS, MAKE_ALPHA_MOV]
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            pending_process = None
            for start, count in batch_ranges:
                result = render_batch(start, count)
                if pending_process is not None:
                    pending_process.result()
                pending_process = pool.submit(process_batch_result, result, count, frame_dir, start)

                idx = start + count
                elapsed = time.time() - t_start
                pct = idx / n_frames * 100
                eta = (elapsed / idx) * (n_frames - idx) if idx > 0 else 0
                print(t(f"    [進捗] {char_dir_name} / {anim} : {idx}/{n_frames}フレーム "
                        f"({pct:.0f}%) 経過{elapsed:.0f}秒 残り約{eta:.0f}秒",
                        f"    [Progress] {char_dir_name} / {anim} : {idx}/{n_frames} frames "
                        f"({pct:.0f}%) elapsed {elapsed:.0f}s, ETA ~{eta:.0f}s"), flush=True)
            if pending_process is not None:
                pending_process.result()

        print(t(f"[書き出しOK] {char_dir_name} / {anim} : {n_frames}フレーム -> {frame_dir}",
                 f"[Frames OK] {char_dir_name} / {anim} : {n_frames} frames -> {frame_dir}"))

        if MAKE_VIDEO:
            mp4_ok, mov_ok = encode_outputs(
                str(frame_dir / "frame_%04d.png"), out_dir, anim, CANVAS_DIM
            )
            if mp4_ok:
                print(t(f"    動画も書き出し: {out_dir / (anim + '.mp4')}",
                         f"    Video also written: {out_dir / (anim + '.mp4')}")
                      + (f" / {out_dir / (anim + '_alpha.mov')}" if mov_ok else ""))
                shutil.rmtree(frame_dir, ignore_errors=True)
            else:
                print(t(f"    [エラー] {char_dir_name} / {anim} : mp4化に失敗、連番pngのまま残す -> {frame_dir}",
                         f"    [Error] {char_dir_name} / {anim} : mp4 encoding failed, keeping PNG sequence -> {frame_dir}"))
                all_ok = False
        else:
            all_ok = False

    harness_path.unlink(missing_ok=True)

    if all_ok:
        cleanup_keep_only_deliverables(out_dir)
        print(t(f"    [クリーンアップ] {char_dir_name} : mp4/mov以外を削除",
                 f"    [Cleanup] {char_dir_name} : deleted everything except mp4/mov"))
    else:
        print(t(f"    [注意] {char_dir_name} : 一部失敗のため中間ファイルは残す(次回また再挑戦される)",
                 f"    [Note] {char_dir_name} : keeping intermediate files due to a partial failure (will retry next run)"))

    return all_ok


BROWSER_RESTART_EVERY = 2
N_PARALLEL_WORKERS = 2

_manifest_lock = threading.Lock()


def new_browser_and_page(p):
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": CANVAS_DIM, "height": CANVAS_DIM})
    page.on("console", lambda msg: (
        print(t(f"    [ブラウザconsole] {msg.type}: {msg.text}", f"    [Browser console] {msg.type}: {msg.text}"))
        if SHOW_BROWSER_LOGS or msg.type in ("warning", "error")
        else None
    ))
    page.on("pageerror", lambda exc: print(t(f"    [ブラウザpageerror] {exc}", f"    [Browser pageerror] {exc}")))
    return browser, page


def worker_loop(worker_id: int, work_items: list, done_manifest: dict):
    with sync_playwright() as p:
        browser, page = new_browser_and_page(p)
        count = 0
        for char_dir_name, skel_name, atlas_name, manifest_key in work_items:
            if count > 0 and count % BROWSER_RESTART_EVERY == 0:
                print(t(f"    [メンテナンス][worker{worker_id}] {BROWSER_RESTART_EVERY}キャラ処理したのでブラウザを再起動",
                         f"    [Maintenance][worker{worker_id}] processed {BROWSER_RESTART_EVERY} characters, restarting browser"))
                browser.close()
                gc.collect()
                browser, page = new_browser_and_page(p)
            count += 1
            try:
                ok = render_character(page, char_dir_name, skel_name, atlas_name)
                if ok:
                    with _manifest_lock:
                        done_manifest[manifest_key] = {
                            "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        save_done_manifest(done_manifest)
            except Exception as e:
                print(t(f"[エラー][worker{worker_id}] {char_dir_name} : {e}",
                         f"[Error][worker{worker_id}] {char_dir_name} : {e}"))
        browser.close()


def main():
    global LANG, MODE, CONFIG_PATH, SPINE_WEBGL_VERSION, PHYSICS_ARG, FFMPEG_BIN

    LANG = choose_language()
    MODE = choose_mode()

    _ensure_playwright_browser()
    FFMPEG_BIN = _ensure_ffmpeg()

    if MODE == "nte":
        CONFIG_PATH = Path(__file__).resolve().parent / "nte_config.json"
        SPINE_WEBGL_VERSION = "4.2.39"
        PHYSICS_ARG = "spine.Physics.update"
    else:
        CONFIG_PATH = Path(__file__).resolve().parent / "wuwa_config.json"
        SPINE_WEBGL_VERSION = "4.1.*"
        PHYSICS_ARG = ""

    load_or_create_config()
    done_manifest = load_done_manifest()

    entries = extract_all(done_manifest)
    if not entries:
        print(t("変換できるアセットが見つからなかった(または全部処理済み)",
                 "No convertible assets were found (or everything was already processed)"))
        return

    global HTTP_PORT
    HTTP_PORT = get_free_port()
    httpd = serve_output_root(HTTP_PORT)
    try:
        n_workers = max(1, min(N_PARALLEL_WORKERS, len(entries)))
        chunks = [entries[i::n_workers] for i in range(n_workers)]
        print(t(f"{n_workers}並列で処理します({len(entries)}件のアセットを振り分け)",
                 f"Processing with {n_workers} parallel worker(s) ({len(entries)} asset(s) to distribute)"))

        threads = [
            threading.Thread(target=worker_loop, args=(i, chunk, done_manifest))
            for i, chunk in enumerate(chunks)
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
    finally:
        httpd.shutdown()

    print(t(f"\n完了。{OUTPUT_ROOT} 以下に出力した(通常再生用の<アニメ名>.mp4、透過用の<アニメ名>_alpha.mov)。",
             f"\nDone. Output written under {OUTPUT_ROOT} "
             f"(<anim>.mp4 for normal playback, <anim>_alpha.mov for transparent background)."))


if __name__ == "__main__":
    main()