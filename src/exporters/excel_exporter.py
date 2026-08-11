from pathlib import Path
import pandas as pd


def export(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(
            ["score", "followers"],
            ascending=[False, False]
        )

    for col in ["review_status", "reject_reason", "reviewer_note"]:
        if col not in df.columns:
            df[col] = ""

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Candidates", index=False)

        ws = writer.book["Candidates"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        for cells in ws.columns:
            letter = cells[0].column_letter
            max_len = max(
                len(str(c.value)) if c.value is not None else 0
                for c in cells
            )
            ws.column_dimensions[letter].width = min(max(max_len + 2, 10), 45)
