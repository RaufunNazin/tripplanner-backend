from django.db import models

class Driver(models.Model):
    name = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50)
    carrier_name = models.CharField(max_length=100)
    home_terminal = models.CharField(max_length=200)
    
    def __str__(self):
        return self.name

class TripPlan(models.Model):
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='trips')
    current_location = models.CharField(max_length=200)
    current_location_coordinates = models.JSONField(null=True, blank=True)
    pickup_location = models.CharField(max_length=200)
    pickup_location_coordinates = models.JSONField(null=True, blank=True)
    dropoff_location = models.CharField(max_length=200)
    dropoff_location_coordinates = models.JSONField(null=True, blank=True)
    current_cycle_used = models.FloatField(help_text="Hours already used in the current cycle")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Route details stored as JSON
    route_data = models.JSONField(null=True, blank=True)
    estimated_miles = models.FloatField(null=True, blank=True)
    estimated_duration = models.FloatField(null=True, blank=True)  # In hours
    
    def __str__(self):
        return f"Trip from {self.pickup_location} to {self.dropoff_location}"

class RestStop(models.Model):
    trip = models.ForeignKey(TripPlan, on_delete=models.CASCADE, related_name='rest_stops')
    location = models.CharField(max_length=200)
    arrival_time = models.DateTimeField()
    departure_time = models.DateTimeField()
    rest_duration = models.FloatField(help_text="Duration of rest in hours")
    is_fuel_stop = models.BooleanField(default=False)
    
    def __str__(self):
        stop_type = "Fuel & Rest" if self.is_fuel_stop else "Rest"
        return f"{stop_type} stop at {self.location}"

class ELDLog(models.Model):
    trip = models.ForeignKey(TripPlan, on_delete=models.CASCADE, related_name='eld_logs')
    date = models.DateField()
    log_data = models.JSONField(help_text="JSON representation of the ELD log entries")
    total_off_duty_hours = models.FloatField(default=0.0)
    total_sleeper_hours = models.FloatField(default=0.0)
    total_driving_hours = models.FloatField(default=0.0)
    total_on_duty_hours = models.FloatField(default=0.0)
    total_hours = models.FloatField(default=0.0)
    total_miles_driven = models.FloatField(default=0.0)
    
    def __str__(self):
        return f"ELD Log for {self.trip} on {self.date}"
    

class Location(models.Model):
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to="eld/")