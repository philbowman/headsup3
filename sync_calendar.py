from re import T
from secrets_parameters import *
from send_email import *

import datetime, pytz, time, socket, logging, httpx, csv, pandas
from logging.handlers import TimedRotatingFileHandler
# use pypypowerschool module included in this repo to run without ssh verification
from pypowerschool import powerschool
from random import randint
from time import sleep
from socket import error as SocketError

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from urllib.error import HTTPError

logging.basicConfig(
     filename='debug.log',
     level=logging.DEBUG, 
     format= '[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
     datefmt='%H:%M:%S'
 )
 
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
#log to file
filelog = TimedRotatingFileHandler("info.log", when='midnight', backupCount=20)
filelog.setLevel(logging.DEBUG)
filelog.setFormatter(formatter)
logging.getLogger('').addHandler(filelog)

# set up logging to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

logger = logging.getLogger(__name__)

creds = service_account.Credentials.from_service_account_file(
		SERVICE_ACCOUNT_FILE, scopes=SCOPES)
delegated_creds = creds.with_subject(calendar_manager_email)
service = build('calendar', 'v3', credentials=delegated_creds)


def my_retry(fn):
    from functools import wraps
    @wraps(fn)
    def wrapped(self, *args, **kwargs):
        failures = 0
        max_tries = 10
        tries = 1
        sleep_time = randint(10, 20)
        while (tries <= max_tries):
            try:
                tries += 1
                return fn(self, *args, **kwargs)
            except (socket.timeout, SocketError, HttpError, TimeoutError, httpx.ReadTimeout, httpx.ConnectError, httpx.ReadError, httpx.ConnectTimeout) as e:
                failures += 1
                message = f"request failed {failures} times: \n{e}"
                logging.info(message)
                print(message)
                sleep(sleep_time)
                sleep_time = tries * sleep_time + randint(1, 10)
    return wrapped

def main():
    #run_update()
    counter = 0
    
    while True:
        now = datetime.datetime.now()

        if now < now.replace(hour=4):
            nextupdate = now.replace(hour=2)
        elif now < now.replace(hour=16):
            nextupdate = now.replace(hour=16)
        else:
            nextupdate = now.replace(hour=4) + datetime.timedelta(days=1)
            
        t = nextupdate - now
        sleep_time = t.total_seconds() + randint(60, 60*60*2)
        logging.info(f"waiting {sleep_time/60/60} hours")
        
        sleep(sleep_time)
        #now += datetime.timedelta(seconds=t.total_seconds())
        
        now = datetime.datetime.now()
        logging.info(now)

        try:
            logging.info("starting update")
            counter += 1
            run_update()
        except Exception as e:
            logging.error(e)
            send_email("OOPS!", e)

def run_update():
    
    runtime_start = time.time()
    
    now = datetime.datetime.now()
    if now > now.replace(hour=15):
        now = now + datetime.timedelta(days=1)
    
    start_date = now.strftime("%Y-%m-%d")
    edt = now + datetime.timedelta(days=30)
    end_date = edt.strftime("%Y-%m-%d")

    #override
    #start_date = "2022-09-26"
    #end_date = "2022-09-27"


    schools = [School(ms_schoolid, ms_calendarid, ms_bell_schedule_calendarid, ms_rotation_calendarid, ms_duty_calendarid, "MS"),
        School(hs_schoolid, hs_calendarid, hs_bell_schedule_calendarid, hs_rotation_calendarid, hs_duty_calendarid, "HS")]

    date_range = Date_Range(schools, start_date, end_date)
    
    runtime = "runtime: " + str(datetime.timedelta(seconds=(time.time()-runtime_start)))
    logging.info(runtime)
    send_email("This was a triumph.", runtime)
    return runtime

