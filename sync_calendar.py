from secrets import *
import datetime, pytz, time, socket, httpx, logging

from pypowerschool import powerschool
from random import random
from time import sleep
from socket import error as SocketError

import google.auth
from google.oauth2 import service_account
from oauth2client.service_account import ServiceAccountCredentials
import googleapiclient.discovery
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

logging.basicConfig(filename='debug.log', encoding='utf-8', level=logging.INFO)

runtime_start = time.time()

def delete_all_events(start_date_str, end_date_str, calendarid):
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
    localized_daystart = pytz.timezone("Asia/Amman").localize(start_date)
    localized_dayend = pytz.timezone("Asia/Amman").localize(end_date + datetime.timedelta(hours=23, minutes=59))
    existing_events = service.events().list(maxResults=2500, calendarId=calendarid, timeMin=str(localized_daystart.isoformat()), timeMax=str(localized_dayend.isoformat())).execute().get('items', [])
    for e in existing_events:
        service.events().delete(calendarId=calendarid, eventId=e['id'], sendUpdates="none").execute()

def my_retry(fn):
    from functools import wraps
    @wraps(fn)
    def wrapped(self, *args, **kwargs):
        failures = 0
        max_tries = 10
        tries = 1
        sleep_time = 0
        while (tries <= max_tries):
            try:
                tries += 1
                return fn(self, *args, **kwargs)
            except (socket.timeout, SocketError, HttpError, httpx.ConnectError, httpx.ReadError, httpx.ConnectTimeout) as e:
                failures += 1
                message = f"failed {failures} times: \n{e}"
                logging.info(message)
                print(message)
                sleep(sleep_time)
                sleep_time = tries * sleep_time + random()
    return wrapped

def main():    

    start_date = "2022-09-18"
    end_date = "2022-09-19"

    schools = [School(hs_schoolid, hs_calendarid, hs_bell_schedule_id), School(ms_schoolid, ms_calendarid, ms_bell_schedule_id)]
    date_ranges = []
    for school in schools:
        date_ranges.append(Date_Range(school, start_date, end_date))
            

    
    
    runtime = time.time()-runtime_start
    logging.info(str(runtime) + "seconds")
    #logging.info(foo.days[0].existing_events)
    return runtime

class School:
    def __init__(self, schoolid, calendarid, block_calendarid):
        self.schoolid = schoolid
        self.calendarid = calendarid
        self.block_calendarid = block_calendarid

class Date_Range:
    def __init__(self, school, start_date, end_date=None):
        self.school = school
        self.start_date = start_date
        if end_date:
            self.end_date = end_date
        else:
            self.end_date = start_date
        self.client = Query()
        self.calendar_days = self.make_calendar_day_list()
        self.days = self.make_days()
    
    @my_retry
    def make_calendar_day_list(self):
        cd = []
        school_days = self.client.calendar_days(self.start_date, self.end_date, self.school.schoolid, True)
        for day in school_days:
            cd.append(day)
        return cd

    def make_days(self):
        days = []
        for d in self.calendar_days:
            days.append(Day(d, self))
        return days

class Day:
    def __init__(self, day, date_range):
        self.day = day
        self.date_range = date_range
        self.school = self.date_range.school
        self.client = Query()
        self.date = datetime.datetime.strptime(self.day['date_value'], "%Y-%m-%d")
        self.localized_daystart = pytz.timezone("Asia/Amman").localize(self.date)
        self.localized_dayend = pytz.timezone("Asia/Amman").localize(self.date + datetime.timedelta(hours=23, minutes=59))
        self.schoolid = self.school.schoolid
        self.termdcids = self.client.termdcids(self.day['date_value'], self.schoolid)
        self.existing_class_events = self.update_existing_events(self.school.calendarid)
        self.existing_block_events = self.update_existing_events(self.school.block_calendarid)
        self.class_meetings = self.make_class_meetings()
        self.block_meetings = self.make_block_meetings()
        self.block_events = self.make_block_events()
        self.class_events = self.make_class_events()
        self.deleted_class_events = self.delete_extra_days(self.class_events, self.existing_class_events, self.school.calendarid)
        self.deleted_block_events = self.delete_extra_days(self.block_events, self.existing_block_events, self.school.block_calendarid)

    @my_retry
    def make_block_meetings(self):
        blocks = self.client.blocks(22371, 681005, True)
        return blocks

    def make_class_meetings(self):
        meet = []
        for termid in self.termdcids:
            meeting_set = self.client.section_meetings(termid, self.schoolid, self.day['bell_schedule_id'], True)
            for m in meeting_set:
                meet.append(m)
        return meet

    def make_block_events(self):
        e = []
        for m in self.block_meetings:
            e.append(Event(m, self, "block"))
        return e        

    def make_class_events(self):
        e = []
        for m in self.class_meetings:
            if int(m['no_of_students']) > 0:
                e.append(Event(m, self, "class"))
        return e

    @my_retry
    def delete_all_events(self, existing_events, calendarid):
        for e in existing_events:
            service.events().delete(calendarId=calendarid, eventId=e['id'], sendUpdates="none").execute()
    
    @my_retry
    def update_existing_events(self, calendarid):
        events = service.events().list(maxResults=2500, calendarId=calendarid, timeMin=str(self.localized_daystart.isoformat()), timeMax=str(self.localized_dayend.isoformat())).execute().get('items', [])
        return events

    @my_retry
    def delete_extra_days(self, events, existing_events, calendarid):

        desired_gcal_event_ids = []
        for e in events:
            if e.calendar_event and e.calendar_event.gcal_event:
                desired_gcal_event_ids.append(e.calendar_event.gcal_event['id'])
        
        deleted_events = []
        for e in existing_events:
            if e['id'] not in desired_gcal_event_ids:
                service.events().delete(calendarId=calendarid, eventId=e['id'], sendUpdates="none").execute()
                deleted_events.append(e)
                logging.info("Successfully deleted" + e['summary'])
            else:
                logging.info(f"Not deleting {e['id']}")

        logging.info("deleted events: \n" + str(deleted_events))
        return deleted_events

