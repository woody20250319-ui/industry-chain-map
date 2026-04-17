#!/usr/bin/env python3
"""
产业链图谱生成器 - 后端服务 V2
支持：颗粒度调整、重点企业标注、市场规模数据
"""
import json
import os
import re
import urllib.request
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

PROMPTS = {
    "brief": """你是一个产业链分析专家。生成简要版产业链图谱。

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
            {"label": "子项名称", "text": "简短描述", "highlight": false, "companies": "代表企业1、企业2", "market": "市场规模（如：2025年约XXX亿元）"}
          ]
        }
      ]
    }
  ]
}

要求：
1. 分为上游、中游、下游三个环节
2. 每个环节2个分类，每个分类2-3个子项
3. highlight为true表示核心/重点（约20%）
4. companies填写1-3家代表性企业（上市公司优先）
5. market填写该细分领域的大致市场规模或增速
6. 只输出JSON""",

    "standard": """你是一个产业链分析专家。生成标准版产业链图谱。

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
            {"label": "子项名称", "text": "详细描述", "highlight": false, "companies": "代表企业1、企业2、企业3", "market": "市场规模及增长率"}
          ]
        }
      ]
    }
  ]
}

要求：
1. 分为上游、中游、下游三个环节
2. 每个环节2-4个分类，每个分类3-5个子项
3. highlight为true表示核心/重点（约20-30%）
4. companies填写2-4家代表性企业（上市公司优先，标注股票代码如有把握）
5. market填写该细分领域的市场规模或增速数据
6. 内容要专业、准确、具体
7. 只输出JSON""",

    "detailed": """你是一个产业链分析专家。生成详细版产业链图谱。

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
            {"label": "子项名称", "text": "详细的专业描述，包含技术参数、应用场景等", "highlight": false, "companies": "代表企业1、企业2、企业3、企业4", "market": "2025年市场规模约XXX亿元，年增长率XX%"}
          ]
        }
      ]
    }
  ]
}

要求：
1. 分为上游、中游、下游三个环节
2. 每个环节3-5个分类，每个分类4-7个子项
3. highlight为true表示核心/重点（约20-30%）
4. companies填写3-5家代表性企业（上市公司优先，标注股票代码）
5. market填写具体市场规模、增长率、预测数据
6. 内容要非常专业、详细、具体，包含关键技术路线、参数、应用场景
7. 只输出JSON"""
}


def get_api_config():
    """从 openclaw 配置读取 API 信息"""
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
                for m in pconf.get('models', []):
                    mid = m.get('id', '')
                    if 'air' in mid.lower() or 'flash' in mid.lower():
                        model = mid
                        break
                break
    except Exception:
        pass
    return api_base, api_key, model


def parse_json_response(content):
    """从LLM输出中提取并修复JSON"""
    if '```json' in content:
        content = content.split('```json')[1].split('```')[0]
    elif '```' in content:
        content = content.split('```')[1].split('```')[0]
    start = content.find('{')
    if start >= 0:
        content = content[start:]
    end = content.rfind('}')
    if end >= 0:
        content = content[:end+1]
    # Remove comments and trailing commas
    content = re.sub(r'//.*?\n', '\n', content)
    content = re.sub(r',\s*([}\]])', r'\1', content)
    return content.strip()


def try_fix_json(content):
    """尝试修复常见的JSON错误"""
    # Fix unquoted values: "text":xxx -> "text": "xxx"
    content = re.sub(r':([^\s"\[\]{}][^"]*?)([",\n}\]])', lambda m:
        (': "' + m.group(1) + '"' + m.group(2)) if not m.group(1).startswith('"') else m.group(0),
        content)
    return content


def call_llm(industry_name, granularity="standard"):
    """调用大模型生成产业链数据"""
    api_base, api_key, model = get_api_config()
    if not api_key:
        return None, "未找到API密钥"

    system_prompt = PROMPTS.get(granularity, PROMPTS["standard"])
    prompt = f"请生成「{industry_name}」的产业链图谱数据。"

    max_tokens = {"brief": 3000, "standard": 5000, "detailed": 8000}.get(granularity, 5000)

    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "user", "content": system_prompt + "\n\n" + prompt}
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
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            content = result['content'][0]['text']

            with open('/tmp/llm-raw-response.txt', 'w') as f:
                f.write(content)

            content = parse_json_response(content)
            data = json.loads(content)
            return data, None

    except json.JSONDecodeError as e:
        # Try fix
        try:
            fixed = try_fix_json(content)
            data = json.loads(fixed)
            return data, None
        except:
            pass
        with open('/tmp/llm-parse-error.txt', 'w') as f:
            f.write(f"Error: {e}\n\nContent:\n{content}")
        return None, f"JSON解析失败: {str(e)}"

    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return None, f"API错误({e.code}): {body[:200]}"
    except Exception as e:
        return None, str(e)


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/generate', methods=['POST'])
def generate():
    body = request.json or {}
    industry = body.get('industry', '').strip()
    granularity = body.get('granularity', 'standard')

    if not industry:
        return jsonify({'error': '请输入产业名称'}), 400

    data, error = call_llm(industry, granularity)

    if error:
        if 'JSON解析' in str(error):
            data, error = call_llm(industry, granularity)

    if error:
        return jsonify({'error': f'生成失败: {error}'}), 500

    return jsonify({'data': data})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8089, debug=False, threaded=True)