class School:
    def __init__(self, schoolid, calendarid, block_calendarid, rotation_calendarid, duty_calendarid, abbreviation):
        self.schoolid = schoolid
        self.calendarid = calendarid
        self.block_calendarid = block_calendarid
        self.rotation_calendarid = rotation_calendarid
        self.duty_calendarid = duty_calendarid
        self.calendarids = [self.calendarid, self.block_calendarid, self.rotation_calendarid, self.duty_calendarid]
        self.abbreviation = abbreviation
        self.days = []
        self.duty_periods = self.make_duty_periods()
        logging.info("INITIALIZED " + str(self))

    def __str__(self):
        return f"SCHOOL {self.abbreviation}"

    def make_duty_periods(self):
        duty_periods = []
        try:
            with open("duties.csv", 'r', encoding='UTF-8') as myfile:
                reader = csv.DictReader(myfile)
                for row in reader:
                    if row['school'] == self.abbreviation:
                        duty_periods.append(row['period'])
                
        except FileNotFoundError:
            logging.info("no duties.csv file found")
        return duty_periods


    def add_day(self, datestr, ps_day, date_range):
        if not ps_day:
            for id in self.calendarids:
                logging.info(f"deleting all events on {datestr}")
                logging.info(f"calendarid: {id}")
                delete_all_events(datestr, datestr, id)
            return None
        logging.info(f"adding {self.abbreviation} day on {datestr}")
        d = Day(ps_day, date_range, self)
        self.days.append(d)
        return d

class Date_Range:
    def __init__(self, schools, start_date, end_date=None):
        self.client = Query()
        self.schools = schools
        self.days = []

        self.start_date = start_date
        if end_date:
            self.end_date = end_date
        else:
            self.end_date = start_date
        
        self.date_list = pandas.date_range(start=start_date, end=end_date).to_pydatetime().tolist()
        for date in self.date_list:
            for school in schools:
                datestr = date.strftime('%Y-%m-%d')
                ps_day = self.make_ps_days(datestr, datestr, school.schoolid)
                day = school.add_day(datestr, ps_day, self)
                if day:
                    self.days.append(day)
        logging.info(f"INITIALIZED {self}")
    def __str__(self):
        return f"DATE RANGE {self.start_date}-{self.end_date}"

    @my_retry
    def make_ps_days(self, start_date, end_date, schoolid):
        cd = []
        school_days = self.client.calendar_days(start_date, end_date, schoolid)
        if len(school_days) == 1:
            return school_days[0]
        elif len(school_days) == 0:
            return []
        for day in school_days:
            cd.append(day)
        return cd

