from datetime import date, timedelta
import requests, io
import pandas as pd

end_date = date.today()
start_date = end_date - timedelta(days=60)
delta = timedelta(days=1)
frames = []
while start_date <= end_date:
    try:
        csv_url = 'https://archives.nseindia.com/content/nsccl/fao_participant_oi_' + start_date.strftime("%d%m%Y") + '.csv'
        req = requests.get(csv_url, timeout=15)
        url_content = req.content
        c = pd.read_csv(io.StringIO(url_content.decode('utf-8')), skiprows=1)
        c['Date'] = start_date.strftime("%d-%m-%Y")
        frames.append(c)
        print('Done for ' + start_date.strftime("%d-%m-%Y"))
    except Exception:
        print('No data for ' + start_date.strftime("%d-%m-%Y"))

    start_date += delta

if frames:
    df = pd.concat(frames, ignore_index=True, axis=0)
    df.to_csv('FDCP_Data.csv')
else:
    print('No data fetched for any date. FDCP_Data.csv not updated.')