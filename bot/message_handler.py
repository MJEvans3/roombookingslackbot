from datetime import datetime, timedelta
import re
from typing import List
from utils.date_utils import parse_date_time
import logging

class MessageHandler:
    def __init__(self, room_manager):
        self.room_manager = room_manager
        
    def handle_message(self, message: str, user_id: str) -> str:
        """Process incoming Slack messages and return appropriate responses."""
        logging.debug(f"Received message: '{message}' from user: {user_id}")
        
        # Remove the bot mention and convert to lowercase
        message = re.sub(r'<@[A-Z0-9]+>\s*', '', message).lower().strip()
        logging.debug(f"Processed message after removing mention: '{message}'")
        
        # Handle cancellation with booking number(s)
        cancel_match = re.match(r'cancel booking[s]?\s+#?(\d+(?:\s*,\s*\d+)*)', message)
        if cancel_match:
            numbers = [int(num.strip()) for num in cancel_match.group(1).split(',')]
            return self._handle_booking_cancellation(user_id, numbers)
        elif message == 'cancel all bookings':
            return self._handle_booking_cancellation(user_id, cancel_all=True)
        elif message == 'cancel booking':
            return self._handle_cancellation_request(user_id)
        elif message == 'book a room':
            return (
                "Please book a room using this format:\n"
                "`@floor10roombooking book [room], [date], [time], [duration], [event details], [internal/client], [Full Contact Name]`\n\n"
                "Example: `@floor10roombooking book nest, tomorrow, 2pm, 2 hours, NWG NCF Customer Playback, client, John Smith`\n"
                "Date formats accepted: 'today', 'tomorrow', '28th November', '22nd of November', '19/12', '19/12/2024'"
            )
        elif message == 'list rooms':
            return self._handle_list_rooms()
        elif message.startswith('list available'):
            return self._handle_list_available(message)
        elif message.startswith('book '):
            return self._handle_booking_request(message, user_id)
        
        # If no command matches, return help message
        logging.debug(f"No command match found for message: '{message}'")
        return self._get_help_message()

    def _handle_booking_request(self, message: str, user_id: str) -> str:
        """Handle room booking requests."""
        # Extract all required fields
        room_match = re.search(r'book\s+(nest|treehouse|lighthouse|raven|hummingbird)', message)
        date_match = re.search(r'(?:book\s+\w+,\s*)(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Za-z]+|\d{1,2}/\d{1,2}(?:/\d{4})?|today|tomorrow)', message)
        time_match = re.search(r',\s*(\d{1,2}(?::\d{2})?(?:am|pm)|\d{2}:\d{2})', message)
        duration_match = re.search(r',\s*(\d+)\s+(hour|minute|min|m|minutes|mins|hours)s?', message)
        event_match = re.search(r',\s*([^,]+?)\s*,\s*(?:internal|client)', message)
        type_match = re.search(r',\s*(internal|client)\s*,', message)
        name_match = re.search(r',\s*(?:internal|client)\s*,\s*([^,]+)$', message)
        
        # Validate all required fields
        if not all([room_match, date_match, time_match, duration_match, event_match, type_match, name_match]):
            return (
                "Please book a room using this format:\n"
                "`@floor10roombooking book [room], [date], [time], [duration], [event details], [internal/client], [Full Contact Name]`\n\n"
                "Example: `@floor10roombooking book nest, tomorrow, 2pm, 2 hours, NWG NCF Customer Playback, client, John Smith`\n"
                "Date formats accepted: 'today', 'tomorrow', '28th November', '22nd of November', '19/12', '19/12/2024'"
            )
        
        # Extract values
        room_id = room_match.group(1).upper()
        date_str = date_match.group(1)
        time_str = time_match.group(1)
        
        # Parse the date and time
        start_time = parse_date_time(date_str, time_str)
        if not start_time:
            return "I couldn't understand the date and time. Please try again."
            
        # Parse duration with support for minutes
        amount = int(duration_match.group(1))
        unit = duration_match.group(2).lower()
        if unit in ['hour', 'hours']:
            duration_minutes = amount * 60
        elif unit in ['minute', 'minutes', 'min', 'mins', 'm']:
            duration_minutes = amount
            # Validate minute durations
            if amount not in [15, 30, 45] and amount < 60:
                return "For bookings less than 1 hour, please use 15, 30, or 45 minute intervals."
        
        # Get other details
        event_name = event_match.group(1).strip()
        meeting_type = type_match.group(1)
        contact_name = name_match.group(1).strip()
        
        # Check room availability
        if not self.room_manager.check_room_availability(room_id, start_time, duration_minutes):
            alternatives = self.room_manager.get_alternative_suggestions(room_id, start_time, duration_minutes)
            return self._format_alternative_suggestions(alternatives)
            
        # Create booking
        booking = self.room_manager.book_room(
            room_id, start_time, duration_minutes,
            event_name, meeting_type, contact_name, user_id
        )
        
        if booking:
            return (
                f"Room {booking['room_name']} booked:\n"
                f"• Date: {start_time.strftime('%B %d, %Y')}\n"
                f"• Time: {start_time.strftime('%I:%M %p')} - {(start_time + timedelta(minutes=duration_minutes)).strftime('%I:%M %p')}\n"
                f"• Event: {event_name}\n"
                f"• Type: {meeting_type}\n"
                f"• Contact: {contact_name}"
            )
        return "Sorry, I couldn't book that room."

    def _handle_cancellation_request(self, user_id: str) -> str:
        """Handle a request to cancel a booking."""
        logging.debug(f"Handling cancellation request for user: {user_id}")
        
        # Get all bookings for this user
        bookings = self.room_manager.get_user_bookings(user_id)
        if not bookings:
            return "You don't have any active bookings to cancel."
        
        # Format the booking list
        booking_list = ["Your active bookings:"]
        for i, booking in enumerate(bookings, 1):
            start_time = datetime.fromisoformat(booking['start_time'])
            booking_list.append(
                f"{i}. {booking['room_name']} on {start_time.strftime('%B %d at %I:%M %p')} - {booking['event_name']}"
            )
        
        booking_list.append("\nTo cancel a booking, reply with one of:")
        booking_list.append("• `@floor10roombooking cancel booking <number>` (e.g., 1)")
        booking_list.append("• `@floor10roombooking cancel bookings <numbers>` (e.g., 1,2,4)")
        booking_list.append("• `@floor10roombooking cancel all bookings`")
        
        return "\n".join(booking_list)

    def _handle_list_rooms(self) -> str:
        """Handle request to list all rooms."""
        rooms = self.room_manager.get_all_rooms()
        response = ["Available rooms:"]
        for room in rooms:
            response.append(f"• {room.name} (Capacity: {room.capacity})")
        return "\n".join(response)

    def _handle_list_available(self, message: str) -> str:
        """Handle request to list available rooms for a specific time."""
        # Extract date and time
        date_match = re.search(r'(today|tomorrow|\d{1,2}(?:st|nd|rd|th)? [A-Za-z]+)', message)
        time_match = re.search(r'(\d{1,2}(?::\d{2})?(?:am|pm)|\d{2}:\d{2})', message)
        
        if not date_match:
            return "Please specify a date. For example: 'list available rooms for tomorrow'"
            
        # If no time specified, show availability for the whole day
        if not time_match:
            date_str = date_match.group(1)
            date = parse_date_time(date_str, "9am")  # Use 9am as default
            if not date:
                return "I couldn't understand the date. Please try again."
                
            response = [f"Available rooms for {date.strftime('%B %d')}:"]
            for room in self.room_manager.get_all_rooms():
                slots = self.room_manager.get_available_slots(room.room_id, date)
                if slots:
                    slot_times = [
                        f"{slot[0].strftime('%I:%M %p')} - {slot[1].strftime('%I:%M %p')}"
                        for slot in slots
                    ]
                    response.append(f"\n{room.name}:")
                    response.extend([f"• {slot}" for slot in slot_times])
            return "\n".join(response)
            
        # Check availability for specific time
        start_time = parse_date_time(date_match.group(1), time_match.group(1))
        if not start_time:
            return "I couldn't understand the date and time. Please try again."
            
        available_rooms = self.room_manager.list_available_rooms(start_time, 60)  # Default 1 hour
        if not available_rooms:
            return f"No rooms available at {start_time.strftime('%B %d %I:%M %p')}"
            
        response = [f"Available rooms for {start_time.strftime('%B %d at %I:%M %p')}:"]
        for room in available_rooms:
            response.append(f"• {room.name} (Capacity: {room.capacity})")
        return "\n".join(response)

    def _format_alternative_suggestions(self, alternatives: dict) -> str:
        """Format alternative booking suggestions."""
        # Get the conflicting booking details
        conflicting_booking = alternatives.get("conflicting_booking")
        response = []
        
        if conflicting_booking:
            meeting_type_text = "a client meeting" if conflicting_booking['meeting_type'] == 'client' else "an internal meeting"
            response.extend([
                "That time is not available:",
                f"• {conflicting_booking['room_name']} is booked for '{conflicting_booking['event_name']}' for {meeting_type_text}",
                f"• Time: {conflicting_booking['start_time'].strftime('%I:%M %p')} - {conflicting_booking['end_time'].strftime('%I:%M %p')}",
                f"• Contact: {conflicting_booking['contact_name']}\n"
            ])
        else:
            response.append("That time is not available.")
        
        response.append("Here are some alternatives:")
        
        if alternatives["available_times"]:
            response.append("\nOther times for the same room:")
            for time in alternatives["available_times"][:8]:  # Show max 8 alternatives
                response.append(f"• {time.strftime('%I:%M %p')}")
                
        if alternatives["other_rooms"]:
            response.append("\nOther available rooms at the requested time:")
            for room in alternatives["other_rooms"]:
                response.append(f"• {room.name} (Capacity: {room.capacity})")
                
        return "\n".join(response)

    def _get_help_message(self) -> str:
        """Return help message with available commands."""
        return (
            "Try these commands:\n"
            "• `@floor10roombooking book a room`\n"
            "• `@floor10roombooking list rooms`\n"
            "• `@floor10roombooking list available rooms for eg. 21 August`\n"
            "• `@floor10roombooking cancel booking`"
        )

    def _handle_booking_cancellation(self, user_id: str, booking_numbers: List[int] = None, cancel_all: bool = False) -> str:
        """Handle the actual cancellation of bookings."""
        # Get current bookings before cancellation
        current_bookings = self.room_manager.get_user_bookings(user_id)
        if not current_bookings:
            return "You don't have any active bookings to cancel."

        # If cancel_all is True, get all booking numbers
        if cancel_all:
            booking_numbers = list(range(1, len(current_bookings) + 1))

        # Validate booking numbers
        if not booking_numbers:
            return "Please specify which booking(s) to cancel."

        invalid_numbers = [n for n in booking_numbers if n < 1 or n > len(current_bookings)]
        if invalid_numbers:
            return f"Invalid booking number(s): {', '.join(map(str, invalid_numbers))}"

        # Get the bookings to cancel
        bookings_to_cancel = [current_bookings[i-1] for i in booking_numbers]
        
        # Cancel the bookings
        cancelled_bookings = []
        for booking in bookings_to_cancel:
            success = self.room_manager.cancel_booking(
                booking['room_id'],
                datetime.fromisoformat(booking['start_time']),
                user_id
            )[0]
            if success:
                cancelled_bookings.append(booking)

        # Format response message
        if not cancelled_bookings:
            return "No bookings were cancelled."
        
        response = ["The following booking(s) were successfully cancelled:"]
        for booking in cancelled_bookings:
            start_time = datetime.fromisoformat(booking['start_time'])
            response.append(
                f"• {booking['room_name']} on {start_time.strftime('%B %d at %I:%M %p')} - {booking['event_name']}"
            )
        
        return "\n".join(response)
    