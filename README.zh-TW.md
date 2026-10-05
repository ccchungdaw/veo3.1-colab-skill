# 🎬 Google Veo 3.1 & MiniMax H3 雙核心 Colab 視訊生成技能

這是一個完整、可獨立使用的 AI 視訊生成技能儲存庫，支援 **Gemini CLI**、**Codex** 與 **Antigravity**。

本技能採用**雙模型核心設計**，支援在 Google 頂級多模態模型 **Google Veo 3 / 3.1** 與熱門開源模型 **MiniMax H3 Turbo** 之間無縫切換。同時整合了 **Web 視覺化控制台** 與 **4 大 Colab GPU 後製增強模組（FLUX.1、RIFE 60fps 補幀、Real-ESRGAN 4K 超解析度、CodeFormer 人臉修復）**，讓您的 Colab 算力發揮最大價值！

---

## 🌟 核心特色

1. **雙模型一鍵切換 (Dual-Engine)**：
   - **✨ Google Veo 3 / 3.1**：免高階 GPU（標準 CPU 即可運作），支援文字生影片、首幀/末幀引導、1~3 張參考圖、16:9/9:16 比例，內建**原生同步對齊音訊與音效**。
   - **🚀 MiniMax H3 Turbo**：需 A100 GPU，支援 1~9 張高語意參考圖（Ref2VA 格式 `<Picture 1>`~`<Picture 9>`）與中文口白分鏡。
2. **4 大 Colab GPU 增強處理模組 (ComfyUI / PyTorch Pipeline)**：
   - 🖼️ **FLUX.1 (Dev/Schnell) 首幀前製生成**：先在 GPU 生成超高細節首幀圖，再轉成視訊。
   - 👤 **CodeFormer 人臉逐幀修復**：自動修復視訊中人物臉部失真與模糊。
   - 🔍 **Real-ESRGAN 4K 超解析度**：將 720p/1080p 升頻至極致 4K 銳利畫質。
   - ⚡ **RIFE V4.6 AI 補幀**：將原生 24fps 平滑升級至 60fps 電影高幀率。
3. **現代深色系 Web 控制台**：零外部套件依賴，即開即用，支援動態選項切換、終端 Log 即時串流監控與視訊直接播放預覽。
4. **完整生命週期管理**：Colab Session 自動啟動與清理，批次任務支援進度斷點紀錄 (`progress.json`)。

---

## 📦 儲存庫結構

```text
veo3.1-colab/
├── SKILL.md                          # Gemini CLI / Codex / Antigravity 技能定義檔
├── install.ps1                       # Windows 原生 PowerShell 安裝腳本
├── install.sh                        # macOS / Linux Bash 安裝腳本
├── run_colab_inference.ps1           # Windows 單支推論快捷啟動器
├── run_colab_inference.sh            # Linux / macOS 單支推論快捷啟動器
├── scripts/
│   ├── web_ui.py                     # 視覺化 Web 控制台伺服器 (Port 7860)
│   ├── runner.py                     # 核心任務排程器 (Session 管理、批次處理、MP4 檢驗)
│   └── patch_colab_cli.py            # Windows 平台 google-colab-cli 相容性修正
├── assets/
│   ├── Veo_3_1_Colab.ipynb           # Veo 3 雲端推論與 4 大增強處理 Notebook
│   ├── MiniMax_H3_Turbo_Colab.ipynb  # MiniMax H3 ComfyUI 本地推論 Notebook
│   └── inputs/
│       ├── sample_prompt.txt         # 範例提示詞
│       └── sample_jobs.json          # 範例批次清單
├── tests/
│   └── test_runner.py                # 單元測試套件 (Mock Colab CLI，不耗費點數)
├── .gitignore
├── LICENSE                           # MIT 授權條款
├── README.md                         # 英文說明文件
└── README.zh-TW.md                   # 繁體中文說明文件
```

---

## 🛠️ 第一步：環境前置準備

在安裝與使用前，請確保完成以下三項基本設定：

