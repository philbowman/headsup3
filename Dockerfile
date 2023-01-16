FROM python:3.10.7-slim-buster

ENV TZ="Asia/Amman"

COPY . .

RUN apt-get update

RUN apt-get --assume-yes install rclone

RUN apt-get --assume-yes install cron

RUN apt-get --assume-yes install nano

RUN pip install --upgrade pip

RUN pip install -r requirements.txt

CMD ["python3", "sync_calendar.py"]