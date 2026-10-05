# 🎬 Google Veo 3.1 & MiniMax H3 Colab Video Generation Skill

A standalone, production-ready AI video generation skill repository for **Gemini CLI**, **Codex**, and **Antigravity**.

Built on a **dual-engine architecture**, this skill enables seamless switching between Google's state-of-the-art **Google Veo 3 / 3.1** and the open-weights **MiniMax H3 Turbo**. It features a **zero-dependency modern Web Control Panel** and **4 Colab GPU post-processing enhancement modules (FLUX.1, RIFE 60fps, Real-ESRGAN 4K, CodeFormer face restoration)** to make maximum use of your Colab compute resources.

---

## 🌟 Key Highlights

1. **Dual-Engine Instant Switch**:
   - **✨ Google Veo 3 / 3.1**: No heavy GPU required (runs on standard CPU runtime to save compute units), native synchronized audio and dialogue, 16:9/9:16 aspect ratios, 720p/1080p/4K resolution, 1~3 reference images or first/last frames.
   - **🚀 MiniMax H3 Turbo**: Self-hosted on Colab A100 GPU with ComfyUI, supporting 1~9 reference images (Ref2VA `<Picture 1>`~`<Picture 9>`) and 4~15s durations.
2. **4 Colab GPU Enhancement Modules (ComfyUI / PyTorch Pipeline)**:
   - 🖼️ **FLUX.1 (Dev/Schnell) First-Frame Pre-generation**: Generate ultra-detailed starting frames directly on the Colab GPU before video synthesis.
   - 👤 **CodeFormer Face Restoration**: Frame-by-frame AI face and facial detail enhancement.
   - 🔍 **Real-ESRGAN 4K Super-Resolution**: Upscale 720p/1080p videos to crisp 4K/8K.
   - ⚡ **RIFE V4.6 Frame Interpolation**: Boost native 24fps video to smooth 60fps cinema high-frame-rate.
3. **Responsive Web Control Panel**: Runs with standard Python (`http.server`), dynamic model switching, live terminal log streaming, and video preview player.
4. **Automated Lifecycle Management**: Automatic Colab session startup and shutdown, with resumable progress tracking (`progress.json`).

---

## 📦 Directory Structure

```text
veo3.1-colab/
├── SKILL.md                          # Skill definition for Gemini CLI / Codex / Antigravity
├── install.ps1                       # Windows PowerShell installer
├── install.sh                        # macOS / Linux Bash installer
├── run_colab_inference.ps1           # Single video PowerShell launcher
├── run_colab_inference.sh            # Single video Bash launcher
├── scripts/
│   ├── web_ui.py                     # Web Control Panel (Port 7860)
│   ├── runner.py                     # Core task runner (Session management, batch queue, verification)
│   └── patch_colab_cli.py            # Windows compatibility patch for google-colab-cli
├── assets/
│   ├── Veo_3_1_Colab.ipynb           # Veo 3 remote inference & 4 enhancement modules notebook
│   ├── MiniMax_H3_Turbo_Colab.ipynb  # MiniMax H3 ComfyUI inference notebook
│   └── inputs/
│       ├── sample_prompt.txt         # Sample prompt text
│       └── sample_jobs.json          # Sample batch manifest
├── tests/
│   └── test_runner.py                # Unit test suite (Mock Colab CLI)
├── .gitignore
├── LICENSE                           # MIT License
├── README.md                         # English documentation
└── README.zh-TW.md                   # Traditional Chinese documentation
```

---

## 🛠️ Step 1: Prerequisites

1. **Install Colab CLI**:
   ```bash
   uv tool install google-colab-cli
   ```
2. **Authenticate Colab**:
   ```bash
   colab --auth=oauth2 usage
   ```
3. **Set Gemini API Key (for Veo 3)**:
   - **Windows (PowerShell)**:
     ```powershell
     $env:GEMINI_API_KEY = "your_api_key_here"
     ```
   - **macOS / Linux (Bash)**:
     ```bash
     export GEMINI_API_KEY="your_api_key_here"
     ```

---

## 📥 Step 2: Install the Skill

Install this skill into your global Gemini CLI or Codex skills directory:

### Windows (PowerShell)
```powershell
.\install.ps1           # Install to Gemini CLI (~/.gemini/skills/veo3.1-colab)
.\install.ps1 -Codex    # Install to Codex (~/.codex/skills/veo3.1-colab)
.\install.ps1 -All      # Install to both
.\install.ps1 -Force    # Force overwrite existing installation with backup
```

