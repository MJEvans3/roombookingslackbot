from datetime import datetime, timedelta
import re
from typing import List
from utils.date_utils import parse_date_time
import logging
import calendar

class MessageHandler:
    def __init__(self, room_manager):
        self.room_manager = room_manager
        
    def handle_message(self, message: str, user_id: str) -> str:
        """Process incoming Slack messages and return appropriate responses."""
        logging.debug(f"Received message: '{message}' from user: {user_id}")
        message = message.lower().strip()
        logging.debug(f"Processed message: '{message}'")
        
        # Handle cancellation with booking number(s)
        cancel_match = re.match(r'cancel booking[s]?\s+#?(\d+(?:\s*,\s*\d+)*)', message)
        if cancel_match:
            numbers = [int(num.strip()) for num in cancel_match.group(1).split(',')]
            return self._handle_booking_cancellation(user_id, numbers)
        elif message == 'cancel all bookings':
            return self._handle_booking_cancellation(user_id, cancel_all=True)
        elif message == 'cancel booking':
            return self._handle_cancellation_request(user_id)
        elif message == 'list rooms':
            return self._handle_list_rooms()
        elif message.startswith('list available'):
            return self._handle_list_available(message)
        elif message.startswith('book '):
            if message.startswith('book recurring '):
                return self._handle_recurring_booking_request(message, user_id)
            return self._handle_booking_request(message, user_id)
        elif message == 'list my bookings':
            return self._handle_list_user_bookings(user_id)
        elif message.startswith('calendar view '):
            return self._handle_show_monthly_bookings(message)
        
        # If no command matches, return help message
        logging.debug(f"No command match found for message: '{message}'")
        return self._get_help_message()

    def _handle_booking_request(self, message: str, user_id: str) -> str:
        """Handle room booking requests."""
        # Extract all required fields
        room_match = re.search(r'book\s+(nest|treehouse|lighthouse|raven|hummingbird)', message)
        date_match = re.search(r'(?:book\s+\w+,\s*)(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Za-z]+|\d{1,2}/\d{1,2}(?:/\d{4})?|today|tomorrow)', message)
        time_match = re.search(r',\s*(\d{1,2}(?:[:.]\d{2})?(?:am|pm)|\d{2}[:.]\d{2})', message)
        duration_match = re.search(r'(?:,\s*)((?:\d+\s*(?:h|m|hours?|minutes?)(?:\s*(?:and|,)?\s*\d+\s*(?:h|m|hours?|minutes?))?)|(?:\d+\s*(?:h|m)))', message)
        event_match = re.search(r',\s*([^,]+?)\s*,\s*(?:internal|client)', message)
        type_match = re.search(r',\s*(internal|client)\s*,', message)
        name_match = re.search(r',\s*(?:internal|client)\s*,\s*([^,]+)$', message)
        
        # Validate all required fields
        if not all([room_match, date_match, time_match, duration_match, event_match, type_match, name_match]):
            return (
                "Please book a room using this format:\n"
                "`/book [room], [date], [time], [duration], [event details], [internal/client], [Full Contact Name]`\n\n"
                "Example: `/book nest, tomorrow, 2pm, 2 hours, NWG NCF Customer Playback, client, John Smith`\n"
                "*Date formats:* 'today', 'tomorrow', '28th Nov', '22nd of November', '19/12', '19/12/2024'\n"
                "*Supported Frequencies:* daily, weekly, biweekly, monthly\n"
                "*Duration formats accepted:*\n"
                "• Hours: '3h', '3 h', '3 hours'\n"
                "• Minutes: '45m', '45 m', '45 minutes'\n"
                "• Combined: '2 hours 30 minutes', '2h 30m'\n\n"
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
        duration_minutes = self._parse_duration(duration_match.group(1))
        
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

    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string into minutes."""
        # Clean up the input string
        duration_str = duration_str.lower().strip()
        
        # Check for hours format (3h, 3 h)
        hours_match = re.match(r'^(\d+)\s*h$', duration_str)
        if hours_match:
            return int(hours_match.group(1)) * 60
        
        # Check for minutes format (45m, 45 m, 45 min)
        minutes_match = re.match(r'^(\d+)\s*(?:m|min)$', duration_str)
        if minutes_match:
            return int(minutes_match.group(1))
        
        # Check for combined format (1h 45m, 1h 45min, 1 hour 45 minutes)
        combined_match = re.match(r'^(\d+)\s*(?:h|hours?)\s*(?:and|,)?\s*(\d+)\s*(?:m|min|minutes?)?$', duration_str)
        if combined_match:
            hours = int(combined_match.group(1))
            minutes = int(combined_match.group(2))
            return hours * 60 + minutes
        
        # Check for hours and minutes format (2 hours 30 minutes, 2 hours, 30 minutes)
        hours_minutes_match = re.match(r'^(?:(\d+)\s*hours?)?(?:\s*(?:and|,)?\s*)?(?:(\d+)\s*(?:min|minutes?))?$', duration_str)
        if hours_minutes_match and (hours_minutes_match.group(1) or hours_minutes_match.group(2)):
            hours = int(hours_minutes_match.group(1) or 0)
            minutes = int(hours_minutes_match.group(2) or 0)
            return hours * 60 + minutes
        
        raise ValueError(
            "Invalid duration format. Please use one of:\n"
            "• '3h' or '3 h' for hours\n"
            "• '45m', '45 min' or '45 minutes' for minutes\n"
            "• '2h 30m', '1h 45min' for combined\n"
            "• '2 hours 30 minutes' or '2 hours and 30 minutes'"
        )

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
        
        booking_list.append("\nTo cancel a booking, use one of:")
        booking_list.append("• `/mybookings cancel <number>` (e.g., 1)")
        booking_list.append("• `/mybookings cancel <numbers>` (e.g., 1,2,4)")
        booking_list.append("• `/mybookings cancel all`")
        
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
        date_match = re.search(r'for\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Za-z]+|\d{1,2}/\d{1,2}(?:/\d{4})?|today|tomorrow)', message)
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
        """Return help message for available commands."""
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

    def _handle_recurring_booking_request(self, message: str, user_id: str) -> str:
        """Handle recurring room booking requests."""
        # Extract all required fields
        room_match = re.search(r'book recurring\s+(nest|treehouse|lighthouse|raven|hummingbird)', message)
        date_match = re.search(r'(?:book\s+recurring\s+\w+,\s*)(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Za-z]+|\d{1,2}/\d{1,2}(?:/\d{4})?|today|tomorrow)', message)
        end_date_match = re.search(r',\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Za-z]+|\d{1,2}/\d{1,2}(?:/\d{4})?|today|tomorrow)', message)
        frequency_match = re.search(r',\s*(daily|weekly|biweekly|monthly)', message)
        time_match = re.search(r',\s*(\d{1,2}(?:[:.]\d{2})?(?:am|pm)|\d{2}[:.]\d{2})', message)
        duration_match = re.search(r'(?:,\s*)((?:\d+\s*(?:h|m|hours?|minutes?|min)(?:\s*(?:and|,)?\s*\d+\s*(?:h|m|hours?|minutes?|min))?)|(?:\d+\s*(?:h|m)))', message)
        event_match = re.search(r',\s*([^,]+?)\s*,\s*(?:internal|client)', message)
        type_match = re.search(r',\s*(internal|client)\s*,', message)
        name_match = re.search(r',\s*(?:internal|client)\s*,\s*([^,]+)$', message)

        # Add debug logging
        logging.debug(f"Start date match: {date_match.group(1) if date_match else None}")
        logging.debug(f"End date match: {end_date_match.group(1) if end_date_match else None}")
        logging.debug(f"Frequency match: {frequency_match.group(1) if frequency_match else None}")

        # Validate all required fields
        if not all([room_match, date_match, end_date_match, frequency_match, time_match, 
                    duration_match, event_match, type_match, name_match]):
            return (
                "Please book a recurring room using this format:\n"
                "`/book recurring [room], [start date], [end date], [frequency], [time], [duration], [event details], [internal/client], [Full Contact Name]`\n\n"
                "Example: `/book recurring nest, 22nd November, 22nd December, weekly, 2pm, 2 hours, Team Sync, internal, John Smith`\n"
                "Frequency options: daily, weekly, biweekly, monthly\n"
                "Date formats accepted: 'today', 'tomorrow', '28th November', '22nd of November', '19/12', '19/12/2024'"
            )

        # Extract values
        room_id = room_match.group(1).upper()
        start_date_str = date_match.group(1)
        end_date_str = end_date_match.group(1)
        frequency = frequency_match.group(1)
        time_str = time_match.group(1)

        # Parse dates and time
        start_date = parse_date_time(start_date_str, time_str)
        end_date = parse_date_time(end_date_str, time_str)
        
        if not start_date or not end_date:
            return "I couldn't understand the dates and time. Please try again."
        
        if start_date.date() >= end_date.date():
            return "The end date must be after the start date."

        # Parse duration
        amount = int(duration_match.group(1))
        unit = duration_match.group(2).lower()
        if unit in ['hour', 'hours']:
            duration_minutes = amount * 60
        elif unit in ['minute', 'minutes', 'min', 'mins', 'm']:
            duration_minutes = amount
            if amount not in [15, 30, 45] and amount < 60:
                return "For bookings less than 1 hour, please use 15, 30, or 45 minute intervals."

        # Get other details
        event_name = event_match.group(1).strip()
        meeting_type = type_match.group(1)
        contact_name = name_match.group(1).strip()

        # Calculate all booking dates based on frequency
        current_date = start_date
        booking_dates = []
        failed_bookings = []
        successful_bookings = []

        while current_date.date() <= end_date.date():
            booking_dates.append(current_date)
            if frequency == 'daily':
                current_date += timedelta(days=1)
            elif frequency == 'weekly':
                current_date += timedelta(days=7)
            elif frequency == 'biweekly':
                current_date += timedelta(days=14)
            elif frequency == 'monthly':
                # Add one month (approximately)
                if current_date.month == 12:
                    next_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    next_date = current_date.replace(month=current_date.month + 1)
                current_date = next_date

        # Try to book each date individually
        for booking_date in booking_dates:
            booking_end = booking_date + timedelta(minutes=duration_minutes)
            
            # Check if this specific timeslot is available
            if self.room_manager.check_room_availability(room_id, booking_date, duration_minutes):
                # Create the booking
                booking = self.room_manager.book_room(
                    room_id, booking_date, duration_minutes,
                    event_name, meeting_type, contact_name, user_id
                )
                if booking:
                    successful_bookings.append(booking_date)
                else:
                    failed_bookings.append(booking_date)
            else:
                failed_bookings.append(booking_date)

        # After all bookings are processed, format the response
        response = []
        if successful_bookings:
            response.append(f"Successfully booked {room_id} for the following dates:")
            for date in successful_bookings:
                response.append(f"• {date.strftime('%B %d')} from {date.strftime('%I:%M %p')} to {(date + timedelta(minutes=duration_minutes)).strftime('%I:%M %p')}")

        if failed_bookings:
            if response:
                response.append("\nThe following bookings could not be made due to conflicts:")
            for date in failed_bookings:
                # Get the conflicting booking for this date
                conflicts = [b for b in self.room_manager.get_room_schedule(room_id) 
                           if datetime.fromisoformat(b['start_time']).date() == date.date() and
                           (datetime.fromisoformat(b['start_time']) <= date + timedelta(minutes=duration_minutes) and
                            datetime.fromisoformat(b['end_time']) >= date)]
                
                if conflicts:
                    conflict = conflicts[0]  # Get the first conflicting booking
                    response.append(
                        f"• {date.strftime('%B %d')} at {date.strftime('%I:%M %p')} - "
                        f"{(date + timedelta(minutes=duration_minutes)).strftime('%I:%M %p')} conflicts with existing booking:\n"
                        f"  '{conflict['event_name']}' ({conflict['start_time'][11:16]} - "
                        f"{conflict['end_time'][11:16]}) - Contact: {conflict['contact_name']}"
                    )
                else:
                    response.append(
                        f"• {date.strftime('%B %d')} at {date.strftime('%I:%M %p')} - "
                        f"{(date + timedelta(minutes=duration_minutes)).strftime('%I:%M %p')}"
                    )

        return "\n".join(response)

    def _handle_list_user_bookings(self, user_id: str) -> str:
        """Handle a request to list user's bookings."""
        bookings = self.room_manager.get_user_bookings(user_id)
        if not bookings:
            return "You don't have any active bookings."
        
        response = ["Your active bookings:"]
        for i, booking in enumerate(bookings, 1):
            start_time = datetime.fromisoformat(booking['start_time'])
            end_time = datetime.fromisoformat(booking['end_time'])
            response.append(
                f"{i}. {booking['room_name']} on {start_time.strftime('%B %d')} "
                f"from {start_time.strftime('%I:%M %p')} to {end_time.strftime('%I:%M %p')} - "
                f"{booking['event_name']}"
            )
        return "\n".join(response)

    def _handle_show_monthly_bookings(self, message: str) -> str:
        """Show monthly bookings in a calendar view."""
        try:
            # Parse month from message
            month_str = message.replace('calendar view ', '').strip()
            month_names = {month.lower(): i for i, month in enumerate(calendar.month_name) if month}
            month_abbr = {month.lower(): i for i, month in enumerate(calendar.month_abbr) if month}
            
            # Room name abbreviations
            room_abbr = {
                "LIGHTHOUSE": "Lght",
                "TREEHOUSE": "Tree",
                "RAVEN": "Ravn",
                "HUMMINGBIRD": "Hmng",
                "NEST": "Nest"
            }
            
            month_str = month_str.lower()
            if month_str in month_names:
                month_num = month_names[month_str]
            elif month_str in month_abbr:
                month_num = month_abbr[month_str]
            else:
                return "Please specify a valid month, e.g., 'December' or 'Dec'"
            
            current_year = datetime.now().year
            if datetime.now().month > month_num:
                current_year += 1

            # First, create detailed bookings view
            all_bookings = []
            for room_id, room in self.room_manager.rooms.items():
                for booking in room.bookings:
                    booking_start = datetime.fromisoformat(booking['start_time'])
                    if booking_start.month == month_num and booking_start.year == current_year:
                        all_bookings.append({
                            'date': booking_start,
                            'start': booking_start,
                            'end': datetime.fromisoformat(booking['end_time']),
                            'room': room.name,
                            'event': booking['event_name'],
                            'type': booking['meeting_type'],
                            'contact': booking['contact_name']
                        })

            # Sort bookings by date and time
            all_bookings.sort(key=lambda x: (x['date'].date(), x['start'].time()))

            # Create response with detailed bookings
            response = [f"Detailed Bookings for {calendar.month_name[month_num]} {current_year}:"]
            current_date = None
            
            for booking in all_bookings:
                booking_date = booking['date'].date()
                if booking_date != current_date:
                    current_date = booking_date
                    response.append(f"\n{booking_date.strftime('%B %d (%A)')}")
                
                response.append(
                    f"• {booking['start'].strftime('%H:%M')}-{booking['end'].strftime('%H:%M')} - "
                    f"{booking['room']} - {booking['event']} - Contact: {booking['contact']}"
                )

            # Add calendar view header
            response.extend([
                f"\n📅 Calendar for {calendar.month_name[month_num]} {current_year}\n",
                "```"
            ])
            
            # Create calendar view
            CELL_WIDTH = 18
            
            # Add weekday headers
            header = "".join(day.ljust(CELL_WIDTH) for day in ["MON", "TUE", "WED", "THU", "FRI"])
            response.append(header)
            response.append("─" * (CELL_WIDTH * 5))
            
            # Process each week
            cal = calendar.monthcalendar(current_year, month_num)
            for week in cal:
                week_lines = [""] * 20  # Increased max lines per week to accommodate more bookings
                max_lines_used = 1  # At least show the date line
                
                # Process only weekdays
                for day_idx in range(min(5, len(week))):
                    day = week[day_idx]
                    if day == 0:
                        # Empty day
                        for i in range(20):  # Increased to match new max lines
                            week_lines[i] += " " * CELL_WIDTH
                        continue
                    
                    # Get all bookings for this day
                    date = datetime(current_year, month_num, day)
                    day_bookings = []
                    for room_id, room in self.room_manager.rooms.items():
                        for booking in room.bookings:
                            booking_start = datetime.fromisoformat(booking['start_time'])
                            booking_end = datetime.fromisoformat(booking['end_time'])
                            if booking_start.date() == date.date():
                                day_bookings.append({
                                    'start': booking_start,
                                    'end': booking_end,
                                    'room': room_abbr[room_id]
                                })
                    
                    # Sort bookings by time
                    day_bookings.sort(key=lambda x: x['start'])
                    
                    # Format day cell with asterisks
                    week_lines[0] += f"*{day}*".ljust(CELL_WIDTH)  # First line is day number with asterisks
                    
                    # Add each booking on its own line - removed the limit
                    for i, booking in enumerate(day_bookings):
                        booking_str = (f"{booking['start'].strftime('%H:%M')}-"
                                     f"{booking['end'].strftime('%H:%M')} "
                                     f"{booking['room']}")
                        week_lines[i + 1] += booking_str.ljust(CELL_WIDTH)
                        max_lines_used = max(max_lines_used, i + 2)
                    
                    # Fill remaining lines with spaces
                    for i in range(len(day_bookings) + 1, 20):  # Increased to match new max lines
                        week_lines[i] += " " * CELL_WIDTH
                
                # Add non-empty lines to response
                response.extend(line.rstrip() for line in week_lines[:max_lines_used])
                response.append("─" * (CELL_WIDTH * 5))
            
            response.append("```")
            return "\n".join(response)
            
        except Exception as e:
            logging.error(f"Error in _handle_show_monthly_bookings: {str(e)}")
            return "Sorry, I encountered an error while creating the calendar view. Please try again."
    