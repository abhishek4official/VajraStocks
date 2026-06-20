import sys
sys.path.insert(0, '.')
import pandas as pd

v1 = pd.read_csv('VajraML/results/walk_forward_results.csv')

v2 = pd.DataFrame([
    {'fold':1,'ic_tp':0.2110,'tp_prec':0.491,'hit_5d':0.701,'ls_return':0.0022},
    {'fold':2,'ic_tp':0.2280,'tp_prec':0.528,'hit_5d':0.825,'ls_return':0.0074},
])

m = v1[v1['fold'].isin([1,2])].merge(v2, on='fold')

print()
print("=" * 88)
print("  VajraML V1  vs  VajraML2 V2  —  2 Completed Folds")
print("=" * 88)
print(f"{'Fold':<5}  {'--- V1 (Regressor) --------------':32}  {'--- V2 (Triple-Barrier) ----------------':40}")
print(f"{'':5}  {'IC':>8}  {'Hit%':>8}  {'L/S%':>8}  {'IC(P_TP)':>10}  {'TP-Prec@10%':>13}  {'Hit5d%':>8}  {'L/S%':>8}")
print("-" * 88)

for _, r in m.iterrows():
    f1 = int(r['fold'])
    print(f"{f1:<5}  {r['lgbm_ic']:>+8.4f}  {r['lgbm_hit']:>8.1%}  {r['ls_lgbm']:>+8.2%}  {r['ic_tp']:>+10.4f}  {r['tp_prec']:>13.1%}  {r['hit_5d']:>8.1%}  {r['ls_return']:>+8.2%}")

print("-" * 88)
print(f"{'Mean':<5}  {m['lgbm_ic'].mean():>+8.4f}  {m['lgbm_hit'].mean():>8.1%}  {m['ls_lgbm'].mean():>+8.2%}  {m['ic_tp'].mean():>+10.4f}  {m['tp_prec'].mean():>13.1%}  {m['hit_5d'].mean():>8.1%}  {m['ls_return'].mean():>+8.2%}")
print("=" * 88)

print()
print("KEY TAKEAWAYS (2 folds)")
print(f"  Hit Rate      V1: {m['lgbm_hit'].mean():.1%}   V2: {m['hit_5d'].mean():.1%}   (+{(m['hit_5d'].mean()-m['lgbm_hit'].mean())*100:.1f} pp improvement)")
print(f"  L/S Return    V1: {m['ls_lgbm'].mean()*100:+.2f}%/period   V2: {m['ls_return'].mean()*100:+.2f}%/period")
print(f"  TP Precision  V2 top-10% hits TP {m['tp_prec'].mean():.1%} vs {0.289:.1%} base  ({m['tp_prec'].mean()/0.289:.1f}x lift)")
print(f"  IC(P_TP)      V2: {m['ic_tp'].mean():+.4f}  (V1 IC: {m['lgbm_ic'].mean():+.4f})")
print()
print("PERIODS COVERED:")
for _, r in m.iterrows():
    print(f"  Fold {int(r['fold'])}: {['Nov 2024 – Feb 2025','Feb 2025 – May 2025'][int(r['fold'])-1]}")
