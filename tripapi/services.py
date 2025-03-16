import requests
import json
from datetime import datetime, timedelta
import math
import os
import matplotlib.pyplot as plt
import cv2
import matplotlib
from django.conf import settings

matplotlib.use('Agg')

class TripPlannerService:
    def __init__(self):
        # Constants for compliance with regulations
        self.MAX_DAILY_DRIVING = 11  # Max driving hours per day
        self.MAX_DAILY_DUTY = 14     # Max on-duty hours per day
        self.MIN_REST_PERIOD = 10    # Min consecutive rest hours per day
        self.MAX_CYCLE_HOURS = 70    # Max duty hours in 8-day cycle
        self.FUEL_DISTANCE = 1000    # Miles between fuel stops
        self.PICKUP_DROPOFF_TIME = 1  # Hour for pickup/dropoff
        self.AVG_SPEED = 55          # Average speed in miles/hour
        
        # OpenRouteService API key and endpoint
        self.ORS_API_KEY = '5b3ce3597851110001cf6248de17e0ce4e6a47d980377adb0d23441b'
        self.ORS_ENDPOINT = 'https://api.openrouteservice.org/v2/directions/driving-hgv'
    
    def _get_coordinates(self, location):
        """Convert address to coordinates using OpenRouteService geocoding API"""
        geocode_url = 'https://api.openrouteservice.org/geocode/search'
        response = requests.get(
            geocode_url,
            params={
                'api_key': self.ORS_API_KEY,
                'text': location,
                'size': 1
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to geocode address: {response.text}")
        
        result = response.json()
        if 'features' in result and len(result['features']) > 0:
            coordinates = result['features'][0]['geometry']['coordinates']
            return coordinates
        else:
            raise Exception(f"No coordinates found for location: {location}")
    
    def calculate_route(self, current_location, pickup_location, dropoff_location):
        """Calculate route using OpenRouteService API"""
        # Get coordinates for locations
        current_coords = self._get_coordinates(current_location)
        pickup_coords = self._get_coordinates(pickup_location)
        dropoff_coords = self._get_coordinates(dropoff_location)
        
        # Build coordinates list for the API request
        # First leg: Current to Pickup
        # Second leg: Pickup to Dropoff
        coordinates = [current_coords, pickup_coords, dropoff_coords]
        
        # Make API request to get the route
        payload = {
            "coordinates": coordinates,
            "instructions": True,         # Include turn-by-turn directions
            "instructions_format": "text",
            "preference": "recommended",  # Recommended route
            "geometry": True,             # Include geometry in response
            "elevation": False,           # No elevation data
            "units": "m"                  # Meters
        }

        headers = {
            "Authorization": self.ORS_API_KEY,  # API Key in Authorization Header
            "Content-Type": "application/json"
        }

        response = requests.post(self.ORS_ENDPOINT, json=payload, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Failed to calculate route: {response.text}")
        
        route_data = response.json()
        
        # Extract distance and duration from the route data
        total_distance_meters = 0
        total_duration_seconds = 0
        
        for route in route_data.get('routes', []):
            total_distance_meters += route.get('summary', {}).get('distance', 0)
            total_duration_seconds += route.get('summary', {}).get('duration', 0)

        # Convert to miles and hours
        total_distance_miles = total_distance_meters / 1609.34
        total_duration_hours = total_duration_seconds / 3600
        
        # Add time for pickup and dropoff
        total_duration_hours += (2 * self.PICKUP_DROPOFF_TIME)  # 1 hour each for pickup and dropoff
        
        return {
            'route_data': route_data,
            'distance_miles': total_distance_miles,
            'duration_hours': total_duration_hours
        }
        
    def get_stop_coordinates(self, query, lon=None, lat=None):
        """
        Get coordinates of a fuel stop or rest stop using ORS API.
        - query: "fuel stop" or "rest stop"
        - lon, lat: Optional coordinates for better accuracy
        """
        url = f"https://api.openrouteservice.org/geocode/search"
        params = {
            "api_key": self.ORS_API_KEY,
            "text": query,
            "boundary.country": "USA",
            "size": 1  # Get the top result
        }
        if lon and lat:
            params["focus.point.lon"] = lon
            params["focus.point.lat"] = lat  # Improve accuracy
        
        response = requests.get(url, params=params)
        data = response.json()

        if data.get("features"):
            location = data["features"][0]["geometry"]["coordinates"]
            return {"longitude": location[0], "latitude": location[1]}
        return None
    
    def plan_rest_stops(self, route_data, current_cycle_used, current_location_coordinates, pickup_location_coordinates, dropoff_location_coordinates):
        """Plan rest stops based on route data and HOS regulations"""
        
        total_miles = route_data['distance_miles']
        
        # Initialize planning variables
        remaining_daily_driving = self.MAX_DAILY_DRIVING
        remaining_daily_duty = self.MAX_DAILY_DUTY
        remaining_cycle_hours = self.MAX_CYCLE_HOURS - current_cycle_used
        miles_since_last_fuel = 0
        
        # Calculate initial departure time
        start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
        current_time = start_time
        
        # List to store rest stops
        rest_stops = []
        
        # Track journey status
        miles_traveled = 0
        hours_driven = 0

        # Split journey into segments
        while miles_traveled < total_miles:
            # Calculate how many miles can be driven before HOS limits
            drivable_hours = min(remaining_daily_driving, remaining_daily_duty, remaining_cycle_hours)
            drivable_miles = drivable_hours * self.AVG_SPEED
            
            # Dynamically calculate stop coordinates based on progress
            current_lon = (
                pickup_location_coordinates[0] +
                ((dropoff_location_coordinates[0] - pickup_location_coordinates[0]) * (miles_traveled / total_miles))
            )
            current_lat = (
                pickup_location_coordinates[1] +
                ((dropoff_location_coordinates[1] - pickup_location_coordinates[1]) * (miles_traveled / total_miles))
            )

            # Check if we need a fuel stop
            if miles_since_last_fuel + drivable_miles > self.FUEL_DISTANCE:
                # Calculate where the fuel stop will be
                miles_to_fuel = self.FUEL_DISTANCE - miles_since_last_fuel
                hours_to_fuel = miles_to_fuel / self.AVG_SPEED
                
                # Update trackers
                miles_traveled += miles_to_fuel
                hours_driven += hours_to_fuel
                miles_since_last_fuel = 0
                
                remaining_daily_driving -= hours_to_fuel
                remaining_daily_duty -= hours_to_fuel
                remaining_cycle_hours -= hours_to_fuel
                
                # Add a short rest/fuel stop (30 min)
                fuel_stop_arrival = current_time + timedelta(hours=hours_to_fuel)
                fuel_stop_departure = fuel_stop_arrival + timedelta(minutes=30)

                # Get actual fuel stop location
                fuel_stop_coords = self.get_stop_coordinates("gas station", lon=current_lon, lat=current_lat)
                fuel_stop_location = fuel_stop_coords if fuel_stop_coords else "Unknown fuel stop"
                
                rest_stops.append({
                    'location': fuel_stop_location,
                    'arrival_time': fuel_stop_arrival,
                    'departure_time': fuel_stop_departure,
                    'rest_duration': 0.5,  # 30 minutes
                    'is_fuel_stop': True
                })
                
                # Update current time
                current_time = fuel_stop_departure
                
                # Subtract rest time from daily duty
                remaining_daily_duty -= 0.5
            
            else:
                # Check if we can complete the remainder of the journey
                remaining_miles = total_miles - miles_traveled
                hours_needed = remaining_miles / self.AVG_SPEED
                
                if hours_needed <= drivable_hours:
                    # We can complete the journey without another rest
                    miles_traveled = total_miles
                    hours_driven += hours_needed
                    current_time += timedelta(hours=hours_needed)
                else:
                    # Drive as far as allowed by HOS, then take required rest
                    miles_traveled += drivable_miles
                    hours_driven += drivable_hours
                    miles_since_last_fuel += drivable_miles
                    
                    # Update time
                    current_time += timedelta(hours=drivable_hours)
                    
                    # Calculate rest duration
                    rest_hours = self.MIN_REST_PERIOD
                    
                    # Add rest stop
                    rest_stop_arrival = current_time
                    rest_stop_departure = rest_stop_arrival + timedelta(hours=rest_hours)

                    # Get actual rest stop location
                    rest_stop_coords = self.get_stop_coordinates("coffee shop", lon=current_lon, lat=current_lat)
                    rest_stop_location = rest_stop_coords if rest_stop_coords else "Unknown rest stop"
                    
                    rest_stops.append({
                        'location': rest_stop_location,
                        'arrival_time': rest_stop_arrival,
                        'departure_time': rest_stop_departure,
                        'rest_duration': rest_hours,
                        'is_fuel_stop': False
                    })
                    
                    # Reset daily limits after rest
                    remaining_daily_driving = self.MAX_DAILY_DRIVING
                    remaining_daily_duty = self.MAX_DAILY_DUTY
                    
                    # Update current time
                    current_time = rest_stop_departure
        
        # Return journey stats and rest stops
        return {
            'total_miles': total_miles,
            'total_driving_hours': hours_driven,
            'departure_time': start_time,
            'estimated_arrival': current_time,
            'rest_stops': rest_stops
        }
    
    def generate_eld_logs(self, trip_plan_data, rest_stops_data, current_cycle_used):
        """
        Generate structured ELD logs ensuring each day totals 24 hours.
        Includes on-duty, off-duty, driving, and rest periods while enforcing compliance.
        """
        print(rest_stops_data)
        departure_time = rest_stops_data['departure_time']
        rest_stops = rest_stops_data['rest_stops']
        total_miles_remaining = rest_stops_data['total_miles']
        total_cycle_hours_used = current_cycle_used

        current_day = departure_time.date()
        eld_logs = []

        while total_miles_remaining > 0 and total_cycle_hours_used < self.MAX_CYCLE_HOURS:
            day_log = {
                'date': current_day,
                'log_entries': [],
                'total_off_duty_hours': 0.0,
                'total_sleeper_hours': 0.0,
                'total_driving_hours': 0.0,
                'total_on_duty_hours': 0.0,
                'total_hours': 0.0,
                'total_miles': 0.0
            }

            # Set start and end times for the current day
            day_start = max(departure_time, datetime.combine(current_day, datetime.min.time()))
            day_end = datetime.combine(current_day, datetime.min.time()) + timedelta(hours=24)
            max_drive_until = datetime.combine(current_day, datetime.min.time()) + timedelta(hours=22)
            current_time = day_start

            # Ensure the driver starts at 6 AM if it's a fresh day
            if current_time.hour == 0:
                current_time += timedelta(hours=6)
                day_log['log_entries'].append({
                    'status': 'off_duty',
                    'start_hour': 0.0,
                    'end_hour': 6.0
                })
                day_log['total_off_duty_hours'] += 6.0

            elif current_time.hour > 0:
                day_log['log_entries'].append({
                    'status': 'off_duty',
                    'start_hour': 0.0,
                    'end_hour': current_time.hour + current_time.minute / 60.0
                })
                day_log['total_off_duty_hours'] += current_time.hour + current_time.minute / 60.0

            # Start with pre-trip inspection (30 min)
            inspection_end_time = current_time + timedelta(minutes=30)
            if inspection_end_time >= day_end:  # Avoid going beyond 24 hours
                inspection_end_time = day_end

            day_log['log_entries'].append({
                'status': 'on_duty',
                'start_hour': current_time.hour + current_time.minute / 60.0,
                'end_hour': inspection_end_time.hour + inspection_end_time.minute / 60.0
            })
            day_log['total_on_duty_hours'] += 0.5
            current_time = inspection_end_time

            # Determine available driving time based on HOS rules
            available_driving_hours = min(11, 70 - total_cycle_hours_used)
            max_possible_drive_hours = total_miles_remaining / 55

            # Stop driving if past 22.0 hours
            if current_time >= max_drive_until:
                driving_hours_today = 0
            else:
                driving_end_time = min(current_time + timedelta(hours=min(available_driving_hours, max_possible_drive_hours)), max_drive_until)
                driving_hours_today = (driving_end_time - current_time).total_seconds() / 3600

            if driving_hours_today > 0:
                day_log['log_entries'].append({
                    'status': 'driving',
                    'start_hour': current_time.hour + current_time.minute / 60.0,
                    'end_hour': driving_end_time.hour + driving_end_time.minute / 60.0
                })
                day_log['total_driving_hours'] += driving_hours_today
                total_miles_remaining -= (driving_hours_today * 55)
                current_time = driving_end_time

            # Process rest stops
            # day_rest_stops = [stop for stop in rest_stops if stop['arrival_time'].date() == current_day]
            # for stop in day_rest_stops:
            #     if current_time < stop['arrival_time']:
            #         # Add driving until the rest stop if applicable
            #         day_log['log_entries'].append({
            #             'status': 'driving',
            #             'start_hour': current_time.hour + current_time.minute / 60.0,
            #             'end_hour': stop['arrival_time'].hour + stop['arrival_time'].minute / 60.0
            #         })
            #         day_log['total_driving_hours'] += (stop['arrival_time'] - current_time).total_seconds() / 3600
            #         current_time = stop['arrival_time']

            #     # Add rest stop
            #     day_log['log_entries'].append({
            #         'status': 'off_duty' if not stop['is_fuel_stop'] else 'on_duty',
            #         'start_hour': stop['arrival_time'].hour + stop['arrival_time'].minute / 60.0,
            #         'end_hour': stop['departure_time'].hour + stop['departure_time'].minute / 60.0
            #     })

            #     if stop['is_fuel_stop']:
            #         day_log['total_on_duty_hours'] += 0.5
            #     else:
            #         day_log['total_off_duty_hours'] += stop['rest_duration']

            #     current_time = stop['departure_time']

            # Ensure no off-duty period starts before the last activity ends
            last_end_hour = max(entry["end_hour"] for entry in day_log["log_entries"])

            # If there is remaining time, add off-duty or sleeper
            if last_end_hour < 24.0:
                day_log['log_entries'].append({
                    'status': 'sleeper',
                    'start_hour': last_end_hour,
                    'end_hour': 24.0
                })
                day_log['total_sleeper_hours'] += (24.0 - last_end_hour)

            # Compute total miles driven
            day_log['total_miles'] = day_log['total_driving_hours'] * self.AVG_SPEED

            # Calculate total hours for the day (must be exactly 24)
            day_log['total_hours'] = (
                day_log['total_off_duty_hours'] +
                day_log['total_sleeper_hours'] +
                day_log['total_driving_hours'] +
                day_log['total_on_duty_hours']
            )

            if round(day_log['total_hours'], 2) != 24.0:
                print(f"Warning: Total hours for {current_day} is {day_log['total_hours']}, should be 24.")

            eld_logs.append(day_log)
            total_cycle_hours_used += (day_log['total_driving_hours'] + day_log['total_on_duty_hours'])
            current_day += timedelta(days=1)

        return eld_logs


    def _add_driving_entry(self, day_log, start_time, end_time):
        """ Helper to add driving entries ensuring compliance with daily limits """
        start_hour = start_time.hour + start_time.minute / 60.0
        end_hour = end_time.hour + end_time.minute / 60.0

        driving_hours = end_hour - start_hour

        # Ensure driving does not go past 24.0 (end of day)
        if end_hour > 24.0:
            driving_hours = 24.0 - start_hour
            end_hour = 24.0

        # Ensure driving does not start after 22.0
        if start_hour >= 22.0:
            return  # No driving allowed past 22.0

        # Ensure driving does not exceed max daily limit
        if day_log['total_driving_hours'] + driving_hours > self.MAX_DAILY_DRIVING:
            driving_hours = self.MAX_DAILY_DRIVING - day_log['total_driving_hours']
            end_hour = start_hour + driving_hours

        # Ensure valid driving hours
        if driving_hours > 0:
            day_log['log_entries'].append({
                'status': 'driving',
                'start_hour': start_hour,
                'end_hour': end_hour
            })
            day_log['total_driving_hours'] += driving_hours
            day_log['total_on_duty_hours'] += driving_hours


    def _add_rest_entry(self, day_log, stop):
        """ Helper to add rest entries correctly handling fuel stops and sleep breaks """
        rest_start_hour = stop['arrival_time'].hour + stop['arrival_time'].minute / 60.0
        rest_end_hour = stop['departure_time'].hour + stop['departure_time'].minute / 60.0

        # Ensure rest period does not exceed 24.0 (end of day)
        if rest_end_hour > 24.0:
            rest_end_hour = 24.0

        # Ensure valid rest times
        if rest_start_hour >= rest_end_hour:
            return  # Skip invalid entries

        if stop['is_fuel_stop']:
            # Fuel stops are on-duty for 30 min, then off-duty if time allows
            fuel_end = min(rest_start_hour + 0.5, rest_end_hour)
            day_log['log_entries'].append({
                'status': 'on_duty',
                'start_hour': rest_start_hour,
                'end_hour': fuel_end
            })
            day_log['total_on_duty_hours'] += fuel_end - rest_start_hour

            # If there's remaining time, switch to off-duty
            if fuel_end < rest_end_hour:
                day_log['log_entries'].append({
                    'status': 'off_duty',
                    'start_hour': fuel_end,
                    'end_hour': rest_end_hour
                })
                day_log['total_off_duty_hours'] += rest_end_hour - fuel_end
        else:
            # Regular rest stops
            day_log['log_entries'].append({
                'status': 'off_duty',
                'start_hour': rest_start_hour,
                'end_hour': rest_end_hour
            })
            
            rest_duration = rest_end_hour - rest_start_hour
            if stop.get('is_sleeper_berth', False):
                day_log['total_sleeper_hours'] += rest_duration
            else:
                day_log['total_off_duty_hours'] += rest_duration

            
    def generate_eld_drawing_data(self, eld_logs):
        """
        Convert ELD logs into a structured format for drawing logs on a PNG.
        """
        formatted_logs = []
        
        for log in eld_logs:
            day_data = []
            for entry in log['log_entries']:
                day_data.append((entry['start_hour'], entry['status']))
                day_data.append((entry['end_hour'], entry['status']))
            formatted_logs.append({'date': log['date'], 'entries': day_data})
        
        return formatted_logs
    
    def generate_image_url(self, image_filename):
        """Generate a media URL for the image."""
        return f"{settings.MEDIA_URL}{image_filename}"
    
    def draw_eld_lines(self, hours):
        # Define media directory
        media_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
        if not os.path.exists(media_dir):
            os.makedirs(media_dir)
        # Load the image
        image_path = os.path.abspath("blank-paper-log.png")
        img = cv2.imread(image_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Define the log graph area coordinates
        height, width, _ = img.shape
        graph_top = int(height * 0.376)
        graph_bottom = int(height * 0.47)
        graph_left = int(width * 0.1265)
        graph_right = int(width * 0.885)
        hour_step = (graph_right - graph_left) / 24
        
        # Define duty status levels (approximate pixel positions)
        status_levels = {
            'off_duty': graph_top,
            'sleeper': graph_top + (graph_bottom - graph_top) * 0.35,
            'driving': graph_top + (graph_bottom - graph_top) * 0.645,
            'on_duty': graph_bottom
        }
        
        # Create a figure
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.imshow(img)
        
        # Draw ELD lines
        prev_x, prev_y = None, None
        prev_hour = None
        total_hours = {"off_duty": 0, "sleeper": 0, "driving": 0, "on_duty": 0}
        for i, (hour, status) in enumerate(hours):
            x = graph_left + hour * hour_step
            y = status_levels[status]
            
            if prev_x is not None and prev_y is not None:
                ax.scatter([x, x], [prev_y, y], color='red', s=10, zorder=2)
                ax.scatter(prev_x, prev_y, color='red', s=10, zorder=2)
                ax.scatter(x, y, color='red', s=10, zorder=2)
                ax.plot([x, x], [prev_y, y], color='black', linewidth=1, zorder=1)
                ax.plot([prev_x, x], [prev_y, prev_y], color='black', linewidth=1, zorder=1)
                
                # Correctly calculate the duration for each status
            if prev_hour is not None:
                duration = hour - prev_hour
                total_hours[status] += duration
            
            prev_x, prev_y = x, y
            prev_hour = hour
        
        # Ensure the last point extends to the end
        last_x = graph_right
        ax.plot([prev_x, last_x], [prev_y, prev_y], color='black', linewidth=1, zorder=1)
        ax.scatter(last_x, prev_y, color='red', s=10, zorder=2)
        
        # Display total hours beside the logs
        for status, hours in total_hours.items():
            y_pos = status_levels[status] + 5
            ax.text(graph_right + 20, y_pos, f"{hours:.2f}", fontsize=6, color='black', ha='center')
            
        # Calculate total on-duty and driving time
        total_on_duty = total_hours["on_duty"] + total_hours["driving"]
        
        # Draw red circle around total on-duty and driving time
        circle_x = graph_right - 50
        circle_y = graph_bottom + 60
        circle_radius = 30
        ax.add_patch(plt.Circle((circle_x, circle_y), circle_radius, color='red', fill=False, linewidth=2))
        ax.text(circle_x, circle_y, f"{total_on_duty:.2f}", fontsize=10, color='black', weight='bold', ha='center', va='center')
        
        # Generate filename & save the image in MEDIA_ROOT
        image_filename = f"eld_log_{datetime.now().strftime('%Y%m%d%H%M%S')}{i}.png"
        output_path = os.path.join(settings.MEDIA_ROOT, image_filename)

        # Ensure matplotlib doesn't show GUI
        plt.axis('off')
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close(fig)

        print(f"✅ ELD log saved at: {output_path}")

        return f"{settings.MEDIA_URL}{image_filename}"
        
    def generate_and_draw_eld_logs(self, eld_logs):
        """
        Process daily logs, convert them into drawing format, and plot.
        Generate a separate PNG file for each day's ELD log.
        """
        drawing_data = self.generate_eld_drawing_data(eld_logs)
        image_paths = []

        for log in drawing_data:
            date_str = log['date'].strftime('%Y-%m-%d')  # Ensure date format is correct
            print(f"Drawing log for date: {date_str}")

            # Save a separate image for each day's ELD log
            image_path = self.draw_eld_lines(log['entries'])  
            image_paths.append(image_path)  # Append each day's image path separately

        print(f"✅ Total images saved: {len(image_paths)}")
        return drawing_data, image_paths