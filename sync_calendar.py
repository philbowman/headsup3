from re import T
from secrets_parameters import *
from send_email import *
from logdef import *
from ps_query import *
from my_retry import *

import datetime, pytz, time, csv, pandas
from random import randint
from time import sleep

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

creds = service_account.Credentials.from_service_account_file(
		SERVICE_ACCOUNT_FILE, scopes=SCOPES)
delegated_creds = creds.with_subject(calendar_manager_email)
service = build('calendar', 'v3', credentials=delegated_creds)

def main(start_date=None, end_date=None):
    run_update(start_date, end_date)
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
        logger.info(f"waiting {sleep_time/60/60} hours")
        
        sleep(sleep_time)
        #now += datetime.timedelta(seconds=t.total_seconds())
        
        now = datetime.datetime.now()
        logger.info(now)

        try:
            logger.info("starting update")
            counter += 1
            run_update(start_date, end_date)
        except Exception as e:
            if isinstance(e.__cause__, MyRetryError):
                logger.error(e)
                send_email('pbowman@acsamman.edu.jo', "OOPS!", str(e))



def run_update(start_date=None, end_date=None):
    runtime_start = time.time()
    if start_date == None:
        now = datetime.datetime.now()
        if now > now.replace(hour=15):
            now = now + datetime.timedelta(days=1)
        start_date = now.strftime("%Y-%m-%d")
    # if end_date == None:
    #     end_date = s2_end_date
        # edt = datetime.datetime.strptime(start_date, "%Y-%m-%d") + datetime.timedelta(days=30)
        # end_date = edt.strftime("%Y-%m-%d")

    #override
    #start_date = "2023-01-29"
    #end_date = "2022-01-20"

    # HS only
    # schools = [School(hs_schoolid, hs_calendarid, hs_bell_schedule_calendarid, hs_rotation_calendarid, hs_duty_calendarid, "HS", True)]

    schools = [School(hs_schoolid, hs_calendarid, hs_bell_schedule_calendarid, hs_rotation_calendarid, hs_duty_calendarid, "HS", True),
               School(ms_schoolid, ms_calendarid, ms_bell_schedule_calendarid, ms_rotation_calendarid, ms_duty_calendarid, "MS", True)
        ]

    if end_date == None:
        end_dates = []
        for school in schools:
            end_dates.append(latest_term_end_date(start_date, school.schoolid))
        end_date = max(end_dates)

    date_range = Date_Range(schools, start_date, end_date)
    
    runtime = "runtime: " + str(datetime.timedelta(seconds=(time.time()-runtime_start)))
    logger.info(runtime)
    send_email('pbowman@acsamman.edu.jo', "This was a triumph.", runtime)
    return runtime

