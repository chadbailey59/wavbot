from loguru import logger


class DialInHandler:
    """Handles all dial-in related functionality and event handling.

    This class encapsulates the logic for incoming calls and handling
    all dial-in related events from the Daily platform.
    """

    def __init__(self, transport, context_aggregator=None):
        """Initialize the DialInHandler.

        Args:
            transport: The Daily transport instance
            task: The PipelineTask instance
            context_aggregator: The context aggregator for the LLM
        """
        self.transport = transport
        self.context_aggregator = context_aggregator
        logger.info("Initializing DialInHandler")
        self._register_handlers()

    def _register_handlers(self):
        """Register all event handlers related to dial-in functionality."""

        @self.transport.event_handler("on_dialin_ready")
        async def on_dialin_ready(transport, data):
            """Handler for when the dial-in is ready (SIP addresses registered with the SIP network)."""
            # For Twilio, Telnyx, etc. You need to update the state of the call
            # and forward it to the sip_uri.
            logger.debug(f"Dial-in ready: {data}")

        @self.transport.event_handler("on_dialin_connected")
        async def on_dialin_connected(transport, data):
            """Handler for when a dial-in call is connected."""
            logger.debug(f"Dial-in connected: {data} and set_bot_ready")

        @self.transport.event_handler("on_dialin_stopped")
        async def on_dialin_stopped(transport, data):
            """Handler for when a dial-in call is stopped."""
            logger.debug(f"Dial-in stopped: {data}")

        @self.transport.event_handler("on_dialin_error")
        async def on_dialin_error(transport, data):
            """Handler for dial-in errors."""
            logger.error(f"Dial-in error: {data}")
            # The bot should leave the call if there is an error
            raise ("Call Error")
            # await self.task.cancel()

        @self.transport.event_handler("on_dialin_warning")
        async def on_dialin_warning(transport, data):
            """Handler for dial-in warnings."""
            logger.warning(f"Dial-in warning: {data}")

        @self.transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            """Handler for when the first participant joins the call."""
            logger.info("First participant joined: {}", participant["id"])
            # Capture the participant's transcription
            await transport.capture_participant_transcription(participant["id"])

            # For the dial-in case, we want the bot to greet the user.
            # We can prompt the bot to speak by putting the context into the pipeline.
            # await self.task.queue_frames(
            #     [self.context_aggregator.user().get_context_frame()]
            # )


class DialOutHandler:
    """Handles a single dial-out call and it is also managing retry attempts.
    In addition handling all dial-out related events from the Daily platform."""

    def __init__(self, transport, dialout_setting, max_attempts=5):
        """Initialize the DialOutHandler for a single call.

        Args:
            transport: The Daily transport instance
            task: The PipelineTask instance
            dialout_setting: Configuration for this specific outbound call
            max_attempts: Maximum number of dial-out attempts on a specific number
        """
        self.transport = transport
        self.dialout_setting = dialout_setting
        self.max_attempts = max_attempts
        self.attempt_count = 0
        self.status = "pending"  # pending, connected, answered, failed, stopped
        self._register_handlers()
        logger.info(f"Initialized DialOutHandler for call: {dialout_setting}")

    async def start(self):
        """Initiates an outbound call using the configured dial-out settings."""
        self.attempt_count += 1

        if self.attempt_count > self.max_attempts:
            logger.error(
                f"Max dialout attempts ({self.max_attempts}) reached for {self.dialout_setting}"
            )
            self.status = "failed"
            return

        logger.debug(
            f"Dialout attempt {self.attempt_count}/{self.max_attempts} for {self.dialout_setting}"
        )

        try:
            if "phoneNumber" in self.dialout_setting:
                logger.info(f"Dialing number: {self.dialout_setting['phoneNumber']}")
                if "callerId" in self.dialout_setting:
                    await self.transport.start_dialout(
                        {
                            "phoneNumber": self.dialout_setting["phoneNumber"],
                            "callerId": self.dialout_setting["callerId"],
                        }
                    )
                else:
                    await self.transport.start_dialout(
                        {"phoneNumber": self.dialout_setting["phoneNumber"]}
                    )
            elif "sipUri" in self.dialout_setting:
                logger.info(f"Dialing sipUri: {self.dialout_setting['sipUri']}")
                await self.transport.start_dialout(
                    {"sipUri": self.dialout_setting["sipUri"]}
                )
        except Exception as e:
            logger.error(f"Error starting dialout: {e}")
            self.status = "failed"

    def _register_handlers(self):
        """Register all event handlers related to the dial-out functionality."""

        @self.transport.event_handler("on_dialout_connected")
        async def on_dialout_connected(transport, data):
            """Handler for when a dial-out call is connected (starts ringing)."""
            self.status = "connected"
            logger.debug(f"Dial-out connected: {data}")

        @self.transport.event_handler("on_dialout_answered")
        async def on_dialout_answered(transport, data):
            """Handler for when a dial-out call is answered (off hook). We capture the transcription, but we do not
            queue up a context frame, because we are waiting for the user to speak first."""
            self.status = "answered"
            session_id = data.get("sessionId")
            await transport.capture_participant_transcription(session_id)
            logger.debug(f"Dial-out answered: {data}")

        @self.transport.event_handler("on_dialout_stopped")
        async def on_dialout_stopped(transport, data):
            """Handler for when a dial-out call is stopped."""
            self.status = "stopped"
            logger.debug(f"Dial-out stopped: {data}")

        @self.transport.event_handler("on_dialout_error")
        async def on_dialout_error(transport, data):
            """Handler for dial-out errors. Will retry this specific call."""
            self.status = "failed"
            await self.start()  # Retry this specific call
            logger.error(f"Dial-out error: {data}, retrying...")

        @self.transport.event_handler("on_dialout_warning")
        async def on_dialout_warning(transport, data):
            """Handler for dial-out warnings."""
            logger.warning(f"Dial-out warning: {data}")
