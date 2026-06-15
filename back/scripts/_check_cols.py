import pandas as pd

for enc in ('utf-8', 'utf-8-sig', 'euc-kr', 'cp949'):
    try:
        c = pd.read_csv('data/raw/clean_final.csv', encoding=enc, nrows=0)
        print(f'clean_final [{enc}]:')
        for col in c.columns:
            print(f'  {col}')
        break
    except Exception as e:
        print(f'{enc} fail: {e}')

print()
c2 = pd.read_csv('data/processed/koweps_extracted.csv', encoding='utf-8-sig', nrows=0)
print('koweps_extracted:')
for col in c2.columns:
    print(f'  {col}')