class Day:
    def __init__(self, ps_day, date_range, school):
        logging.info(f"creating day {ps_day['date_value']}")
        self.client = date_range.client
        #inherit from date_range and section_meeting query
        self.day = ps_day
        self.calendar_day_dcid = ps_day['dcid']
        self.date_range = date_range
        self.school = school
        self.schoolid = school.schoolid
        self.termdcids = self.query_term_dcids()
        self.terms = []
        self.term = self.query_term()
        self.term_abbreviations = self.make_term_abbreviations()
        self.term_abbreviation = self.term['abbreviation']

        #strings to use for allday titles
        self.block_string = "" #constructed during make_block_meetings
        self.number = ""
        self.name = self.make_day_name()

        self.desired_duty_events = []
        self.duty_events = [] #generated at the Event level
        
        #date objects
        self.date = datetime.datetime.strptime(ps_day['date_value'], "%Y-%m-%d")
        self.localized_daystart = pytz.timezone("Asia/Amman").localize(self.date)
        self.localized_dayend = pytz.timezone("Asia/Amman").localize(self.date + datetime.timedelta(hours=23, minutes=59))

        #block events
        self.desired_block_events = []
        self.existing_block_events = self.update_existing_events(self.school.block_calendarid)
        self.existing_duty_events = self.update_existing_events(self.school.duty_calendarid)
        self.block_meetings = self.make_block_meetings()
        self.block_events = self.make_block_events()
        self.deleted_block_events = self.delete_extra_events(self.block_events, self.existing_block_events, self.desired_block_events, self.school.block_calendarid)

        #duty events

        self.deleted_block_events = self.delete_extra_events(self.duty_events, self.existing_duty_events, self.desired_duty_events, self.school.duty_calendarid)
                
        #class events
        self.desired_class_events = []
        self.existing_class_events = self.update_existing_events(self.school.calendarid)
        self.class_meetings = self.make_class_meetings()
        self.class_events = self.make_class_events()
        self.deleted_class_events = self.delete_extra_events(self.class_events, self.existing_class_events, self.desired_class_events, self.school.calendarid)
        
        #allday events
        self.allday_event = All_Day_Event(self)

        logging.info("INITIALIZED" + str(self))

    def __str__(self):
        return f"DAY {self.date} {self.term_abbreviation} {self.term_abbreviations} {self.school}"

    def make_term_abbreviations(self):
        abr = []
        for t in self.terms:
            abr.append(t['abbreviation'])
        logging.info(f"terms for {self.day['date_value']}: {abr}")
        return abr

        
    def query_term(self):
        terms = self.client.terms(self.day['date_value'], self.schoolid)
        self.terms = terms
        earliest_end_date = terms[0]['lastday']
        term = terms[0]
        for t in terms:
            if t['lastday'] < earliest_end_date:
                term = t
                earliest_end_date = t['lastday']
        return term

    def make_day_name(self):
        bs_name = self.day['bs_name']
        logging.info(f"bs name: {self.day['bs_name']}")
        #grab a single digit separated by spaces out of the bell schedule name after replacing underscores with spaces
        numbers = [int(s) for s in bs_name.replace("_", " ").split() if s.isdigit()]
        if len(numbers) == 1:
            self.number = numbers[0]
        else:
            self.number = "?"
        logging.info(f"number: {self.number}")

        return "Day " + str(self.number)

    @my_retry
    def query_term_dcids(self):
        return self.client.termdcids(self.day['date_value'], self.schoolid)

    @my_retry
    def update_existing_events(self, calendarid):
        events = service.events().list(maxResults=2500, calendarId=calendarid, timeMin=str(self.localized_daystart.isoformat()), timeMax=str(self.localized_dayend.isoformat())).execute().get('items', [])
        return events

    @my_retry
    def make_class_meetings(self):
        meet = []
        for termid in self.termdcids:
            meeting_set = self.client.section_meetings(termid, self.schoolid, self.day['bell_schedule_id'])
            for m in meeting_set:
                try:
                    if m['teacher_email'] not in selected_teachers and update_only_selected_teachers:
                        continue
                    else:
                        meet.append(m)
                except KeyError:
                    continue
                
        return meet

    def make_class_events(self):
        e = []
        for m in self.class_meetings:
            if int(m['no_of_students']) > 0:
                ev = Event(m, self, "class")
                e.append(ev)
                self.desired_class_events.append(ev.calendar_event.gcal_event)
        return e

    @my_retry
    def make_block_meetings(self):
        blocks = self.client.blocks(self.calendar_day_dcid, self.schoolid)
        block_list = []
        for b in blocks:
            block_list.append(b['abbreviation'])
        self.block_string = ",".join(block_list)
        return blocks

    def make_block_events(self):
        e = []
        for m in self.block_meetings:
            ev = Event(m, self, "block")
            e.append(ev)
            self.desired_block_events.append(ev.calendar_event.gcal_event)
        return e        
    
    @my_retry
    def delete_extra_events(self, events, existing_events, desired_events, calendarid):
        existing_events = self.update_existing_events(calendarid)
        desired_gcal_event_ids = []
        for e in desired_events:
            desired_gcal_event_ids.append(e['id'])

        #logging.info(f"desired events: {desired_events}")
        logging.debug(f"desired ids: {desired_gcal_event_ids}")
        deleted_events = []
        for e in existing_events:
            if e['id'] not in desired_gcal_event_ids:
                logging.info(f"{e['id']} not in desired list")
                service.events().delete(calendarId=calendarid, eventId=e['id'], sendUpdates="none").execute()
                deleted_events.append(e)
                logging.info("Successfully deleted" + e['summary'])
            else:
                logging.info(f"Not deleting {e['id']}")

        logging.debug("deleted events: \n" + str(deleted_events))
        return deleted_events

    @my_retry
    def delete_all_events(self, existing_events, calendarid):
        for e in existing_events:
            service.events().delete(calendarId=calendarid, eventId=e['id'], sendUpdates="none").execute()

