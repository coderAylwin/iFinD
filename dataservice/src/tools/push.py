# -*- coding: utf-8 -*-
"""
飞书/Lark 机器人推送工具类

供所有数据获取脚本复用，通过 webhook 推送消息到飞书群。

用法：
    from tools.push import push_message

    push_message("Hello, world!")          # 纯文本
    push_message("标题", ["行1", "行2"])    # 多行
"""
import os
from pathlib import Path

# 项目根目录（IFIND_DATA/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 从 .env 读取 webhook（若已加载过 dotenv 则直接取）
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / 'dataservice' / '.env')
except ImportError:
    pass

# 默认 webhook
DEFAULT_WEBHOOK = "https://open.larksuite.com/open-apis/bot/v2/hook/c0942982-532e-4f09-a1c0-fa3bb34b34de"


def get_webhook():
    """获取 webhook URL：优先环境变量 PUSH_WEBHOOK，否则用默认"""
    return os.getenv('PUSH_WEBHOOK', '').strip() or DEFAULT_WEBHOOK


def push_message(text, lines=None):
    """
    推送文本消息到飞书群。

    Args:
        text: 首行/主文本
        lines: (可选) 后续多行内容列表

    Returns:
        bool: 是否推送成功
    """
    webhook = get_webhook()
    if not webhook:
        print("  推送: 未配置 PUSH_WEBHOOK，跳过")
        return False

    if lines:
        content = text + "\n" + "\n".join(str(x) for x in lines)
    else:
        content = text

    try:
        import requests
        resp = requests.post(
            webhook,
            json={"msg_type": "text", "content": {"text": content}},
            timeout=10,
        )
        ok = resp.status_code == 200
        print(f"  推送: HTTP {resp.status_code} {'成功' if ok else '失败'}: {resp.text[:100]}")
        return ok
    except Exception as e:
        print(f"  推送失败: {e}")
        return False


def push_markdown(title, text, color="blue"):
    """
    推送富文本卡片消息（飞书 interactive 卡片）。

    Args:
        title: 卡片标题
        text: 卡片内容（纯文本）
        color: 主题色 blue/green/red/orange/purple/grey/turquoise
    """
    webhook = get_webhook()
    if not webhook:
        print("  推送: 未配置 PUSH_WEBHOOK，跳过")
        return False

    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": title},
                       "template": color},
            "elements": [{"tag": "div",
                          "text": {"tag": "lark_md", "content": text}}],
        },
    }

    try:
        import requests
        resp = requests.post(webhook, json=card, timeout=10)
        ok = resp.status_code == 200
        print(f"  推送卡片: HTTP {resp.status_code} {'成功' if ok else '失败'}")
        return ok
    except Exception as e:
        print(f"  推送失败: {e}")
        return False


if __name__ == '__main__':
    # 测试
    push_message("测试消息", ["这是工具类", "推送成功"])