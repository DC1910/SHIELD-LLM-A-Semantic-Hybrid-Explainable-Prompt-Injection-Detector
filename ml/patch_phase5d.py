import pandas as pd

df = pd.read_csv('../data/train_phase5d.csv')

# The 2 remaining missing cyber terms from audit
extra_benign = [
    # password attack variants (benign usage)
    {"text": "What is a password attack?", "label": 0, "source": "synthetic_cybersec"},
    {"text": "How do password attacks work?", "label": 0, "source": "synthetic_cybersec"},
    {"text": "What are the types of password attacks?", "label": 0, "source": "synthetic_cybersec"},
    {"text": "How do you defend against password attacks?", "label": 0, "source": "synthetic_cybersec"},
    {"text": "password attack", "label": 0, "source": "synthetic_cybersec"},
    # network attack variants (benign usage)
    {"text": "What is a network attack?", "label": 0, "source": "synthetic_cybersec"},
    {"text": "How are network attacks detected?", "label": 0, "source": "synthetic_cybersec"},
    {"text": "What are common network attacks?", "label": 0, "source": "synthetic_cybersec"},
    {"text": "How do you prevent network attacks?", "label": 0, "source": "synthetic_cybersec"},
    {"text": "network attack", "label": 0, "source": "synthetic_cybersec"},
    # OWASP LLM Top 10 (also missing from section 6)
    {"text": "What is the OWASP LLM Top 10?", "label": 0, "source": "synthetic_pi_education"},
    {"text": "Explain OWASP Top 10 for LLMs.", "label": 0, "source": "synthetic_pi_education"},
    {"text": "What vulnerabilities are in the OWASP Top 10 for LLMs?", "label": 0, "source": "synthetic_pi_education"},
    {"text": "How does OWASP categorize LLM risks?", "label": 0, "source": "synthetic_pi_education"},
    {"text": "What is LLM01 prompt injection in OWASP?", "label": 0, "source": "synthetic_pi_education"},
]

extra_df = pd.DataFrame(extra_benign)

# Load guard
challenge = pd.read_csv('../data/benign_challenge.csv')
val  = pd.read_csv('../data/val.csv')
test = pd.read_csv('../data/test.csv')
guard = set()
for g in [challenge, val, test]:
    guard.update(g['text'].astype(str).str.strip().str.lower())

# Filter against guard
extra_df = extra_df[~extra_df['text'].str.strip().str.lower().isin(guard)]

# Filter against existing training set  
existing_keys = set(df['text'].str.strip().str.lower())
extra_df = extra_df[~extra_df['text'].str.strip().str.lower().isin(existing_keys)]

print(f'Adding {len(extra_df)} extra rows')
df = pd.concat([df, extra_df], ignore_index=True).sample(frac=1, random_state=42).reset_index(drop=True)
print(f'Final: {len(df)} rows  (benign={( df.label==0).sum()}, malicious={(df.label==1).sum()})')
print(f'Ratio: {(df.label==1).sum()/(df.label==0).sum():.3f}x')

df.to_csv('../data/train_phase5d.csv', index=False)
print('Saved.')