class School:
    def __init__(self, schoolid, calendarid, block_calendarid, rotation_calendarid, duty_calendarid, abbreviation, make_allschool_events=False):
        self.schoolid = schoolid
        self.calendarid = calendarid
        self.block_calendarid = block_calendarid
        self.rotation_calendarid = rotation_calendarid
        self.duty_calendarid = duty_calendarid
        self.calendarids = [self.calendarid, self.block_calendarid, self.rotation_calendarid, self.duty_calendarid]
        self.abbreviation = abbreviation
        self.make_allschool_events = make_allschool_events
        self.days = []
        self.duty_periods = self.make_duty_periods()
        logger.info("INITIALIZED " + str(self))

    #raise intentional error to test retry
    def whoopsie(self):
        Whoopsie()

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
            logger.info("no duties.csv file found")
        logger.debug(f"{self.abbreviation} duty periods: {duty_periods}")
        return duty_periods


    def add_day(self, datestr, ps_day, date_range):
        if not ps_day:
            for id in self.calendarids:
                logger.info(f"no calendar day or bell schedule on {datestr}")
                logger.info(f"deleting all events on {datestr}")
                logger.info(f"calendarid: {id}")
                delete_all_events(datestr, datestr, id)

            logger.info(f"deleting all ALLDAY events on {datestr}")
            logger.info(f"{self.abbreviation} rotation calendarid: {self.rotation_calendarid}")
            All_Day_Event.delete_all_events(datestr, datestr, self.rotation_calendarid)
            if self.make_allschool_events == True:
                for calendarid in allschool_rotation_calendar_ids:
                    logger.info(f"allschool calendarid: {calendarid}")
                    All_Day_Event.delete_all_events(datestr, datestr, calendarid)
            return None
        logger.info(f"adding {self.abbreviation} day on {datestr}")
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
        logger.info(self.date_list)
        for date in self.date_list:
            datestr = date.strftime('%Y-%m-%d')
            for exclude_cal in exclude_rotaton_calendar_ids:
                All_Day_Event.delete_all_events(datestr, datestr, exclude_cal)
            for school in schools:
                logger.info(f"adding {school.abbreviation} day {datestr}")
                ps_day = self.make_ps_days(datestr, datestr, school.schoolid)
                logger.info("ps_day: " + str(ps_day))
                day = school.add_day(datestr, ps_day, self)
                if day:
                    self.days.append(day)
                else:
                    logger.info(f"not adding {datestr}")
        logger.info(f"INITIALIZED {self}")
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
        logger.info(f"creating day {ps_day['date_value']}")
        self.client = date_range.client
        #inherit from date_range and section_meeting query
        self.day = ps_day
        self.bs_name = self.day['bs_name']
        self.calendar_day_dcid = ps_day['dcid']
        self.date_range = date_range
        self.school = school
        self.schoolid = school.schoolid
        self.terms = []
        self.term = self.query_term()
        self.termdcids = self.query_term_dcids()
        self.term_abbreviations = self.make_term_abbreviations()
        self.term_abbreviation = self.term['abbreviation']
        #TODO this is a hack bc the cycle day letter comes from the bs_name in make_block_meetings(). Need to update plugin to grab cycle_day_letter in ps_query.py calendar_days()
        self.cycle_day_letter = ps_day.get('cycle_day_letter', 'A')

        #strings to use for allday titles
        self.block_string = "" #constructed during make_block_meetings
        self.number = ""
        self.block_abbreviations = []
        self.name = self.make_day_name()
        self.teacher_emails = []

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
        self.deleted_duty_events = self.delete_extra_events(self.duty_events, self.existing_duty_events, self.desired_duty_events, self.school.duty_calendarid)
                
        #class events
        self.desired_class_events = []
        self.existing_class_events = self.update_existing_events(self.school.calendarid)
        self.class_meetings = self.make_class_meetings()
        self.class_events = self.make_class_events()
        self.deleted_class_events = self.delete_extra_events(self.class_events, self.existing_class_events, self.desired_class_events, self.school.calendarid)
        
        #allday events
        self.allday_event = All_Day_Event(self, self.school.rotation_calendarid)
        if self.school.make_allschool_events == True:
            for calendarid in allschool_rotation_calendar_ids:
                self.allschool_allday_event = All_Day_Event(self, calendarid, True)
        self.make_teacher_events_public()
        logger.info(f"INITIALIZED {self}")

    def __str__(self):
        return f"DAY {self.date} {self.term_abbreviation} {self.term_abbreviations} {self.school}"
    
    def make_teacher_events_public(self):
        logger.info(f"Making event public on teacher calendars...")
        for email in self.teacher_emails:
            logger.info(f"Impersonating {email}")
            p_service = make_impersonated_service(email)
            teachers_events = list_events_impersonated(p_service, email, str(self.localized_daystart.isoformat()), str(self.localized_dayend.isoformat()), "event_type=class")
            teachers_events += list_events_impersonated(p_service, email, str(self.localized_daystart.isoformat()), str(self.localized_dayend.isoformat()), "event_type=duty")
            payload = {"visibility": "public"}
            for event in teachers_events:
                if 'visibility' not in event or event['visibility'] != "public":
                    logger.info(f"making event public for {email}: {event['summary']}")
                    logger.debug(event)
                    patch_event_impersonated(p_service, event['id'], payload)
                else:
                    logger.debug("event is already public:")
                    logger.debug(event)


    def make_term_abbreviations(self):
        abr = []
        for t in self.terms:
            abr.append(t['abbreviation'])
        logger.info(f"terms for {self.day['date_value']}: {abr}")
        return abr

        
    def query_term(self):
        terms = self.client.terms(self.day['date_value'], self.schoolid)
        
        self.terms = [t for t in terms if t['firstday'] <= self.day['date_value'] and t['lastday'] >= self.day['date_value']]
        if not self.terms:
            return None
        term = self.terms[0]
        earliest_end_date = term['lastday']
        for t in self.terms:
            # find the term with the earliest end date
            if t['lastday'] < earliest_end_date:
                term = t
                earliest_end_date = t['lastday']
        return term

    def make_day_name(self):
        
        logger.info(f"bs name: {self.bs_name}")

        #grab a single digit separated by spaces out of the bell schedule name after replacing underscores with spaces
        #or grabs digits from multi-character bell schedule identifier (separated by spaces/underscores) such as 'A1' or 'B4'
        split_bs_name = self.bs_name.replace("_", " ").split()
        try:
            daynumber = self.bs_name.replace("_", " ").replace(" ", "").split("(")[-1].replace(")", "")[-1]
        except (IndexError, ValueError):
            daynumber = ""
        bs_identifiers = [s for s in split_bs_name if s[-1].isdigit()]
        if len(bs_identifiers) == 1:
            if daynumber.isdigit():
                self.number = daynumber
            else:
                self.number = bs_identifiers[0][-1]
            if len(bs_identifiers[0]) > 1:   
                self.cycle_day_letter = bs_identifiers[0][0]

        else:
            self.number = "?"
        logger.info(f"number: {self.number}")

        return "Day " + str(self.number)

    def query_term_dcids(self):
        return [t['dcid'] for t in self.terms]
        # return self.client.termdcids(self.day['date_value'], self.schoolid)

    @my_retry
    def update_existing_events(self, calendarid, sharedextendedproperty=None):
        if sharedextendedproperty and len(sharedextendedproperty) == 1:
            events = service.events().list(sharedExtendedProperty=sharedextendedproperty, maxResults=2500, calendarId=calendarid, timeMin=str(self.localized_daystart.isoformat()), timeMax=str(self.localized_dayend.isoformat())).execute().get('items', [])    
        else:
            events = service.events().list(maxResults=2500, calendarId=calendarid, timeMin=str(self.localized_daystart.isoformat()), timeMax=str(self.localized_dayend.isoformat())).execute().get('items', [])
        return events

    @my_retry
    def make_class_meetings(self):
        meet = []
        for termid in self.termdcids:
            meeting_set = self.client.section_meetings(termid, self.schoolid, self.day['bell_schedule_id'], self.cycle_day_letter)
            for m in meeting_set:
                try:
                    if m['teacher_email'] not in selected_teachers and update_only_selected_teachers:
                        continue
                    else:
                        meet.append(m)
                except KeyError:
                    continue
        meet = sorted(meet, key=lambda d: d['start_time'])

        for m in meet:
            blocks = [b for abbr, b in self.block_dict.items() if b['abbreviation'] == m['period_abbreviation']]
            m['adjusted_abbreviation'] = m['period_abbreviation']
            for b in blocks:
                if m['start_time'] == b['start_time'] and m['end_time'] == b['end_time']:
                    m['adjusted_abbreviation'] = b['adjusted_abbreviation']
            # self.block_list.append(m['period_abbreviation'])
        return meet

    def make_class_events(self):
        e = []
        logger.info("CLASS MEETINGS:")
        logger.info(self.class_meetings)
        for m in self.class_meetings:
            if int(m['no_of_students']) > 0:
                ev = Event(m, self, "class")
                e.append(ev)
                self.desired_class_events.append(ev.calendar_event.gcal_event)
        return e

    @my_retry
    def make_block_meetings(self):
        # get blocks for the day from PS
        blocks = self.client.blocks(self.calendar_day_dcid, self.schoolid)

        self.block_dict = {}
        
        for b in blocks:
            

            logger.info(f"block dict: {self.block_dict}")
            
            # handle numbered (not lettered) period abbreviations
            if b['abbreviation'].isdigit():
                b['adjusted_abbreviation'] = period_abbreviation_exceptions[self.cycle_day_letter][str(b['abbreviation'])]
            else:
                b['adjusted_abbreviation'] = str(b['abbreviation'])

            i = 2 #counter for multiple instances of a block
            suffix = "" #string to add to end of period abbreviation in the case of multiple instances
            b['instance'] = 1
            while b['adjusted_abbreviation'] in self.block_dict and b['start_time'] != self.block_dict[b['abbreviation']]['start_time'] and b['end_time'] != self.block_dict[b['abbreviation']]['end_time']:
                logger.info(f"{b['adjusted_abbreviation']} already in block dict")
                b['adjusted_abbreviation'] = b['adjusted_abbreviation'] + str(i)
                b['instance'] = i
                i += 1
            
            logger.info(f"adjusted abbr: {b['adjusted_abbreviation']}")
            self.block_dict[b['adjusted_abbreviation']] = b
        self.block_abbreviations = [b for b in self.block_dict]
        self.block_string = ",".join(self.block_abbreviations)
        logger.info(f"blocks: {self.block_abbreviations}")
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

        #logger.info(f"desired events: {desired_events}")
        logger.debug(f"desired ids: {desired_gcal_event_ids}")
        deleted_events = []
        for e in existing_events:
            if e['id'] not in desired_gcal_event_ids:
                logger.info(f"{e['id']} not in desired list")
                service.events().delete(calendarId=calendarid, eventId=e['id'], sendUpdates="none").execute()
                deleted_events.append(e)
                logger.info("Successfully deleted " + e['summary'])
            else:
                logger.debug(f"Not deleting {e['id']}")

        logger.debug("deleted events: \n" + str(deleted_events))
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
            self.room = meeting['room']
        except KeyError:
            self.room = ""
        try:
            self.term = meeting['term_name']
        except KeyError:
            self.term = day.term_abbreviation
        logger.info("term: " + self.term)
    
        self.start_timestamp = int(meeting['start_time'])
        self.end_timestamp = int(meeting['end_time'])

        if event_type == "class":
            self.no_of_students = int(meeting['no_of_students'])
            self.section_dcid = meeting['section_dcid']
            self.duties = []
            prefix = meeting['adjusted_abbreviation'] + "-"
            self.title = f"{prefix}{meeting['course_name']} ({meeting['lastfirst']})"
            self.teacher_email = self.meeting['teacher_email']
            self.emails = self.make_emails_list()
        if event_type == "block":
            self.teacher_email = ""
            self.no_of_students = -1
            self.section_dcid = -1
            self.emails = []
            t = None

            if period_title_exceptions:
                for exc in period_title_exceptions:
                    if meeting['abbreviation'] == exc['abbreviation']:
                        t = exc['title']
                        if meeting['instance'] > 1:
                            t += " " + str(meeting['instance'])
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
            self.teacher_email = ""
            self.emails = duty['teacher_emails']
            self.title = duty['title']

        self.start_datetime = self.date + datetime.timedelta(seconds=self.start_timestamp)
        self.end_datetime = self.date + datetime.timedelta(seconds=self.end_timestamp)
        self.meeting_time = f"{self.start_datetime.isoformat()}-{self.end_datetime.isoformat()[-8:]}"
        self.calendar_event = self.make_calendar_event()
        logger.info("INITIALIZED " + str(self))

    def __str__(self):
        return f"EVENT {self.title} {self.meeting_time} [{len(self.emails)} attendees] room {self.room}"

    def make_duty_events(self):
        logger.info(f"making {self.school.abbreviation} duties for {self.title} on Day {self.day.number}" )
        duties = []
        try:
            with open("duties.csv", 'r', encoding='UTF-8') as myfile:
                reader = csv.DictReader(myfile)
                #TODO remove blank lines
                for row in reader:
                    logger.debug(str(row))
                    if not (row['email'] and row['duty'] and row['day'] and row['period'] and row['semester'] and row['school']):
                        logger.debug("...skipping")
                        continue
                    if row['school'] == self.school.abbreviation and row['period'] == self.title and row['semester'] in self.day.term_abbreviations and str(row['day']) == str(self.day.number):
                        logger.info(f"creating {str(row)}")
                        duty = {'teacher_emails': row['email'].replace(" ", "").replace("\n", "").split(","), 'title': row['duty'] + " Duty", 'day': "Day " + row['day']}
                        d = Event(self.meeting, self.day, "duty", duty)
                        duties.append(d)
                        self.day.duty_events.append(d)
                        self.day.desired_duty_events.append(d.calendar_event.gcal_event)
                    else:
                        logger.debug("...skipping")
        except FileNotFoundError:
            logger.error("no duties.csv file found")
        return duties

    @my_retry
    def make_emails_list(self):
        logger.debug(self.meeting)
        e = [self.teacher_email]
        if extra_invites:
            for exc in extra_invites:
                if self.title == exc['event_title']:
                    e.append(exc['email'])
        if coteachers:
            for t, ct in coteachers.items():
                if self.teacher_email == t:
                    e.append(ct)

        self.roster = self.client.roster(self.meeting)
        for s in self.roster:
            e.append(s['email'])
        return e

    def make_calendar_event(self):
        #block and duty events have -1 as no_of_students
        if self.no_of_students > 0 or self.no_of_students == -1:
            logger.info("creating Calendar Event")
            return Calendar_Event(self)
        return None