class Event:
    def __init__(self, meeting, day, event_type):
        self.event_type = event_type
        self.meeting = meeting
        self.day = day
        self.date = self.day.date
        self.school = self.day.school
        self.client = Query()
        self.roster = []
        self.event_type = event_type
        self.start_timestamp = int(meeting['start_time'])
        self.end_timestamp = int(meeting['end_time'])
        if self.event_type == "class":
            self.term = meeting['term_name']
            self.no_of_students = int(meeting['no_of_students'])
            self.section_dcid = meeting['section_dcid']
            self.emails = self.make_emails_list()
            self.title = f"{meeting['period_abbreviation']}-{meeting['course_name']} ({meeting['last_name']})"
        if self.event_type == "block":
            self.term = "block"
            self.no_of_students = -1
            self.section_dcid = -1
            self.emails = []
            self.title = meeting['abbreviation']

        self.start_datetime = self.date + datetime.timedelta(seconds=self.start_timestamp)
        self.end_datetime = self.date + datetime.timedelta(seconds=self.end_timestamp)
        self.meeting_time = f"{self.start_datetime.isoformat()}-{self.end_datetime.isoformat()[-8:]}"
        self.calendar_event = self.make_calendar_event()
        logging.info(self)
    #def __init__(self, )

    def make_calendar_event(self):
        if self.no_of_students > 0 or self.no_of_students == -1:
            logging.info("creating Calendar Event")
            return Calendar_Event(self)
        return None
    
    def make_emails_list(self):
        e = []
        if update_only_selected_teachers == True:
            if self.meeting['teacher_email'] not in selected_teachers:
                return e
        e = [self.meeting['teacher_email']]
        self.roster = self.client.roster(self.meeting, True)
        for s in self.roster:
            e.append(s['email'])
        return e


    def __str__(self):
        return f"{self.title} {self.meeting_time} {self.emails}"

