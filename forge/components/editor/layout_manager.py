from collections import namedtuple

VisualLine = namedtuple("VisualLine", ["text", "doc_line_num", "start_col"])


class LineLayoutManager:
    def __init__(self, font):
        self.font = font
        self.visual_lines = []

    def calculate_layout(self, document_lines, canvas_width, word_wrap):
        self.visual_lines.clear()
        if not word_wrap or canvas_width <= 0:
            for i, line_text in enumerate(document_lines):
                self.visual_lines.append(VisualLine(line_text, i, 0))
            return

        for doc_line_num, line_text in enumerate(document_lines):
            if not line_text:
                self.visual_lines.append(VisualLine("", doc_line_num, 0))
                continue

            current_col = 0
            while current_col < len(line_text):
                fit_index = self._find_fit_index(line_text, current_col, canvas_width)
                self.visual_lines.append(
                    VisualLine(
                        line_text[current_col:fit_index], doc_line_num, current_col
                    )
                )
                current_col = fit_index

    def _find_fit_index(self, text, start_index, max_width):
        if self.font.measure(text[start_index:]) <= max_width:
            return len(text)

        end_index = start_index
        last_space = -1
        while end_index < len(text):
            if self.font.measure(text[start_index : end_index + 1]) > max_width:
                break
            if text[end_index].isspace():
                last_space = end_index + 1
            end_index += 1

        if last_space != -1:
            return last_space
        return end_index if end_index > start_index else start_index + 1
