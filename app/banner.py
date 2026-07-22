"""ASCII-баннер приложения: печать resources/rating_v2.txt с диагональным градиентом."""

import os
import sys


def print_banner() -> None:
    banner_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "rating_v2.txt")
    if not os.path.exists(banner_path):
        return
    try:
        with open(banner_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        if not lines:
            return

        max_w = max(len(line) for line in lines)
        max_h = len(lines)
        diagonal_coeff = 4.0
        max_val = (max_w - 1) + (max_h - 1) * diagonal_coeff

        colors = [
            (79, 70, 229),   # Indigo
            (147, 51, 234),  # Violet
            (236, 72, 153),  # Pink
        ]

        def get_gradient_color(t: float) -> tuple[int, int, int]:
            t = max(0.0, min(1.0, t))
            if t >= 1.0:
                return colors[-1]
            segment_size = 1.0 / (len(colors) - 1)
            segment_idx = int(t // segment_size)
            local_t = (t - (segment_idx * segment_size)) / segment_size
            c1 = colors[segment_idx]
            c2 = colors[segment_idx + 1]
            r = int(c1[0] + (c2[0] - c1[0]) * local_t)
            g = int(c1[1] + (c2[1] - c1[1]) * local_t)
            b = int(c1[2] + (c2[2] - c1[2]) * local_t)
            return r, g, b

        colored_lines = []
        for row_idx, line in enumerate(lines):
            colored_chars = []
            for col_idx, char in enumerate(line):
                if char.isspace():
                    colored_chars.append(char)
                else:
                    val = col_idx + row_idx * diagonal_coeff
                    t = val / max_val if max_val > 0 else 0
                    r, g, b = get_gradient_color(t)
                    colored_chars.append(f"\033[38;2;{r};{g};{b}m{char}\033[0m")
            colored_lines.append("".join(colored_chars))

        sys.stdout.write("\n".join(colored_lines) + "\n")
        sys.stdout.flush()
    except Exception:
        pass
