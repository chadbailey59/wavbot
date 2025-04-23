FROM dailyco/pipecat-base:latest

COPY ./requirements.txt requirements.txt
COPY ./40-440hz.wav 40-440hz.wav

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY ./bot.py bot.py