---
name: industry-chain-map
description: >
  Generate interactive industry chain (产业链) maps as HTML pages.
  Input an industry name (e.g. 低空经济, 新能源汽车, 半导体, 人工智能),
  call an LLM to produce upstream/midstream/downstream chain data,
  render a polished dark/light-theme web page, and optionally export
  standalone HTML files. Triggers on: "产业链图谱", "产业链地图",
  "industry chain", "产业链生成", "生成产业链", or when the user
  wants a visual industry chain diagram/map for any sector.
---

# Industry Chain Map Generator

Generate interactive, exportable industry chain (产业链) maps from an industry name.

## Architecture

- **Backend**: `assets/app.py` — Flask server that calls an LLM (Anthropic Messages API) to generate structured JSON chain data
- **Frontend**: `assets/index.html` — Single-page app with dark/light theme toggle, preset chips, and export buttons
- **No external DB** — LLM output rendered directly in browser

## Deployment

1. Copy `assets/app.py` and `assets/index.html` to a directory
2. Install dependencies:
   ```bash
   pip install flask flask-cors
   ```
3. The app reads the LLM API config from `~/.openclaw/openclaw.json` (OpenClaw provider config). Alternatively, set environment variables `OPENAI_API_KEY` and `OPENAI_BASE_URL`.
4. Start:
   ```bash
   python3 app.py
   ```
   Serves on `0.0.0.0:8089` by default. Override with `--port` or env `PORT`.

## API

### `POST /api/generate`

Request:
```json
{ "industry": "低空经济" }
```

Response (success):
```json
{
  "data": {
    "title": "低空经济产业链图谱",
    "sections": [
      {
        "name": "上游",
        "subtitle": "原材料与核心零部件",
        "categories": [
          {
            "name": "关键材料",
            "items": [
              { "label": "碳纤维", "text": "轻量化复合材料", "highlight": true }
            ]
          }
        ]
      }
    ]
  }
}
```

Response (error):
```json
{ "error": "error description" }
```

## LLM Prompt

The system prompt is embedded in `app.py`. It instructs the LLM to output a strict JSON schema with:
- 3 sections (上游/中游/下游)
- Each section has 2-4 categories with 3-5 items
- ~20-30% of items flagged as `highlight: true` (core/key elements)

## Frontend Features

- **Preset chips**: Click to quickly generate common industries
- **Dark/Light theme toggle**: Saved in localStorage
- **Export HTML**: Downloads a standalone HTML file (like the original template style)
- **Copy JSON**: Copies structured data to clipboard
- **Responsive**: Works on mobile (single column) and desktop (3-column layout)

## Customization

- Add more preset industries: Edit the `.preset-chip` buttons in `assets/index.html`
- Change LLM model: Edit the model selection logic in `app.py` (defaults to `glm-4.5-air`)
- Change port: Set `PORT` env var or edit the last line of `app.py`
