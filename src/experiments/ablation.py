from pathlib import Path
import matplotlib.pyplot as plt

from src.calibrate.grid_search import load_labels, run_one_config
from src.trust_engine.pipeline import DEMO_CONFIG


OUT_DIR = Path("docs/experiments")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run_ablation(name, **switches):
    print(f"\nRunning: {name}")

    labels = load_labels()

    result = run_one_config(
        DEMO_CONFIG,
        labels,
        enable_data=switches.get("enable_data", True),
        enable_single=switches.get("enable_single", True),
        enable_multi=switches.get("enable_multi", True),
        enable_physics=switches.get("enable_physics", True),
    )

    print(name, result)
    return result


def get_score(result):
    possible_keys = [
        "error_catch_rate",
        "catch_rate",
        "errors_caught_rate",
        "error_detection_rate",
    ]

    for key in possible_keys:
        if key in result:
            return float(result[key])

    if "error_rate" in result:
        return 1.0 - float(result["error_rate"])

    for key, value in result.items():
        if isinstance(value, (int, float)) and 0 <= value <= 1:
            return float(value)

    raise ValueError(
        f"Cannot find suitable metric. Available results: {result}"
    )


def main():

    experiments = {
        "Full Trust Engine": {
            "enable_data": True,
            "enable_single": True,
            "enable_multi": True,
            "enable_physics": True,
        },

        "No Data Evidence": {
            "enable_data": False,
            "enable_single": True,
            "enable_multi": True,
            "enable_physics": True,
        },

        "No Single-Model": {
            "enable_data": True,
            "enable_single": False,
            "enable_multi": True,
            "enable_physics": True,
        },

        "No Multi-Model": {
            "enable_data": True,
            "enable_single": True,
            "enable_multi": False,
            "enable_physics": True,
        },

        "No Physics": {
            "enable_data": True,
            "enable_single": True,
            "enable_multi": True,
            "enable_physics": False,
        },
    }

    results = {}

    for name, switches in experiments.items():
        result = run_ablation(name, **switches)
        results[name] = get_score(result)

    print("\n===== Ablation Results =====")

    for name, score in results.items():
        print(f"{name}: {score:.3f}")

    names = list(results.keys())
    scores = list(results.values())

    plt.figure(figsize=(10, 6))
    plt.bar(names, scores)

    plt.ylabel("Reliability / Safety Score")
    plt.title("Trust Engine Ablation Study")
    plt.ylim(0, 1)

    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()

    out_path = OUT_DIR / "ablation.png"

    plt.savefig(out_path, dpi=200)
    plt.close()

    print(f"\nSaved figure to: {out_path}")


if __name__ == "__main__":
    main()
