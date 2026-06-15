import pandas as pd, sys

out = []
c1 = pd.read_csv('data/raw/clean_final.csv', encoding='utf-8', nrows=0)
out.append('=== clean_final.csv ===')
for col in c1.columns:
    out.append(f'  {col}')

out.append('')
c2 = pd.read_csv('data/processed/koweps_extracted.csv', encoding='utf-8-sig', nrows=0)
out.append('=== koweps_extracted.csv ===')
for col in c2.columns:
    out.append(f'  {col}')

with open('scripts/_cols_out.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('saved to scripts/_cols_out.txt')
