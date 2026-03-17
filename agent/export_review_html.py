"""
export_review_html.py
~~~~~~~~~~~~~~~~~~~~~
根据 suggestion.json 与单股 JSON 生成可浏览器打开的 HTML 报告。
支持在复评流程结束后自动调用，也可单独对已有结果导出。

用法：
  python agent/export_review_html.py
  python agent/export_review_html.py --suggestion data/review/2026-03-17/suggestion.json
  python agent/export_review_html.py --date 2026-03-17 --open
"""

import argparse
import json
import base64
from pathlib import Path
import sys

try:
    from review_config import load_review_config
except ImportError:
    from agent.review_config import load_review_config

_ROOT = Path(__file__).resolve().parent.parent


def _escape(s: str) -> str:
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _img_to_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(suffix, "image/jpeg")
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def build_html(
    suggestion: dict,
    out_dir: Path,
    kline_dir: Path,
    embed_images: bool = True,
) -> str:
    pick_date = suggestion.get("date", "")
    min_score = suggestion.get("min_score_threshold", 0)
    total = suggestion.get("total_reviewed", 0)
    recs = suggestion.get("recommendations", [])
    excluded = suggestion.get("excluded", [])

    rows = []
    for r in recs:
        code = r.get("code", "")
        rank = r.get("rank", "")
        score = r.get("total_score", 0)
        verdict = r.get("verdict", "")
        signal_type = r.get("signal_type", "")
        comment = r.get("comment", "")

        img_src = ""
        day_chart = kline_dir / pick_date / f"{code}_day.jpg"
        if not day_chart.exists():
            day_chart = kline_dir / pick_date / f"{code}_day.png"
        if day_chart.exists():
            if embed_images:
                img_src = _img_to_data_uri(day_chart)
            else:
                # 相对路径：report.html 在 out_dir 下，图片在 kline_dir/pick_date
                rel = Path("..") / ".." / kline_dir.name / pick_date / day_chart.name
                img_src = str(rel).replace("\\", "/")

        score_str = f"{score:.1f}" if isinstance(score, (int, float)) else str(score)
        img_tag = f'<img src="{img_src}" alt="{code}" class="kline-img"/>' if img_src else "—"

        detail = ""
        detail_file = out_dir / f"{code}.json"
        if detail_file.exists():
            try:
                with open(detail_file, encoding="utf-8") as f:
                    detail_data = json.load(f)
                detail = json.dumps(detail_data, ensure_ascii=False, indent=2)
            except Exception:
                pass

        rows.append({
            "rank": rank,
            "code": code,
            "score_str": score_str,
            "verdict": verdict,
            "signal_type": signal_type,
            "comment": comment,
            "img_tag": img_tag,
            "detail_json": detail,
        })

    excluded_str = "、".join(excluded) if excluded else "无"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>选股复评报告 · {pick_date}</title>
  <style>
    :root {{ --bg: #0f0f12; --card: #1a1a1f; --text: #e4e4e7; --muted: #71717a; --accent: #22c55e; --border: #27272a; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: "Segoe UI", system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 1.5rem; line-height: 1.5; }}
    h1 {{ font-size: 1.5rem; margin: 0 0 0.5rem; }}
    .meta {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 1.5rem; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }}
    th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ background: #252528; color: var(--muted); font-weight: 600; font-size: 0.85rem; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover {{ background: #222225; }}
    .code {{ font-weight: 600; font-family: ui-monospace, monospace; }}
    .score {{ color: var(--accent); font-weight: 600; }}
    .verdict {{ font-size: 0.9rem; }}
    .kline-img {{ max-width: 320px; max-height: 200px; display: block; border-radius: 4px; border: 1px solid var(--border); }}
    .detail {{ font-size: 0.8rem; color: var(--muted); white-space: pre-wrap; max-height: 8em; overflow-y: auto; }}
    .excluded {{ margin-top: 1rem; padding: 0.8rem; background: var(--card); border-radius: 8px; border: 1px solid var(--border); font-size: 0.9rem; color: var(--muted); }}
  </style>
</head>
<body>
  <h1>选股复评报告</h1>
  <p class="meta">选股日期：{pick_date} · 评审总数：{total} · 推荐门槛：score ≥ {min_score} · 达标：{len(recs)} 只</p>
  <table>
    <thead>
      <tr>
        <th>排名</th>
        <th>代码</th>
        <th>总分</th>
        <th>信号</th>
        <th>研判</th>
        <th>日线图</th>
        <th>备注</th>
      </tr>
    </thead>
    <tbody>
"""
    for r in rows:
        html += f"""
      <tr>
        <td>{r["rank"]}</td>
        <td class="code">{r["code"]}</td>
        <td class="score">{r["score_str"]}</td>
        <td>{_escape(r["signal_type"])}</td>
        <td class="verdict">{_escape(r["verdict"])}</td>
        <td>{r["img_tag"]}</td>
        <td>{_escape(r["comment"])}</td>
      </tr>"""
    html += """
    </tbody>
  </table>
  <div class="excluded">未达门槛代码：""" + excluded_str + """</div>
</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser(description="导出复评结果为 HTML 报告")
    parser.add_argument("--suggestion", type=Path, help="suggestion.json 路径")
    parser.add_argument("--date", type=str, help="选股日期（与 --review-dir 配合，替代 --suggestion）")
    parser.add_argument("--review-dir", type=Path, help="review 输出根目录，默认从 config 读")
    parser.add_argument("--output", "-o", type=Path, help="输出 HTML 路径，默认与 suggestion 同目录 report.html")
    parser.add_argument("--no-embed", action="store_true", help="不内嵌图片，使用相对路径（便于大图）")
    parser.add_argument("--open", action="store_true", help="生成后在默认浏览器中打开")
    parser.add_argument("--config", type=Path, default=_ROOT / "config" / "review.yaml", help="统一配置（用于读 kline_dir/output_dir）")
    args = parser.parse_args()

    if args.suggestion:
        suggestion_path = Path(args.suggestion)
        out_dir = suggestion_path.parent
    elif args.date and args.review_dir:
        out_dir = Path(args.review_dir) / args.date
        suggestion_path = out_dir / "suggestion.json"
    else:
        try:
            config = load_review_config(args.config)
        except FileNotFoundError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        out_dir = config["output_dir"]
        # 需要 pick_date：从 candidates 或最新子目录推断
        candidates_path = config["candidates"]
        if candidates_path.exists():
            with open(candidates_path, encoding="utf-8") as f:
                pick_date = json.load(f).get("pick_date", "")
            if pick_date:
                out_dir = out_dir / pick_date
                suggestion_path = out_dir / "suggestion.json"
            else:
                print("[ERROR] candidates 中无 pick_date，请使用 --suggestion 或 --date + --review-dir", file=sys.stderr)
                sys.exit(1)
        else:
            # 取 output_dir 下最新一个日期目录
            subdirs = [d for d in config["output_dir"].iterdir() if d.is_dir()]
            if not subdirs:
                print("[ERROR] 未找到已有复评目录，请先运行复评或指定 --suggestion", file=sys.stderr)
                sys.exit(1)
            out_dir = max(subdirs, key=lambda d: d.name)
            suggestion_path = out_dir / "suggestion.json"
        if not suggestion_path.exists():
            print(f"[ERROR] 不存在: {suggestion_path}", file=sys.stderr)
            sys.exit(1)
    else:
        print("[ERROR] 请指定 --suggestion 或 --date + --review-dir，或确保 config 与 candidates 可用", file=sys.stderr)
        sys.exit(1)

    if not suggestion_path.exists():
        print(f"[ERROR] 不存在: {suggestion_path}", file=sys.stderr)
        sys.exit(1)

    try:
        cfg = load_review_config(args.config)
        kline_dir = cfg["kline_dir"]
    except Exception:
        kline_dir = out_dir.parent.parent / "kline"  # 默认 data/kline

    with open(suggestion_path, encoding="utf-8") as f:
        suggestion = json.load(f)

    embed_images = not args.no_embed
    html = build_html(suggestion, out_dir, kline_dir, embed_images=embed_images)

    out_html = args.output or (out_dir / "report.html")
    out_html = Path(out_html)
    out_html.write_text(html, encoding="utf-8")
    print(f"[INFO] 已生成: {out_html}")

    if args.open:
        import webbrowser
        webbrowser.open(out_html.as_uri())
    return out_html


def export_to_html(
    suggestion_path: Path,
    out_dir: Path,
    kline_dir: Path,
    output_path: Path | None = None,
    embed_images: bool = True,
    open_browser: bool = False,
) -> Path:
    """供复评流程或其它脚本调用：根据 suggestion.json 生成 report.html。"""
    with open(suggestion_path, encoding="utf-8") as f:
        suggestion = json.load(f)
    html = build_html(suggestion, out_dir, kline_dir, embed_images=embed_images)
    out_html = output_path or (out_dir / "report.html")
    out_html = Path(out_html)
    out_html.write_text(html, encoding="utf-8")
    if open_browser:
        import webbrowser
        webbrowser.open(out_html.as_uri())
    return out_html
</think>
简化 HTML 结构，去掉有问题的 detail 行，改为仅展示主表与日线图。
<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
StrReplace