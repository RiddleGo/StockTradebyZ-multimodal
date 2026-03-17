"""
pipeline/cli.py — 统一命令行入口。
用法：python -m pipeline.cli preselect
"""
from __future__ import annotations

import argparse
import datetime
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.select_stock import run_preselect, resolve_preselect_output_dir
from pipeline.schemas import CandidateRun
from pipeline.pipeline_io import save_candidates

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("cli")


def cmd_preselect(args: argparse.Namespace) -> None:
    logger.info("===== 量化初选开始 =====")
    pick_ts, candidates = run_preselect(
        config_path=args.config or None,
        data_dir=args.data or None,
        end_date=args.end_date or None,
        pick_date=args.date or None,
    )
    pick_date_str = pick_ts.strftime("%Y-%m-%d")
    run_date_str = datetime.date.today().isoformat()
    run = CandidateRun(run_date=run_date_str, pick_date=pick_date_str, candidates=candidates, meta={"config": args.config, "data_dir": args.data, "total": len(candidates)})
    resolved_output_dir = resolve_preselect_output_dir(config_path=args.config or None, output_dir=args.output or None)
    paths = save_candidates(run, candidates_dir=resolved_output_dir)
    logger.info("===== 初选完成 =====")
    logger.info("选股日期 : %s", pick_date_str)
    logger.info("候选数量 : %d 只", len(candidates))
    for key, path in paths.items():
        logger.info("%-8s → %s", key, path)
    if candidates:
        print(f"\n{'代码':>8} {'策略':>6} {'收盘价':>8} {'砖型增长':>10}")
        print("-" * 44)
        for c in candidates:
            bg = f"{c.brick_growth:.2f}x" if c.brick_growth is not None else " —"
            print(f"{c.code:>8} {c.strategy:>6} {c.close:>8.2f} {bg:>10}")
    else:
        print("\n(今日无候选股票)")


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline.cli", description="AgentTrader 量化初选 CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("preselect", help="运行量化初选")
    p.add_argument("--config", default=None, help="rules_preselect.yaml 路径")
    p.add_argument("--data", default=None, help="CSV 数据目录")
    p.add_argument("--date", default=None, help="选股基准日期 YYYY-MM-DD")
    p.add_argument("--end-date", dest="end_date", default=None, help="数据截断日期")
    p.add_argument("--output", default=None, help="候选输出目录")
    p.add_argument("--log-dir", dest="log_dir", default=None, help="流水日志目录")
    args = parser.parse_args()
    if args.command == "preselect":
        cmd_preselect(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
