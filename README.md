ComfyUI-dAIly

Two handy custom nodes for ComfyUI to help with prompt crafting and token management:

- **Token Info Display (CLIP / T5 / Qwen)**  
  Real-time token counter for CLIP-L, T5-XXL (Flux), and Qwen models. Shows token counts + character count, and dynamically updates the node title for quick glance.

- **Prompt Mixer Daily (CSV Wildcards)**  
  Generate varied, seed-controlled prompts from your own CSV files. Supports placeholders like `{Skin}`, `{Hairstyle}`, `{Pose}`, etc. Choose between flat single-line output or preserved paragraphs/line-breaks.

## Features

- Token counter works even without connected models (falls back to public tokenizers)
- Prompt mixer is fully reproducible with seed
- CSV loading supports multiple encodings (UTF-8-SIG preferred)
- Optional manual override for any field
- Thread-safe CSV caching
- Clean output JSON with used values + seed

## Installation

### Via ComfyUI Manager (recommended)

1. Open ComfyUI Manager  
2. Search for **"dAIly Prompt & Token Utils"** (or just "dAIly")  
3. Install
<img width="880" height="793" alt="Capture d&#39;écran 2026-03-03 101342" src="https://github.com/user-attachments/assets/e50b3bfa-72b0-464c-bc93-a54d148e692f" />
### Manual install

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/DailyMok/ComfyUI-dAIly.git


