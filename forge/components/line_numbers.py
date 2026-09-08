import customtkinter as ctk


class LineNumbers(ctk.CTkCanvas):
    def __init__(self, master, code_editor, font, **kwargs):
        super().__init__(master, **kwargs)
        self.code_editor = code_editor
        self.font = font
        self.configure(width=55, bg="#2b2b2b", highlightthickness=0)

        self.bind("<Button-1>", self.on_click)

    def on_click(self, event):
        y = self.canvasy(event.y)
        clicked_items = self.find_overlapping(event.x, y, event.x, y)
        for item_id in clicked_items:
            tags = self.gettags(item_id)
            if "fold_marker" in tags and len(tags) > 1:
                try:
                    lineno = int(tags[1].split("_")[1])
                    self.code_editor.actions.toggle_fold(lineno)
                    break
                except (ValueError, IndexError):
                    continue

    def redraw(self, top_doc_line, folding_markers={}, folded_lines=set()):
        self.delete("all")
        if not self.code_editor.winfo_exists():
            return

        y = self.code_editor.y_padding
        height = self.winfo_height()
        doc_line_idx = top_doc_line

        while y < height and doc_line_idx < len(self.code_editor.doc.lines):
            line_num_to_display = doc_line_idx + 1

            if doc_line_idx in folding_markers:
                marker_char = "▶" if doc_line_idx in folded_lines else "▼"
                marker_id = self.create_text(
                    20, y, anchor="nw", text=marker_char, fill="#777777", font=self.font
                )
                self.itemconfig(
                    marker_id, tags=("fold_marker", f"line_{line_num_to_display}")
                )

            self.create_text(
                50,
                y,
                anchor="ne",
                text=str(line_num_to_display),
                fill="#777777",
                font=self.font,
            )

            y += self.code_editor.line_height

            if doc_line_idx in folded_lines and doc_line_idx in folding_markers:
                doc_line_idx = folding_markers[doc_line_idx]["end_lineno"] + 1
            else:
                doc_line_idx += 1
