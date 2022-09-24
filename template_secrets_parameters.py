ps_url = "ps.council.org"
client_id = ""
client_secret = ""


# Used for creating Block Schedule events and duties. 
# If a bell schedule item is associated with a period that matches one of these abbreviations, the title of the event on Google Calendar will match its corresponding title in the dictionary in this list.
# These names should also match the duty schedule periods in duty_schedule.csv
period_abbreviation_exceptions = [{"abbreviation": "BRK", "title": "Break"}, {"abbreviation": "COH", "title": "Cohort"}]

# invite additional people to certain classes. title must match Google Calendar title exactly
extra_invites = [{"event_title": "D-English 10 (Antipaxos)", "email": "guillermo@mosquitocollectors.biz"}]

s1_end_date = "2023-01-18"
s2_end_date = "2023-06-14"


# calendar request credentials
cred_location = "G_credentials/" #location of service.json
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']
SERVICE_ACCOUNT_EMAIL = ''
SERVICE_ACCOUNT_FILE = f"{cred_location}service.json"
calendar_manager_email = 'nadja@acouncil.org' #user that is impersonated when creating calendar events
calendar_manager_password = "" #app specific

hs_schoolid = 681005
hs_bell_schedule_calendarid = "c_a264725kdc3wwetyhdsd0dmj6u0@group.calendar.google.com"
hs_calendarid = "c_brskvure0p7f1d3sadfdsfgiis@group.calendar.google.com"
hs_duty_calendarid = "c_viqgghjyhfc0153kqeniierrw1qimfrms@group.calendar.google.com"
hs_rotation_calendarid = "c_s37sr8c5n1g8e9wwqqemv6qt7k@group.calendar.google.com"


ms_schoolid = 5678
ms_bell_schedule_calendarid = "c_ha92hheo65vmfdsafdsahm7eso120c@group.calendar.google.com"
ms_calendarid = "c_183271fa808515ce56b3582c592asdfdsafds70f21d84aa5782ad0d3a0d48@group.calendar.google.com"
ms_duty_calendarid = "c_9820ec9a662355a891d19cfdsafdsae813ed3c1148f83eca3472@group.calendar.google.com"
ms_rotation_calendarid = "c_5e4c0192c40adfdsf2039c6cefb33301ebaffb6b2045b6049ef76de6ac5@group.calendar.google.com"

test_calendar_id = "c_oal6dmewqrej76j9dft0igc@group.calendar.google.com"

timezone = 'Asia/Amman'

# used for debugging
update_only_selected_teachers = False
selected_teachers = []
#selected_teachers = ["colin@council.org", "nadja@council.org"]
