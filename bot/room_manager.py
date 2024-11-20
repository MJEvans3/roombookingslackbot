from datetime import datetime, timedelta, time
from typing import List, Dict, Optional, Tuple
import json
import os
import logging

class Room:
    def __init__(self, room_id: str, name: str, capacity: int):
        self.room_id = room_id
        self.name = name
        self.capacity = capacity
        self.bookings: List[Dict] = []

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "name": self.name,
            "capacity": self.capacity,
            "bookings": self.bookings
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Room':
        """Create a Room instance from a dictionary."""
        return cls(
            room_id=data["room_id"],
            name=data["name"],
            capacity=data["capacity"]
        )

class RoomManager:
    def __init__(self):
        # Get the current script's directory
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Create data directory path relative to project root
        self.data_dir = os.path.join(current_dir, 'data')
        self.data_file = os.path.join(self.data_dir, 'rooms.json')
        self.rooms: Dict[str, Room] = {}
        self._load_rooms()
        self.last_booking_conflict = None  # Store the last booking conflict for template generation

    def _load_rooms(self):
        """Load rooms from JSON file or create default rooms if file doesn't exist."""
        try:
            # Create data directory if it doesn't exist
            os.makedirs(self.data_dir, exist_ok=True)
            
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    for room_id, room_data in data.items():
                        room = Room(
                            room_id=room_id,
                            name=room_data["name"],
                            capacity=room_data["capacity"]
                        )
                        room.bookings = room_data.get("bookings", [])
                        self.rooms[room.room_id] = room
            else:
                # Create default rooms
                default_rooms = [
                    Room("NEST", "The Nest", 30),
                    Room("TREEHOUSE", "The Treehouse", 15),
                    Room("LIGHTHOUSE", "The Lighthouse", 15),
                    Room("RAVEN", "Raven", 4),
                    Room("HUMMINGBIRD", "Hummingbird", 4)
                ]
                for room in default_rooms:
                    self.rooms[room.room_id] = room
                self._save_rooms()
        except Exception as e:
            logging.error(f"Error loading rooms: {e}")
            self.rooms = {}

    def _save_rooms(self):
        """Save current room state to JSON file."""
        try:
            data = {
                room.room_id: room.to_dict()
                for room in self.rooms.values()
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving rooms: {e}")

    def check_room_availability(self, room_id: str, start_time: datetime, duration_minutes: int) -> bool:
        """Check if a room is available for booking."""
        if room_id not in self.rooms:
            logging.debug(f"Room {room_id} not found")
            return False
        
        # Calculate end time
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        logging.debug(f"Checking availability for {room_id}")
        logging.debug(f"Requested time: {start_time} to {end_time}")
        
        # Get all bookings for the room
        bookings = self.get_room_schedule(room_id)
        
        # Check for conflicts with existing bookings
        for booking in bookings:
            booking_start = datetime.fromisoformat(booking["start_time"])
            booking_end = datetime.fromisoformat(booking["end_time"])
            
            logging.debug(f"Existing booking: {booking_start} to {booking_end}")
            
            # Check if there's any overlap
            if (start_time < booking_end and end_time > booking_start):
                logging.debug(f"Conflict found with booking: {booking['event_name']}")
                return False
                
        logging.debug("No conflicts found, room is available")
        return True

    def find_available_room(self, start_time: datetime, duration_minutes: int) -> Optional[Room]:
        """Find an available room for the specified time slot."""
        for room in self.rooms.values():
            if self.check_room_availability(room.room_id, start_time, duration_minutes):
                return room
        return None
    def book_room(self, room_name: str, start_time: datetime, duration_minutes: int, 
                  event_name: str, meeting_type: str, contact_name: str, user_id: str) -> Optional[dict]:
        """Book a room if available."""
        # Make room name case-insensitive
        room_name = room_name.upper()
        
        # Check if room exists
        if room_name not in self.rooms:
            return None
        
        room = self.rooms[room_name]

        # Calculate end time
        end_time = start_time + timedelta(minutes=duration_minutes)

        # Create new booking
        new_booking = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": duration_minutes,
            "event_name": event_name,
            "meeting_type": meeting_type,
            "contact_name": contact_name,
            "user_id": user_id  # Store the Slack user ID
        }

        # Add booking to room's schedule
        room.bookings.append(new_booking)

        # Save updated bookings to file
        self._save_rooms()

        # Return booking confirmation
        return {
            "room_name": room.name,
            "booking": {
                "start_time": start_time,
                "end_time": end_time
            },
            "event_name": event_name
        }
    def get_room_schedule(self, room_id: str) -> List[dict]:
        """Get all bookings for a room."""
        if room_id not in self.rooms:
            return []
        return sorted(
            self.rooms[room_id].bookings,
            key=lambda x: datetime.fromisoformat(x["start_time"])
        )

    def cancel_booking(self, room_id: str, start_time: datetime, user_id: str) -> tuple[bool, str]:
        """Cancel a booking if the user is authorized."""
        logging.debug(f"Attempting to cancel booking - Room: {room_id}, Time: {start_time}, User: {user_id}")
        
        if room_id not in self.rooms:
            logging.debug(f"Room not found: {room_id}")
            return False, "Room not found."

        room = self.rooms[room_id]
        start_time_str = start_time.isoformat()
        
        for i, booking in enumerate(room.bookings):
            if booking.get("start_time") == start_time_str:
                # Check if the user is authorized to cancel
                if booking.get("user_id") != user_id:
                    logging.debug(f"Unauthorized cancellation attempt - Booking user: {booking.get('user_id')}, Request user: {user_id}")
                    return False, "You are not authorized to cancel this booking."
                
                # Remove the booking
                logging.debug(f"Cancelling booking: {booking}")
                room.bookings.pop(i)
                self._save_rooms()
                return True, f"Booking cancelled successfully for {room.name}."
        
        logging.debug("No matching booking found")
        return False, "No booking found for the specified time."

    def list_available_rooms(self, start_time: datetime, duration_minutes: int) -> List[Room]:
        """List all rooms available at the specified time."""
        available_rooms = []
        for room in self.rooms.values():
            if self.check_room_availability(room.room_id, start_time, duration_minutes):
                available_rooms.append(room)
        return available_rooms

    def get_room_schedule_formatted(self, room_id: str) -> str:
        """Get formatted schedule for a room."""
        if room_id not in self.rooms:
            return "Room not found"
        
        bookings = self.get_room_schedule(room_id)
        room = self.rooms[room_id]
        
        if not bookings:
            return f"*{room.name}* (Capacity: {room.capacity})\nNo bookings scheduled"
        
        schedule = [f"*{room.name}* (Capacity: {room.capacity})\nUpcoming bookings:"]
        for booking in bookings:
            start = datetime.fromisoformat(booking["start_time"])
            end = datetime.fromisoformat(booking["end_time"])
            schedule.append(
                f"• {start.strftime('%Y-%m-%d %I:%M %p')} - "
                f"{end.strftime('%I:%M %p')} "
                f"({booking['duration_minutes']} minutes)"
            )
        
        return "\n".join(schedule)
    def get_all_rooms(self) -> List[Room]:
        """Return a list of all rooms."""
        return list(self.rooms.values())

    def load_rooms(self):
        """Load rooms from JSON file."""
        try:
            with open('data/rooms.json', 'r') as f:
                data = json.load(f)
                for room_id, room_data in data.items():
                    print(f"Loading room: {room_id} with data: {room_data}")  # Debugging line
                    # Ensure room_id is in the room_data
                    if "room_id" not in room_data:
                        room_data["room_id"] = room_id
                    self.rooms[room_id] = Room.from_dict(room_data)
        except Exception as e:
            print(f"Error loading rooms: {e}")

    def get_available_times_for_day(self, room_id: str, date: datetime, duration_minutes: int) -> List[datetime]:
        """Get all available time slots for a given day."""
        available_times = []
        room = self.rooms.get(room_id)
        if not room:
            return []

        # Check every hour from 9 AM to 5 PM
        start_hour = 9
        end_hour = 17
        
        current_time = datetime.combine(date.date(), datetime.min.time().replace(hour=start_hour))
        end_time = datetime.combine(date.date(), datetime.min.time().replace(hour=end_hour))
        
        while current_time <= end_time:
            if self.check_room_availability(room_id, current_time, duration_minutes):
                available_times.append(current_time)
            current_time += timedelta(hours=1)
        
        return available_times

    def get_alternative_suggestions(self, room_id: str, start_time: datetime, duration_minutes: int) -> dict:
        """Get alternative booking suggestions."""
        # Get the conflicting booking if any
        room = self.rooms.get(room_id)
        conflicting_booking = None
        
        if room:
            for booking in room.bookings:
                booking_start = datetime.fromisoformat(booking['start_time'])
                booking_end = datetime.fromisoformat(booking['end_time'])
                if (start_time >= booking_start and start_time < booking_end):
                    conflicting_booking = {
                        **booking,
                        'room_name': room.name,
                        'start_time': booking_start,
                        'end_time': booking_end
                    }
                    break
        
        # Get available times for the same room on the same day
        available_times = self.get_available_times_for_day(room_id, start_time, duration_minutes)
        
        # Get other available rooms for the same time
        other_rooms = []
        for other_room in self.rooms.values():
            if other_room.room_id != room_id and self.check_room_availability(other_room.room_id, start_time, duration_minutes):
                other_rooms.append(other_room)
        
        return {
            "conflicting_booking": conflicting_booking,
            "available_times": available_times,
            "other_rooms": other_rooms
        }

    def get_booking_details(self, room_id: str, start_time: datetime) -> Optional[dict]:
        """Get booking details for a specific time."""
        if room_id not in self.rooms:
            return None
        
        bookings = self.get_room_schedule(room_id)
        target_time = start_time.isoformat()
        
        for booking in bookings:
            booking_start = datetime.fromisoformat(booking["start_time"])
            booking_end = datetime.fromisoformat(booking["end_time"])
            
            if (start_time >= booking_start and start_time < booking_end):
                return {
                    "event_name": booking["event_name"],
                    "contact_name": booking["contact_name"],
                    "start_time": booking_start,
                    "end_time": booking_end,
                    "meeting_type": booking["meeting_type"]
                }
        return None

    def get_user_bookings(self, user_id: str) -> List[Dict]:
        """Get all active bookings for a specific user."""
        current_time = datetime.now()
        user_bookings = []
        
        for room in self.rooms.values():
            for booking in room.bookings:
                booking_time = datetime.fromisoformat(booking['start_time'])
                if booking.get('user_id') == user_id and booking_time > current_time:
                    user_bookings.append({
                        **booking,
                        'room_id': room.room_id,
                        'room_name': room.name
                    })
        
        # Sort by start time
        user_bookings.sort(key=lambda x: x['start_time'])
        return user_bookings

    def cancel_bookings(self, user_id: str, booking_numbers: List[int] = None, cancel_all: bool = False) -> Tuple[bool, str]:
        """Cancel one or more bookings for a user."""
        bookings = self.get_user_bookings(user_id)
        if not bookings:
            return False, "You don't have any active bookings to cancel."
        
        if cancel_all:
            booking_numbers = list(range(1, len(bookings) + 1))
        
        if not booking_numbers:
            return False, "Please specify which booking(s) to cancel."
        
        cancelled = []
        errors = []
        
        for num in booking_numbers:
            if num < 1 or num > len(bookings):
                errors.append(f"Invalid booking number: {num}")
                continue
            
            booking = bookings[num - 1]
            success = self._remove_booking(booking['room_id'], booking['start_time'], user_id)
            if success:
                cancelled.append(f"{booking['room_name']} on {datetime.fromisoformat(booking['start_time']).strftime('%B %d at %I:%M %p')}")
            else:
                errors.append(f"Failed to cancel booking #{num}")
        
        # Construct response message
        response = []
        if cancelled:
            response.append("Successfully cancelled the following bookings:")
            response.extend([f"• {booking}" for booking in cancelled])
        if errors:
            if response:
                response.append("\nErrors:")
            response.extend([f"• {error}" for error in errors])
        
        return bool(cancelled), "\n".join(response)

    def get_available_slots(self, room_id: str, date: datetime) -> List[Tuple[datetime, datetime]]:
        """Get available time slots for a room on a specific date."""
        room = self.rooms.get(room_id)
        if not room:
            return []
        
        # Set business hours (e.g., 9 AM to 6 PM)
        start_hour = 9
        end_hour = 18
        
        # Create datetime objects for start and end of business day
        day_start = datetime.combine(date.date(), time(start_hour, 0))
        day_end = datetime.combine(date.date(), time(end_hour, 0))
        
        # Get all bookings for this room on this date
        bookings = []
        for booking in room.bookings:
            booking_start = datetime.fromisoformat(booking["start_time"])
            booking_end = datetime.fromisoformat(booking["end_time"])
            
            # Only consider bookings that overlap with this day
            if (booking_start.date() == date.date() or booking_end.date() == date.date()):
                bookings.append((booking_start, booking_end))
        
        # Sort bookings by start time
        bookings.sort(key=lambda x: x[0])
        
        # Find available slots
        available_slots = []
        current_time = day_start
        
        for booking_start, booking_end in bookings:
            # If there's a gap before this booking, add it to available slots
            if current_time < booking_start:
                available_slots.append((current_time, booking_start))
            current_time = max(current_time, booking_end)
        
        # Add any remaining time after the last booking
        if current_time < day_end:
            available_slots.append((current_time, day_end))
        
        return available_slots

    def create_booking(self, room_id: str, start_time: datetime, duration: timedelta, 
                      event_details: str, booking_type: str, contact_name: str) -> Optional[Dict]:
        """Create a new booking."""
        room = self.get_room(room_id)
        if not room:
            return None
            
        end_time = start_time + duration
        
        # Check if room is available
        if not room.is_available(start_time, end_time):
            return None
            
        # Create the booking
        booking = {
            'start_time': start_time,
            'end_time': end_time,
            'event_details': event_details,
            'booking_type': booking_type,
            'contact_name': contact_name
        }
        
        room.bookings.append(booking)
        # Sort bookings by start time
        room.bookings.sort(key=lambda x: x['start_time'])
        
        return booking
    
    def book_recurring_meetings(self, room_id: str, start_date: datetime, end_date: datetime, 
                              frequency: str, duration_minutes: int, event_name: str, 
                              meeting_type: str, contact_name: str, user_id: str) -> Tuple[List[datetime], List[datetime]]:
        """Book recurring meetings and return successful and failed booking dates."""
        successful_bookings = []
        failed_bookings = []
        current_date = start_date

        while current_date.date() <= end_date.date():
            if self.check_room_availability(room_id, current_date, duration_minutes):
                booking = self.book_room(
                    room_id, current_date, duration_minutes,
                    event_name, meeting_type, contact_name, user_id
                )
                if booking:
                    successful_bookings.append(current_date)
                else:
                    failed_bookings.append(current_date)
            else:
                failed_bookings.append(current_date)

            # Increment date based on frequency
            if frequency == 'daily':
                current_date += timedelta(days=1)
            elif frequency == 'weekly':
                current_date += timedelta(days=7)
            elif frequency == 'biweekly':
                current_date += timedelta(days=14)
            elif frequency == 'monthly':
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)

        return successful_bookings, failed_bookings
