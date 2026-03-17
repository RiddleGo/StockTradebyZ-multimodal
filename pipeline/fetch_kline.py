"""
pipeline/fetch_kline.py — 从 Tushare 拉取日 K 线并保存为 data/raw/*.csv
配置：config/fetch_kline.yaml（out、stocklist、start、end、workers）
环境变量：TUSHARE_TOKEN
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "fetch_kline.yaml"


def _resolve_path(cfg_val: str, default: str) -> Path:
    p = (cfg_val or default).strip().lstrip("./")
    return _PROJECT_ROOT / p if not Path(p).is_absolute() else Path(p)


def main():
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"找不到配置文件：{_CONFIG_PATH}")
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        raise ValueError("请先设置环境变量 TUSHARE_TOKEN")
    import tushare as ts
    ts.set_token(token)
    pro = ts.pro_api()
    out = _resolve_path(cfg.get("out"), "data/raw")
    out.mkdir(parents=True, exist_ok=True)
    stocklist = _resolve_path(cfg.get("stocklist"), "pipeline/stocklist.csv")
    if not stocklist.exists():
        raise FileNotFoundError(f"股票列表不存在：{stocklist}，请从 StockTradebyZ 复制 pipeline/stocklist.csv")
    df = pd.read_csv(stocklist)
    if "ts_code" not in df.columns or "symbol" not in df.columns:
        raise ValueError("stocklist 需含 ts_code 与 symbol 列")
    codes = df["symbol"].astype(str).str.zfill(6).tolist()
    start = str(cfg.get("start", "20190101"))
    end = str(cfg.get("end", "today"))
    if end.lower() == "today":
        from datetime import date
        end = date.today().strftime("%Y%m%d")
    from tqdm import tqdm
    from concurrent.futures import ThreadPoolExecutor, as_completed
    workers = int(cfg.get("workers", 8))
    def fetch_one(code):
        ts_code = code + ".SH" if code.startswith(("60", "68", "9")) else (code + ".BJ" if code.startswith(("4", "8")) else code + ".SZ")
        try:
            d = ts.pro_bar(ts_code=ts_code, adj="qfq", start_date=start, end_date=end, freq="D", api=pro)
            if d is None or d.empty:
                pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume"]).to_csv(out / f"{code}.csv", index=False)
                return
            d = d.rename(columns={"trade_date": "date", "vol": "volume"})[["date", "open", "close", "high", "low", "volume"]]
            d["date"] = pd.to_datetime(d["date"])
            d = d.sort_values("date").drop_duplicates("date").reset_index(drop=True)
            d.to_csv(out / f"{code}.csv", index=False)
        except Exception as e:
            print(f"[WARN] {code}: {e}")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(tqdm(as_completed([ex.submit(fetch_one, c) for c in codes]), total=len(codes), desc="下载"))
    print(f"已保存至 {out}")


if __name__ == "__main__":
    main()
