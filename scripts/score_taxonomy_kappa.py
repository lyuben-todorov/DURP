"""Score the Scheme-2 taxonomy validation: Cohen's κ + per-category precision.

Run AFTER humans have filled the `human_label` column of one or more label
sheets produced by build_taxonomy_sample.py. Computes:

  - classifier-vs-human κ      — does the automated classifier agree with the
                                 human ground truth? (validates the tool)
  - human-vs-human κ           — if two coders' sheets are given, are the
                                 categories themselves well-defined?
                                 (validates the taxonomy; the number the
                                 literature reports)
  - per-category precision     — of the candidates the classifier called X,
                                 what fraction did the human agree were X?
  - a confusion matrix         — where classifier and human disagree.

Stdlib only — no sklearn. Cohen's κ = (po - pe) / (1 - pe), where po is
observed agreement and pe is chance agreement from the marginal label
frequencies.

Usage:
  # classifier vs one coder:
  python3 scripts/score_taxonomy_kappa.py \\
      --answer-key data/taxonomy-validation/answer_key.csv \\
      --coder data/taxonomy-validation/label_sheet.coderA.csv

  # add a second coder for human-human κ:
  python3 scripts/score_taxonomy_kappa.py \\
      --answer-key .../answer_key.csv \\
      --coder .../sheet.coderA.csv --coder2 .../sheet.coderB.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter


def _read_labels(path: str, key_col: str, label_col: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            k = (row.get(key_col) or "").strip()
            v = (row.get(label_col) or "").strip()
            if k and v:
                out[k] = v
    return out


def cohen_kappa(pairs: list[tuple[str, str]]) -> tuple[float, float, float]:
    """Return (kappa, observed_agreement, expected_agreement) for a list of
    (label_a, label_b) pairs over a shared category set."""
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    cats = set(ca) | set(cb)
    pe = sum((ca.get(c, 0) / n) * (cb.get(c, 0) / n) for c in cats)
    kappa = (po - pe) / (1 - pe) if pe != 1.0 else 1.0
    return kappa, po, pe


def _interpret(k: float) -> str:
    if k != k:  # nan
        return "n/a"
    if k < 0: return "poor (worse than chance)"
    if k < 0.20: return "slight"
    if k < 0.40: return "fair"
    if k < 0.60: return "moderate"
    if k < 0.80: return "substantial"
    return "near-perfect"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--answer-key", required=True,
                   help="answer_key.csv from build_taxonomy_sample.py")
    p.add_argument("--coder", required=True,
                   help="A filled label_sheet.csv (human_label column).")
    p.add_argument("--coder2", default=None,
                   help="Optional second coder's sheet, for human-human κ.")
    args = p.parse_args()

    clf = _read_labels(args.answer_key, "candidate_key", "classifier_category")
    human = _read_labels(args.coder, "candidate_key", "human_label")

    # classifier vs human: only over candidates the human actually labelled
    shared = [k for k in human if k in clf]
    if not shared:
        print("ERROR: no overlap between coder sheet and answer key "
              "(did you fill human_label?)", file=sys.stderr)
        return 1
    pairs = [(clf[k], human[k]) for k in shared]
    kappa, po, pe = cohen_kappa(pairs)

    print(f"=== classifier vs human ({len(shared)} labelled) ===")
    print(f"  observed agreement po = {po:.3f}")
    print(f"  chance agreement   pe = {pe:.3f}")
    print(f"  Cohen's kappa         = {kappa:.3f}  [{_interpret(kappa)}]")
    print(f"  raw accuracy          = {po:.1%}")
    print()

    # per-category precision (classifier's perspective)
    print("=== per-category precision (of what the classifier called X, "
          "how many humans agreed) ===")
    by_clf: dict[str, list[bool]] = {}
    for k in shared:
        by_clf.setdefault(clf[k], []).append(clf[k] == human[k])
    print(f"  {'category':24} {'n':>4} {'precision':>10}")
    for cat in sorted(by_clf):
        hits = by_clf[cat]
        prec = sum(hits) / len(hits)
        print(f"  {cat:24} {len(hits):>4} {prec:>9.1%}")
    print()

    # confusion: where they disagree
    disagreements = [(k, clf[k], human[k]) for k in shared if clf[k] != human[k]]
    if disagreements:
        print(f"=== {len(disagreements)} disagreements (classifier -> human) ===")
        confusion = Counter((c, h) for _, c, h in disagreements)
        for (c, h), n in confusion.most_common():
            print(f"  {c:24} -> {h:24} ×{n}")
        print()
        print("  candidates:")
        for k, c, h in sorted(disagreements):
            print(f"    {k:40} clf={c:20} human={h}")
        print()

    # human-human κ (taxonomy validity)
    if args.coder2:
        human2 = _read_labels(args.coder2, "candidate_key", "human_label")
        both = [k for k in human if k in human2]
        if both:
            hpairs = [(human[k], human2[k]) for k in both]
            hk, hpo, hpe = cohen_kappa(hpairs)
            print(f"=== human vs human ({len(both)} double-coded) ===")
            print(f"  observed agreement = {hpo:.3f}")
            print(f"  Cohen's kappa      = {hk:.3f}  [{_interpret(hk)}]")
        else:
            print("WARNING: no overlap between the two coder sheets", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
