import psycopg2

CONN_PARAMS = dict(
    host='db.pdbmcskznoaiybdiobje.supabase.co',
    port=5432,
    dbname='postgres',
    user='postgres',
    password='guid-saltation-covet',
    sslmode='require'
)

def run():
    conn = psycopg2.connect(**CONN_PARAMS)
    cur = conn.cursor()
    sep = '=' * 70

    # Section 1
    print(f'\n{sep}')
    print('  1. m1_trade_indicator_2')
    print(sep)

    cur.execute('SELECT COUNT(*) FROM m1_trade_indicator_2')
    row_count_trade = cur.fetchone()[0]
    print(f'\n  Row count: {row_count_trade}')

    cur.execute(
        'SELECT trade_id, ticker, date, direction, model, '
        'is_winner, pnl_r, bar_time, candle_range_pct, '
        'sma_config, h1_structure '
        'FROM m1_trade_indicator_2 ORDER BY trade_id LIMIT 3'
    )
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print('\n  First 3 rows:')
    for r in rows:
        for c, v in zip(cols, r):
            print(f'    {c:22s} : {v}')
        print()

    cur.execute(
        'SELECT is_winner, COUNT(*) AS cnt '
        'FROM m1_trade_indicator_2 GROUP BY is_winner ORDER BY is_winner'
    )
    print('  Count by is_winner:')
    for r in cur.fetchall():
        print(f'    is_winner={r[0]}  ->  {r[1]}')

    # Section 2
    print(f'\n{sep}')
    print('  2. m1_ramp_up_indicator_2')
    print(sep)

    cur.execute('SELECT COUNT(*) FROM m1_ramp_up_indicator_2')
    row_count_ramp = cur.fetchone()[0]
    print(f'\n  Row count: {row_count_ramp}')

    cur.execute('SELECT COUNT(DISTINCT trade_id) FROM m1_ramp_up_indicator_2')
    distinct_ramp = cur.fetchone()[0]
    print(f'  Distinct trade_ids: {distinct_ramp}')

    cur.execute(
        'SELECT trade_id, COUNT(*) AS cnt FROM m1_ramp_up_indicator_2 '
        'GROUP BY trade_id HAVING COUNT(*) != 25 ORDER BY trade_id'
    )
    bad = cur.fetchall()
    if bad:
        print(f'\n  WARNING: {len(bad)} trade(s) do NOT have exactly 25 rows:')
        for b in bad[:10]:
            print(f'    trade_id={b[0]}  rows={b[1]}')
        if len(bad) > 10:
            print(f'    ... and {len(bad)-10} more')
    else:
        print('  All trades have exactly 25 rows: OK')

    cur.execute(
        'SELECT trade_id, MIN(bar_sequence) AS min_seq, MAX(bar_sequence) AS max_seq '
        'FROM m1_ramp_up_indicator_2 GROUP BY trade_id ORDER BY trade_id LIMIT 1'
    )
    r = cur.fetchone()
    if r:
        print(f'\n  Sample bar_sequence range (trade_id={r[0]}): {r[1]} .. {r[2]}')

    # Section 3
    print(f'\n{sep}')
    print('  3. m1_post_trade_indicator_2')
    print(sep)

    cur.execute('SELECT COUNT(*) FROM m1_post_trade_indicator_2')
    row_count_post = cur.fetchone()[0]
    print(f'\n  Row count: {row_count_post}')

    cur.execute('SELECT COUNT(DISTINCT trade_id) FROM m1_post_trade_indicator_2')
    distinct_post = cur.fetchone()[0]
    print(f'  Distinct trade_ids: {distinct_post}')

    cur.execute(
        'SELECT trade_id, COUNT(*) AS cnt FROM m1_post_trade_indicator_2 '
        'GROUP BY trade_id HAVING COUNT(*) != 25 ORDER BY trade_id'
    )
    bad = cur.fetchall()
    if bad:
        print(f'\n  WARNING: {len(bad)} trade(s) do NOT have exactly 25 rows:')
        for b in bad[:10]:
            print(f'    trade_id={b[0]}  rows={b[1]}')
        if len(bad) > 10:
            print(f'    ... and {len(bad)-10} more')
    else:
        print('  All trades have exactly 25 rows: OK')

    cur.execute('SELECT COUNT(*) FROM m1_post_trade_indicator_2 WHERE is_winner IS NULL')
    null_winner = cur.fetchone()[0]
    print(f'\n  Rows where is_winner IS NULL: {null_winner}')
    if null_winner == 0:
        print('  is_winner fully populated: OK')
    else:
        print('  WARNING: Some rows have NULL is_winner')

    # Section 4
    print(f'\n{sep}')
    print('  4. Cross-table consistency')
    print(sep)

    cur.execute('SELECT DISTINCT trade_id FROM m1_trade_indicator_2 ORDER BY trade_id')
    ids_trade = set(r[0] for r in cur.fetchall())

    cur.execute('SELECT DISTINCT trade_id FROM m1_ramp_up_indicator_2 ORDER BY trade_id')
    ids_ramp = set(r[0] for r in cur.fetchall())

    cur.execute('SELECT DISTINCT trade_id FROM m1_post_trade_indicator_2 ORDER BY trade_id')
    ids_post = set(r[0] for r in cur.fetchall())

    print(f'\n  Distinct trade_ids in m1_trade_indicator_2   : {len(ids_trade)}')
    print(f'  Distinct trade_ids in m1_ramp_up_indicator_2 : {len(ids_ramp)}')
    print(f'  Distinct trade_ids in m1_post_trade_indicator_2: {len(ids_post)}')

    if ids_trade == ids_ramp == ids_post:
        print('\n  All 3 tables have IDENTICAL trade_id sets: OK')
    else:
        in_trade_not_ramp = ids_trade - ids_ramp
        in_trade_not_post = ids_trade - ids_post
        in_ramp_not_trade = ids_ramp - ids_trade
        in_post_not_trade = ids_post - ids_trade
        if in_trade_not_ramp:
            print(f'\n  In trade but NOT ramp_up: {len(in_trade_not_ramp)} ids  (e.g. {sorted(list(in_trade_not_ramp))[:5]})')
        if in_trade_not_post:
            print(f'  In trade but NOT post_trade: {len(in_trade_not_post)} ids  (e.g. {sorted(list(in_trade_not_post))[:5]})')
        if in_ramp_not_trade:
            print(f'  In ramp_up but NOT trade: {len(in_ramp_not_trade)} ids  (e.g. {sorted(list(in_ramp_not_trade))[:5]})')
        if in_post_not_trade:
            print(f'  In post_trade but NOT trade: {len(in_post_not_trade)} ids  (e.g. {sorted(list(in_post_not_trade))[:5]})')

    cur.execute('SELECT COUNT(*) FROM trades_2')
    trades2_total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(DISTINCT trade_id) FROM trades_2')
    trades2_distinct = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM m5_atr_stop_2')
    atr_total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(DISTINCT trade_id) FROM m5_atr_stop_2')
    atr_distinct = cur.fetchone()[0]

    print(f'\n  trades_2 total rows: {trades2_total}  (distinct trade_ids: {trades2_distinct})')
    print(f'  m5_atr_stop_2 total rows: {atr_total}  (distinct trade_ids: {atr_distinct})')
    pct = 100 * len(ids_trade) / max(atr_distinct, 1)
    print(f'  m1_trade_indicator_2 coverage: {len(ids_trade)} / {atr_distinct} trades with outcomes ({pct:.1f}%)')

    # Section 5
    print(f'\n{sep}')
    print('  5. Pending trades (in m5_atr_stop_2 but NOT in m1_trade_indicator_2)')
    print(sep)

    cur.execute(
        'SELECT COUNT(DISTINCT a.trade_id) FROM m5_atr_stop_2 a '
        'LEFT JOIN m1_trade_indicator_2 t ON a.trade_id = t.trade_id '
        'WHERE t.trade_id IS NULL'
    )
    pending = cur.fetchone()[0]
    print(f'\n  Trades with outcomes but missing from m1_trade_indicator_2: {pending}')
    if pending == 0:
        print('  Fully populated: OK')
    else:
        cur.execute(
            'SELECT DISTINCT a.trade_id FROM m5_atr_stop_2 a '
            'LEFT JOIN m1_trade_indicator_2 t ON a.trade_id = t.trade_id '
            'WHERE t.trade_id IS NULL ORDER BY a.trade_id LIMIT 10'
        )
        missing = [r[0] for r in cur.fetchall()]
        print(f'  Sample missing trade_ids: {missing}')

    # Section 6
    print(f'\n{sep}')
    print('  6. NULL indicator check on m1_trade_indicator_2')
    print(sep)

    cur.execute('SELECT COUNT(*) FROM m1_trade_indicator_2 WHERE candle_range_pct IS NULL')
    null_crp = cur.fetchone()[0]
    print(f'\n  Rows where candle_range_pct IS NULL: {null_crp}')
    if null_crp == 0:
        print('  All indicator bars found: OK')
    else:
        pct2 = 100 * null_crp / max(row_count_trade, 1)
        print(f'  WARNING: {null_crp}/{row_count_trade} rows ({pct2:.1f}%) have NULL candle_range_pct')
        cur.execute(
            'SELECT trade_id, ticker, date, bar_time FROM m1_trade_indicator_2 '
            'WHERE candle_range_pct IS NULL ORDER BY trade_id LIMIT 5'
        )
        print('  Sample NULL rows:')
        for r in cur.fetchall():
            print(f'    trade_id={r[0]}  ticker={r[1]}  date={r[2]}  bar_time={r[3]}')

    print(f'\n{sep}')
    print('  DONE')
    print(f'{sep}\n')

    cur.close()
    conn.close()

if __name__ == '__main__':
    run()
