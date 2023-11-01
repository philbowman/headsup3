# headsup3
- the calendar where class events are placed cannot contain any user-added events; they will be deleted on update
- "Day _" events can be added to calendars with user-added events, but the events maintained by the app will be corrected when an update is run
- make sure time zone of target calendar matches `timezone` parameter in secrets_parameters.py 

docker build -t headsup .
docker run --name headsup --restart always -d headsup
docker logs -f --tail 500 headsup
docker exec -it headsup bash