class Calendar_Event:
    def __init__(self, event, skip_students=False):
        self.event = event
        self.title = event.title        
        self.school = event.school
        self.skip_students = skip_students
        self.attendees = [] #generated in make_payload
        self.description = ""
        
        if event.event_type == "block":
            self.calendarid = self.school.block_calendarid
            self.existing_events = event.day.existing_block_events
            self.teacher_emails = []
        if event.event_type == "class":
            self.calendarid = self.school.calendarid
            self.existing_events = event.day.existing_class_events
            self.teacher_emails = [self.event.teacher_email]
        if event.event_type == "duty":
            self.calendarid = self.school.duty_calendarid
            self.existing_events = event.day.existing_duty_events
            self.teacher_emails = [em for em in self.event.emails if em]
        for em in self.teacher_emails:
            if em not in self.event.day.teacher_emails:
                self.event.day.teacher_emails.append(em)
        self.payload = self.make_payload()
        self.gcal_event = self.update()

        logger.info(f"INITIALIZED {self}")

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
        self.attendees = sorted(attendees, key=lambda d: d['email'])
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
            "location": self.event.room,
            "attendees": self.attendees,
            "visibility": "public",
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
                    'no_of_students': str(self.event.no_of_students),
                    'teacher': self.event.teacher_email
                }
            }
        }
        return payload

    def compare_attendees(self, event):
        logger.debug(f"desired attendees: {self.attendees}")
        
        if 'attendees' not in event.keys():
            logger.debug("No existing attendees")
            if self.attendees:
                logger.warn("attendees do not match")
                return False
            return True
        else:
            logger.debug(f"existing attendees: {event['attendees']}")
            if len(self.attendees) != len(event['attendees']):
                return False
            desired_attendee_emails = [a['email'] for a in self.attendees]
            for attendee in event['attendees']:
                if attendee['responseStatus'] != "accepted" or attendee['email'] not in desired_attendee_emails:
                    logger.warn("attendees do not match")
                    return False
            existing_attendee_emails = [a['email'] for a in event['attendees']]
            for email in desired_attendee_emails:
                if email not in existing_attendee_emails:
                    logger.warn("attendees do not match")
                    return False
            return True



    @my_retry
    def update(self):
        logger.info(f"updating {self.payload['summary']} on {self.event.day.date}")
        logger.debug(self.payload)
        logger.debug(f"{len(self.existing_events)} existing events")
        for event in self.existing_events:    
            try:
                #find by name
                if self.payload['summary'] == event['summary']:
                    logger.info("Found existing event")

                    # compare attendees
                    attendees_match = self.compare_attendees(event)

                    #compare extended properties
                    if self.payload['extendedProperties']['shared'] == event['extendedProperties']['shared'] and attendees_match and self.payload['start']['dateTime'] == event['start']['dateTime'][:-6] and self.payload['end']['dateTime'] == event['end']['dateTime'][:-6] and "visibility" in event.keys() and self.payload['visibility'] == event['visibility']:
                        logger.info("Existing event is up to date")
                        logger.debug(event)
                        return event
                    else:
                        #update changed event
                        logger.debug(f"shared properties are the same? {self.payload['extendedProperties']['shared'] == event['extendedProperties']['shared']}")
                        logger.info(f"updating {self.payload['summary']}")
                        logger.debug(f"payload: {self.payload['extendedProperties']['shared']}")
                        logger.debug(f"existing: {event}")

                        new_event = service.events().update(calendarId=self.calendarid, eventId=event['id'], body=self.payload, sendUpdates="none").execute()
                        #double checking. Attributes are sometimes in the wrong order or are empty on the calendar, but don't exist locally. This is to prevent patching the event every time the script runs.
                        if self.payload['extendedProperties']['shared'] == new_event['extendedProperties']['shared'] and self.compare_attendees(new_event):
                            return new_event
                        else:
                            logger.info(f"still doesn't match. Recreating event.")
                            self.delete(new_event)
                            return self.add()
            except (KeyError, TypeError) as e:
                logger.warn(f"{event['summary']} does not match {self.payload['summary']}")
                logger.warn(e)
        return self.add()

    @my_retry
    def add(self):
        logger.info(f"adding {self.title}")
        gcal_event = None
        self.make_payload()
        gcal_event = service.events().insert(conferenceDataVersion=1, calendarId=self.calendarid, body=self.payload, sendUpdates="none").execute()
        return gcal_event
    
    @my_retry
    def delete(self, event=None):
        if event == None:
            try:
                event = self.gcal_event
            except AttributeError:
                logger.info("No gcal event to delete")
                return
        error = ""
        try:
            d = service.events().delete(calendarId=self.calendarid, eventId=event['id'], sendUpdates="none").execute()
            if d:
                error = f"error when deleting {event['summary']}: {d}"

        except HttpError as e:
            error = f"error when deleting {event['summary']}: ({e})"

        if error != None:
            return error
        logger.info("Successfully deleted" + event['summary'])
    
