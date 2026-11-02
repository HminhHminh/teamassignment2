"""Summarize section 6 measurements produced by the team's monte_carlo CLI."""
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path


def svg_chart(path, title, x_label, y_label, series, log_x=False):
    width, height = 900, 540
    left, right, top, bottom = 90, 30, 70, 90
    plot_w, plot_h = width - left - right, height - top - bottom
    points = [(x, y) for values in series.values() for x, y in values if y > 0]
    if not points:
        return
    tx = (lambda x: math.log10(x)) if log_x else (lambda x: x)
    xs = [tx(x) for x, _ in points]
    ys = [y for _, y in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if xmin == xmax:
        xmax += 1
    if ymin == ymax:
        ymax += 1
    colors = ["#1565c0", "#e65100", "#2e7d32", "#8e24aa"]
    sx = lambda x: left + (tx(x) - xmin) / (xmax - xmin) * plot_w
    sy = lambda y: top + plot_h - (y - ymin) / (ymax - ymin) * plot_h

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="{width/2}" y="32" text-anchor="middle" font-size="22">{title}</text>',
             f'<path d="M{left},{top} V{top+plot_h} H{left+plot_w}" fill="none" stroke="#333"/>']
    for i in range(6):
        y = top + plot_h * i / 5
        lines.append(f'<path d="M{left},{y:.1f} H{left+plot_w}" stroke="#ddd"/>')
    tick_values = sorted(set(x for x, _ in points)) if log_x else [
        xmin + (xmax - xmin) * i / 5 for i in range(6)
    ]
    for value in tick_values:
        label = str(value) if log_x else f"{value:.1f}"
        xpos = sx(value) if log_x else left + (value - xmin) / (xmax - xmin) * plot_w
        lines.append(f'<text x="{xpos:.1f}" y="{top+plot_h+24}" text-anchor="middle" font-size="12">{label}</text>')
    lines += [f'<text x="{left+plot_w/2}" y="{height-25}" text-anchor="middle" font-size="15">{x_label}</text>',
              f'<text transform="translate(22,{top+plot_h/2}) rotate(-90)" text-anchor="middle" font-size="15">{y_label}</text>']
    for index, (name, values) in enumerate(sorted(series.items())):
        color = colors[index % len(colors)]
        values = sorted((x, y) for x, y in values if y > 0)
        coords = " ".join(f'{sx(x):.1f},{sy(y):.1f}' for x, y in values)
        lines.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="3"/>')
        for x, y in values:
            lines.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4" fill="{color}"/>')
        ly = top + 20 * index
        lines.append(f'<path d="M{left+plot_w-145},{ly} h22" stroke="{color}" stroke-width="3"/>')
        lines.append(f'<text x="{left+plot_w-118}" y="{ly+5}" font-size="12">{name}</text>')
    lines.append('</svg>')
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines))


def main(filename, core_count):
    output_dir = Path(filename).parent
    grouped = defaultdict(list)
    with open(filename, newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            approach = {"2": "local", "3": "shared", "batch": "batch"}[row["approach"]]
            frequency = int(row["k"]) if approach == "batch" else 0
            key = (approach, int(row["threads"]), frequency)
            grouped[key].append(float(row["time"]))

    averages = {key: sum(values) / len(values) for key, values in grouped.items()}
    with open(output_dir / "section6_summary.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["approach", "threads", "k", "runs", "average_seconds"])
        for key in sorted(averages):
            writer.writerow([*key, len(grouped[key]), f"{averages[key]:.9f}"])

    scaling = defaultdict(list)
    comparison = defaultdict(list)
    sync_frequency = defaultdict(list)
    for (approach, threads, frequency), seconds in averages.items():
        if approach == "local":
            scaling["local accumulation"].append((threads, seconds))
            comparison["local accumulation"].append((threads, seconds))
        elif approach == "shared":
            comparison["shared mutex"].append((threads, seconds))
        elif threads == core_count:
            sync_frequency["batch accumulation"].append((frequency, seconds))

    svg_chart(output_dir / "section6_thread_scaling.svg", "6.2 Thread scaling", "Threads (log scale)", "Average seconds", scaling, log_x=True)
    svg_chart(output_dir / "section6_local_vs_shared.svg", "6.3 Local vs shared counter", "Threads (log scale)", "Average seconds", comparison, log_x=True)
    svg_chart(output_dir / "section6_sync_frequency.svg", "6.1 Synchronization frequency", "Iterations per mutex update (log scale)", "Average seconds", sync_frequency, log_x=True)
    print("Created section6_summary.csv and the three section 6 SVG charts.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "section6_results.csv",
         int(sys.argv[2]) if len(sys.argv) > 2 else 1)
