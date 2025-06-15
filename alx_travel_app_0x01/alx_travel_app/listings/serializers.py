from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Listing, Booking, Review


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']
        read_only_fields = ['id']


class ListingSerializer(serializers.ModelSerializer):
    """
    Serializer for Listing model
    """
    host = UserSerializer(read_only=True)
    host_id = serializers.IntegerField(write_only=True, required=False)
    average_rating = serializers.ReadOnlyField()
    total_reviews = serializers.ReadOnlyField()
    amenities_list = serializers.SerializerMethodField()
    
    class Meta:
        model = Listing
        fields = [
            'listing_id',
            'host',
            'host_id',
            'name',
            'description',
            'location',
            'price_per_night',
            'property_type',
            'max_guests',
            'bedrooms',
            'bathrooms',
            'amenities',
            'amenities_list',
            'available',
            'average_rating',
            'total_reviews',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['listing_id', 'created_at', 'updated_at']
    
    def get_amenities_list(self, obj):
        """Convert amenities string to list"""
        if obj.amenities:
            return [amenity.strip() for amenity in obj.amenities.split(',')]
        return []
    
    def create(self, validated_data):
        """Create a new listing"""
        # If host_id is provided, use it; otherwise use the current user
        if 'host_id' in validated_data:
            host_id = validated_data.pop('host_id')
            validated_data['host'] = User.objects.get(id=host_id)
        else:
            # Assume the current user from the request context
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                validated_data['host'] = request.user
        
        return super().create(validated_data)
    
    def validate_price_per_night(self, value):
        """Validate price is positive"""
        if value <= 0:
            raise serializers.ValidationError("Price per night must be positive")
        return value
    
    def validate_max_guests(self, value):
        """Validate max guests is reasonable"""
        if value <= 0:
            raise serializers.ValidationError("Max guests must be at least 1")
        if value > 20:
            raise serializers.ValidationError("Max guests cannot exceed 20")
        return value


class BookingSerializer(serializers.ModelSerializer):
    """
    Serializer for Booking model
    """
    listing = ListingSerializer(read_only=True)
    listing_id = serializers.UUIDField(write_only=True)
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    duration_nights = serializers.ReadOnlyField()
    
    class Meta:
        model = Booking
        fields = [
            'booking_id',
            'listing',
            'listing_id',
            'user',
            'user_id',
            'check_in_date',
            'check_out_date',
            'number_of_guests',
            'total_price',
            'status',
            'special_requests',
            'duration_nights',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['booking_id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Custom validation for booking dates and availability"""
        check_in = data.get('check_in_date')
        check_out = data.get('check_out_date')
        listing_id = data.get('listing_id')
        number_of_guests = data.get('number_of_guests', 1)
        
        # Validate dates
        if check_out and check_in and check_out <= check_in:
            raise serializers.ValidationError("Check-out date must be after check-in date")
        
        # Validate listing exists and is available
        if listing_id:
            try:
                listing = Listing.objects.get(listing_id=listing_id)
                if not listing.available:
                    raise serializers.ValidationError("This listing is not available for booking")
            except Listing.DoesNotExist:
                raise serializers.ValidationError("Invalid listing ID")
            
            # Validate number of guests
            if number_of_guests > listing.max_guests:
                raise serializers.ValidationError(
                    f"Number of guests ({number_of_guests}) exceeds maximum allowed ({listing.max_guests})"
                )
            
            # Check for conflicting bookings
            if check_in and check_out:
                conflicting_bookings = Booking.objects.filter(
                    listing=listing,
                    status__in=['confirmed', 'pending'],
                    check_in_date__lt=check_out,
                    check_out_date__gt=check_in
                )
                
                # Exclude current booking if updating
                if self.instance:
                    conflicting_bookings = conflicting_bookings.exclude(booking_id=self.instance.booking_id)
                
                if conflicting_bookings.exists():
                    raise serializers.ValidationError("These dates are not available")
        
        return data
    
    def create(self, validated_data):
        """Create a new booking with calculated total price"""
        listing_id = validated_data.pop('listing_id')
        listing = Listing.objects.get(listing_id=listing_id)
        validated_data['listing'] = listing
        
        # Set user if not provided
        if 'user_id' in validated_data:
            user_id = validated_data.pop('user_id')
            validated_data['user'] = User.objects.get(id=user_id)
        else:
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                validated_data['user'] = request.user
        
        # Calculate total price
        check_in = validated_data['check_in_date']
        check_out = validated_data['check_out_date']
        nights = (check_out - check_in).days
        validated_data['total_price'] = listing.price_per_night * nights
        
        return super().create(validated_data)


class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for Review model
    """
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    listing = ListingSerializer(read_only=True)
    listing_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Review
        fields = [
            'review_id',
            'listing',
            'listing_id',
            'user',
            'user_id',
            'rating',
            'comment',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['review_id', 'created_at', 'updated_at']
    
    def validate_rating(self, value):
        """Validate rating is between 1 and 5"""
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
    
    def create(self, validated_data):
        """Create a new review"""
        listing_id = validated_data.pop('listing_id')
        listing = Listing.objects.get(listing_id=listing_id)
        validated_data['listing'] = listing
        
        # Set user if not provided
        if 'user_id' in validated_data:
            user_id = validated_data.pop('user_id')
            validated_data['user'] = User.objects.get(id=user_id)
        else:
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                validated_data['user'] = request.user
        
        return super().create(validated_data)