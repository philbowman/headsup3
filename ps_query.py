from pypypowerschool import Client as PSClient
import datetime
from my_retry import *
from secrets_parameters import ps_url, client_id, client_secret
from logdef import *

class Query:
    def __init__(self):
        self.client = PSClient(ps_url, client_id, client_secret, 300)

    @my_retry
    def call(self, query_name, parameters):
        logger.info(query_name)	
        response = remove_dupes(self.client.powerquery(query_name, parameters))
        logger.debug(response)
        return response

    def assignments(self, sectiondcid):
        query_name = "/ws/xte/section/assignment/"
        p = {
            "section_ids": sectiondcid
        }
        assignments = self.client.powerquery(query_name, p)
        return assignments

    def district_cycle_days(self, yearid_in=None):
        if not yearid_in:
            yearids = self.yearid()
        else:
            yearids = [yearid_in]

        query_name = "/ws/schema/query/com.pearson.core.calendar.district_cycle_days"
        cycle_days = []
        for yearid in yearids:
            p = {
                "yearid": yearid
            }
            cd = self.call(query_name, p)
            print(cd)
            cycle_days += cd
        return cycle_days
    
    def calendar_days(self, start_date, end_date, schoolid):
        query_name = "/ws/schema/query/" + "headsup_calendar_days"
        p = {
            "school_id_in": schoolid,
            "start_date": start_date,
            "end_date": end_date
        }
        calendar_days = self.call(query_name, p)
        return calendar_days

    def blocks(self, calendar_day_dcid_in, schoolid):
        query_name = "/ws/schema/query/" + "headsup_blocks"
        p = {
            
                "calendar_day_dcid_in": calendar_day_dcid_in,
                "school_id": schoolid
        }
        blocks = self.call(query_name, p)
        return blocks

    def section_meetings(self, termdcid, schoolid, bell_schedule_id, cycle_day_letter=None):
        query_name = "/ws/schema/query/" + "headsup_section_meetings"
        p = {
            
                "schoolid": schoolid,
                "termdcid": termdcid,
                "bell_schedule_id": bell_schedule_id
        }
        section_meetings = self.call(query_name, p)
        if cycle_day_letter:
            return [s for s in section_meetings if cycle_day_letter == s['cycle_day_letter']]
        return section_meetings
    
    def roster(self, event):
        query_name = "/ws/schema/query/" + "headsup_roster"

        p = {
            "section_dcid": event['section_dcid']
        }
        roster = self.call(query_name, p)
        return roster

    def yearid(self, currentdate=None):
        if not currentdate:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
        else:
            date = currentdate
        # print(date)
        query_name = "/ws/schema/query/" + "com.pearson.core.terms.yearid"
        p = {
        "schoolid": 0,
        "currentdate": date
        }
        yearids = self.call(query_name, p)
        # print(yearids)
        if not yearids:
            return []
        return [y['yearid'] for y in yearids]

    def terms(self, date, schoolid):
        #get the yearid
        yearids = self.yearid(date)
        terms = []
        for yearid in yearids:
            #get the terms for the year
            query_name = "/ws/schema/query/" + "com.pearson.core.terms.year_terms"
            p = {
            "schoolid": schoolid,
            "yearid": yearid
            }
            terms += self.call(query_name, p)
        return terms

    def termdcids(self, date, schoolid):
        #get the yearid
        yearids = self.yearid(date)

        #get the terms for the year
        terms = []
        for yearid in yearids:
            query_name = "/ws/schema/query/" + "com.pearson.core.terms.year_terms"
            p = {
            "schoolid": schoolid,
            "yearid": yearid
            }
            
            terms += self.call(query_name, p)
        termdcids = []
        for t in terms:
            if t['firstday'] <= date and t['lastday'] >= date:
                termdcids.append(t['dcid'])
        return termdcids

def remove_dupes(l):
    seen = set()
    new_l = []
    for d in l:
        t = tuple(d.items())
        if t not in seen:
            seen.add(t)
            new_l.append(d)
        else:
            logger.debug("removed dupe: " + str(d))

    return new_l




# def ps_query_test():
#     date = ""
#     while date != "exit":
#         date = input("date: ")
#         print(Query().district_cycle_days(date))