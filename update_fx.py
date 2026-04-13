"""
毎月1日に GitHub Actions から実行される為替データ更新スクリプト
三菱UFJリサーチ&コンサルティング 月末・月中平均 TTS を取得して
index.html と fx_data.json を更新する
"""
import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime

MURC_URL = "https://www.murc-kawasesouba.jp/fx/monthend/index.php"

def fetch_murc():
    """三菱UFJサイトから最新の月次TTS/TTBデータを取得"""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; fx-updater/1.0)"}
    res = requests.get(MURC_URL, headers=headers, timeout=30)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "lxml")

    data = []
    # テーブルを探索
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all(["td","th"])]
            if len(cells) < 4:
                continue
            # 年月列 YYYY/MM または YYYYMM 形式を検出
            ym_raw = cells[0]
            m = re.match(r"(\d{4})[/\-]?(\d{2})", ym_raw)
            if not m:
                continue
            ym = f"{m.group(1)}-{m.group(2)}"
            try:
                # USD列: TTS, TTB, TTM / CNY列: TTS, TTB, TTM
                # サイト構造に応じて列インデックスを調整
                usd_tts = float(cells[1]) if cells[1] else None
                usd_ttb = float(cells[2]) if cells[2] else None
                usd_ttm = float(cells[3]) if cells[3] else None
                cny_tts = float(cells[4]) if len(cells) > 4 and cells[4] else None
                cny_ttb = float(cells[5]) if len(cells) > 5 and cells[5] else None
                cny_ttm = float(cells[6]) if len(cells) > 6 and cells[6] else None
                data.append({
                    "ym": ym,
                    "usd_tts": usd_tts,
                    "usd_ttb": usd_ttb,
                    "usd_ttm": usd_ttm,
                    "cny_tts": cny_tts,
                    "cny_ttb": cny_ttb,
                    "cny_ttm": cny_ttm,
                })
            except (ValueError, IndexError):
                continue
    return data

def merge_data(existing, fetched):
    """既存データに新規月分をマージ（重複は上書き）"""
    merged = {d["ym"]: d for d in existing}
    updated = 0
    for d in fetched:
        if d["usd_tts"] is None:
            continue
        if d["ym"] not in merged or merged[d["ym"]] != d:
            merged[d["ym"]] = d
            updated += 1
    result = sorted(merged.values(), key=lambda x: x["ym"])
    print(f"  既存: {len(existing)}件 / 取得: {len(fetched)}件 / 追加・更新: {updated}件 / 合計: {len(result)}件")
    return result

def build_html(fx_data):
    """index.html を再生成"""
    # 既存HTMLのFX_DATAブロックを置換
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    new_json = json.dumps(fx_data, ensure_ascii=False)
    # const FX_DATA = [...]; の部分を置換
    html_new = re.sub(
        r"const FX_DATA = \[.*?\];",
        f"const FX_DATA = {new_json};",
        html,
        flags=re.DOTALL
    )
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_new)

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 為替データ更新開始")

    # 既存データ読み込み
    if os.path.exists("fx_data.json"):
        with open("fx_data.json", "r", encoding="utf-8") as f:
            existing = json.load(f)
        print(f"  既存データ読み込み: {len(existing)}件")
    else:
        existing = []
        print("  既存データなし（初回）")

    # 三菱UFJから取得
    print("  三菱UFJサイトからデータ取得中...")
    try:
        fetched = fetch_murc()
        print(f"  取得成功: {len(fetched)}件")
    except Exception as e:
        print(f"  取得失敗: {e}")
        print("  既存データをそのまま使用")
        fetched = []

    # マージ
    merged = merge_data(existing, fetched)

    # fx_data.json 保存
    with open("fx_data.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print("  fx_data.json 保存完了")

    # index.html 更新
    build_html(merged)
    print("  index.html 更新完了")
    print(f"  最新月: {merged[-1]['ym'] if merged else 'なし'}")
    print("完了")

if __name__ == "__main__":
    main()
