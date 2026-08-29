from database import connect, DB_PATH


def status():
    con = connect()
    rows = con.execute('''SELECT timeframe, COUNT(*) AS candles, MIN(ts), MAX(ts)
                          FROM candles WHERE instrument=?
                          GROUP BY timeframe ORDER BY timeframe''',
                       ('NSE_INDEX|Nifty 50',)).fetchall()
    con.close()
    return rows


if __name__ == '__main__':
    print(f'Database: {DB_PATH}')
    for timeframe, count, first, last in status():
        print(f'{timeframe}: {count:,} candles | {first} -> {last}')
