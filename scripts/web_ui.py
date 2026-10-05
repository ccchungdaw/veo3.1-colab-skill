#!/usr/bin/env python3
"""Local Web Control Panel for Google Veo 3 & MiniMax H3 Colab Video Generation."""

import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

PORT = 7860
SKILL_DIR = Path(__file__).resolve().parents[1]
RUNNER_SCRIPT = SKILL_DIR / "scripts" / "runner.py"

active_task = {
    "status": "idle",  # idle, running, completed, failed
    "logs": [],
    "output_file": None,
    "error": None,
    "started_at": None,
}


HTML_CONTENT = """<!DOCTYPE html>
<html lang="zh-TW" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI 視訊生成控制中心 - Veo 3 & MiniMax H3</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8' },
            accent: { 500: '#8b5cf6', 600: '#7c3aed' }
          }
        }
      }
    }
  </script>
  <style>
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #18181b; }
    ::-webkit-scrollbar-thumb { background: #3f3f46; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #52525b; }
  </style>
</head>
<body class="bg-zinc-950 text-zinc-100 min-h-screen font-sans antialiased selection:bg-brand-500 selection:text-white">

  <!-- Header -->
  <header class="border-b border-zinc-800 bg-zinc-900/60 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-accent-600 flex items-center justify-center font-bold text-xl shadow-lg shadow-brand-500/20">
          🎬
        </div>
        <div>
          <h1 class="text-lg font-bold bg-gradient-to-r from-white via-zinc-200 to-zinc-400 bg-clip-text text-transparent">AI 視訊生成控制中心</h1>
          <p class="text-xs text-zinc-400">Google Veo 3.1 & MiniMax H3 雙核心 Colab Skill</p>
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <!-- API Key 輸入區 (自動保存至瀏覽器) -->
        <div class="flex items-center space-x-2 bg-zinc-950/80 border border-zinc-800 rounded-xl px-3 py-1.5 focus-within:border-brand-500 transition shadow-inner">
          <span class="text-xs text-amber-400 font-medium">🔑 API Key:</span>
          <input id="api-key-input" type="password" oninput="saveApiKey()" placeholder="貼上 Gemini API Key..." class="bg-transparent text-xs text-zinc-200 focus:outline-none w-48 font-mono">
          <button type="button" onclick="toggleApiKeyVisibility()" class="text-zinc-500 hover:text-zinc-300 text-xs px-1" title="顯示/隱藏金鑰">👁️</button>
        </div>

        <!-- 查詢餘額按鈕 -->
        <button id="btn-check-balance" onclick="checkBalance()" class="text-xs px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 transition flex items-center space-x-1.5 shadow-sm">
          <span>⚡ 查詢 Colab 餘額</span>
          <span id="balance-badge" class="hidden text-brand-400 font-mono font-bold"></span>
        </button>
      </div>
    </div>
  </header>

  <!-- 提示模態框 (Modal for Colab CLI help) -->
  <div id="colab-help-modal" class="hidden fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
      <div class="flex items-center justify-between border-b border-zinc-800 pb-3">
        <h3 class="font-bold text-amber-400 flex items-center space-x-2">
          <span>⚠️</span>
          <span>Colab 餘額讀取狀態</span>
        </h3>
        <button onclick="closeColabModal()" class="text-zinc-400 hover:text-white text-sm">✕</button>
      </div>
      <div id="colab-modal-content" class="text-xs text-zinc-300 space-y-3 leading-relaxed">
        <!-- 動態填入說明 -->
      </div>
      <div class="pt-2 flex justify-end">
        <button onclick="closeColabModal()" class="px-4 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium">我知道了</button>
      </div>
    </div>
  </div>

  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">

      <!-- 左側：參數配置面版 (7 欄) -->
      <div class="lg:col-span-7 space-y-6">

        <!-- 模型切換 Tabs -->
        <div class="bg-zinc-900 border border-zinc-800 rounded-2xl p-2 flex space-x-2 shadow-xl">
          <button id="tab-veo" onclick="switchModel('veo')" class="flex-1 py-3 px-4 rounded-xl font-medium text-sm transition flex items-center justify-center space-x-2 bg-gradient-to-r from-brand-600 to-blue-700 text-white shadow-lg shadow-brand-500/20">
            <span>✨ Google Veo 3 / 3.1</span>
            <span class="text-xs px-2 py-0.5 rounded-full bg-blue-900/60 text-blue-200 border border-blue-400/30">原生音訊・4K</span>
          </button>
          <button id="tab-minimax" onclick="switchModel('minimax')" class="flex-1 py-3 px-4 rounded-xl font-medium text-sm transition flex items-center justify-center space-x-2 text-zinc-400 hover:text-white hover:bg-zinc-800/60">
            <span>🚀 MiniMax H3 Turbo</span>
            <span class="text-xs px-2 py-0.5 rounded-full bg-purple-900/60 text-purple-200 border border-purple-400/30">1~9圖引導・A100</span>
          </button>
        </div>

        <!-- 提示詞面板 -->
        <div class="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center space-x-2">
              <span>✍️ 核心生成提示詞 (Prompt)</span>
            </h2>
            <span id="prompt-hint" class="text-xs text-brand-400">支援運鏡、光影與原生聲音描述</span>
          </div>
          <textarea id="prompt-input" rows="4" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-sm focus:outline-none focus:border-brand-500 transition text-zinc-200" placeholder="例如：Cinematic 4k shot of a snow leopard perched on a Himalayan mountain ridge at sunrise, cold wind blowing, photorealistic, synchronized atmospheric soundscape."></textarea>

          <!-- 負向提示詞 (Veo 專用) -->
          <div id="veo-negative-box" class="space-y-1">
            <label class="text-xs text-zinc-400">負向提示詞 (Negative Prompt)</label>
            <input id="negative-prompt-input" type="text" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-brand-500 transition text-zinc-300" value="blurry, low quality, distorted, watermark, jittery">
          </div>
        </div>

        <!-- 動態模型選項：Veo 3 特有選項 -->
        <div id="veo-options-panel" class="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-5">
          <div class="flex items-center justify-between border-b border-zinc-800 pb-3">
            <h2 class="text-sm font-semibold uppercase tracking-wider text-blue-400">⚙️ Veo 3 專屬參數</h2>
            <div class="flex items-center space-x-2">
              <span id="api-status-badge" class="text-[11px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">金鑰檢查中...</span>
              <span class="text-xs px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800">✅ 免 GPU 點數</span>
            </div>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-medium text-zinc-400 mb-1.5">模型等級</label>
              <select id="veo-model-select" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-brand-500">
                <option value="veo-3.1-generate-preview">Veo 3 Generate (最高畫質旗艦)</option>
                <option value="veo-3.1-fast-generate-preview" selected>Veo 3 Fast Generate (快速平衡・每日50次免費)</option>
                <option value="veo-3.1-lite-generate-preview">Veo 3 Lite Generate (輕量高輸送量)</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-medium text-zinc-400 mb-1.5">畫面比例</label>
              <select id="veo-aspect-select" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-brand-500">
                <option value="16:9" selected>16:9 橫向電影螢幕 (Landscape)</option>
                <option value="9:16">9:16 直式短影音 (Reels / TikTok / Shorts)</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-medium text-zinc-400 mb-1.5">解析度</label>
              <select id="veo-res-select" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-brand-500">
                <option value="720p">720p HD</option>
                <option value="1080p" selected>1080p Full HD</option>
                <option value="4k">4K Ultra HD</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-medium text-zinc-400 mb-1.5">秒數長度</label>
              <select id="veo-duration-select" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-brand-500">
                <option value="4">4 秒</option>
                <option value="6" selected>6 秒 (預設流暢)</option>
                <option value="8">8 秒 (最大標準長度)</option>
              </select>
            </div>
          </div>

          <!-- 圖片引導 (I2V / 參考圖) -->
          <div class="border-t border-zinc-800/80 pt-4 space-y-3">
            <label class="block text-xs font-medium text-zinc-400">圖片引導模式 (可選)</label>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="text-[11px] text-zinc-400">首幀圖片路徑 (First Frame)</label>
                <input id="veo-first-frame" type="text" placeholder="例如：C:/images/hero.png" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-brand-500">
              </div>
              <div>
                <label class="text-[11px] text-zinc-400">末幀圖片路徑 (Last Frame 內插)</label>
                <input id="veo-last-frame" type="text" placeholder="例如：C:/images/end.png" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-brand-500">
              </div>
            </div>
          </div>
        </div>

        <!-- 動態模型選項：MiniMax H3 特有選項 (預設隱藏) -->
        <div id="minimax-options-panel" class="hidden bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-5">
          <div class="flex items-center justify-between border-b border-zinc-800 pb-3">
            <h2 class="text-sm font-semibold uppercase tracking-wider text-purple-400">⚙️ MiniMax H3 專屬參數</h2>
            <span class="text-xs px-2 py-0.5 rounded bg-purple-950/80 text-purple-300 border border-purple-800">⚡ 需 A100 GPU (ComfyUI)</span>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-medium text-zinc-400 mb-1.5">推論模式</label>
              <select id="minimax-mode-select" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-accent-500">
                <option value="reference" selected>Ref2VA (多參考圖語意引導)</option>
                <option value="first_frame">FL2VA (第一幀首圖引導)</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-zinc-400 mb-1.5">影片長度 (秒)</label>
              <input id="minimax-duration" type="number" min="4" max="15" value="12" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-accent-500">
            </div>
            <div>
              <label class="block text-xs font-medium text-zinc-400 mb-1.5">隨機種子碼 (Seed)</label>
              <input id="minimax-seed" type="text" placeholder="留空則隨機生成" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-accent-500">
            </div>
            <div>
              <label class="block text-xs font-medium text-zinc-400 mb-1.5">權重精度 (依 GPU 自動挑選)</label>
              <input type="text" value="Auto (INT8 / FP8 / BF16)" disabled class="w-full bg-zinc-950/50 border border-zinc-800/50 rounded-xl p-2.5 text-xs text-zinc-500">
            </div>
          </div>

          <!-- 參考圖路徑 (1~9張) -->
          <div class="space-y-2 pt-2 border-t border-zinc-800">
            <label class="block text-xs font-medium text-zinc-400">參考圖片路徑 (逗號分隔，對應 &lt;Picture 1&gt; ~ &lt;Picture 9&gt;)</label>
            <input id="minimax-images" type="text" placeholder="C:/images/img1.png, C:/images/img2.jpg" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-accent-500">
          </div>
        </div>

        <!-- 🚀 4 大 Colab GPU 增強處理模組 (ComfyUI / PyTorch Pipeline) -->
        <div class="bg-gradient-to-b from-zinc-900 to-zinc-900/90 border border-indigo-950/60 rounded-2xl p-6 shadow-xl space-y-4">
          <div class="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div class="flex items-center space-x-2">
              <span class="text-lg">🔥</span>
              <h2 class="text-sm font-semibold uppercase tracking-wider text-indigo-400">Colab GPU 增強處理模組 (消耗 200 點好幫手)</h2>
            </div>
            <span class="text-[11px] text-zinc-400">整合 ComfyUI 後製技術</span>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">

            <!-- 1. RIFE 補幀 -->
            <label class="flex items-start space-x-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 hover:border-indigo-600/50 cursor-pointer transition">
              <input id="chk-interpolate" type="checkbox" class="mt-1 w-4 h-4 rounded text-brand-500 focus:ring-0 bg-zinc-900 border-zinc-700">
              <div>
                <span class="text-xs font-bold text-zinc-200 block">⚡ RIFE V4.6 AI 補幀 (60fps)</span>
                <span class="text-[11px] text-zinc-400">將原生 24fps 流暢平滑化至 60fps 電影高幀率</span>
              </div>
            </label>

            <!-- 2. Real-ESRGAN 超解析度 -->
            <label class="flex items-start space-x-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 hover:border-indigo-600/50 cursor-pointer transition">
              <input id="chk-upscale" type="checkbox" class="mt-1 w-4 h-4 rounded text-brand-500 focus:ring-0 bg-zinc-900 border-zinc-700">
              <div>
                <span class="text-xs font-bold text-zinc-200 block">🔍 Real-ESRGAN 4K 超解析度</span>
                <span class="text-[11px] text-zinc-400">逐幀 AI 升頻銳化，細節放大升至 4K/8K</span>
              </div>
            </label>

            <!-- 3. CodeFormer 人臉修復 -->
            <label class="flex items-start space-x-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 hover:border-indigo-600/50 cursor-pointer transition">
              <input id="chk-face-restore" type="checkbox" class="mt-1 w-4 h-4 rounded text-brand-500 focus:ring-0 bg-zinc-900 border-zinc-700">
              <div>
                <span class="text-xs font-bold text-zinc-200 block">👤 CodeFormer 人臉逐幀修復</span>
                <span class="text-[11px] text-zinc-400">自動追蹤視訊人物面孔，修復五官失真瑕疵</span>
              </div>
            </label>

            <!-- 4. FLUX.1 前製首幀 -->
            <label class="flex items-start space-x-3 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 hover:border-indigo-600/50 cursor-pointer transition">
              <input id="chk-flux" type="checkbox" onchange="toggleFluxPrompt()" class="mt-1 w-4 h-4 rounded text-brand-500 focus:ring-0 bg-zinc-900 border-zinc-700">
              <div>
                <span class="text-xs font-bold text-zinc-200 block">🖼️ FLUX.1 前製首幀生成</span>
                <span class="text-[11px] text-zinc-400">先在 Colab 產出極致人物首圖，再轉成視訊</span>
              </div>
            </label>
          </div>

          <!-- FLUX 提示詞輸入 (可選展延) -->
          <div id="flux-prompt-box" class="hidden pt-2">
            <label class="block text-xs font-medium text-indigo-300 mb-1">FLUX.1 專用提示詞 (若留空則沿用主提示詞)</label>
            <input id="flux-prompt-input" type="text" placeholder="例如：Ultra-high detail 8k portrait of cyberpunk warrior..." class="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-indigo-500">
          </div>
        </div>

        <!-- 提交生成按鈕 -->
        <button id="btn-submit" onclick="submitInference()" class="w-full py-4 rounded-xl font-bold text-sm bg-gradient-to-r from-brand-600 via-blue-600 to-accent-600 hover:opacity-95 transition shadow-xl shadow-brand-500/25 flex items-center justify-center space-x-2 text-white">
          <span>🚀 啟動視訊推論任務</span>
        </button>

      </div>

      <!-- 右側：即時狀態與輸出監視器 (5 欄) -->
      <div class="lg:col-span-5 space-y-6">

        <!-- 輸出預覽面板 -->
        <div class="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-semibold uppercase tracking-wider text-zinc-400">📺 成品視訊預覽</h2>
            <span id="task-badge" class="text-xs px-2.5 py-0.5 rounded-full bg-zinc-800 text-zinc-400 font-mono">IDLE</span>
          </div>

          <div id="video-container" class="aspect-video w-full rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-center overflow-hidden relative">
            <div id="video-placeholder" class="text-center p-6 text-zinc-500 space-y-2">
              <span class="text-3xl block">📼</span>
              <p class="text-xs">尚未有生成影片，執行完成後將在此自動播放與下載</p>
            </div>
            <video id="video-player" controls class="hidden w-full h-full object-contain"></video>
          </div>

          <div id="download-box" class="hidden flex items-center justify-between pt-2">
            <span id="output-filepath" class="text-xs font-mono text-zinc-400 truncate max-w-[240px]"></span>
            <a id="btn-download" href="#" download class="text-xs px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-medium transition">💾 下載 MP4</a>
          </div>
        </div>

        <!-- 即時終端紀錄 (Live Terminal Log) -->
        <div class="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-3">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center space-x-2">
              <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>即時終端輸出 (Log)</span>
            </h2>
            <button onclick="clearLogs()" class="text-[11px] text-zinc-500 hover:text-zinc-300">清空</button>
          </div>
          <div id="terminal-box" class="h-80 bg-zinc-950 border border-zinc-800 rounded-xl p-3 font-mono text-[11px] text-zinc-300 overflow-y-auto space-y-1 select-text">
            <div class="text-zinc-500">等待執行指令...</div>
          </div>
        </div>

      </div>

    </div>
  </main>

  <script>
    let currentModel = 'veo';
    let pollInterval = null;

    // 頁面載入時初始化 API Key
    document.addEventListener('DOMContentLoaded', () => {
      const savedKey = localStorage.getItem('gemini_api_key') || '';
      if (savedKey) {
        document.getElementById('api-key-input').value = savedKey;
      }
      updateKeyStatus();
    });

    function saveApiKey() {
      const val = document.getElementById('api-key-input').value.trim();
      localStorage.setItem('gemini_api_key', val);
      updateKeyStatus();
    }

    function toggleApiKeyVisibility() {
      const input = document.getElementById('api-key-input');
      input.type = input.type === 'password' ? 'text' : 'password';
    }

    function updateKeyStatus() {
      const key = document.getElementById('api-key-input').value.trim();
      const badge = document.getElementById('api-status-badge');
      if (key) {
        badge.className = "text-[11px] px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800";
        badge.textContent = "API Key 已填寫 ✅";
      } else {
        badge.className = "text-[11px] px-2 py-0.5 rounded bg-amber-950/80 text-amber-400 border border-amber-800";
        badge.textContent = "未填 API Key ⚠️";
      }
    }

    function switchModel(model) {
      currentModel = model;
      const tabVeo = document.getElementById('tab-veo');
      const tabMini = document.getElementById('tab-minimax');
      const veoPanel = document.getElementById('veo-options-panel');
      const miniPanel = document.getElementById('minimax-options-panel');
      const veoNegBox = document.getElementById('veo-negative-box');

      if (model === 'veo') {
        tabVeo.className = "flex-1 py-3 px-4 rounded-xl font-medium text-sm transition flex items-center justify-center space-x-2 bg-gradient-to-r from-brand-600 to-blue-700 text-white shadow-lg shadow-brand-500/20";
        tabMini.className = "flex-1 py-3 px-4 rounded-xl font-medium text-sm transition flex items-center justify-center space-x-2 text-zinc-400 hover:text-white hover:bg-zinc-800/60";
        veoPanel.classList.remove('hidden');
        miniPanel.classList.add('hidden');
        veoNegBox.classList.remove('hidden');
      } else {
        tabMini.className = "flex-1 py-3 px-4 rounded-xl font-medium text-sm transition flex items-center justify-center space-x-2 bg-gradient-to-r from-purple-600 to-accent-600 text-white shadow-lg shadow-purple-500/20";
        tabVeo.className = "flex-1 py-3 px-4 rounded-xl font-medium text-sm transition flex items-center justify-center space-x-2 text-zinc-400 hover:text-white hover:bg-zinc-800/60";
        miniPanel.classList.remove('hidden');
        veoPanel.classList.add('hidden');
        veoNegBox.classList.add('hidden');
      }
    }

    function toggleFluxPrompt() {
      const chk = document.getElementById('chk-flux').checked;
      const box = document.getElementById('flux-prompt-box');
      if (chk) box.classList.remove('hidden');
      else box.classList.add('hidden');
    }

    async function checkBalance() {
      const badge = document.getElementById('balance-badge');
      badge.classList.remove('hidden');
      badge.textContent = '查詢中...';
      try {
        const res = await fetch('/api/usage');
        const data = await res.json();
        if (data.status === 'ok' && data.balance !== undefined) {
          badge.textContent = `${data.balance} 單位`;
          badge.className = "text-emerald-400 font-mono font-bold";
        } else {
          badge.textContent = '未連線';
          badge.className = "text-amber-400 font-mono font-bold";
          showColabModal(data);
        }
      } catch (e) {
        badge.textContent = '連線失敗';
        badge.className = "text-rose-400 font-mono font-bold";
        showColabModal({
          title: "連線伺服器異常",
          message: e.message
        });
      }
    }

    function showColabModal(info) {
      const modal = document.getElementById('colab-help-modal');
      const content = document.getElementById('colab-modal-content');

      let html = '';
      if (info.status === 'not_installed' || info.error === 'not_installed') {
        html = `
          <p class="font-bold text-white text-sm">🔍 檢測到本機尚未安裝 Google Colab CLI！</p>
          <p>因為尚未安裝 <code>google-colab-cli</code> 工具，系統無法直接向 Colab 查詢您的算力餘額與連線狀態。</p>
          <div class="bg-zinc-950 p-3 rounded-xl border border-zinc-800 font-mono text-[11px] text-zinc-300 space-y-1">
            <p class="text-zinc-500"># 步驟 1: 安裝 Colab CLI</p>
            <p class="text-brand-400">pip install google-colab-cli</p>
            <p class="text-zinc-500"># 步驟 2: 完成 Google 帳號授權</p>
            <p class="text-brand-400">colab --auth=oauth2 usage</p>
          </div>
          <div class="p-3 bg-blue-950/40 border border-blue-900/50 rounded-xl text-blue-200">
            💡 <strong>超棒特點：</strong>如果您使用 <strong>Google Veo 3</strong> 且未開啟 Colab GPU 增強，只要在上方填寫 <strong>Gemini API Key</strong>，本系統可<strong>直接在本機端生成</strong>，完全不需要 Colab CLI 也能正常出片！
          </div>
        `;
      } else {
        html = `
          <p class="font-bold text-white text-sm">⚠️ Colab 查詢失敗</p>
          <p class="text-rose-400 font-mono">${escapeHtml(info.message || info.error || '未知錯誤')}</p>
          <p>若您已安裝 Colab CLI，請在終端機執行 <code>colab --auth=oauth2 usage</code> 重新完成 OAuth2 授權。</p>
        `;
      }
      content.innerHTML = html;
      modal.classList.remove('hidden');
    }

    function closeColabModal() {
      document.getElementById('colab-help-modal').classList.add('hidden');
    }

    async function submitInference() {
      const prompt = document.getElementById('prompt-input').value.trim();
      if (!prompt) {
        alert('請先輸入生成提示詞 (Prompt)！');
        return;
      }

      const apiKey = document.getElementById('api-key-input').value.trim();
      if (currentModel === 'veo' && !apiKey) {
        alert('【請輸入 Gemini API Key】\\n生成 Veo 3 視訊需要填寫 API Key。\\n請在頁面上方「🔑 API Key」輸入框貼上從 Google AI Studio (aistudio.google.com) 免費取得的金鑰！');
        document.getElementById('api-key-input').focus();
        return;
      }

      const payload = {
        engine: currentModel,
        api_key: apiKey,
        prompt: prompt,
        flux: document.getElementById('chk-flux').checked,
        flux_prompt: document.getElementById('flux-prompt-input').value.trim(),
        interpolate: document.getElementById('chk-interpolate').checked ? 60 : null,
        upscale: document.getElementById('chk-upscale').checked ? '4k' : null,
        face_restore: document.getElementById('chk-face-restore').checked,
      };

      if (currentModel === 'veo') {
        payload.model = document.getElementById('veo-model-select').value;
        payload.aspect_ratio = document.getElementById('veo-aspect-select').value;
        payload.resolution = document.getElementById('veo-res-select').value;
        payload.duration = parseInt(document.getElementById('veo-duration-select').value);
        payload.negative_prompt = document.getElementById('negative-prompt-input').value;
        payload.first_frame = document.getElementById('veo-first-frame').value.trim();
        payload.last_frame = document.getElementById('veo-last-frame').value.trim();
      } else {
        payload.mode = document.getElementById('minimax-mode-select').value;
        payload.duration = parseInt(document.getElementById('minimax-duration').value);
        payload.seed = document.getElementById('minimax-seed').value.trim();
        payload.images = document.getElementById('minimax-images').value.split(',').map(s => s.trim()).filter(Boolean);
      }

      document.getElementById('btn-submit').disabled = true;
      document.getElementById('btn-submit').classList.add('opacity-50');

      appendLog(`[系統] 正在發送推論任務... (模型: ${currentModel})`);

      try {
        const res = await fetch('/api/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const resData = await res.json();
        if (resData.success) {
          startPolling();
        } else {
          alert('啟動失敗: ' + (resData.error || '未知錯誤'));
          document.getElementById('btn-submit').disabled = false;
          document.getElementById('btn-submit').classList.remove('opacity-50');
        }
      } catch (err) {
        alert('連線失敗: ' + err.message);
        document.getElementById('btn-submit').disabled = false;
        document.getElementById('btn-submit').classList.remove('opacity-50');
      }
    }

    function startPolling() {
      if (pollInterval) clearInterval(pollInterval);
      pollInterval = setInterval(async () => {
        try {
          const res = await fetch('/api/status');
          const data = await res.json();
          updateUIStatus(data);
          if (data.status === 'completed' || data.status === 'failed') {
            clearInterval(pollInterval);
            document.getElementById('btn-submit').disabled = false;
            document.getElementById('btn-submit').classList.remove('opacity-50');
          }
        } catch (e) {}
      }, 2000);
    }

    function updateUIStatus(data) {
      const badge = document.getElementById('task-badge');
      badge.textContent = data.status.toUpperCase();
      if (data.status === 'running') {
        badge.className = "text-xs px-2.5 py-0.5 rounded-full bg-blue-900/60 text-blue-400 font-mono animate-pulse";
      } else if (data.status === 'completed') {
        badge.className = "text-xs px-2.5 py-0.5 rounded-full bg-emerald-900/60 text-emerald-400 font-mono";
      } else if (data.status === 'failed') {
        badge.className = "text-xs px-2.5 py-0.5 rounded-full bg-rose-900/60 text-rose-400 font-mono";
      }

      if (data.logs && data.logs.length > 0) {
        const term = document.getElementById('terminal-box');
        term.innerHTML = data.logs.map(line => `<div class="leading-relaxed">${escapeHtml(line)}</div>`).join('');
        term.scrollTop = term.scrollHeight;
      }

      if (data.output_file && data.status === 'completed') {
        const player = document.getElementById('video-player');
        const holder = document.getElementById('video-placeholder');
        const dlBox = document.getElementById('download-box');
        const dlBtn = document.getElementById('btn-download');
        const pathSpan = document.getElementById('output-filepath');

        player.src = '/api/video?t=' + Date.now();
        player.classList.remove('hidden');
        holder.classList.add('hidden');
        dlBox.classList.remove('hidden');
        dlBtn.href = '/api/video';
        pathSpan.textContent = data.output_file;
      }
    }

    function appendLog(line) {
      const term = document.getElementById('terminal-box');
      const div = document.createElement('div');
      div.className = "leading-relaxed text-brand-400";
      div.textContent = line;
      term.appendChild(div);
      term.scrollTop = term.scrollHeight;
    }

    function clearLogs() {
      document.getElementById('terminal-box').innerHTML = '<div class="text-zinc-500">已清空紀錄</div>';
    }

    function escapeHtml(text) {
      return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
  </script>
</body>
</html>
"""


class WebUIHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/" or url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode("utf-8"))
        elif url.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(active_task).encode("utf-8"))
        elif url.path == "/api/usage":
            # 檢查 Colab CLI 是否安裝
            if not shutil.which("colab"):
                data = {
                    "status": "not_installed",
                    "error": "not_installed",
                    "message": "本機尚未安裝 Google Colab CLI 工具 (未找到 colab 命令)"
                }
            else:
                try:
                    out = subprocess.run([sys.executable, str(RUNNER_SCRIPT), "usage", "--json"], capture_output=True, text=True, timeout=15)
                    if out.returncode == 0:
                        parsed = json.loads(out.stdout)
                        data = {"status": "ok", **parsed}
                    else:
                        data = {"status": "error", "message": out.stderr.strip() or "查詢失敗"}
                except Exception as e:
                    data = {"status": "error", "message": str(e)}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        elif url.path == "/api/video":
            if active_task["output_file"] and os.path.isfile(active_task["output_file"]):
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(os.path.getsize(active_task["output_file"])))
                self.end_headers()
                with open(active_task["output_file"], "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(body)
                threading.Thread(target=run_inference_task, args=(data,), daemon=True).start()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run_inference_task(payload: dict):
    global active_task
    active_task["status"] = "running"
    active_task["logs"] = [f"任務啟動: {payload.get('engine', 'veo').upper()} 模型"]
    active_task["error"] = None
    active_task["output_file"] = None
    active_task["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    output_dir = SKILL_DIR / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"video_{int(time.time())}.mp4"

    cmd = [
        sys.executable,
        str(RUNNER_SCRIPT),
        "single",
        "--prompt", payload.get("prompt", ""),
        "--output", str(out_file),
    ]

    api_key = payload.get("api_key")
    if api_key:
        cmd.extend(["--api-key", api_key])
        os.environ["GEMINI_API_KEY"] = api_key

    engine = payload.get("engine", "veo")
    if engine == "veo":
        cmd.extend([
            "-e", "veo",
            "--model", payload.get("model", "veo-3.1-fast-generate-preview"),
            "--duration", str(payload.get("duration", 5)),
            "--aspect-ratio", payload.get("aspect_ratio", "16:9"),
            "--resolution", payload.get("resolution", "1080p"),
        ])
        if payload.get("first_frame"):
            cmd.extend(["--first-frame", payload["first_frame"]])
        if payload.get("last_frame"):
            cmd.extend(["--last-frame", payload["last_frame"]])
    else:
        # MiniMax H3
        cmd.extend([
            "-e", "minimax",
            "--duration", str(payload.get("duration", 12)),
            "--gpu", "A100",
        ])
        if payload.get("seed"):
            cmd.extend(["--seed", str(payload["seed"])])
        for img in payload.get("images", []):
            if img:
                cmd.extend(["-i", img])

    # 4 大增強參數
    if payload.get("flux"):
        cmd.extend(["--flux-prompt", payload.get("flux_prompt") or payload.get("prompt")])
    if payload.get("interpolate"):
        cmd.extend(["--interpolate", str(payload["interpolate"])])
    if payload.get("upscale"):
        cmd.extend(["--upscale", str(payload["upscale"])])
    if payload.get("face_restore"):
        cmd.append("--face-restore")
    if payload.get("use_colab"):
        cmd.append("--use-colab")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            clean = line.strip()
            if clean:
                active_task["logs"].append(clean)
                active_task["logs"] = active_task["logs"][-100:]
        ret = proc.wait()
        if ret == 0 and out_file.is_file():
            active_task["status"] = "completed"
            active_task["output_file"] = str(out_file)
            active_task["logs"].append(f"🎉 影片生成完成！路徑: {out_file}")
        else:
            active_task["status"] = "failed"
            active_task["error"] = f"推論程式結束碼: {ret}"
            active_task["logs"].append(f"❌ 執行失敗 (Exit Code: {ret})")
    except Exception as exc:
        active_task["status"] = "failed"
        active_task["error"] = str(exc)
        active_task["logs"].append(f"❌ 異常錯誤: {exc}")


def main():
    print(f"=======================================================")
    print(f"🎬 AI 視訊控制中心 (Veo 3 & MiniMax H3 雙核心)")
    print(f"網頁伺服器已啟動: http://127.0.0.1:{PORT}")
    print(f"請在瀏覽器開啟上述網址進行可視化操作")
    print(f"=======================================================")
    with socketserver.TCPServer(("", PORT), WebUIHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
