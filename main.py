import datetime
import io
import os
import sys
import requests

# 确保在 Windows 控制台下支持 UTF-8 打印
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 从系统环境变量读取 Bark Key
BARK_DEVICE_KEY = os.environ.get("BARK_KEY")
COINGECKO_API_URL = "https://api.coingecko.com/api/v3/simple/price"


def get_btc_price() -> dict:
    """调用 CoinGecko 免费 API 获取比特币（BTC）的最新美元价格及 24 小时涨跌幅。"""
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            COINGECKO_API_URL, params=params, headers=headers, timeout=10
        )
        response.raise_for_status()
        data = response.json()
        btc_info = data.get("bitcoin", {})
        price = btc_info.get("usd")
        change_24h = btc_info.get("usd_24h_change")

        if price is None:
            raise ValueError(f"CoinGecko 返回数据中未找到比特币价格: {data}")

        return {"price": price, "change_24h": change_24h}
    except requests.exceptions.RequestException as e:
        print(f"[Error] 获取 CoinGecko 数据失败: {e}", file=sys.stderr)
        raise


def send_bark_notification(
    title: str,
    body: str,
    device_key: str = None,
    group: str = "BTC 价格提醒",
    icon: str = "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
) -> bool:
    """使用 requests 调用 Bark API 发送推送通知。"""
    key = device_key or BARK_DEVICE_KEY
    if not key:
        print(
            "[Error] 未检测到 Bark Key！请先配置环境变量 BARK_KEY（例如：export BARK_KEY=xxxx 或在 GitHub Secrets 中配置 BARK_KEY）。",
            file=sys.stderr,
        )
        return False

    bark_url = f"https://api.day.app/{key}/"
    payload = {
        "title": title,
        "body": body,
        "group": group,
        "icon": icon,
        "sound": "minuet",
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}

    try:
        response = requests.post(bark_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        res_json = response.json()
        if res_json.get("code") == 200:
            print(f"[Success] Bark 消息推送成功: {res_json.get('message', 'ok')}")
            return True
        else:
            print(f"[Warning] Bark 推送返回异常: {res_json}", file=sys.stderr)
            return False
    except requests.exceptions.RequestException as e:
        print(f"[Error] Bark API 请求失败: {e}", file=sys.stderr)
        raise


def main():
    print("=" * 45)
    print("🚀 正在获取比特币（BTC）最新价格...")
    btc_data = get_btc_price()
    price = btc_data["price"]
    change_24h = btc_data.get("change_24h")

    # 获取当前时间
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 涨跌幅符号
    change_str = ""
    if change_24h is not None:
        sign = "+" if change_24h >= 0 else ""
        emoji = "📈" if change_24h >= 0 else "📉"
        change_str = f"\n24h 涨跌: {emoji} {sign}{change_24h:.2f}%"

    # 格式化推送内容
    title = f"💰 BTC 最新价格: ${price:,.2f}"
    body = f"当前价格: ${price:,.2f}{change_str}\n发送时间: {now_str}"

    print(f"📊 获取成功！")
    print(f"   - 标题: {title}")
    print(f"   - 正文:\n{body}")
    print("-" * 45)
    print("📲 正在发送 Bark 手机推送...")

    success = send_bark_notification(title, body)
    if success:
        print("🎉 推送任务顺利完成！")
    else:
        print("❌ 推送任务未成功，请检查 Bark Key 配置。")
    print("=" * 45)


if __name__ == "__main__":
    main()
