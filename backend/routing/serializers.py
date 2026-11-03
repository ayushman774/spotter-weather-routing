
from rest_framework import serializers


class RoutePlanSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)
    departure_time = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField(min_value=0)
    checkpoint_interval_miles = serializers.ChoiceField(
        choices=[10, 25, 50],
        default=25,
    )

    def validate(self, attrs):
        if attrs["departure_time"].utcoffset() is None:
            raise serializers.ValidationError(
                "Departure time must include a timezone."
            )

        if attrs["origin"].strip().lower() == (
            attrs["destination"].strip().lower()
        ):
            raise serializers.ValidationError(
                "Origin and destination must be different."
            )

        return attrs
