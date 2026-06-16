"""Generate a visual confusion matrix for the saved spam model metrics."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def plot_confusion_matrix(metrics_path, output_path):
    metrics = json.loads(Path(metrics_path).read_text(encoding="utf-8"))
    matrix = metrics["confusion_matrix"]
    labels = metrics.get("labels", ["ham", "spam"])

    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=160)
    image = ax.imshow(matrix, cmap="Blues")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax.set_title(
        f"Spam Classifier Confusion Matrix\nAccuracy: {metrics['accuracy']:.2%}",
        pad=14,
    )
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_xticks(range(len(labels)), labels)
    ax.set_yticks(range(len(labels)), labels)

    max_value = max(max(row) for row in matrix)
    for row_index, row in enumerate(matrix):
        for col_index, value in enumerate(row):
            color = "white" if value > max_value * 0.55 else "#1f2933"
            ax.text(
                col_index,
                row_index,
                str(value),
                ha="center",
                va="center",
                color=color,
                fontsize=14,
                fontweight="bold",
            )

    ax.set_xticks([x - 0.5 for x in range(1, len(labels))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(labels))], minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False)

    fig.tight_layout()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Plot the spam classifier confusion matrix as a PNG image."
    )
    parser.add_argument(
        "--metrics",
        default="data/models/spam_metrics.json",
        help="Path to spam_metrics.json.",
    )
    parser.add_argument(
        "--output",
        default="docs/spam_confusion_matrix.png",
        help="Output PNG path.",
    )
    args = parser.parse_args()
    output = plot_confusion_matrix(args.metrics, args.output)
    print(f"Saved confusion matrix to {output}")


if __name__ == "__main__":
    main()