class Event:
    def __init__(self, meeting, day, event_type, duty=None):
        self.client = day.client
        self.roster = [] #generated during make_emails_list()

        self.meeting = meeting
        self.day = day
        self.date = day.date
        self.school = day.school
        self.event_type = event_type
        try:
            self.term = meeting['term_name']
        except KeyError:
            self.term = day.term_abbreviation
        logging.info("term: " + self.term)
    
        self.start_timestamp = int(meeting['start_time'])
        self.end_timestamp = int(meeting['end_time'])

        if event_type == "class":
            self.no_of_students = int(meeting['no_of_students'])
            self.section_dcid = meeting['section_dcid']
            self.duties = []
            prefix = meeting['period_abbreviation'] + "-"
            self.title = f"{prefix}{meeting['course_name']} ({meeting['last_name']})"
            self.emails = self.make_emails_list()
        if event_type == "block":
            self.no_of_students = -1
            self.section_dcid = -1
            self.emails = []
            t = None
            if period_abbreviation_exceptions:
                for exc in period_abbreviation_exceptions:
                    if meeting['abbreviation'] == exc['abbreviation']:
                        t = exc['title']
                        break
            if t:
                self.title = t
            else:
                self.title = meeting['abbreviation']
            if self.title in self.school.duty_periods:
                self.duties = self.make_duty_events()
        if event_type == "duty":
            self.no_of_students = -1
            self.section_dcid = -1
            self.emails = duty['teacher_emails']
            self.title = duty['title']

        self.start_datetime = self.date + datetime.timedelta(seconds=self.start_timestamp)
        self.end_datetime = self.date + datetime.timedelta(seconds=self.end_timestamp)
        self.meeting_time = f"{self.start_datetime.isoformat()}-{self.end_datetime.isoformat()[-8:]}"
        self.calendar_event = self.make_calendar_event()
        logging.info("INITIALIZED " + str(self))

    def __str__(self):
        return f"EVENT {self.title} {self.meeting_time} [{len(self.emails)} attendees]"

    def make_duty_events(self):
        logging.info(f"making {self.school.abbreviation} duties for {self.title} on Day {self.day.number}" )
        duties = []
        try:
            with open("duties.csv", 'r', encoding='UTF-8') as myfile:
                reader = csv.DictReader(myfile)
                #TODO remove blank lines
                for row in reader:
                    logging.debug(str(row))
                    if not (row['email'] and row['duty'] and row['day'] and row['period'] and row['semester'] and row['school']):
                        logging.debug("...skipping")
                        continue
                    if row['school'] == self.school.abbreviation and row['period'] == self.title and row['semester'] in self.day.term_abbreviations and str(row['day']) == str(self.day.number):
                        logging.info(f"creating {str(row)}")
                        duty = {'teacher_emails': row['email'].replace(" ", "").split(","), 'title': row['duty'] + " Duty", 'day': "Day " + row['day']}
                        d = Event(self.meeting, self.day, "duty", duty)
                        duties.append(d)
                        self.day.duty_events.append(d)
                        self.day.desired_duty_events.append(d.calendar_event.gcal_event)
                    else:
                        logging.debug("...skipping")
        except FileNotFoundError:
            logging.error("no duties.csv file found")
        return duties

    @my_retry
    def make_emails_list(self):
        logging.debug(self.meeting)
        e = [self.meeting['teacher_email']]
        if extra_invites:
            for exc in extra_invites:
                if self.title == exc['event_title']:
                    e.append(exc['email'])

        self.roster = self.client.roster(self.meeting)
        for s in self.roster:
            e.append(s['email'])
        return e

    def make_calendar_event(self):
        #block and duty events have -1 as no_of_students
        if self.no_of_students > 0 or self.no_of_students == -1:
            logging.info("creating Calendar Event")
            return Calendar_Event(self)
        return None

