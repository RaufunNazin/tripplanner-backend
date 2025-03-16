# tripplanner/tripapi/serializers.py
from rest_framework import serializers
from .models import Driver, TripPlan, RestStop, ELDLog

class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = '__all__'

class RestStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestStop
        fields = '__all__'

class ELDLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ELDLog
        fields = '__all__'

class TripPlanSerializer(serializers.ModelSerializer):
    rest_stops = RestStopSerializer(many=True, read_only=True)
    eld_logs = ELDLogSerializer(many=True, read_only=True)
    
    class Meta:
        model = TripPlan
        fields = '__all__'
        
class TripInputSerializer(serializers.Serializer):
    current_location = serializers.CharField(max_length=200)
    current_location_coordinates = serializers.JSONField(required=False)
    pickup_location = serializers.CharField(max_length=200)
    pickup_location_coordinates = serializers.JSONField(required=False)
    dropoff_location = serializers.CharField(max_length=200)
    dropoff_location_coordinates = serializers.JSONField(required=False)
    current_cycle_used = serializers.FloatField()
    driver_id = serializers.IntegerField(required=False)
