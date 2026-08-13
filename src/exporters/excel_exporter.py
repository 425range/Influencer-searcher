from pathlib import Path
import pandas as pd


def _format_sheet(writer, sheet_name):
    ws = writer.book[sheet_name]
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cells in ws.columns:
        letter = cells[0].column_letter
        max_len = max(len(str(c.value)) if c.value is not None else 0 for c in cells)
        ws.column_dimensions[letter].width = min(max(max_len + 2, 10), 45)


def export(candidates_rows, reels_rows, rejected_rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    cdf = pd.DataFrame(candidates_rows)
    rdf = pd.DataFrame(reels_rows)
    xdf = pd.DataFrame(rejected_rows)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        cdf.to_excel(writer, sheet_name="Candidates", index=False)
        _format_sheet(writer, "Candidates")

        rdf.to_excel(writer, sheet_name="Reels", index=False)
        _format_sheet(writer, "Reels")

        xdf.to_excel(writer, sheet_name="Rejected", index=False)
        _format_sheet(writer, "Rejected")
