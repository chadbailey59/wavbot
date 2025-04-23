# WAVBOT

This Pipecat Cloud bot runs on any transport(*) and immediately starts playing the included `40-440hz.wav` file as soon as a client connects. The wav file includes a 440 Hz sine wave tone and a voice that counts from one to forty.

You should be able to deploy it using the standard Pipecat Cloud deploy process. You can run it locally with `LOCAL_RUN=1 python bot.py`. If you have a `DAILY_API_KEY` set in your .env it will use Daily; otherwise, it will use the SmallWebRTCTransport.