class Calendar_Event:
    def __init__(self, event, skip_students=False):
        self.event = event
        self.title = event.title        
        self.school = event.school
        self.skip_students = skip_students

        self.description = ""

        if event.event_type == "block":
            self.calendarid = self.school.block_calendarid
            self.existing_events = event.day.existing_block_events
        if event.event_type == "class":
            self.calendarid = self.school.calendarid
            self.existing_events = event.day.existing_class_events
        if event.event_type == "duty":
            self.calendarid = self.school.duty_calendarid
            self.existing_events = event.day.existing_duty_events

        self.payload = self.make_payload()
        self.gcal_event = self.update()
        logging.info(f"INITIALIZED {self}")

    def __str__(self):
        return f"CALENDAR EVENT {self.title} ({self.school})"

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
            'start': 
            {
                'dateTime': self.event.start_datetime.isoformat(),
                'timeZone': 'Asia/Amman',
            },
            'end': 
            {
                'dateTime': self.event.end_datetime.isoformat(),
                'timeZone': 'Asia/Amman',
            },
            "guestsCanInviteOthers": False,
            "guestsCanModify": False,
            "description": self.description,
            "attendees": attendees,
            "extendedProperties": 
            {
                "shared": 
                {
                    'event_type': self.event.event_type,
                    'schoolid': str(self.school.schoolid),
                    'end_dateT': self.event.end_datetime.isoformat(),
                    'description': self.description, 
                    'section_dcid': str(self.event.section_dcid),
                    'term': self.event.term,
                    'start_dateT': self.event.start_datetime.isoformat(),
                    'no_of_students': str(self.event.no_of_students)
                }
            }
        }
        return payload

    def compare_attendees(self,remote):
        remote_emails = []
        for a in remote:
            remote_emails.append(a['email'])
            if a['email'] not in self.event.emails:
                logging.debug(f"{a['email']} not in {self.event.emails}")
                return False
        for e in self.event.emails:
            if e not in remote_emails:
                logging.debug(f"{e} not in {remote_emails}")
                return False
        return True

    @my_retry
    def update(self):
        logging.info(f"updating {self.payload['summary']} on {self.event.day.date}")
        logging.debug(self.payload)
        logging.debug(f"{len(self.existing_events)} existing events")
        for event in self.existing_events:    
            try:
                #find by name
                if self.payload['summary'] == event['summary']:
                    logging.info("Found existing event")

                    #compare extended properties
                    if self.payload['extendedProperties']['shared'] == event['extendedProperties']['shared'] and self.compare_attendees(event['attendees']):
                        logging.info("Existing event is up to date")
                        return event
                    else:
                        #patch changed event
                        logging.info(f"patching {self.payload['summary']}")
                        logging.debug(f"payload: {self.payload['extendedProperties']['shared']}")
                        logging.debug(f"existing: {event['extendedProperties']['shared']}")
                        return service.events().patch(calendarId=self.calendarid, eventId=event['id'], body=self.payload, sendUpdates="none").execute()
            except (KeyError, TypeError) as e:
                logging.warn(f"{event['summary']} does not match {self.payload['summary']}")
                logging.warn(e)
        return self.add()

    @my_retry
    def add(self):
        logging.info(f"adding {self.title}")
        gcal_event = None
        self.make_payload()
        gcal_event = service.events().insert(conferenceDataVersion=1, calendarId=self.calendarid, body=self.payload, sendUpdates="none").execute()
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
    