### 1. 安裝 Google Colab CLI
使用 [`uv`](https://docs.astral.sh/uv/) 工具安裝 Colab 命令列工具：
```bash
uv tool install google-colab-cli
```

### 2. 授權 Colab 帳號
第一次執行需進行 Google OAuth2 授權（並查詢帳戶剩餘運算單元）：
```bash
colab --auth=oauth2 usage
```
依照畫面提示在瀏覽器登入即可。

### 3. 設定 Gemini API Key (Veo 3 使用)
在終端機設定您的 API 金鑰（可從 [Google AI Studio](https://aistudio.google.com/) 免費取得）：
- **Windows (PowerShell)**：
  ```powershell
  $env:GEMINI_API_KEY = "你的_API_KEY"
  ```
- **macOS / Linux (Bash)**：
  ```bash
  export GEMINI_API_KEY="你的_API_KEY"
  ```

---

## 📥 第二步：技能安裝 (Install Skills)

您可以將本技能安裝至 **Gemini CLI** 或 **Codex** 的全域技能目錄中：

### Windows (PowerShell)
```powershell
# 預設安裝至 Gemini CLI (~/.gemini/skills/veo3.1-colab)
.\install.ps1

# 安裝至 Codex (~/.codex/skills/veo3.1-colab)
.\install.ps1 -Codex

# 同時安裝至 Gemini CLI 與 Codex
.\install.ps1 -All

# 若已有舊安裝想強制覆蓋更新 (舊目錄會自動備份)：
.\install.ps1 -Force
```

### macOS / Linux (Bash)
```bash
chmod +x install.sh run_colab_inference.sh
./install.sh            # 預設安裝至 Gemini CLI
./install.sh --codex    # 安裝至 Codex
./install.sh --all      # 同時安裝至兩者
./install.sh --force    # 強制覆蓋更新
```

安裝完成後，在 Gemini CLI、Codex 或 Antigravity 中開啟新的對話，系統便會自動辨識並載入 `veo3.1-colab` 技能！

---

## 🖥️ 第三步：啟動視覺化操作介面 (Web UI)

本專案內建純 Python 標準函式庫驅動的視覺化 Web 控制台，**不需額外安裝 gradio、flask 或額外依賴**！

### 啟動指令：
```powershell
python scripts/web_ui.py
```

終端機會顯示：
```text
=======================================================
🎬 AI 視訊控制中心 (Veo 3 & MiniMax H3 雙核心)
網頁伺服器已啟動: http://127.0.0.1:7860
請在瀏覽器開啟上述網址進行可視化操作
=======================================================
```

### 操作說明：
1. **開啟瀏覽器**：造訪 `http://127.0.0.1:7860`。
2. **切換模型 (Model Tabs)**：
   - 點擊 **`Google Veo 3 / 3.1`**：表單即時呈現解析度 (720p/1080p/4K)、比例 (16:9/9:16)、秒數 (5~8s)、首末幀欄位與負向提示詞。
   - 點擊 **`MiniMax H3 Turbo`**：表單即時切換為 Ref2VA / FL2VA 模式、1~9 張參考圖槽位、秒數 (4~15s) 與 Seed 設定。
3. **勾選 Colab GPU 增強模組**：
   - 自由勾選 `⚡ RIFE 60fps 補幀`、`🔍 Real-ESRGAN 4K`、`👤 CodeFormer 人臉修復` 或 `🖼️ FLUX.1 首幀生成`。
4. **查詢與生成**：
   - 點擊右上角「⚡ 查詢 Colab 餘額」檢視即時點數。
   - 點擊「🚀 啟動 Colab 視訊推論任務」。
   - 右側將即時串流終端 Log，生成完成後自動載入視訊播放器並提供下載。

---

## 💻 第四步：命令列推論指南 (CLI Usage)

若您習慣使用命令列或自動化腳本，可以直接使用 `scripts/runner.py`：

### 1. 單支影片生成 (`single`)

#### 範例 A：純 Veo 3 生成（最節省點數，免 GPU）
```powershell
python scripts/runner.py single `
  -e veo `
  -m veo-3-fast `
  -p "Cinematic shot of a snow leopard perched on a Himalayan mountain ridge at sunrise, photorealistic." `
  -a 16:9 `
  -r 1080p `
  -d 5 `
  -o ./snow_leopard.mp4
```

#### 範例 B：Veo 3 + 4 大 GPU 增強模組全開（消耗 Colab 運算單元）
```powershell
python scripts/runner.py single `
  -e veo `
  -p "Cyberpunk warrior standing on a neon skyscraper in heavy rain" `
  --flux-prompt "Masterpiece portrait of cyberpunk warrior, highly detailed, 8k" `
  --face-restore `
  --interpolate 60 `
  --upscale 4k `
  --gpu A100 `
  -o ./cyberpunk_master.mp4
```

#### 範例 C：MiniMax H3 參照圖生成（開源模型）
```powershell
python scripts/runner.py single `
  -e minimax `
  -i "C:/images/character_front.png" `
  -i "C:/images/character_side.png" `
  -p "A cinematic shot of the character in <Picture 1> walking down the street." `
  -d 12 `
  --gpu A100 `
  -o ./minimax_scene.mp4
```

---

### 2. 批次佇列生成 (`batch`)

將多個視訊工作寫入 JSON 清單（如 `jobs.json`）：

```json
{
  "jobs": [
    {
      "id": "scene_01",
      "engine": "veo",
      "title": "Opening Cinema",
      "prompt": "Cinematic shot of hero standing on mountain cliff at dawn.",
      "model": "veo-3.1-fast-generate-preview",
      "duration_seconds": 5,
      "aspect_ratio": "16:9",
      "resolution": "1080p",
      "interpolate": "60",
      "upscale": "4k",
      "output_name": "scene_01"
    },
    {
      "id": "scene_02",
      "engine": "minimax",
      "title": "Character Action",
      "reference_images": ["C:/images/hero.png"],
      "prompt": "The warrior in <Picture 1> draws a glowing sword.",
      "duration_seconds": 8,
      "output_name": "scene_02"
    }
  ]
}
```

執行批次任務：
```powershell
python scripts/runner.py batch `
  --manifest ./jobs.json `
  --output-dir ./outputs `
  --progress ./outputs/progress.json
```
- 所有任務共用同一個 Colab Session，避免反覆開關 VM。
- 即時將進度寫入 `progress.json`，即使中途失敗，已下載的影片仍會完整保留。
- 批次結束後自動終止 Session，絕不佔用額外背景時間。

---

## 📋 參數對照一覽表

| 參數 | 縮寫 | 可選值 | 說明 |
| :--- | :--- | :--- | :--- |
| `--engine` | `-e` | `veo`, `minimax` | 切換視訊生成引擎（預設: `veo`） |
| `--prompt` | `-p` | 字串或文字檔路徑 | 核心生成提示詞（必要） |
| `--model` | `-m` | `veo-3-fast`, `veo-3-generate`, `veo-3-lite` | Veo 模型版本（亦支援全名） |
| `--duration` | `-d` | `5~8` (Veo), `4~15` (MiniMax) | 影片長度（秒） |
| `--aspect-ratio` | `-a` | `16:9`, `9:16` | 畫面比例（橫向電影 / 直式短影音） |
| `--resolution` | `-r` | `720p`, `1080p`, `4k` | 輸出解析度 |
| `--image` | `-i` | 圖片路徑（可重複傳入） | 參考圖片（Veo 上限 3 張，MiniMax 上限 9 張） |
| `--first-frame` | | 圖片路徑 | 首幀引導圖 (Image-to-Video) |
| `--last-frame` | | 圖片路徑 | 末幀引導圖（首末幀內插過渡） |
| `--flux-prompt` | | 提示詞字串 | 啟用 **FLUX.1 前製生成** 首幀圖 |
| `--face-restore` | | 旗標 (無須帶值) | 啟用 **CodeFormer 人臉逐幀修復** |
| `--upscale` | | `none`, `2x`, `4k`, `4x` | 啟用 **Real-ESRGAN 超解析度升頻** |
| `--interpolate` | | `none`, `48`, `60`, `120` | 啟用 **RIFE AI 補幀** 至指定 FPS |
| `--gpu` | | `none`, `T4`, `L4`, `A100` | 指定 Colab 運算硬體（純 Veo 建議 `none`，開源/增強建議 `A100`） |
| `--output` | `-o` | 輸出檔案路徑 | 指定 MP4 輸出檔名 |

---

## 🧪 執行單元測試

儲存庫自帶完整單元測試，透過 Mock Colab CLI 模擬所有指令，**完全不耗用真實 API 額度或 Colab 點數**：

```powershell
python -m unittest tests/test_runner.py
```
預期輸出：
```text
....
----------------------------------------------------------------------
Ran 4 tests in 5.25s
OK
```

---

## 📄 授權條款

本專案採用 [MIT License](file:///d:/workspace/SKILLS/veo3.1-colab/LICENSE) 開源授權。
