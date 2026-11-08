# Measured offline experiments — 8 November 2026

These are entirely synthetic software experiments, not drug repurposing findings. Source: `models/evaluation/synthetic-evaluation.json` and `models/evaluation/experiments.json`, produced by the commands below. The `synthetic-v2` fixture has 72 entities and 152 edges, including 48 fictional indication pairs. The label-free projection has one connected component, no isolated nodes and 100% source-provenance coverage. Fictional protein interaction edges connect modules so unknown candidates have inspectable paths. Synthetic provenance is not biomedical evidence.

Seed 42; 60 maximum training epochs; validation-loss early stopping; 57 training, 19 validation and 20 test pairs. Forty-eight known synthetic pairs and 48 sampled unknown pairs are disjoint across splits. Every TREATS edge is excluded from graph message passing, structural features and path explanations. Unknown pairs are unlabeled controls, not confirmed negatives.

| Model | ROC-AUC | Average precision | Precision@10 | Recall@10 |
|---|---:|---:|---:|---:|
| R-GCN + DistMult | 0.4100 | 0.5615 | 0.40 | 0.40 |
| Logistic regression | 1.0000 | 1.0000 | 1.00 | 1.00 |
| Random forest | 1.0000 | 1.0000 | 1.00 | 1.00 |
| Common neighbors | 0.5000 | 0.5000 | 0.50 | 0.50 |
| Jaccard | 0.5000 | 0.5000 | 0.50 | 0.50 |
| Adamic–Adar | 0.5000 | 0.5000 | 0.50 | 0.50 |
| Resource allocation | 0.5000 | 0.5000 | 0.50 | 0.50 |
| Personalized PageRank | 1.0000 | 1.0000 | 1.00 | 1.00 |
| Logistic regression: topology only | 1.0000 | 1.0000 | 1.00 | 1.00 |
| Logistic regression: degree only | 0.5000 | 0.5000 | 0.50 | 0.50 |

Average precision is the reported PR summary; it is not trapezoidal PR-AUC. Ranking metrics are pooled across sampled test pairs. Ties use stable input order, so tied baseline ranking metrics depend on that order. These values do not estimate full-catalog retrieval performance or clinical efficacy. Perfect fixture scores indicate the simplicity of the constructed structure, not a validated biomedical model.

The ablations refit logistic regression on the same training split using topology-only versus degree-only features. They do not ablate the GNN or establish biological causality. Three fixture diseases were analyzed through all nine existing agent stages, each yielding 18 candidates. Each case includes ten weight perturbations: every component is multiplied by 0.8 or 1.2 and all weights are normalized. All observed perturbations preserved the full candidate order (maximum rank shift zero; top-five overlap one). Reports retain these diagnostics along with full computed candidate explanations. Stability on this fixture does not establish robustness on real biomedical data.

Reproduce from the repository root:

```powershell
python scripts/train_model.py
python scripts/evaluate_model.py
python scripts/run_experiments.py
python -m pytest -q
```

Historical fixture verification: three React tests passed with the initial synthetic implementation. The later real-data milestone passed 21 backend tests and five frontend tests, with two external-database tests skipped. TypeScript validation and the production build passed. See [measured real-source results](real_results.md) for the three completed real disease case studies. The production bundle still triggers a size advisory. Docker deployment, temporal/cold-start validation and clinical claim adjudication remain unverified or unimplemented.