class All_Day_Event:
    def __init__(self, day, calendarid, allschool=False):
        self.day = day
        self.name = day.name
        self.calendarid = calendarid
        if allschool == True:
            if day.name == "Day 0":
                self.title = "MS/HS " + day.name
            else:
                self.title = day.name
            self.description = day.school.abbreviation + ": " + day.block_string
        else:
            self.title = day.name + "-" + day.block_string
            self.description = ""
        self.date = day.day['date_value']
        self.school = day.school
        self.block_string = day.block_string
        self.event_type = "allday"
        

        self.payload = self.make_payload()
        self.existing_events = self.update_existing_events()
        self.gcal_event = self.update()
        self.deleted_events = self.delete_extra_events()
        logger.info(f"INITIALIZED {self}")

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
                    "blocks": f"{self.school.abbreviation}: {self.block_string}",
                    "title": self.title,
                    "schedule": self.day.bs_name,
                    "bs_name": self.day.bs_name
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
        logger.info("updating " + payload['summary'])
        logger.info(f"{len(self.existing_events)} existing events")
        for event in self.existing_events:    
            try:
                #find by extended properties
                if event['extendedProperties']['shared']['event_type'] == "allday":
                    logger.info("Found existing event:")
                    
                    logger.info(event['extendedProperties']['shared'])
                    logger.info(self.payload['extendedProperties']['shared'])
                    self.update_description(event)
                    if not self.title[self.title.index("Day ")+len("Day "):].isdigit():
                        self.title = event['title']

                    if event['extendedProperties']['shared'] == payload['extendedProperties']['shared']:
                        logger.info("Existing event is up to date")
                        return event
                    else:
                        logger.info(f"updating {payload['summary']}")
                        return service.events().update(calendarId=self.calendarid, eventId=event['id'], body=self.payload, sendUpdates="none").execute()
            except (KeyError, TypeError) as e:
                logger.debug(event['summary'] + "does not match:")
                logger.debug(e)

        return service.events().insert(conferenceDataVersion=1, calendarId=self.calendarid, body=self.payload, sendUpdates="none").execute()

    def update_description(self, event):
        blocks_dict = {s[:s.index(':')]: s[s.index(':')+2:] for s in self.payload['extendedProperties']['shared']['blocks'].split('\n')}
        try:
            for abbreviation, block_string in {s[:s.index(':')]: f"{s[s.index(':')+2:]}" for s in event['extendedProperties']['shared']['blocks'].split('\n')}.items():
                blocks_dict.setdefault(abbreviation, block_string)
        except ValueError:
            pass
        new_desc = []
        for abbreviation, block_string in blocks_dict.items():
            new_desc.append(f"{abbreviation}: {block_string}")
        self.description = "\n".join(new_desc)
        self.payload['description'] = self.description
        self.payload['extendedProperties']['shared']['description'] = self.description
        self.payload['extendedProperties']['shared']['blocks'] = self.description
        return self.description


    @my_retry
    @staticmethod
    def delete_all_events(start_date_str, end_date_str, calendarid):
        logger.info("")
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
        localized_daystart = pytz.timezone("Asia/Amman").localize(start_date).isoformat()
        localized_dayend = pytz.timezone("Asia/Amman").localize(end_date + datetime.timedelta(hours=23, minutes=59)).isoformat()
        print(start_date_str)
        print(end_date_str)
        print(localized_daystart)
        print(localized_dayend)
        print(calendarid)
        existing_events = service.events().list(maxResults=2500, calendarId=calendarid, timeMin=localized_daystart, timeMax=localized_dayend).execute().get('items', [])
        deleted_events = []
        for e in existing_events:
            try:
                if e['extendedProperties']['shared']['event_type'] == "allday":
                    logger.debug(f"found allday event {e}")
                    service.events().delete(calendarId=calendarid, eventId=e['id'], sendUpdates="none").execute()
                    deleted_events.append(e)
                    logger.debug(f"Deleted {e['summary']} (not in desired list)")
                else:
                    logger.debug(f"Not deleting {e['id']}")
            except KeyError:
                logger.debug(f"Not deleting {e['id']}")

        logger.debug("deleted events: \n" + str(deleted_events))
        return deleted_events

    @my_retry
    def delete_extra_events(self):
        self.existing_events = self.update_existing_events()
        deleted_events = []
        for e in self.existing_events:
            is_allday = False
            try:
                if e['extendedProperties']['shared']['event_type'] == "allday":
                    logger.debug(f"found allday event {e}")
                    is_allday = True
            except KeyError:
                if e['summary'][:4] == "Day ":
                    logger.debug(f"found allday event {e}")
                    is_allday = True
            if is_allday:
                if e['id'] != self.gcal_event['id']:
                    service.events().delete(calendarId=self.calendarid, eventId=e['id'], sendUpdates="none").execute()
                    deleted_events.append(e)
                    logger.debug(f"Deleted {e['summary']} (not in desired list)")
                else:
                    logger.debug(f"Not deleting {e['id']}")

        logger.debug("deleted events: \n" + str(deleted_events))
        return deleted_events

