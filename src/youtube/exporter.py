from pathlib import Path
import pandas as pd


def export_excel(channel_rows, video_rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    channels = pd.DataFrame(channel_rows)
    videos = pd.DataFrame(video_rows)

    if not channels.empty:
        channels = channels.sort_values(
            ["score", "subscribers"],
            ascending=[False, False],
        )
        channels["review_status"] = ""
        channels["reject_reason"] = ""
        channels["reviewer_note"] = ""

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        channels.to_excel(writer, sheet_name="Channels", index=False)
        videos.to_excel(writer, sheet_name="Videos", index=False)

        for sheet in writer.book.sheetnames:
            ws = writer.book[sheet]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for cells in ws.columns:
                letter = cells[0].column_letter
                max_len = max(
                    len(str(c.value)) if c.value is not None else 0
                    for c in cells
                )
                ws.column_dimensions[letter].width = min(
                    max(max_len + 2, 10), 55
                )
