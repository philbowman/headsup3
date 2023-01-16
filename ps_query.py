# use pypypowerschool module included in this repo to run without ssh verification
from pypowerschool import powerschool
from my_retry import *
from secrets_parameters import ps_url, client_id, client_secret
from logdef import *

class Query:
    def __init__(self):
        self.client = powerschool.Client(ps_url, client_id, client_secret)

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

    def section_meetings(self, termdcid, schoolid, bell_schedule_id):
        query_name = "/ws/schema/query/" + "headsup_section_meetings"
        p = {
            
                "schoolid": schoolid,
                "termdcid": termdcid,
                "bell_schedule_id": bell_schedule_id
        }
        section_meetings = self.call(query_name, p)
        return section_meetings

    def roster(self, event):
        query_name = "/ws/schema/query/" + "headsup_roster"

        p = {
            "section_dcid": event['section_dcid']
        }
        roster = self.call(query_name, p)
        return roster

    def terms(self, date, schoolid):
            #get the yearid
        query_name = "/ws/schema/query/" + "com.pearson.core.terms.yearid"
        p = {
        "schoolid": 0,
        "currentdate": date
        }
        yearids = self.call(query_name, p)
        yearid = yearids[0]['yearid']

        #get the terms for the year
        query_name = "/ws/schema/query/" + "com.pearson.core.terms.year_terms"
        p = {
        "schoolid": schoolid,
        "yearid": yearid
        }
        terms = self.call(query_name, p)
        return terms

    def termdcids(self, date, schoolid):
        #get the yearid
        query_name = "/ws/schema/query/" + "com.pearson.core.terms.yearid"
        p = {
        "schoolid": 0,
        "currentdate": date
        }
        yearids = self.call(query_name, p)
        try:
            yearid = yearids[0]['yearid']
        except IndexError:
            return []

        #get the terms for the year
        query_name = "/ws/schema/query/" + "com.pearson.core.terms.year_terms"
        p = {
        "schoolid": schoolid,
        "yearid": yearid
        }
        termdcids = []
        terms = self.call(query_name, p)

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
