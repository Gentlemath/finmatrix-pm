"""Plot per-country momentum long-short returns from cached JKP decile data.

Reads local_data/global_momentum_deciles.csv (produced by cache_global_momentum_data_wrds.py)
and writes two figures to local_data/figures/ (gitignored):

  1. momentum_yearly_heatmap.png  — market x year, diverging color centred at 0
  2. momentum_yearly_bars.png     — small-multiple yearly bars per market

Diverging red<->blue (CVD-safe; red = negative, blue = positive), neutral at 0.
"""

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402  (must follow matplotlib.use)
from matplotlib.colors import TwoSlopeNorm  # noqa: E402

DATA = Path("local_data/global_momentum_deciles.csv")
OUTDIR = Path("local_data/figures")
ORDER = ["USA", "GBR", "DEU", "FRA", "JPN", "HKG", "KOR", "CHN"]
NEG, POS = "#c0392b", "#2166ac"          # red = negative, blue = positive


def yearly_long_short() -> pd.DataFrame:
    """Annual long-short (D10-D1) return per market; rows=market, cols=year."""
    d = pd.read_csv(DATA, parse_dates=["date"])
    out = {}
    for c in ORDER:
        piv = d[d.excntry == c].pivot_table(index="date", columns="decile", values="vw_ret")
        ls = (piv[10] - piv[1]).dropna().sort_index()
        out[c] = (1 + ls).groupby(ls.index.year).prod() - 1
    return pd.DataFrame(out).T.reindex(ORDER)


def plot_heatmap(yearly: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(18, 4.6))
    cmap = plt.cm.RdBu.copy()
    cmap.set_bad("#eeeeee")              # missing years (e.g. early China) in grey
    norm = TwoSlopeNorm(vmin=-0.6, vcenter=0.0, vmax=0.6)   # clip color at +/-60%
    im = ax.imshow(np.ma.masked_invalid(yearly.values), aspect="auto", cmap=cmap, norm=norm)

    years = [int(y) for y in yearly.columns]
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(years, rotation=90, fontsize=7)
    ax.set_yticks(range(len(yearly.index)))
    ax.set_yticklabels(yearly.index, fontsize=10)
    for i in range(yearly.shape[0]):
        for j in range(yearly.shape[1]):
            v = yearly.values[i, j]
            if pd.notna(v):
                # white text on saturated (dark) cells, dark text on pale ones
                tc = "white" if abs(v) > 0.33 else "#222222"
                ax.text(j, i, f"{v * 100:.0f}", ha="center", va="center",
                        fontsize=5.5, color=tc)
    cbar = fig.colorbar(im, ax=ax, fraction=0.015, pad=0.01)
    cbar.set_label("Annual return (clipped +/-60%)", fontsize=9)
    ax.set_title("Momentum long-short (D10-D1) annual return by market "
                 "— value-weighted large-cap", fontsize=12, pad=10)
    ax.set_xlabel("Year")
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def plot_bars(yearly: pd.DataFrame, path: Path) -> None:
    years = [int(y) for y in yearly.columns]
    fig, axes = plt.subplots(4, 2, figsize=(13, 12), sharex=True, sharey=True)
    for ax, c in zip(axes.ravel(), ORDER):
        vals = yearly.loc[c].values * 100
        ax.bar(years, vals, width=0.85,
               color=[NEG if (v < 0) else POS for v in np.nan_to_num(vals)])
        ax.axhline(0, color="#888888", lw=0.8)
        ax.set_title(c, fontsize=11)
        ax.grid(True, axis="y", alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Momentum long-short (D10-D1) yearly return by market (%)", fontsize=13)
    fig.supylabel("Annual return (%)")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    yearly = yearly_long_short()
    plot_heatmap(yearly, OUTDIR / "momentum_yearly_heatmap.png")
    plot_bars(yearly, OUTDIR / "momentum_yearly_bars.png")
    print(f"wrote figures to {OUTDIR.resolve()}/")
    print(" ", "momentum_yearly_heatmap.png")
    print(" ", "momentum_yearly_bars.png")


if __name__ == "__main__":
    main()
