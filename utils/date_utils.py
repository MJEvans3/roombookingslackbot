# utils/date_utils.py
from datetime import datetime, timedelta
import calendar
import logging

def parse_date_time(date_str: str, time_str: str) -> datetime:
    """Parse date and time strings into a datetime object."""
    logging.debug(f"Attempting to parse date: '{date_str}' and time: '{time_str}'")
    
    # Ensure inputs are strings and strip whitespace
    if not isinstance(date_str, str) or not isinstance(time_str, str):
        logging.debug("Invalid input types")
        return None
        
    date_str = date_str.lower().strip()
    time_str = time_str.lower().strip()
    logging.debug(f"Processed inputs - date: '{date_str}', time: '{time_str}'")
    
    # Get current date
    today = datetime.now()
    
    # Handle relative dates
    if date_str == "today":
        target_date = today
    elif date_str == "tomorrow":
        target_date = today + timedelta(days=1)
    else:
        try:
            # Try to parse date in DD/MM or DD/MM/YYYY format
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 2:  # DD/MM format
                    day, month = map(int, parts)
                    year = today.year
                elif len(parts) == 3:  # DD/MM/YYYY format
                    day, month, year = map(int, parts)
                else:
                    logging.debug(f"Invalid slash format: {date_str}")
                    return None
                
                target_date = datetime(year, month, day)
                
            else:
                # Handle formats like "2nd December" or "2nd of December"
                # Remove 'of' and split remaining parts
                date_str = date_str.replace(' of ', ' ')
                parts = date_str.split()
                
                # We should now have exactly 2 parts (day and month)
                if len(parts) != 2:
                    logging.debug(f"Invalid parts length after removing 'of': {len(parts)}")
                    return None
                
                day_str, month_str = parts
                
                # Remove ordinal indicators (st, nd, rd, th) from day
                day = int(day_str.replace('st', '').replace('nd', '').replace('rd', '').replace('th', ''))
                logging.debug(f"Parsed day: {day}, month: '{month_str}'")
                
                # Get month number (1-12)
                month_names = {month.lower(): i for i, month in enumerate(calendar.month_name) if month}
                month_abbr = {month.lower(): i for i, month in enumerate(calendar.month_abbr) if month}
                
                if month_str in month_names:
                    month = month_names[month_str]
                elif month_str in month_abbr:
                    month = month_abbr[month_str]
                else:
                    logging.debug(f"Could not parse month: '{month_str}'")
                    return None
                
                logging.debug(f"Resolved month number: {month}")
                target_date = datetime(today.year, month, day)
            
            logging.debug(f"Initial target date: {target_date}")
            
            # If the date has already passed this year, use next year
            # (only for non-slash formats or when year wasn't specified)
            if '/' not in date_str or len(date_str.split('/')) == 2:
                if target_date.date() < today.date():
                    target_date = target_date.replace(year=today.year + 1)
                    logging.debug(f"Date adjusted to next year: {target_date}")
            
        except (ValueError, AttributeError) as e:
            logging.debug(f"Error parsing date: {str(e)}")
            return None
    
    # For list available rooms command, we don't need time parsing
    if time_str == "":
        logging.debug("No time provided, returning date only")
        return target_date
    
    # Parse time
    try:
        if "am" in time_str or "pm" in time_str:
            time = datetime.strptime(time_str, "%I%p").time()
        else:
            time = datetime.strptime(time_str, "%H:%M").time()
            
        result = datetime.combine(target_date.date(), time)
        logging.debug(f"Final datetime: {result}")
        return result
    except ValueError as e:
        logging.debug(f"Error parsing time: {str(e)}")
        return None
    