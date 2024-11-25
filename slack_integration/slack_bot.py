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
        self.web_client = WebClient(token=SLACK_BOT_TOKEN)
        self.client = SocketModeClient(
            app_token=slack_token,
            web_client=self.web_client
        )
        self.room_manager = room_manager
        self.message_handler = MessageHandler(room_manager)
        self.client.socket_mode_request_listeners.append(self.process_message)
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
        if req.type == "slash_commands":
            client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
            command = req.payload
            
            try:
                response = self._handle_slash_command(command)
                
                # All responses are ephemeral (only visible to the user)
                self.web_client.chat_postEphemeral(
                    channel=command["channel_id"],
                    user=command["user_id"],
                    text=response
                )
                
            except Exception as e:
                logging.error(f"Error handling slash command: {e}")
                self.web_client.chat_postEphemeral(
                    channel=command["channel_id"],
                    user=command["user_id"],
                    text="Sorry, I encountered an error processing your request."
                )
    
        elif req.type == "events_api" and req.payload.get("event", {}).get("type") == "app_mention":
            # Handle bot mentions
            client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
            event = req.payload["event"]
            
            # Send welcome message as ephemeral response
            self.web_client.chat_postEphemeral(
                channel=event["channel"],
                user=event["user"],
                text=self._get_welcome_message()
            )

    def _handle_slash_command(self, command: dict) -> str:
        """Handle slash commands."""
        command_type = command["command"]
        text = command["text"].strip()
        user_id = command["user_id"]
        
        if command_type == "/book":
            if not text:
                return (
                    "Please use one of these formats:\n\n"
                    "*Single Booking:*\n"
                    "`/book [room], [date], [time], [duration], [event details], [internal/client], [Full Contact Name]`\n\n"
                    "*Recurring Booking:*\n"
                    "`/book recurring [room], [start date], [end date], [frequency], [time], [duration], [event details], [internal/client], [Full Contact Name]`\n\n"
                    "*Examples:*\n"
                    "• `/book nest, tomorrow, 2pm, 2 hours, Team Meeting, internal, John Smith`\n"
                    "• `/book recurring nest, 22nd Nov, 22nd Dec, weekly, 2pm, 2 hours, Team Sync, internal, John Smith`\n"
                    "*Date formats:* 'today', 'tomorrow', '28th Nov', '22nd of November', '19/12', '19/12/2024'\n"
                    "*Supported Frequencies:* daily, weekly, biweekly, monthly\n"
                    "*Duration formats accepted:*\n"
                    "• Hours: '3h', '3 h', '3 hours'\n"
                    "• Minutes: '45m', '45 m', '45 minutes'\n"
                    "• Combined: '2 hours 30 minutes', '2h 30m'\n\n"
                    )
            if text.startswith('recurring '):
                return self.message_handler.handle_message(f"book {text}", user_id)
            return self.message_handler.handle_message(f"book {text}", user_id)
        
        elif command_type == "/rooms":
            if not text:
                return self.message_handler.handle_message("list rooms", user_id)
            elif text.startswith('available '):
                return self.message_handler.handle_message(f"list available rooms for {text[10:]}", user_id)
            return "Invalid format. Use `/rooms` or `/rooms available [date]`"
        
        elif command_type == "/mybookings":
            if not text:
                return self.message_handler.handle_message("list my bookings", user_id)
            elif text.startswith('cancel '):
                numbers = text[7:].strip()
                if numbers == "all":
                    return self.message_handler.handle_message("cancel all bookings", user_id)
                return self.message_handler.handle_message(f"cancel booking {numbers}", user_id)
            return "Invalid format. Use `/mybookings` or `/mybookings cancel [number(s)]` or `/mybookings cancel all`"
        
        elif command_type == "/calendar":
            if not text:
                return "Please specify a month, e.g., `/calendar December`"
            return self.message_handler.handle_message(f"calendar view {text}", user_id)
        
        return "Unknown command"

    def start(self):
        """Start the Slack bot."""
        logging.info("Bot is starting up...")
        self.client.connect()
        logging.info("Bot is connected and running!")
        
    def _get_welcome_message(self) -> str:
        """Return the welcome message with available commands."""
        return (
            "Hello! Here are the available commands:\n\n"
            "*Begin Booking Process:*\n"
            "• `/book` - Single bookings or recurring bookings\n"
            "*Calendar View*\n"
            "• `/calendar [month]` - View calendar for a month\n"
            "*Other Commands:*\n"
            "• `/rooms available [date]` - Check room availability\n"
            "• `/rooms` - List all rooms\n"
            "• `/mybookings` - View your bookings\n"
            "• `/mybookings cancel [number(s)]` - Cancel specific bookings after viewing them\n"
        )