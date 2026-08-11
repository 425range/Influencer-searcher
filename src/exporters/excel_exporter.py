from pathlib import Path
import pandas as pd


def export_candidates(rows: list[dict], path: str):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows)

    if "score" in df.columns:
        df = df.sort_values("score", ascending=False)

    # Human review columns are deliberately part of the output.
    if "review_status" not in df.columns:
        df["review_status"] = ""
    if "reject_reason" not in df.columns:
        df["reject_reason"] = ""
    if "reviewer_note" not in df.columns:
        df["reviewer_note"] = ""

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Candidates", index=False)

        ws = writer.book["Candidates"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        for col_cells in ws.columns:
            max_len = 0
            for cell in col_cells:
                value = "" if cell.value is None else str(cell.value)
                max_len = max(max_len, len(value))
            width = min(max(max_len + 2, 10), 45)
            ws.column_dimensions[col_cells[0].column_letter].width = width
