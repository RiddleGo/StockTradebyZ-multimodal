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
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

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


# 单股详情 JSON 字段中文标签与信号类型映射
_SCORE_LABELS = {
    "trend_structure": "趋势结构",
    "price_position": "价格位置",
    "volume_behavior": "量价行为",
    "previous_abnormal_move": "前期异动",
}
_SIGNAL_LABELS = {
    "trend_start": "主升启动",
    "rebound": "跌后反弹",
    "distribution_risk": "出货风险",
}
_VERDICT_LABELS = {"PASS": "通过", "WATCH": "观察", "FAIL": "不通过"}


def _render_detail_html(detail_data: dict) -> str:
    """将单股评分 JSON 渲染为结构化、易读的 HTML 卡片。"""
    if not detail_data or not isinstance(detail_data, dict):
        return ""
    scores = detail_data.get("scores") or {}
    total = detail_data.get("total_score")
    signal_type = detail_data.get("signal_type", "")
    verdict = detail_data.get("verdict", "")
    comment = detail_data.get("comment", "")
    parts = []

    # 维度得分：进度条 + 分数
    parts.append('<div class="detail-panel"><div class="detail-section"><span class="detail-section-title">维度得分</span><div class="detail-scores">')
    for key, label in _SCORE_LABELS.items():
        val = scores.get(key)
        if val is None:
            continue
        pct = min(100, max(0, int(val) * 20))
        parts.append(f'<div class="detail-score-item"><span class="detail-score-label">{_escape(label)}</span><div class="detail-score-bar"><div class="detail-score-fill" style="width:{pct}%"></div></div><span class="detail-score-num">{val}</span></div>')
    if total is not None:
        parts.append(f'<div class="detail-score-item detail-total"><span class="detail-score-label">总分</span><span class="detail-score-num accent">{total}</span></div>')
    parts.append("</div></div>")

    # 推理过程（若有）
    reason_keys = [
        ("trend_reasoning", "趋势推理"),
        ("position_reasoning", "位置推理"),
        ("volume_reasoning", "量价推理"),
        ("abnormal_move_reasoning", "异动推理"),
        ("signal_reasoning", "信号推理"),
    ]
    for key, title in reason_keys:
        text = detail_data.get(key)
        if not text or not str(text).strip():
            continue
        parts.append(f'<div class="detail-section"><span class="detail-section-title">{_escape(title)}</span><p class="detail-reasoning">{_escape(str(text).strip())}</p></div>')

    # 结论行：信号 + 研判 + 点评
    parts.append('<div class="detail-section detail-conclusion">')
    parts.append(f'<span class="detail-badge signal">{_escape(_SIGNAL_LABELS.get(signal_type, signal_type))}</span>')
    parts.append(f'<span class="detail-badge verdict">{_escape(_VERDICT_LABELS.get(verdict, verdict))}</span>')
    if comment:
        parts.append(f'<p class="detail-comment">{_escape(comment)}</p>')
    parts.append("</div></div>")
    return "".join(parts)


