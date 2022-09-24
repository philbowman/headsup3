FROM python:3.10.7-slim-buster

ENV TZ="Asia/Amman"

COPY . .

RUN apt-get update

RUN apt-get install rclone

RUN apt-get install cron

RUN apt-get install nano

RUN pip install -r requirements.txt

CMD ["python3", "sync_calendar.py"]