### macOS / Linux (Bash)
```bash
chmod +x install.sh run_colab_inference.sh
./install.sh            # Install to Gemini CLI
./install.sh --codex    # Install to Codex
./install.sh --all      # Install to both
./install.sh --force    # Force overwrite
```

---

## 🖥️ Step 3: Launch the Web Control Panel (Web UI)

Run the built-in, zero-dependency Web UI:

```powershell
python scripts/web_ui.py
```

Open your browser at: **`http://127.0.0.1:7860`**

### Features:
- **Instant Model Switching**: Toggle between **Google Veo 3** and **MiniMax H3 Turbo** with dynamic form update.
- **Enhancement Checkboxes**: Toggle RIFE 60fps, Real-ESRGAN 4K, CodeFormer face restoration, and FLUX.1 first-frame pre-generation.
- **Colab Balance Check**: Query your compute units in one click.
- **Live Terminal Logs**: Real-time streaming of Colab execution.
- **Integrated Video Player**: Direct playback and download upon completion.

---

## 💻 Step 4: CLI & Batch Usage

### 1. Single Video Generation (`single`)

#### Pure Veo 3 (Saves Compute Units, CPU Runtime):
```powershell
python scripts/runner.py single `
  -e veo `
  -m veo-3-fast `
  -p "Cinematic shot of a snow leopard perched on a Himalayan mountain ridge at sunrise" `
  -a 16:9 `
  -r 1080p `
  -d 5 `
  -o ./snow_leopard.mp4
```

#### Veo 3 with All 4 GPU Enhancements:
```powershell
python scripts/runner.py single `
  -e veo `
  -p "Cyberpunk female warrior standing on a skyscraper in heavy rain" `
  --flux-prompt "Masterpiece portrait of cyberpunk female warrior, neon lighting, 8k" `
  --face-restore `
  --interpolate 60 `
  --upscale 4k `
  --gpu A100 `
  -o ./cyberpunk_master.mp4
```

#### MiniMax H3 Reference Generation:
```powershell
python scripts/runner.py single `
  -e minimax `
  -i "C:/images/hero.png" `
  -p "The hero in <Picture 1> walking down a neon street." `
  -d 12 `
  --gpu A100 `
  -o ./minimax_scene.mp4
```

### 2. Batch Manifest (`batch`)

```powershell
python scripts/runner.py batch `
  --manifest ./assets/inputs/sample_jobs.json `
  --output-dir ./outputs `
  --progress ./outputs/progress.json
```

---

## 📋 Parameter Reference

| Parameter | Short | Values | Description |
| :--- | :--- | :--- | :--- |
| `--engine` | `-e` | `veo`, `minimax` | Video generation engine (default: `veo`) |
| `--prompt` | `-p` | string or text file | Video prompt text (required) |
| `--model` | `-m` | `veo-3-fast`, `veo-3-generate`, `veo-3-lite` | Model variant |
| `--duration` | `-d` | `5~8` (Veo), `4~15` (MiniMax) | Video duration in seconds |
| `--aspect-ratio` | `-a` | `16:9`, `9:16` | Aspect ratio |
| `--resolution` | `-r` | `720p`, `1080p`, `4k` | Output resolution |
| `--image` | `-i` | image paths | Reference image (repeatable) |
| `--first-frame` | | image path | First frame (Image-to-Video) |
| `--last-frame` | | image path | Last frame (Frame interpolation) |
| `--flux-prompt` | | prompt string | Pre-generate first frame with **FLUX.1** |
| `--face-restore` | | flag | Enable **CodeFormer** face restoration |
| `--upscale` | | `none`, `2x`, `4k`, `4x` | Enable **Real-ESRGAN** super-resolution |
| `--interpolate` | | `none`, `48`, `60`, `120` | Enable **RIFE AI** frame interpolation |
| `--gpu` | | `none`, `T4`, `L4`, `A100` | Colab GPU hardware |
| `--output` | `-o` | filepath | Output MP4 path |

---

## 🧪 Testing

Run the test suite with simulated Colab CLI (zero API or compute consumption):
```powershell
python -m unittest tests/test_runner.py
```

---

## 📄 License

This project is licensed under the [MIT License](file:///d:/workspace/SKILLS/veo3.1-colab/LICENSE).
