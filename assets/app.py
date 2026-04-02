#!/usr/bin/env python3
"""
产业链图谱生成器 - 后端服务
接收产业名称，调用大模型生成产业链图谱JSON
"""
import json
import os
import subprocess
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

SYSTEM_PROMPT = """你是一个产业链分析专家。用户会给你一个产业名称，你需要生成该产业的产业链图谱数据。

严格按照以下JSON格式输出，不要输出任何其他内容：

{
  "title": "XX产业链图谱",
  "sections": [
    {
      "name": "上游",
      "subtitle": "简短描述",
      "categories": [
        {
          "name": "分类名称",
          "items": [
            {"label": "子项名称", "text": "详细描述", "highlight": false},
            {"label": "关键材料", "text": "具体材料描述", "highlight": true}
          ]
        }
      ]
    },
    {
      "name": "中游",
      "subtitle": "简短描述",
      "categories": [...]
    },
    {
      "name": "下游",
      "subtitle": "简短描述",
      "categories": [...]
    }
  ]
}

要求：
1. 分为上游、中游、下游三个环节
2. 每个环节2-4个分类，每个分类3-5个子项
3. highlight为true表示该环节的核心/重点内容（约占总项的20-30%）
4. 内容要专业、准确、具体，包含关键技术、产品、应用等
5. 只输出JSON，不要任何解释文字"""

def call_llm(industry_name):
    """调用大模型生成产业链数据"""
    import urllib.request

    prompt = f"请生成「{industry_name}」的产业链图谱数据。"

    # 从 openclaw 配置读取 API 信息
    api_base = "https://open.bigmodel.cn/api/anthropic"
    api_key = ""
    model = "glm-4.5-air"

    try:
        with open(os.path.expanduser('~/.openclaw/openclaw.json')) as f:
            cfg = json.load(f)
        providers = cfg.get('models', {}).get('providers', {})
        for pname, pconf in providers.items():
            if pconf.get('apiKey'):
                api_key = pconf['apiKey']
                api_base = pconf.get('baseUrl', api_base)
                # Use a fast non-reasoning model
                for m in pconf.get('models', []):
                    mid = m.get('id', '')
                    if 'air' in mid.lower() or 'flash' in mid.lower():
                        model = mid
                        break
                break
    except Exception:
        pass

    if not api_key:
        return None, "未找到API密钥"

    # Anthropic Messages API format
    payload = json.dumps({
        "model": model,
        "max_tokens": 4000,
        "messages": [
            {"role": "user", "content": SYSTEM_PROMPT + "\n\n" + prompt}
        ]
    }).encode('utf-8')

    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01'
    }

    req = urllib.request.Request(
        f"{api_base.rstrip('/')}/v1/messages",
        data=payload,
        headers=headers,
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            content = result['content'][0]['text']

            # Save raw response for debugging
            with open('/tmp/llm-raw-response.txt', 'w') as f:
                f.write(content)

            # 提取JSON部分
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            # Remove leading/trailing non-JSON
            start = content.find('{')
            if start >= 0:
                content = content[start:]
            end = content.rfind('}')
            if end >= 0:
                content = content[:end+1]
            # Remove JS-style comments and trailing commas
            import re
            content = re.sub(r'//.*?\n', '\n', content)  # single-line comments
            content = re.sub(r',\s*([}\]])', r'\1', content)  # trailing commas
            data = json.loads(content.strip())
            return data, None
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return None, f"API错误({e.code}): {body[:200]}"
    except json.JSONDecodeError as e:
        # Save the problematic content for debugging
        with open('/tmp/llm-parse-error.txt', 'w') as f:
            f.write(f"Error: {e}\n\nContent:\n{content}")
        return None, f"JSON解析失败: {str(e)}"
    except Exception as e:
        return None, str(e)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/generate', methods=['POST'])
def generate():
    body = request.json or {}
    industry = body.get('industry', '').strip()
    
    if not industry:
        return jsonify({'error': '请输入产业名称'}), 400
    
    data, error = call_llm(industry)
    
    if error:
        return jsonify({'error': f'生成失败: {error}'}), 500
    
    return jsonify({'data': data})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8089, debug=False, threaded=True)