@my_retry
def delete_all_events(start_date_str, end_date_str, calendarid):
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
    localized_daystart = pytz.timezone("Asia/Amman").localize(start_date)
    localized_dayend = pytz.timezone("Asia/Amman").localize(end_date + datetime.timedelta(hours=23, minutes=59))
    existing_events = service.events().list(maxResults=2500, calendarId=calendarid, timeMin=str(localized_daystart.isoformat()), timeMax=str(localized_dayend.isoformat())).execute().get('items', [])
    for e in existing_events:
        service.events().delete(calendarId=calendarid, eventId=e['id'], sendUpdates="none").execute()

@my_retry
def make_impersonated_service(email):
    p_creds = creds.with_subject(email)
    return build('calendar', 'v3', credentials=p_creds)

@my_retry
def list_events_impersonated(p_service, calendarid, timemin, timemax, extendedproperty=None):
    if extendedproperty:
        events = p_service.events().list(sharedExtendedProperty=extendedproperty, maxResults=2500, calendarId=calendarid, timeMin=timemin, timeMax=timemax).execute().get('items', [])    
    else:
        events = p_service.events().list(maxResults=2500, calendarId=calendarid, timeMin=timemin, timeMax=timemax).execute().get('items', [])
    return events

@my_retry
def patch_event_impersonated(p_service, event_id, payload, calendar_id="primary"):
    return p_service.events().patch(calendarId=calendar_id, eventId=event_id, body=payload, sendUpdates="none").execute()

def latest_term_end_date(date:str, schoolid):
    client = Query()
    terms = client.terms(date, schoolid)
    latest_end_date = date

    terms = [t for t in terms if t['lastday'] >= date]
    if terms:
        for t in terms:
            # find the term with the earliest end date
            if t['lastday'] > latest_end_date:
                latest_end_date = t['lastday']
    months_ahead = 12
    term_end_dates = [latest_end_date]
    for i in range(months_ahead):
        one_month_later = datetime.datetime.strptime(latest_end_date, "%Y-%m-%d") + datetime.timedelta(days=30*i+1)
        ed = client.terms(one_month_later.strftime("%Y-%m-%d"), schoolid)
        ed = [t['lastday'] for t in ed]
        # input(ed)
        term_end_dates += ed
                              
    # input(term_end_dates)
    # input(max(term_end_dates))
    return max(term_end_dates)


if __name__ == "__main__":
        if len(sys.argv) == 2:
            run_update(sys.argv[1])
        elif len(sys.argv) == 3:
            run_update(sys.argv[1], sys.argv[2])
        else:
            main()
        # ps_query_test()