class Calendar_Event:
    def __init__(self, event):
        self.event = event
        self.school = event.school
        if event.event_type == "block":
            self.calendarid = self.school.block_calendarid
            self.existing_events = event.day.existing_block_events
        if event.event_type == "class":
            self.calendarid = self.school.calendarid
            self.existing_events = event.day.existing_class_events
        self.title = self.event.title
        self.description = ""
        self.skip_students = False
        self.payload = self.make_payload()
        self.gcal_event = self.payload



        self.update()

    def make_payload(self):
        attendees = []
        for email in self.event.emails:
            if self.skip_students:
                    attendees.append({'email': self.event.emails[0], 'responseStatus': "accepted"})
                    break
            else:
                attendees.append({'email': email, 'responseStatus': "accepted"})

        payload =  {
            'summary': self.title,
            'start': {
                'dateTime': self.event.start_datetime.isoformat(),
                'timeZone': 'Asia/Amman',
            },
            'end': {
                'dateTime': self.event.end_datetime.isoformat(),
                'timeZone': 'Asia/Amman',
            },
            "guestsCanInviteOthers": False,
            "guestsCanModify": False,
            "description": self.description,
            "attendees": attendees,
            "extendedProperties": {
                "shared": {
                    "invitees": str(attendees),
                    "event_type": self.event.event_type,
                    "section_dcid": str(self.event.section_dcid),
                    "no_of_students": str(self.event.no_of_students),
                    "term": self.event.term,
                    "start_dateT": self.event.start_datetime.isoformat(),
                    "end_dateT": self.event.end_datetime.isoformat(),
                    "description": self.description,
                    "schoolid": str(self.school.schoolid)
                },
            }
        }
        return payload
    
    @my_retry
    def update(self):
        logging.info("updating " + self.gcal_event['summary'])
        logging.info(f"{len(self.existing_events)} existing events")
        for event in self.existing_events:    
            try:
                #find by name
                if self.gcal_event['summary'] == event['summary']:
                    logging.info("Found existing event")

                    if self.gcal_event['extendedProperties']['shared'] == self.gcal_event['extendedProperties']['shared']:
                        logging.info("Existing event is up to date")
                        self.gcal_event = event
                        return
                    else:
                        logging.info(f"patching {event['summary']}")
                        self.gcal_event = service.events().patch(calendarId=self.calendarid, eventId=event['id'], body=self.payload, sendUpdates="none").execute()
                        return
            except (KeyError, TypeError) as e:
                logging.debug(event['summary'] + "does not match:")
                logging.debug(e)
        self.gcal_event = self.add_to_calendar()
        return self.gcal_event

    @my_retry
    def add_to_calendar(self, log=False):
        gcal_event = None
        self.make_payload()
        gcal_event = service.events().insert(conferenceDataVersion=1, calendarId=self.calendarid, body=self.payload, sendUpdates="none").execute()
        self.gcal_event = gcal_event
        return gcal_event
    
    @my_retry
    def delete(self, event=None):
        if self.gcal_event == None and event == None:
            logging.info("No gcal event to delete")
            return None
        if event == None:
            event = self.gcal_event
        logging.info(f"Attempting delete of {event['summary']}")
        error = ""
        try:
            d = service.events().delete(calendarId=cal_gcal_id, eventId=gcal_id, sendUpdates="none").execute()
            
            if d:
                error = f"error when deleting {event['summary']}: {d}"

        except HttpError as e:
            error = f"error when deleting {event['summary']}: ({e})"

        if error != None:
            return error
        logging.info("Successfully deleted" + event['summary'])

class Query:
    
    def __init__(self):
        self.client = powerschool.Client(ps_url, client_id, client_secret)

    @my_retry
    def call(self, query_name, parameters, log):
        if log:
            logging.info(query_name)	
        response = remove_dupes(self.client.powerquery(query_name, parameters))
        return response

    def calendar_days(self, start_date, end_date, schoolid, log=False):
        query_name = "/ws/schema/query/org.psugcal.ps8.school.headsup_calendar_days"
        p = {
            "school_id_in": schoolid,
            "start_date": start_date,
            "end_date": end_date
        }
        calendar_days = self.call(query_name, p, log)
        return calendar_days

    def blocks(self, calendar_day_dcid_in, schoolid, log=False):
        query_name = "/ws/schema/query/org.psugcal.ps8.school.headsup_blocks"
        p = {
            
                "calendar_day_dcid_in": calendar_day_dcid_in,
                "school_id": schoolid
        }
        blocks = self.call(query_name, p, True)
        return blocks

    def section_meetings(self, termdcid, schoolid, bell_schedule_id, log=False):
        query_name = "/ws/schema/query/org.psugcal.ps8.school.headsup_section_meetings"
        p = {
            
                "schoolid": schoolid,
                "termdcid": termdcid,
                "bell_schedule_id": bell_schedule_id
        }
        section_meetings = self.call(query_name, p, True)
        return section_meetings

    def roster(self, event, log=False):
        query_name = "/ws/schema/query/org.psugcal.ps8.school.headsup_roster"

        p = {
            "section_dcid": event['section_dcid']
        }
        roster = self.call(query_name, p, log)
        return roster

    def termdcids(self, date, schoolid, log=False):
            #get the yearid
        query_name = "/ws/schema/query/com.pearson.core.terms.yearid"
        p = {
        "schoolid": 0,
        "currentdate": date
        }
        yearids = self.call(query_name, p, log)
        yearid = yearids[0]['yearid']

        #get the terms for the year
        query_name = "/ws/schema/query/com.pearson.core.terms.year_terms"
        p = {
        "schoolid": schoolid,
        "yearid": yearid
        }
        termdcids = []
        terms = self.call(query_name, p, log)

        for t in terms:
            if t['firstday'] < date and t['lastday'] > date:
                termdcids.append(t['dcid'])
        return termdcids


def write_to_file(payload, filename):
    with open(filename, 'w') as file:
        for row in payload:
            file.write(str(row))


def remove_dupes(l):
    seen = set()
    new_l = []
    for d in l:
        t = tuple(d.items())
        if t not in seen:
            seen.add(t)
            new_l.append(d)
        else:
            logging.info("removed dupe: " + str(d))

    return new_l


if __name__ == "__main__":
    main()