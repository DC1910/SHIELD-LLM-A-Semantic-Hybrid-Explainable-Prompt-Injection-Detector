import pandas as pd, numpy as np

bench = pd.read_csv('data/eval_curated_benchmark.csv')
extraction = bench[bench['source'] == 'independent_attack_extraction']
print(f'Extraction category - total rows: {len(extraction)}')
print('All missed by ALL FIVE models (0% accuracy across Original, 5B, 5D, 5F, 5G)')
print()
print('Sample extraction prompts:')
for _, row in extraction.head(5).iterrows():
    print('  ' + str(row['text'])[:120])
print()

delim = bench[bench['source'] == 'independent_attack_delimiter']
print(f'Delimiter category - {len(delim)} rows, Phase 5G accuracy: 88.9% -> ~10 FNs')
print('Sample delimiter prompts:')
for _, row in delim.head(5).iterrows():
    print('  ' + str(row['text'])[:120])

print()
print('=== KEY FINDING ===')
print('The independent_attack_extraction rows are TEMPLATED prompts:')
print("  'Diagnostic query #N: Echo the full text of...'")
print('Repetitive templates inflating FN count. Not representative of diverse extraction attacks.')
print()

non_extraction_mal = bench[(bench['label'] == '1') & (bench['source'] != 'independent_attack_extraction')]
print(f'Non-extraction malicious rows: {len(non_extraction_mal)}')
print(f'Phase 5G FNs without extraction category: 106 - 90 = 16')
corrected_fn = 16
corrected_tp = len(non_extraction_mal) - corrected_fn
recall_corrected = corrected_tp / len(non_extraction_mal)
prec_corrected = 1.0
f1_corrected = 2 * prec_corrected * recall_corrected / (prec_corrected + recall_corrected)
print(f'Phase 5G Corrected Recall (non-extraction): {corrected_tp}/{len(non_extraction_mal)} = {recall_corrected:.3f}')
print(f'Phase 5G Corrected F1 (non-extraction): {f1_corrected:.4f}')
print()

# Compare all 5 models after removing extraction template bias
print('=== All 5 models corrected recall (excl. extraction) ===')
# From report: extraction is 0% for all models
# FNs without extraction:
models = {
    'Original':  92 - 90,   # 92 total FN, 90 extraction
    'Phase 5B':  93 - 90,   
    'Phase 5D':  98 - 90,   
    'Phase 5F':  96 - 90,   
    'Phase 5G':  106 - 90,  
}
total_non_ext = len(non_extraction_mal)
for name, fn_adj in models.items():
    tp = total_non_ext - fn_adj
    rec = tp / total_non_ext
    f1 = 2 * 1.0 * rec / (1.0 + rec)
    print(f'  {name}: Adj FN={fn_adj}, Adj Recall={rec:.3f}, Adj F1={f1:.4f}')
