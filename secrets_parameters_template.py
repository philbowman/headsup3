ps_url = ""
client_id = ""
client_secret = ""

# Used for creating Block Schedule events and duties. 
# If a bell schedule item is associated with a period that matches one of these abbreviations, the title of the event on Google Calendar will match its corresponding title in the dictionary in this list.
# These names should also match the duty schedule periods in duty_schedule.csv
period_title_exceptions = [{"abbreviation": "BRK", "title": "Break"}, {"abbreviation": "LUN", "title": "Lunch"}, {"abbreviation": "COH", "title": "Cohort"}, {"abbreviation": "ADV", "title": "Advisory"}, {"abbreviation": "EX", "title": "Explore"}, {"abbreviation": "FLX", "title": "Flex"}]
period_abbreviation_exceptions = {"A": {"1": "A", "2": "B", "3": "C", "4": "D"}, "B": {"1": "E", "2": "F", "3": "G", "4": "H"}}
additional_bell_schedules = {'bell_schedule_title': 'associated_bell_schedule_title'}

# invite additional people to certain classes. title must match Google Calendar title exactly
extra_invites = [{"event_title": "", "email": ""}]
coteachers = {"teacher_email": "coteacher_email"}

s1_end_date = ""
s2_end_date = ""

# calendar request credentials
cred_location = "G_credentials/"
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']
SERVICE_ACCOUNT_EMAIL = ''
SERVICE_ACCOUNT_FILE = f"{cred_location}service.json"
calendar_manager_email = ''
calendar_manager_password = "" #app specific

hs_schoolid = 0
hs_bell_schedule_calendarid = ""
hs_calendarid = ""
hs_duty_calendarid = ""
hs_rotation_calendarid = ""


ms_schoolid = 0
ms_bell_schedule_calendarid = ""
ms_calendarid = ""
ms_duty_calendarid = ""
ms_rotation_calendarid = ""

test_calendar_id = ""
allschool_rotation_calendar_ids = [""]
# delete all all-day events created by this program from these calendars
exclude_rotaton_calendar_ids = [""]

timezone = ''

# used for debugging
update_only_selected_teachers = False
selected_teachers = []
#selected_teachers = ["teacher_email"]
