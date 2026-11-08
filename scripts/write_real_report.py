"""Render documentation from the actual saved experiment report."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    report=json.loads((ROOT/'models/evaluation/real-experiments.json').read_text(encoding='utf-8'))
    manifest=json.loads((ROOT/'data/real/latest.json').read_text(encoding='utf-8'))
    graph=report['graph']
    lines=['# Measured real-source results — 8 November 2026','',
        'These measurements describe a small retrospective, selection-biased benchmark. They are not evidence of therapeutic effectiveness.',
        '',f"Snapshot: `{manifest['snapshot_id']}`. Graph SHA-256: `{graph['sha256']}`.",
        '',f"Graph: {graph['nodes']} entities, {graph['edges']} relationships, {graph['connected_components']} label-free connected components and {len(graph['isolated_nodes'])} isolated nodes. Source-provenance coverage: {graph['provenance_coverage']:.0%}. This measures source presence, not evidence quality.",
        '', '| Entity type | Count |','|---|---:|']
    lines += [f'| {kind} | {count} |' for kind,count in graph['entity_distribution'].items()]
    split=report['evaluation']['split']
    lines += ['',f"Seed 42; {split['train']} training / {split['validation']} validation / {split['test']} test pairs. Unknown controls are unlabeled. All clinical edges and publication context are excluded from the R-GCN predictive graph.",
        '', '| Model | ROC-AUC | Average precision | Precision@10 | Recall@10 |','|---|---:|---:|---:|---:|']
    for name,row in report['evaluation']['metrics'].items():
        lines.append(f"| {name} | {row['roc_auc']:.4f} | {row['average_precision']:.4f} | {row['precision_at_10']:.4f} | {row['recall_at_10']:.4f} |")
    lines += ['','## Disease-specific held-out results','',
        '| Disease | Test pairs | Positive labels | ROC-AUC | Average precision |','|---|---:|---:|---:|---:|']
    names={c['disease']['id']:c['disease']['name'] for c in report['cases']}
    for id,row in report['reevaluation']['per_disease'].items():
        auc='Undefined (one test class)' if row['roc_auc'] is None else f"{row['roc_auc']:.4f}"
        ap='Undefined' if row['average_precision'] is None else f"{row['average_precision']:.4f}"
        lines.append(f"| {names[id]} | {row['test_pairs']} | {row['positives']} | {auc} | {ap} |")
    lines += ['','The disease samples are too small and imbalanced to support generalization claims. An all-positive disease test subset cannot measure discrimination, even when average precision is one. No model-superiority or clinical-efficacy claim follows from the pooled table.',
        '', '## Executed candidate workflows','',
        '| Disease | Computed candidates | Candidates with paths | Unreviewed candidate search hits | Maximum sensitivity rank shift |',
        '|---|---:|---:|---:|---:|']
    for case in report['cases']:
        candidates=case['candidates']
        lines.append(f"| {case['disease']['name']} | {len(candidates)} | {sum(bool(c['graph_paths']) for c in candidates)} | {sum(len(c['publications']) for c in candidates)} | {max(s['max_rank_shift'] for s in case['weight_sensitivity'])} |")
    lines += ['', 'All nine stages completed for every disease. Weight diagnostics perturb each of five components by ±20%, renormalize and rerank; these are engineering sensitivity checks, not scientifically validated weights. Search hits are unreviewed and may duplicate publications across candidates. They are not counts of independent supporting experiments. Candidates without paths explicitly lack graph-path support. Full candidate identities and evidence remain in `models/evaluation/real-experiments.json`; none is presented here as a treatment recommendation.',
        '', 'The fixed snapshot and final model configuration are reported without selecting the best intermediate run. Candidate evidence availability can vary with upstream availability and cache state. Raw source timestamps and retrieval statuses are retained.',
        '', 'Verification for the real-data milestone: 21 backend tests passed; two external-database tests skipped at that stage. Five frontend tests, TypeScript validation and the Vite production build passed. Real-snapshot API verification passed. See [later deployment results](deployment_results.md) for live database verification and current Docker status.',
        '', 'Reproduce with `python scripts/run_real_case_studies.py`, then `python scripts/verify_real_api.py` and `python scripts/write_real_report.py`. See [methodology and limitations](real_case_studies.md).', '']
    (ROOT/'docs/real_results.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Wrote docs/real_results.md from measured artifacts')