class All_Day_Event:
    def __init__(self, day):
        self.day = day
        self.name = day.name
        self.title = day.name + "-" + day.block_string
        self.date = day.day['date_value']
        self.school = day.school
        self.block_string = day.block_string
        self.event_type = "allday"
        self.description = ""
        self.calendarid = day.school.rotation_calendarid 

        self.payload = self.make_payload()
        self.existing_events = self.update_existing_events()
        self.gcal_event = self.update()
        self.deleted_events = self.delete_extra_events()
        logging.info(f"INITIALIZED {self}")

    def __str__(self):
        return f"ALLDAY EVENT {self.title}"

    def make_payload(self):        
        payload =  {
            'summary': self.title,
            'start': {
                'date': self.date
            },
            'end': {
                'date': self.date
            },
            "description": self.description,
            "extendedProperties": {
                "shared": {
                    "event_type": self.event_type,
                    "date": self.date,
                    "description": self.description,
                    "schoolid": str(self.school.schoolid),
                    "blocks": self.block_string,
                    "title": self.title
                },
            }
        }
        return payload

    @my_retry
    def update_existing_events(self):
        events = service.events().list(maxResults=2500, calendarId=self.calendarid, timeMin=str(self.day.localized_daystart.isoformat()), timeMax=str(self.day.localized_dayend.isoformat())).execute().get('items', [])
        return events

    @my_retry
    def update(self):
        payload = self.payload
        logging.info("updating " + payload['summary'])
        logging.info(f"{len(self.existing_events)} existing events")
        for event in self.existing_events:    
            try:
                #find by name
                if event['extendedProperties']['shared']['event_type'] == "allday":
                    logging.info("Found existing event")

                    if event['extendedProperties']['shared'] == payload['extendedProperties']['shared']:
                        logging.info("Existing event is up to date")

                        return event
                    else:
                        logging.info(f"patching {payload['summary']}")
                        return service.events().patch(calendarId=self.calendarid, eventId=event['id'], body=self.payload, sendUpdates="none").execute()
            except (KeyError, TypeError) as e:
                logging.debug(event['summary'] + "does not match:")
                logging.debug(e)

        return service.events().insert(conferenceDataVersion=1, calendarId=self.calendarid, body=self.payload, sendUpdates="none").execute()

    @my_retry
    def delete_extra_events(self):
        self.existing_events = self.update_existing_events()
        deleted_events = []
        for e in self.existing_events:
            if e['extendedProperties']['shared']['event_type'] == "allday":
                if e['id'] != self.gcal_event['id']:
                    service.events().delete(calendarId=self.calendarid, eventId=e['id'], sendUpdates="none").execute()
                    deleted_events.append(e)
                    logging.debug(f"Deleted {e['summary']} \n(not in desired list)")
                else:
                    logging.debug(f"Not deleting {e['id']}")

        logging.debug("deleted events: \n" + str(deleted_events))
        return deleted_events

class Query:
    
    def __init__(self):
        self.client = powerschool.Client(ps_url, client_id, client_secret)

    @my_retry
    def call(self, query_name, parameters):
        logging.info(query_name)	
        response = remove_dupes(self.client.powerquery(query_name, parameters))
        logging.debug(response)
        return response

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
        yearid = yearids[0]['yearid']

        #get the terms for the year
        query_name = "/ws/schema/query/" + "com.pearson.core.terms.year_terms"
        p = {
        "schoolid": schoolid,
        "yearid": yearid
        }
        termdcids = []
        terms = self.call(query_name, p)

        for t in terms:
            if t['firstday'] < date and t['lastday'] > date:
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
            logging.debug("removed dupe: " + str(d))

    return new_l

@my_retry
def delete_all_events(start_date_str, end_date_str, calendarid):
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
    localized_daystart = pytz.timezone("Asia/Amman").localize(start_date)
    localized_dayend = pytz.timezone("Asia/Amman").localize(end_date + datetime.timedelta(hours=23, minutes=59))
    existing_events = service.events().list(maxResults=2500, calendarId=calendarid, timeMin=str(localized_daystart.isoformat()), timeMax=str(localized_dayend.isoformat())).execute().get('items', [])
    for e in existing_events:
        service.events().delete(calendarId=calendarid, eventId=e['id'], sendUpdates="none").execute()

if __name__ == "__main__":
        main()