import datetime
import io
import os
import re
import sys
import urllib.parse
from typing import List, Dict
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

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
}


# ==========================================
# 1. 获取比特币（BTC）实时价格
# ==========================================
def get_btc_price() -> dict:
    """调用 CoinGecko 免费 API 获取比特币（BTC）最新价格及 24 小时涨跌幅。"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    try:
        response = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
        btc_info = response.json().get("bitcoin", {})
        price = btc_info.get("usd")
        change_24h = btc_info.get("usd_24h_change")

        if price is None:
            raise ValueError(f"返回数据中未找到比特币价格")

        return {"price": price, "change_24h": change_24h}
    except Exception as e:
        print(f"[Warning] 获取比特币价格失败: {e}", file=sys.stderr)
        return {"price": None, "change_24h": None}


# ==========================================
# 2. 获取日本下关天气与 12 小时降雨预警
# ==========================================
WMO_WEATHER_CODES = {
    0: ("晴朗", "☀️"),
    1: ("大部晴朗", "🌤️"),
    2: ("多云", "⛅"),
    3: ("阴天", "☁️"),
    45: ("有雾", "🌫️"),
    48: ("沉降雾", "🌫️"),
    51: ("轻微毛毛雨", "🌦️"),
    53: ("中度毛毛雨", "🌦️"),
    55: ("密集毛毛雨", "🌧️"),
    56: ("轻微冻毛毛雨", "🌧️"),
    57: ("密集冻毛毛雨", "🌧️"),
    61: ("微量小雨", "🌧️"),
    63: ("中雨", "🌧️"),
    65: ("大雨", "🌧️"),
    66: ("轻微冻雨", "🌧️"),
    67: ("强冻雨", "🌧️"),
    71: ("小雪", "❄️"),
    73: ("中雪", "❄️"),
    75: ("大雪", "❄️"),
    77: ("雪粒", "❄️"),
    80: ("微弱阵雨", "🌦️"),
    81: ("中度阵雨", "🌧️"),
    82: ("强阵雨", "⛈️"),
    85: ("轻度阵雪", "🌨️"),
    86: ("强阵雪", "🌨️"),
    95: ("雷暴", "⛈️"),
    96: ("雷暴伴小冰雹", "⛈️"),
    99: ("雷暴伴大冰雹", "⛈️"),
}
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}


def get_shimonoseki_weather() -> dict:
    """调用 Open-Meteo API 查询日本下关未来 12 小时降水概率与天气。"""
    lat, lon, tz = 33.9578, 130.9415, "Asia/Tokyo"
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=precipitation_probability,weather_code,temperature_2m"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min"
        f"&timezone={tz}&forecast_days=2"
    )
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        precip_probs = hourly.get("precipitation_probability", [])
        weather_codes = hourly.get("weather_code", [])
        temps = hourly.get("temperature_2m", [])

        daily = data.get("daily", {})
        max_temp = daily.get("temperature_2m_max", [None])[0]
        min_temp = daily.get("temperature_2m_min", [None])[0]

        now_hour = datetime.datetime.now().strftime("%Y-%m-%dT%H:00")
        start_idx = 0
        for i, t in enumerate(times):
            if t >= now_hour:
                start_idx = i
                break

        next_12_probs = [p for p in precip_probs[start_idx : start_idx + 12] if p is not None]
        next_12_codes = [c for c in weather_codes[start_idx : start_idx + 12] if c is not None]
        next_12_temps = [t for t in temps[start_idx : start_idx + 12] if t is not None]

        current_code = next_12_codes[0] if next_12_codes else 0
        current_temp = next_12_temps[0] if next_12_temps else (min_temp or 0)
        cond_desc, cond_emoji = WMO_WEATHER_CODES.get(current_code, ("多云", "⛅"))

        max_prob = max(next_12_probs) if next_12_probs else 0
        has_rain = any(code in RAIN_CODES for code in next_12_codes) or max_prob > 30

        if has_rain:
            umbrella_tip = "🌧️ 今天有雨，出门记得带伞！"
        else:
            umbrella_tip = "☀️ 今日无雨，出行无忧。"

        temp_range_str = (
            f"{min_temp:.1f}°C ~ {max_temp:.1f}°C"
            if min_temp is not None and max_temp is not None
            else f"{current_temp:.1f}°C"
        )

        return {
            "condition": cond_desc,
            "emoji": cond_emoji,
            "current_temp": f"{current_temp:.1f}°C",
            "temp_range": temp_range_str,
            "max_precip_prob": max_prob,
            "rain_warning": has_rain,
            "umbrella_tip": umbrella_tip,
        }
    except Exception as e:
        print(f"[Warning] 获取天气数据失败: {e}", file=sys.stderr)
        return {
            "condition": "多云",
            "emoji": "⛅",
            "current_temp": "--°C",
            "temp_range": "--°C",
            "max_precip_prob": 0,
            "rain_warning": False,
            "umbrella_tip": "🌤️ 出门请留意天气变化。",
        }


# ==========================================
# 3. 聚合全网热点 TOP 10 (微博、抖音、X、知乎)
# ==========================================
def fetch_weibo_hot() -> List[str]:
    """抓取微博实时热搜。"""
    url = "https://weibo.com/ajax/side/hotSearch"
    headers = {**DEFAULT_HEADERS, "Referer": "https://weibo.com/"}
    topics = []
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.ok:
            for item in r.json().get("data", {}).get("realtime", []):
                if not item.get("is_ad") and not item.get("is_star") and item.get("word"):
                    topics.append(item["word"].strip())
    except Exception:
        pass
    return topics


def fetch_douyin_hot() -> List[str]:
    """抓取抖音实时热点。"""
    urls = [
        "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/",
        "https://www.douyin.com/aweme/v1/web/hot/search/list/",
    ]
    topics = []
    for url in urls:
        try:
            r = requests.get(url, headers=DEFAULT_HEADERS, timeout=5)
            if r.ok:
                word_list = r.json().get("word_list") or r.json().get("data", {}).get("word_list", [])
                for item in word_list:
                    word = item.get("word")
                    if word and word not in topics:
                        topics.append(word.strip())
                if topics:
                    break
        except Exception:
            continue
    return topics


def fetch_twitter_hot() -> List[str]:
    """抓取 Twitter / X 热门趋势。"""
    url = "https://getdaytrends.com/japan/"
    topics = []
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=5)
        if r.ok:
            for m in re.findall(r'<a href="/japan/trend/([^"/]+)/"', r.text):
                decoded = urllib.parse.unquote(m).strip()
                if decoded and decoded not in topics:
                    topics.append(decoded)
    except Exception:
        pass
    return topics


def fetch_zhihu_hot() -> List[str]:
    """抓取知乎热榜备用。"""
    url = "https://api.zhihu.com/topstory/hot-lists/total"
    topics = []
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=5)
        if r.ok:
            for item in r.json().get("data", []):
                t = item.get("target", {}).get("title")
                if t:
                    topics.append(t.strip())
    except Exception:
        pass
    return topics


def get_top_10_hot_topics() -> List[Dict[str, str]]:
    """整合精选 TOP 10 核心热点。"""
    wb = fetch_weibo_hot()
    dy = fetch_douyin_hot()
    tw = fetch_twitter_hot()
    zh = fetch_zhihu_hot()

    selected = []
    seen = set()

    def add(source, title):
        if not title:
            return
        t = title.replace("\n", " ").strip()
        if t not in seen and len(t) > 1:
            seen.add(t)
            selected.append({"source": source, "title": t})

    for t in wb[:3]:
        add("微博", t)
    for t in dy[:3]:
        add("抖音", t)
    for t in tw[:3]:
        add("X/Twitter", t)

    pool = [("知乎", zh), ("微博", wb[3:]), ("抖音", dy[3:]), ("X/Twitter", tw[3:])]
    for src, p in pool:
        if len(selected) >= 10:
            break
        for t in p:
            if len(selected) >= 10:
                break
            add(src, t)

    return selected[:10]


# ==========================================
# 4. Bark 推送消息格式化与发送
# ==========================================
def send_combined_bark_push(btc: dict, weather: dict, hot_topics: List[Dict[str, str]]) -> bool:
    """将 BTC 行情、天气降雨预警和全网热点组合为一条优雅通知并推送到 Bark。"""
    device_key = os.environ.get("BARK_KEY") or BARK_DEVICE_KEY
    if not device_key:
        print(
            "[Error] 未检测到 Bark Key！请先配置环境变量 BARK_KEY（如：export BARK_KEY=xxxx 或在 GitHub Secrets 中配置）。",
            file=sys.stderr,
        )
        return False

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_rain = weather.get("rain_warning", False)
    cond_emoji = weather.get("emoji", "🌤️")
    weather_cond = weather.get("condition", "晴")

    # 1. 动态标题
    btc_price_str = f"${btc['price']:,.0f}" if btc.get("price") else "行情已更新"
    if is_rain:
        title = f"🌧️ 降雨预警·每日早报 | 日本下关 · BTC {btc_price_str}"
        icon_url = "https://cdn-icons-png.flaticon.com/512/1163/1163624.png"
    else:
        title = f"☀️ 每日早报 | 下关 {weather_cond}{cond_emoji} · BTC {btc_price_str}"
        icon_url = "https://assets.coingecko.com/coins/images/1/large/bitcoin.png"

    # 2. 组装正文
    body_lines = []

    # BTC 板块
    body_lines.append("【🪙 比特币 (BTC) 实时行情】")
    if btc.get("price") is not None:
        price_val = btc["price"]
        change_val = btc.get("change_24h")
        change_str = ""
        if change_val is not None:
            sign = "+" if change_val >= 0 else ""
            emoji = "📈" if change_val >= 0 else "📉"
            change_str = f" (24h: {emoji} {sign}{change_val:.2f}%)"
        body_lines.append(f"• 最新价格: ${price_val:,.2f}{change_str}")
    else:
        body_lines.append("• 价格信息暂时获取失败")
    body_lines.append("")

    # 天气预警板块
    body_lines.append("【📍 日本·下关天气 & 降雨预警】")
    body_lines.append(f"• 天气状况: {weather_cond} {cond_emoji} (气温 {weather.get('temp_range', '--')})")
    body_lines.append(f"• 降水概率: 未来12小时最高 {weather.get('max_precip_prob', 0)}%")
    body_lines.append(f"• 出行提醒: {weather.get('umbrella_tip', '')}")
    body_lines.append("")

    # 全网热点板块
    body_lines.append("【🔥 今日全网热点 TOP 10】")
    for idx, item in enumerate(hot_topics, 1):
        body_lines.append(f"{idx}. [{item['source']}] {item['title']}")

    body_lines.append("")
    body_lines.append(f"⏰ 发送时间: {now_str}")

    body_text = "\n".join(body_lines)

    # 3. HTTP POST 发送
    bark_url = f"https://api.day.app/{device_key}/"
    payload = {
        "title": title,
        "body": body_text,
        "group": "全能每日早报",
        "icon": icon_url,
        "sound": "calypso" if is_rain else "minuet",
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}

    try:
        response = requests.post(bark_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        res_json = response.json()
        if res_json.get("code") == 200:
            print(f"[Success] 聚合早报 Bark 推送成功: {res_json.get('message', 'ok')}")
            return True
        else:
            print(f"[Warning] Bark 推送返回异常: {res_json}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[Error] Bark API 请求失败: {e}", file=sys.stderr)
        return False


# ==========================================
# 5. 主程序入口
# ==========================================
def main():
    print("=" * 55)
    print("🌅 开始获取 BTC 价格、日本下关天气预警与全网热点...")
    print("=" * 55)

    # 1. BTC 价格
    print("1️⃣ 正在获取比特币（BTC）最新价格...")
    btc_data = get_btc_price()
    if btc_data.get("price"):
        print(f"   BTC 当前价格: ${btc_data['price']:,.2f} (24h: {btc_data.get('change_24h', 0):+.2f}%)")

    # 2. 天气预警
    print("2️⃣ 正在获取日本下关天气与降水概率...")
    weather_data = get_shimonoseki_weather()
    print(f"   下关天气: {weather_data['condition']} {weather_data['emoji']} | 降雨概率: {weather_data['max_precip_prob']}%")
    print(f"   提醒: {weather_data['umbrella_tip']}")

    # 3. 全网热点
    print("3️⃣ 正在抓取微博、抖音、Twitter/X 热点...")
    hot_topics = get_top_10_hot_topics()
    print(f"   已获取 {len(hot_topics)} 条核心热点。")

    # 4. 合并推送
    print("-" * 55)
    print("📲 正在发送聚合早报到手机 Bark...")
    success = send_combined_bark_push(btc_data, weather_data, hot_topics)

    if success:
        print("🎉 恭喜！包含 BTC 价格、天气降雨预警和热榜的早报已成功推送到手机！")
    else:
        print("❌ 推送未成功，请检查 BARK_KEY 环境变量配置。")
    print("=" * 55)


if __name__ == "__main__":
    main()
