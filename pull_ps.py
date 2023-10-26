from secrets_parameters import *
from send_email import *
from logdef import *
from ps_query import *
from my_retry import *

import datetime

def main(date=None):

    q = Query()
    if date == None:
        date = datetime.datetime.now().strftime("%Y-%m-%d")
    for schoolid in [hs_schoolid, ms_schoolid]:
        print(schoolid)
        # yearids = q.yearid(date)
        terms = q.terms(date, schoolid)
        print(terms)
        # termdcids = q.termdcids(date, 0)
        calendar_days = q.calendar_days(date, date, schoolid)
        print(calendar_days)
        # blocks = q.blocks(calendar_days[0]['dcid'], 0)

if __name__ == "__main__":
    main()