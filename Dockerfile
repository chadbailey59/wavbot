FROM dailyco/pipecat-base:latest

COPY ./requirements.txt requirements.txt
COPY ./40-440hz.wav 40-440hz.wav

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY ./daily_phone.py daily_phone.py
COPY ./bot.py bot.py