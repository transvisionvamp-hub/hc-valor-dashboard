#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import numbers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.analysis import AnalysisEngine
from src.read_data import DataLoader


COMPANY = "HCバロー"
OUTPUT_PATH = PROJECT_DIR / "web" / "dashboard_data.json"


def fiscal_year(yyyymm: str) -> int:
    year, month = int(yyyymm[:4]), int(yyyymm[4:])
    return year if month >= 4 else year - 1


def json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, numbers.Real):
        number = float(value)
        if not math.isfinite(number):
            return None
        return int(number) if number.is_integer() else number
    return value


def aggregate_month(data: pd.DataFrame, month: str) -> dict[str, Any]:
    frame = data[data["年月"].astype(str).eq(month)]
    if frame.empty:
        return {"sales": None, "gross_profit": None, "gross_margin": None}
    sales = pd.to_numeric(frame["売上"], errors="coerce").sum()
    gross = pd.to_numeric(frame["粗利"], errors="coerce").sum()
    return {
        "sales": json_value(sales),
        "gross_profit": json_value(gross),
        "gross_margin": json_value(gross / sales if sales else None),
    }


def dimension_top10(
    data: pd.DataFrame, latest_month: str, previous_year_month: str, dimension: str
) -> list[dict[str, Any]]:
    latest = data[data["年月"].astype(str).eq(latest_month)]
    previous = data[data["年月"].astype(str).eq(previous_year_month)]
    if latest.empty:
        return []

    group_columns = [dimension]
    if dimension == "商品名":
        group_columns.append("JANコード")

    current = latest.groupby(group_columns, dropna=False, as_index=False).agg(
        sales=("売上", "sum"), gross_profit=("粗利", "sum")
    )
    prior = previous.groupby(group_columns, dropna=False, as_index=False).agg(
        previous_sales=("売上", "sum")
    )
    merged = current.merge(prior, on=group_columns, how="left")
    merged["previous_sales"] = merged["previous_sales"].fillna(0)
    merged["gross_margin"] = merged["gross_profit"].div(
        merged["sales"].replace(0, pd.NA)
    )
    merged["sales_yoy"] = merged["sales"] - merged["previous_sales"]
    merged = merged.sort_values("sales", ascending=False).head(10)

    records: list[dict[str, Any]] = []
    for row in merged.to_dict("records"):
        record = {
            "name": str(row.get(dimension, "") or "").strip(),
            "sales": json_value(row.get("sales")),
            "gross_profit": json_value(row.get("gross_profit")),
            "gross_margin": json_value(row.get("gross_margin")),
            "sales_yoy": json_value(row.get("sales_yoy")),
        }
        if dimension == "商品名":
            jan = row.get("JANコード", "")
            record["jan"] = "" if pd.isna(jan) else str(jan).strip()
        records.append(record)
    return records


def build_insights(
    month: str,
    kpi: dict[str, Any],
    manufacturers: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> list[str]:
    insights: list[str] = []
    month_label = f"{int(month[4:])}月"
    sales_yoy = kpi.get("sales_yoy")
    margin_yoy = kpi.get("gross_margin_yoy")
    if sales_yoy is not None and margin_yoy is not None:
        sales_text = "上回った" if sales_yoy >= 0 else "下回った"
        margin_text = "改善" if margin_yoy >= 0 else "悪化"
        insights.append(
            f"{month_label}の売上は前年を{sales_text}。粗利率は前年から"
            f"{abs(margin_yoy):.1%}ポイント{margin_text}。"
        )
    if manufacturers:
        increased = max(manufacturers, key=lambda item: item.get("sales_yoy") or 0)
        decreased = min(manufacturers, key=lambda item: item.get("sales_yoy") or 0)
        insights.append(
            f"主要メーカーでは、最大増収が{increased['name']}、"
            f"最大減収が{decreased['name']}。"
        )
    if products:
        insights.append(f"売上上位商品は{products[0]['name']}。")
    return insights


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        loader = DataLoader(PROJECT_DIR / "input")
        report_data = loader.load_report_across()
        plan_data = loader.load_company_plan()
        engine = AnalysisEngine(report_data, plan_data)
        actual = engine.extract_company(COMPANY).copy()
    except Exception as exc:
        print(f"データ読み込みエラー: {exc}", file=sys.stderr)
        actual = pd.DataFrame()
        plan_data = pd.DataFrame()

    if actual.empty:
        payload = {
            "meta": {
                "company": COMPANY,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "latest_month": None,
                "period_start": None,
                "period_end": None,
            },
            "kpi": {
                key: None
                for key in (
                    "sales",
                    "gross_profit",
                    "gross_margin",
                    "sales_yoy",
                    "gross_profit_yoy",
                    "gross_margin_yoy",
                    "sales_plan",
                    "achievement_rate",
                )
            },
            "fiscal_comparison": [],
            "manufacturer_top10": [],
            "product_top10": [],
            "insights": [],
        }
    else:
        months = sorted(actual["年月"].dropna().astype(str).unique())
        latest_month = months[-1]
        previous_year_month = f"{int(latest_month[:4]) - 1}{latest_month[4:]}"
        current = aggregate_month(actual, latest_month)
        previous = aggregate_month(actual, previous_year_month)
        month_name = f"{int(latest_month[4:])}月"
        plan_row = plan_data[
            plan_data["企業名"].astype(str).eq(COMPANY)
            & plan_data["月"].astype(str).eq(month_name)
        ] if not plan_data.empty else pd.DataFrame()
        sales_plan = (
            pd.to_numeric(plan_row["売上計画"], errors="coerce").sum()
            if not plan_row.empty
            else None
        )
        kpi = {
            "sales": current["sales"],
            "gross_profit": current["gross_profit"],
            "gross_margin": current["gross_margin"],
            "sales_yoy": json_value(
                current["sales"] - previous["sales"]
                if current["sales"] is not None and previous["sales"] is not None
                else None
            ),
            "gross_profit_yoy": json_value(
                current["gross_profit"] - previous["gross_profit"]
                if current["gross_profit"] is not None
                and previous["gross_profit"] is not None
                else None
            ),
            "gross_margin_yoy": json_value(
                current["gross_margin"] - previous["gross_margin"]
                if current["gross_margin"] is not None
                and previous["gross_margin"] is not None
                else None
            ),
            "sales_plan": json_value(sales_plan),
            "achievement_rate": json_value(
                current["sales"] / sales_plan
                if current["sales"] is not None and sales_plan
                else None
            ),
        }
        fiscal_years = sorted({fiscal_year(month) for month in months})[-2:]
        comparison = []
        for month_number in range(4, 13):
            item: dict[str, Any] = {
                "month": f"{month_number}月",
                "month_number": month_number,
            }
            has_data = False
            for year in fiscal_years:
                yyyymm = f"{year if month_number >= 4 else year + 1}{month_number:02d}"
                values = aggregate_month(actual, yyyymm)
                item[f"{year}年度"] = values
                has_data = has_data or values["sales"] is not None
            if has_data:
                comparison.append(item)

        manufacturers = dimension_top10(
            actual, latest_month, previous_year_month, "メーカー名"
        )
        products = dimension_top10(
            actual, latest_month, previous_year_month, "商品名"
        )
        payload = {
            "meta": {
                "company": COMPANY,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "latest_month": latest_month,
                "period_start": months[0],
                "period_end": months[-1],
            },
            "kpi": kpi,
            "fiscal_comparison": comparison,
            "manufacturer_top10": manufacturers,
            "product_top10": products,
            "insights": build_insights(
                latest_month, kpi, manufacturers, products
            ),
        }

    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"ダッシュボードデータを生成しました: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
