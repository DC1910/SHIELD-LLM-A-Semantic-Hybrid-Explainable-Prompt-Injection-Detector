import pandas as pd

df = pd.read_csv('../data/train_phase5d.csv')
challenge = pd.read_csv('../data/benign_challenge.csv')
val  = pd.read_csv('../data/val.csv')
test = pd.read_csv('../data/test.csv')

guard = set()
for g in [challenge, val, test]:
    guard.update(g['text'].astype(str).str.strip().str.lower())

print(f'Rows before cleanup: {len(df)}')

# 1. Remove challenge/val/test overlaps
df['_key'] = df['text'].astype(str).str.strip().str.lower()
df = df[~df['_key'].isin(guard)].reset_index(drop=True)
print(f'After guard removal: {len(df)}')

# 2. Find cross-label conflicts
label_counts = df.groupby('_key')['label'].apply(lambda x: x.nunique())
conflicting_keys = set(label_counts[label_counts > 1].index)
print(f'Cross-label conflicts to remove: {len(conflicting_keys)}')

for k in list(conflicting_keys)[:5]:
    rows = df[df['_key'] == k][['text','label','source']].to_dict('records')
    for r in rows:
        txt = str(r['text'])[:60]
        print(f'  label={r["label"]} src={r["source"]} text="{txt}"')

# Remove all conflicting rows (conservative)
df = df[~df['_key'].isin(conflicting_keys)].reset_index(drop=True)
print(f'After conflict removal: {len(df)}')

# 3. Final dedup by key
df = df.drop_duplicates(subset='_key').drop(columns='_key').reset_index(drop=True)
print(f'After final dedup: {len(df)}')
print(f'  Benign:    {(df.label==0).sum()}')
print(f'  Malicious: {(df.label==1).sum()}')
print(f'  Ratio:     {(df.label==1).sum()/(df.label==0).sum():.3f}x')

# 4. Final overlap verify
df['_key'] = df['text'].astype(str).str.strip().str.lower()
remaining = df['_key'].isin(guard).sum()
print(f'Remaining guard overlap: {remaining}')

cross_check = df.groupby('_key')['label'].apply(lambda x: x.nunique() > 1).sum()
print(f'Remaining cross-label conflicts: {cross_check}')

df = df.drop(columns='_key')
df.to_csv('../data/train_phase5d.csv', index=False)
print('Saved clean train_phase5d.csv')
