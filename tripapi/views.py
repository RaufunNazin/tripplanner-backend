from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.http import HttpResponse
from .models import Driver, TripPlan, RestStop, ELDLog
from .serializers import DriverSerializer, TripPlanSerializer, RestStopSerializer, ELDLogSerializer, TripInputSerializer
from .services import TripPlannerService
import json
from datetime import datetime

class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer

class TripPlanViewSet(viewsets.ModelViewSet):
    queryset = TripPlan.objects.all()
    serializer_class = TripPlanSerializer

@api_view(['POST'])
def plan_trip(request):
    """
    Create a trip plan with rest stops and ELD logs
    """
    serializer = TripInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # Get validated data
    data = serializer.validated_data
    current_location = data['current_location']
    pickup_location = data['pickup_location']
    dropoff_location = data['dropoff_location']
    current_cycle_used = data['current_cycle_used']
    
    # Get driver (create default if not provided)
    driver_id = data.get('driver_id')
    if driver_id:
        try:
            driver = Driver.objects.get(id=driver_id)
        except Driver.DoesNotExist:
            return Response({"error": "Driver not found"}, status=status.HTTP_404_NOT_FOUND)
    else:
        # Create a default driver if not specified
        driver, created = Driver.objects.get_or_create(
            name="Default Driver",
            defaults={
                'license_number': 'DEFAULT123',
                'carrier_name': 'Default Carrier',
                'home_terminal': 'Default Terminal'
            }
        )
    
    try:
        # Initialize trip planner service
        trip_planner = TripPlannerService()
        
        # Calculate route
        route_result = trip_planner.calculate_route(
            current_location, 
            pickup_location, 
            dropoff_location
        )
        
        # Plan rest stops
        rest_stops_result = trip_planner.plan_rest_stops(
            route_result,
            current_cycle_used,
            current_location_coordinates=trip_planner._get_coordinates(current_location),
            pickup_location_coordinates=trip_planner._get_coordinates(pickup_location),
            dropoff_location_coordinates=trip_planner._get_coordinates(dropoff_location),
        )
        
        # Generate ELD logs
        eld_logs_result = trip_planner.generate_eld_logs(
            route_result,
            rest_stops_result,
            current_cycle_used
        )
        
        drawing_data, image_path = trip_planner.generate_and_draw_eld_logs(eld_logs_result)
        
        # Create trip plan object
        trip_plan = TripPlan.objects.create(
            driver=driver,
            current_location=current_location,
            current_location_coordinates=trip_planner._get_coordinates(current_location),
            pickup_location=pickup_location,
            pickup_location_coordinates=trip_planner._get_coordinates(pickup_location),
            dropoff_location=dropoff_location,
            dropoff_location_coordinates=trip_planner._get_coordinates(dropoff_location),
            current_cycle_used=current_cycle_used,
            route_data=route_result['route_data'],
            estimated_miles=route_result['distance_miles'],
            estimated_duration=route_result['duration_hours']
        )
        
        # Create rest stops
        for stop_data in rest_stops_result['rest_stops']:
            RestStop.objects.create(
                trip=trip_plan,
                location=stop_data['location'],
                arrival_time=stop_data['arrival_time'],
                departure_time=stop_data['departure_time'],
                rest_duration=stop_data['rest_duration'],
                is_fuel_stop=stop_data['is_fuel_stop']
            )
        
        # Create ELD logs
        for log_data in eld_logs_result:
            # Generate drawing data for this log
            
            ELDLog.objects.create(
                trip=trip_plan,
                date=log_data['date'],
                log_data={
                    'entries': log_data['log_entries'],
                },
                total_off_duty_hours=log_data['total_off_duty_hours'],
                total_sleeper_hours=log_data['total_sleeper_hours'],
                total_driving_hours=log_data['total_driving_hours'],
                total_on_duty_hours=log_data['total_on_duty_hours'],
                total_hours=log_data['total_hours'],
                total_miles_driven=log_data['total_miles']
            )
        
        # Return complete trip plan with rest stops and ELD logs
        response_data = TripPlanSerializer(trip_plan).data
        
        return Response({"trip_plan": response_data, "drawing_data": drawing_data, "image_path": image_path}, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# @api_view(['GET'])
# def generate_eld_log_image(request, log_id):
#     """
#     Generate an ELD log image for a specific log
#     """
#     try:
#         eld_log = ELDLog.objects.get(id=log_id)
        
#         # In a real implementation, you'd generate an image here
#         # For now, we'll just return the drawing data
#         return Response(eld_log.log_data)
    
#     except ELDLog.DoesNotExist:
#         return Response(
#             {"error": "ELD log not found"},
#             status=status.HTTP_404_NOT_FOUND
#         )