def build_html(
    suggestion: dict,
    out_dir: Path,
    kline_dir: Path,
    embed_images: bool = True,
    generated_at: str | None = None,
) -> str:
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

        detail_rendered = ""
        detail_fallback = ""
        detail_file = out_dir / f"{code}.json"
        if detail_file.exists():
            try:
                with open(detail_file, encoding="utf-8") as f:
                    detail_data = json.load(f)
                detail_rendered = _render_detail_html(detail_data)
                detail_fallback = _escape(json.dumps(detail_data, ensure_ascii=False, indent=2))
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
            "detail_rendered": detail_rendered,
            "detail_fallback": detail_fallback,
        })

    excluded_str = "、".join(excluded) if excluded else "无"
    codes_js = json.dumps([r["code"] for r in rows], ensure_ascii=False)
    csv_rows_js = json.dumps([
        [r["rank"], r["code"], r["score_str"], r["signal_type"], r["verdict"], r["comment"]]
        for r in rows
    ], ensure_ascii=False)

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
    .meta {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 0.5rem; }}
    .toolbar {{ margin-bottom: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }}
    .toolbar button {{ padding: 0.4rem 0.8rem; border-radius: 6px; border: 1px solid var(--border); background: var(--card); color: var(--text); cursor: pointer; font-size: 0.9rem; }}
    .toolbar button:hover {{ background: #252528; }}
    .toolbar button.primary {{ background: var(--accent); color: #0f0f12; border-color: var(--accent); }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }}
    th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ background: #252528; color: var(--muted); font-weight: 600; font-size: 0.85rem; }}
    tr:last-child td {{ border-bottom: none; }}
    tr.data-row {{ cursor: pointer; }}
    tr.data-row:hover {{ background: #222225; }}
    tr.detail-row td {{ background: #1e1e22; padding: 0.8rem 1rem; border-bottom: 1px solid var(--border); vertical-align: top; }}
    .detail-panel {{ max-width: 720px; }}
    .detail-section {{ margin-bottom: 0.75rem; }}
    .detail-section:last-child {{ margin-bottom: 0; }}
    .detail-section-title {{ display: block; font-size: 0.75rem; color: var(--muted); margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .detail-scores {{ display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; align-items: center; }}
    .detail-score-item {{ display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; }}
    .detail-score-item.detail-total {{ margin-left: 0.5rem; }}
    .detail-score-label {{ min-width: 4.2em; color: var(--muted); }}
    .detail-score-bar {{ width: 64px; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }}
    .detail-score-fill {{ height: 100%; background: var(--accent); border-radius: 3px; transition: width 0.2s; }}
    .detail-score-num {{ font-weight: 600; min-width: 1.2em; }}
    .detail-score-num.accent {{ color: var(--accent); }}
    .detail-reasoning {{ margin: 0; font-size: 0.85rem; line-height: 1.5; color: var(--text); }}
    .detail-conclusion {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; }}
    .detail-badge {{ font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; }}
    .detail-badge.signal {{ background: #1e3a2f; color: #4ade80; border: 1px solid #22c55e; }}
    .detail-badge.verdict {{ background: #252528; color: var(--text); border: 1px solid var(--border); }}
    .detail-comment {{ margin: 0.35rem 0 0; width: 100%; font-size: 0.9rem; color: var(--text); line-height: 1.5; }}
    .detail-content {{ font-size: 0.8rem; color: var(--muted); white-space: pre-wrap; max-height: 12em; overflow-y: auto; font-family: ui-monospace, monospace; }}
    .code {{ font-weight: 600; font-family: ui-monospace, monospace; }}
    .score {{ color: var(--accent); font-weight: 600; }}
    .verdict {{ font-size: 0.9rem; }}
    .kline-img {{ max-width: 320px; max-height: 200px; display: block; border-radius: 4px; border: 1px solid var(--border); }}
    .excluded {{ margin-top: 1rem; padding: 0.8rem; background: var(--card); border-radius: 8px; border: 1px solid var(--border); font-size: 0.9rem; color: var(--muted); }}
    .disclaimer {{ margin-top: 1.5rem; padding: 0.8rem; font-size: 0.8rem; color: var(--muted); border-top: 1px solid var(--border); }}
  </style>
</head>
<body>
  <h1>选股复评报告</h1>
  <p class="meta">选股日期：{pick_date} · 评审总数：{total} · 推荐门槛：score ≥ {min_score} · 达标：{len(recs)} 只 · 生成时间：{generated_at}</p>
  <div class="toolbar">
    <button type="button" class="primary" onclick="copyCodes()">复制推荐代码</button>
    <button type="button" onclick="exportCsv()">导出 CSV</button>
  </div>
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
      <tr class="data-row" data-code="{_escape(r["code"])}" onclick="toggleDetail(this)">
        <td>{r["rank"]}</td>
        <td class="code">{r["code"]}</td>
        <td class="score">{r["score_str"]}</td>
        <td>{_escape(r["signal_type"])}</td>
        <td class="verdict">{_escape(r["verdict"])}</td>
        <td>{r["img_tag"]}</td>
        <td>{_escape(r["comment"])}</td>
      </tr>"""
        if r["detail_rendered"] or r["detail_fallback"]:
            content = r["detail_rendered"] if r["detail_rendered"] else f'<div class="detail-content">{r["detail_fallback"]}</div>'
            html += f"""
      <tr class="detail-row" style="display:none;"><td colspan="7"><div class="detail-panel-wrap">{content}</div></td></tr>"""
    html += """
    </tbody>
  </table>
  <div class="excluded">未达门槛代码：""" + excluded_str + """</div>
  <p class="disclaimer">本报告由程序自动生成，结果仅供参考，不构成任何投资建议。投资有风险，决策需谨慎。</p>
  <script>
    var RECOMMENDATION_CODES = """ + codes_js + """;
    var CSV_ROWS = """ + csv_rows_js + """;
    function copyCodes() {
      var text = RECOMMENDATION_CODES.join('\\n');
      navigator.clipboard.writeText(text).then(function() { alert('已复制 ' + RECOMMENDATION_CODES.length + ' 只代码到剪贴板'); }, function() { prompt('请手动复制', text); });
    }
    function exportCsv() {
      var header = '排名,代码,总分,信号,研判,备注\\n';
      var body = CSV_ROWS.map(function(r) { return r.map(function(c) { return '"' + String(c).replace(/"/g, '""') + '"'; }).join(','); }).join('\\n');
      var blob = new Blob(['\\ufeff' + header + body], { type: 'text/csv;charset=utf-8' });
      var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'recommendations.csv'; a.click(); URL.revokeObjectURL(a.href);
    }
    function toggleDetail(tr) {
      var next = tr.nextElementSibling;
      if (next && next.classList.contains('detail-row')) { next.style.display = next.style.display === 'none' ? '' : 'none'; }
    }
  </script>
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
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = build_html(suggestion, out_dir, kline_dir, embed_images=embed_images, generated_at=generated_at)

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
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = build_html(suggestion, out_dir, kline_dir, embed_images=embed_images, generated_at=generated_at)
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