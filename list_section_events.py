from logdef import *
from ps_query import *
from runtimer import *
from secrets_parameters import *

import datetime, pytz, time, csv, pandas, json

@runtimer
def main(date=None):
    section_events = {}
    client = Query()
    if not date:
        date = datetime.datetime.now().strftime("%Y-%m-%d")
    # schools = {hs_schoolid: "HS", ms_schoolid: "MS"}
    schools = {hs_schoolid: "HS"}
    terms = {}
    start_dates = []
    end_dates = []
    schedules = {}
    saved_calls = 0
    for schoolid, school_abbreviation in schools.items():
            schedules.setdefault(schoolid, {})
            psterms = client.terms(date, schoolid)
            for t in psterms:
                  terms[t['dcid']] = t['abbreviation']
                  start_dates.append(t['firstday'])
                  end_dates.append(t['lastday'])
            school_days = client.calendar_days(min(start_dates), max(end_dates), schoolid)
            bell_schedule_ids = list(set([day['bell_schedule_id'] for day in school_days]))
            for bsid in bell_schedule_ids:
                  schedules[schoolid].setdefault(bsid, {})
            for day in school_days:
                logger.info(day['date_value'])
                for t in psterms:
                    if day['date_value'] < t['firstday'] or day['date_value'] > t['lastday']:
                          continue
                    schedules[schoolid][day['bell_schedule_id']].setdefault(t['dcid'], {})
                    if not schedules[schoolid][day['bell_schedule_id']][t['dcid']]:
                        schedules[schoolid][day['bell_schedule_id']][t['dcid']] = client.section_meetings(t['dcid'], schoolid, day['bell_schedule_id'])
                    else:
                          saved_calls += 1
                          logger.info(f"found meeting, saved {saved_calls}")

                    for meeting in schedules[schoolid][day['bell_schedule_id']][t['dcid']]:
                        # roster = client.roster(meeting)
                        meet = {'date': day['date_value'], 'bell_schedule': day['bs_name'], 'school': school_abbreviation}
                        for k in ['start_time', 'end_time', 'term_name']:
                                meet[k] = meeting[k]
                        section_events.setdefault(meeting['section_dcid'], meeting)
                        section_events[meeting['section_dcid']].setdefault('meetings', [])
                        section_events[meeting['section_dcid']]['meetings'].append(meet)



    with open('section_events.json', 'w', encoding='utf-8') as jsonf:
        jsonf.write(json.dumps(section_events, indent=4))



if __name__ == "__main__":
            main()