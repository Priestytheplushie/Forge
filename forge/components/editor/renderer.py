from pygments import lex
from .layout_manager import VisualLine


class EditorRenderer:
    def __init__(self, editor_view):
        self.editor = editor_view
        self.doc = editor_view.doc
        self.canvas = editor_view.canvas
        self.font = editor_view.font
        self.layout_manager = editor_view.layout_manager
        self.visible_layout = []

    def redraw(self):
        text_pool_idx, rect_pool_idx, line_pool_idx = 0, 0, 0

        self.generate_visible_layout()

        num_visual_lines = len(self.visible_layout)
        height = self.canvas.winfo_height()
        visible_v_lines_on_screen = (
            height 
        )

        total_doc_lines = len(self.doc.lines)
        if total_doc_lines > visible_v_lines_on_screen:
            content_fraction = visible_v_lines_on_screen / total_doc_lines
            start_pos = self.editor.top_line / total_doc_lines
            self.editor.v_scrollbar.set(start_pos, start_pos + content_fraction)
        else:
            self.editor.v_scrollbar.set(0, 1)

        start_pos, end_pos = self.editor._get_selection_range()
        max_line_width = 0

        y = self.editor.y_padding
        for visual_line in self.visible_layout:
            doc_line_idx, line_content = (
                visual_line.doc_line_num,
                self.doc.lines[visual_line.doc_line_num],
            )
            max_line_width = max(max_line_width, self.font.measure(line_content))

            if start_pos:
                rect_pool_idx = self._draw_selection_for_visual_line(
                    visual_line, y, start_pos, end_pos, rect_pool_idx
                )

            if visual_line.start_col == 0:
                indent_space = len(line_content) - len(line_content.lstrip(" "))
                for i in range(1, (indent_space 
                    guide_x = (
                        5 + self.font.measure(" " * (i * 4)) - self.editor.x_offset
                    )
                    if guide_x > 0:
                        line_pool_idx = self._draw_pooled_line(
                            line_pool_idx,
                            guide_x,
                            y,
                            guide_x,
                            y + self.editor.line_height,
                            fill="#404040",
                        )

            if (
                doc_line_idx in self.editor._syntax_cache
                and self.editor._syntax_cache[doc_line_idx]["text"] == line_content
            ):
                lexed_tokens = self.editor._syntax_cache[doc_line_idx]["tokens"]
            else:
                lexed_tokens = list(lex(line_content, self.editor.lexer))
                self.editor._syntax_cache[doc_line_idx] = {
                    "text": line_content,
                    "tokens": lexed_tokens,
                }

            col_offset = 0
            for token, text in lexed_tokens:
                start_tok_col, end_tok_col = col_offset, col_offset + len(text)
                if (
                    start_tok_col < visual_line.start_col + len(visual_line.text)
                    and end_tok_col > visual_line.start_col
                ):
                    draw_start = max(visual_line.start_col, start_tok_col)
                    draw_end = min(
                        visual_line.start_col + len(visual_line.text), end_tok_col
                    )
                    draw_text = line_content[draw_start:draw_end]
                    if not draw_text:
                        continue
                    color = self.editor.tag_colors.get(str(token), "white")
                    x_pos = (
                        5
                        - self.editor.x_offset
                        + self.font.measure(line_content[:draw_start])
                    )
                    text_pool_idx = self._draw_pooled_text(
                        text_pool_idx, x_pos, y, draw_text, color
                    )
                col_offset += len(text)

            line_pool_idx = self._draw_diagnostics_for_visual_line(
                visual_line, y, line_pool_idx
            )
            y += self.editor.line_height

        self._hide_unused_pool_items(text_pool_idx, self.editor._text_item_pool)
        self._hide_unused_pool_items(rect_pool_idx, self.editor._rect_item_pool)
        self._hide_unused_pool_items(line_pool_idx, self.editor._line_item_pool)

        width = self.canvas.winfo_width()
        if not self.editor.word_wrap and max_line_width > width and max_line_width > 0:
            content_fraction = width / max_line_width
            start_pos = self.editor.x_offset / max_line_width
            self.editor.h_scrollbar.set(start_pos, start_pos + content_fraction)
        else:
            self.editor.h_scrollbar.set(0, 1)

        cursor_coords = self.get_cursor_screen_coords()
        if cursor_coords[0] is not None and cursor_coords[1] is not None:
            self.canvas.coords(
                self.editor.cursor_obj,
                cursor_coords[0],
                cursor_coords[1],
                cursor_coords[0],
                cursor_coords[1] + self.editor.line_height,
            )
            self.canvas.lift(self.editor.cursor_obj)
            self.canvas.itemconfigure(self.editor.cursor_obj, state="normal")
        else:
            self.canvas.itemconfigure(self.editor.cursor_obj, state="hidden")

        self.editor.line_numbers.redraw(
            self.editor.top_line, self.editor.folding_markers, self.editor._folded_lines
        )

    def generate_visible_layout(self):
        self.visible_layout.clear()
        doc_line_idx = self.editor.top_line
        y = self.editor.y_padding
        height = self.canvas.winfo_height()
        width = self.canvas.winfo_width()

        while doc_line_idx < len(self.doc.lines) and y < height:
            if doc_line_idx in self.editor._folded_lines:
                line_text = self.doc.lines[doc_line_idx]
                placeholder = (
                    line_text[: line_text.find(":") + 1] + " ... "
                    if ":" in line_text
                    else line_text.split()[0] + " ... " if line_text.split() else "..."
                )
                self.visible_layout.append(VisualLine(placeholder, doc_line_idx, 0))
                y += self.editor.line_height
                doc_line_idx = (
                    self.editor.folding_markers.get(doc_line_idx, {}).get(
                        "end_lineno", doc_line_idx
                    )
                    + 1
                )
                continue

            line_text = self.doc.lines[doc_line_idx]
            if not self.editor.word_wrap or not line_text:
                self.visible_layout.append(VisualLine(line_text, doc_line_idx, 0))
                y += self.editor.line_height
            else:
                current_col = 0
                while current_col < len(line_text):
                    fit_index = self.layout_manager._find_fit_index(
                        line_text, current_col, width - 10
                    )
                    self.visible_layout.append(
                        VisualLine(
                            line_text[current_col:fit_index], doc_line_idx, current_col
                        )
                    )
                    current_col = fit_index
                    y += self.editor.line_height

            doc_line_idx += 1

    def get_visual_line_idx_for_pos(self, doc_line, doc_col):
        for i, v_line in enumerate(self.visible_layout):
            if v_line.doc_line_num == doc_line:
                if v_line.start_col <= doc_col <= v_line.start_col + len(v_line.text):
                    return i
        return -1

    def get_cursor_screen_coords(self):
        line, col = self.editor.cursor_pos
        v_idx = self.get_visual_line_idx_for_pos(line, col)
        if v_idx != -1:
            visual_line = self.visible_layout[v_idx]
            col_in_chunk = col - visual_line.start_col
            x = (
                5
                - self.editor.x_offset
                + self.font.measure(visual_line.text[:col_in_chunk])
            )
            y = (v_idx * self.editor.line_height) + self.editor.y_padding
            return x, y
        return None, None

    def screen_to_doc_pos(self, x, y):
        v_line_idx = (
            int((y - self.editor.y_padding) 
            if self.editor.line_height > 0
            else 0
        )
        v_line_idx = min(v_line_idx, len(self.visible_layout) - 1)
        v_line_idx = max(0, v_line_idx)
        if not self.visible_layout:
            return 0, 0

        visual_line = self.visible_layout[v_line_idx]
        logical_x = x + self.editor.x_offset
        col_in_chunk = 0
        min_dist = float("inf")
        for i in range(len(visual_line.text) + 1):
            dist = abs(self.font.measure(visual_line.text[:i]) - logical_x + 5)
            if dist < min_dist:
                min_dist = dist
                col_in_chunk = i
        return visual_line.doc_line_num, visual_line.start_col + col_in_chunk

    def _draw_pooled_text(self, pool_idx, x, y, text, fill):
        if pool_idx >= len(self.editor._text_item_pool):
            self.editor._text_item_pool.append(
                self.canvas.create_text(0, 0, anchor="nw", font=self.font)
            )
        item_id = self.editor._text_item_pool[pool_idx]
        self.canvas.coords(item_id, x, y)
        self.canvas.itemconfig(item_id, text=text, fill=fill)
        return pool_idx + 1

    def _draw_pooled_rect(self, pool_idx, x1, y1, x2, y2, **kwargs):
        if pool_idx >= len(self.editor._rect_item_pool):
            self.editor._rect_item_pool.append(
                self.canvas.create_rectangle(0, 0, 0, 0, outline="")
            )
        item_id = self.editor._rect_item_pool[pool_idx]
        self.canvas.coords(item_id, x1, y1, x2, y2)
        self.canvas.itemconfig(item_id, **kwargs)
        return pool_idx + 1

    def _draw_pooled_line(self, pool_idx, *coords, **kwargs):
        if pool_idx >= len(self.editor._line_item_pool):
            self.editor._line_item_pool.append(self.canvas.create_line(0, 0, 0, 0))
        item_id = self.editor._line_item_pool[pool_idx]
        self.canvas.coords(item_id, *coords)
        self.canvas.itemconfig(item_id, **kwargs)
        return pool_idx + 1

    def _hide_unused_pool_items(self, last_used_idx, pool):
        for i in range(last_used_idx, len(pool)):
            item_id = pool[i]
            item_type = self.canvas.type(item_id)
            if item_type in ("line", "rectangle"):
                self.canvas.coords(item_id, -100, -100, -100, -100)
            else:
                self.canvas.coords(item_id, -100, -100)
            if item_type == "text":
                self.canvas.itemconfig(item_id, text="")

    def _draw_selection_for_visual_line(
        self, v_line, y, sel_start, sel_end, rect_pool_idx
    ):
        v_start_pos, v_end_pos = (v_line.doc_line_num, v_line.start_col), (
            v_line.doc_line_num,
            v_line.start_col + len(v_line.text),
        )
        if not (sel_end > v_start_pos and sel_start < v_end_pos):
            return rect_pool_idx
        start_col = (
            max(sel_start[1], v_start_pos[1])
            if v_line.doc_line_num == sel_start[0]
            else v_start_pos[1]
        )
        end_col = (
            min(sel_end[1], v_end_pos[1])
            if v_line.doc_line_num == sel_end[0]
            else v_end_pos[1]
        )
        doc_line_text = self.doc.lines[v_line.doc_line_num]
        start_x = (
            self.font.measure(doc_line_text[:start_col]) + 5 - self.editor.x_offset
        )
        end_x = self.font.measure(doc_line_text[:end_col]) + 5 - self.editor.x_offset
        if end_x > start_x:
            rect_pool_idx = self._draw_pooled_rect(
                rect_pool_idx,
                start_x,
                y,
                end_x,
                y + self.editor.line_height,
                fill="#003366",
                stipple="gray50",
                outline="",
            )
        return rect_pool_idx

    def _draw_diagnostics_for_visual_line(self, visual_line, y, line_pool_idx):
        doc_line_idx = visual_line.doc_line_num
        line_diagnostics = [
            d
            for d in self.editor.diagnostics
            if d["range"]["start"]["line"] == doc_line_idx
        ]
        if not line_diagnostics:
            return line_pool_idx
        line_content = self.doc.lines[doc_line_idx]
        char_severities = {}
        for diag in line_diagnostics:
            s_char, e_char = (
                diag["range"]["start"]["character"],
                diag["range"]["end"]["character"],
            )
            severity, code, msg = (
                diag.get("severity", 4),
                diag.get("code", ""),
                diag.get("message", ""),
            )
            is_style = (
                any(str(code).startswith(sc) for sc in self.editor.style_hint_codes)
                or "line too long" in msg
            )
            is_unused = "unused" in msg.lower()
            effective_severity = 5 if is_unused else 4 if is_style else severity
            if s_char == e_char and e_char < len(line_content):
                e_char += 1
            for i in range(s_char, e_char):
                if effective_severity < char_severities.get(i, {}).get("severity", 99):
                    char_severities[i] = {"severity": effective_severity}
        if not char_severities:
            return line_pool_idx
        sorted_chars = sorted(char_severities.keys())
        start_char, current_sev = sorted_chars[0], char_severities[sorted_chars[0]]
        for i in range(1, len(sorted_chars)):
            char = sorted_chars[i]
            if char != sorted_chars[i - 1] + 1 or char_severities[char] != current_sev:
                line_pool_idx = self._draw_diag_range(
                    line_content,
                    y,
                    start_char,
                    sorted_chars[i - 1] + 1,
                    current_sev,
                    visual_line,
                    line_pool_idx,
                )
                start_char, current_sev = char, char_severities[char]
        line_pool_idx = self._draw_diag_range(
            line_content,
            y,
            start_char,
            sorted_chars[-1] + 1,
            current_sev,
            visual_line,
            line_pool_idx,
        )
        return line_pool_idx

    def _draw_diag_range(
        self,
        line_content,
        y,
        start_char,
        end_char,
        sev_info,
        visual_line,
        line_pool_idx,
    ):
        v_line_start, v_line_end = visual_line.start_col, visual_line.start_col + len(
            visual_line.text
        )
        draw_start, draw_end = max(start_char, v_line_start), min(end_char, v_line_end)
        if draw_start >= draw_end:
            return line_pool_idx
        severity = sev_info["severity"]
        style, color = "solid", "#F44747"
        if severity == 2:
            color = "#FFD700"
        elif severity == 3:
            color = "#569CD6"
            style = "dotted"
        elif severity == 4:
            color = "#808080"
            style = "dotted"
        elif severity == 5:
            color = None
        if color:
            x1 = self.font.measure(line_content[:draw_start]) + 5 - self.editor.x_offset
            x2 = self.font.measure(line_content[:draw_end]) + 5 - self.editor.x_offset
            return self._draw_squiggly_pooled(
                line_pool_idx, x1, y + self.editor.line_height - 1, x2, color, style
            )
        return line_pool_idx

    def _draw_squiggly_pooled(self, line_pool_idx, x1, y1, x2, color, style="solid"):
        if not color or x1 >= x2:
            return line_pool_idx
        if style == "solid":
            points = []
            amplitude = 1.5
            wavelength = 4
            x = x1
            direction = 1
            while x < x2:
                points.extend((x, y1))
                x_next = x + wavelength / 2
                if x_next > x2:
                    points.extend((x2, y1))
                    break
                points.extend((x_next, y1 + amplitude * direction))
                x += wavelength
                direction *= -1
            if len(points) > 2:
                return self._draw_pooled_line(
                    line_pool_idx, *points, fill=color, width=1.0
                )
        elif style == "dotted":
            return self._draw_pooled_line(
                line_pool_idx, x1, y1, x2, y1, fill=color, width=1.5, dash=(2, 3)
            )
        return line_pool_idx
