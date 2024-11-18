from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.web import WebClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from bot.room_manager import RoomManager
from config.config import SLACK_BOT_TOKEN
from bot.message_handler import MessageHandler
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SlackBot:
    def __init__(self, slack_token: str, room_manager: RoomManager):
        # Create web client with bot token
        self.web_client = WebClient(token=SLACK_BOT_TOKEN)

        # Create socket mode client with app token
        self.client = SocketModeClient(
            app_token=slack_token,
            web_client=self.web_client
        )

        self.room_manager = room_manager
        self.message_handler = MessageHandler(room_manager)  # Add this line
        self.client.socket_mode_request_listeners.append(self.process_message)

        # Test connection during initialization
        self._test_connection()
        
    def _test_connection(self):
        """Test the Slack connection and permissions."""
        try:
            auth_response = self.web_client.auth_test()
            logging.info(f"Bot connected as {auth_response['bot_id']} to workspace {auth_response['team']}")
        except Exception as e:
            logging.error(f"Failed to authenticate with Slack: {e}")
            raise

    def process_message(self, client: SocketModeClient, req: SocketModeRequest):
        """Process incoming socket mode requests."""
        if req.type == "events_api":
            # Acknowledge the request
            client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
            
            # Extract the event from the request
            event = req.payload["event"]
            
            try:
                # Only handle app_mention events
                if event["type"] == "app_mention":
                    message = event["text"]
                    channel_id = event["channel"]
                    user_id = event["user"]
                    
                    # Process message using MessageHandler
                    response = self.message_handler.handle_message(message, user_id)
                    
                    # Send response back to Slack
                    self.web_client.chat_postMessage(
                        channel=channel_id,
                        text=response
                    )
                    
            except Exception as e:
                logging.error(f"Error in handle_socket_mode_request: {e}")
                self.web_client.chat_postMessage(
                    channel=event["channel"],
                    text="Sorry, I encountered an error processing your request."
                )

    def start(self):
        """Start the Slack bot."""
        logging.info("Bot is starting up...")
        self.client.connect()
        logging.info("Bot is connected and running!")
        
        # Send welcome message to all channels the bot is in
        try:
            channels = self.web_client.conversations_list()
            welcome_message = (
                "Hello! I can help you book meeting rooms. Try these commands:\n"
                "• `@floor10roombooking book a room`\n"
                "• `@floor10roombooking list rooms`\n"
                "• `@floor10roombooking list available rooms for eg. 21 August`\n"
                "• `@floor10roombooking cancel booking`"
            )
            
            for channel in channels["channels"]:
                if channel["is_member"]:
                    self.web_client.chat_postMessage(
                        channel=channel["id"],
                        text=welcome_message
                    )
        except Exception as e:
            logging.error(f"Failed to send welcome message: {e}")