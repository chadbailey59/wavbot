#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import json
import os
import wave

import aiohttp
from dotenv import load_dotenv
from loguru import logger
from pipecat.frames.frames import OutputAudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.frame_processor import FrameDirection
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.transports.services.daily import DailyParams, DailyTransport
from pipecatcloud.agent import (
    DailySessionArguments,
    SessionArguments,
    WebSocketSessionArguments,
)

from daily_phone import DialInHandler, DialOutHandler

load_dotenv(override=True)


# Check if we're in local development mode
LOCAL_RUN = os.getenv("LOCAL_RUN")
if LOCAL_RUN:
    import asyncio
    import webbrowser

    try:
        from local_runner import configure
    except ImportError:
        logger.error(
            "Could not import local_runner module. Local development mode may not work."
        )
DAILY_API_KEY = os.getenv("DAILY_API_KEY")
DAILY_ROOM_URL = os.getenv("DAILY_ROOM_URL")
print(f"Daily API KEY: {DAILY_API_KEY}")
# Load environment variables

# Load wav file
script_dir = os.path.dirname(__file__)
full_path = os.path.join(script_dir, "40-440hz.wav")
with wave.open(full_path) as audio_file:
    sound = OutputAudioRawFrame(
        audio_file.readframes(-1), audio_file.getframerate(), audio_file.getnchannels()
    )


async def main(transport: BaseTransport):
    """Main pipeline setup and execution function.

    Args:
        room_url: The Daily room URL
        token: The Daily room token
    """
    logger.debug("Starting bot")

    pipeline = Pipeline(
        [
            transport.input(),
            transport.output(),
        ]
    )

    task = PipelineTask(
        pipeline,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, _):
        logger.info("Client connected")
        # TODO: Add send_audio to fastapiwebsockettransport
        if isinstance(transport, FastAPIWebsocketTransport):
            await transport._output.queue_frame(sound, FrameDirection.DOWNSTREAM)
        else:
            await transport.send_audio(sound)

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, participant, reason):
        logger.info("Client disconnected")
        await task.cancel()

    runner = PipelineRunner()

    await runner.run(task)


shared_params = {
    "audio_out_enabled": True,
}


async def bot(args: SessionArguments):
    """Bot entry point compatible with Pipecat Cloud. SessionArguments
    will be a different subclass depending on how the session is started.

    args: either DailySessionArguments or WebsocketSessionArguments
    DailySessionArguments:
        room_url: The Daily room URL
        token: The Daily room token
        body: The configuration object from the request body
        session_id: The session ID for logging

    WebsocketSessionArguments:
        websocket: The websocket for connecting to Twilio
    """
    logger.info(f"Starting PCC bot. args: {args}")

    if isinstance(args, WebSocketSessionArguments):
        logger.debug("Starting WebSocket bot")

        start_data = args.websocket.iter_text()
        await start_data.__anext__()
        call_data = json.loads(await start_data.__anext__())
        stream_sid = call_data["start"]["streamSid"]
        call_sid = call_data["start"]["callSid"]
        transport = FastAPIWebsocketTransport(
            websocket=args.websocket,
            params=FastAPIWebsocketParams(
                **shared_params,
                serializer=TwilioFrameSerializer(stream_sid, call_sid),
            ),
        )
    elif isinstance(args, DailySessionArguments):
        logger.debug("Starting bot in room: {}", args.room_url)

        # Dial-in configuration:
        # dialin_settings are received when a call is triggered to
        # Daily via pinless_dialin. This can be a phone number on Daily or a
        # sip interconnect from Twilio or Telnyx.
        dialin_settings = None
        dialled_phonenum = None
        caller_phonenum = None
        if raw_dialin_settings := args.body.get("dialin_settings"):
            # these fields can capitalize the first letter
            dialled_phonenum = raw_dialin_settings.get("To") or raw_dialin_settings.get(
                "to"
            )
            caller_phonenum = raw_dialin_settings.get(
                "From"
            ) or raw_dialin_settings.get("from")
            dialin_settings = {
                # these fields can be received as snake_case or camelCase.
                "call_id": raw_dialin_settings.get("callId")
                or raw_dialin_settings.get("call_id"),
                "call_domain": raw_dialin_settings.get("callDomain")
                or raw_dialin_settings.get("call_domain"),
            }
            logger.debug(
                f"Dialin settings: To: {dialled_phonenum}, From: {caller_phonenum}, dialin_settings: {dialin_settings}"
            )

        # Dial-out configuration
        dialout_settings = args.body.get("dialout_settings")
        logger.debug(f"Dialout settings: {dialout_settings}")

        logger.debug("Starting Daily bot")
        transport = DailyTransport(
            args.room_url,
            args.token,
            "Respond bot",
            DailyParams(**shared_params, transcription_enabled=False),
        )

        handlers = {}
        # Initialize appropriate handlers based on the call type
        if dialin_settings:
            handlers["dialin"] = DialInHandler(transport)

        if dialout_settings:
            # Create a handler for each dial-out setting
            # i.e., each phone number/sip address gets its own handler
            # allows more control on retries and state management
            handlers["dialout"] = [
                DialOutHandler(transport, setting) for setting in dialout_settings
            ]

    try:
        await main(transport)
        logger.info("Bot process completed")
    except Exception as e:
        logger.exception(f"Error in bot process: {str(e)}")
        raise


# Local development
async def local_daily():
    """This is an entrypoint for running your bot locally but using Daily
    for the transport. To use this, you'll need to have DAILY_API_KEY or DAILY_ROOM_URL
    set in your .env file.
    """
    try:
        async with aiohttp.ClientSession() as session:
            if DAILY_ROOM_URL:
                room_url = DAILY_ROOM_URL
                token = None
            else:
                (room_url, token) = await configure(session)

            logger.warning(f"Talk to your voice agent here: {room_url}")
            webbrowser.open(room_url)
            transport = DailyTransport(
                room_url=room_url,
                token=token,
                bot_name="Bot",
                params=DailyParams(**shared_params),
            )
            await main(transport)
    except Exception as e:
        logger.exception(f"Error in local development mode: {e}")


async def run_bot(webrtc_connection):
    """An entrypoint for using the SmallWebRTCTransport, which doesn't require a Daily
    account or API key.
    """
    from pipecat.transports.network.small_webrtc import SmallWebRTCTransport

    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection, params=TransportParams(**shared_params)
    )
    await main(transport)


# Local development entry point
if LOCAL_RUN and __name__ == "__main__":
    if DAILY_API_KEY or DAILY_ROOM_URL:
        try:
            asyncio.run(local_daily())
        except Exception as e:
            logger.exception(f"Failed to run in local mode: {e}")
    else:
        # Use the SmallWebRTCTransport
        from run import main

        main()
