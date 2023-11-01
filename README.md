# headsup3
the calendar where events are placed cannot contain any user-added calendars; they will be deleted on update
make sure time zone of target calendar matches `timezone` parameter in secrets.py 

docker build -t headsup .
docker run --name headsup --restart always -d headsup
docker logs -f --tail 500 headsup
docker exec -it headsup bash



