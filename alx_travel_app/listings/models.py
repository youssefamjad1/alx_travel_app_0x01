from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class Listing(models.Model):
    """
    Model representing a travel listing (hotel, apartment, etc.)
    """
    PROPERTY_TYPES = [
        ('hotel', 'Hotel'),
        ('apartment', 'Apartment'),
        ('house', 'House'),
        ('villa', 'Villa'),
        ('resort', 'Resort'),
        ('hostel', 'Hostel'),
        ('guesthouse', 'Guest House'),
    ]
    
    listing_id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique identifier for the listing"
    )
    
    host = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='listings',
        help_text="The user who created this listing"
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Name/title of the listing"
    )
    
    description = models.TextField(
        help_text="Detailed description of the listing"
    )
    
    location = models.CharField(
        max_length=200,
        help_text="Location of the listing (city, country)"
    )
    
    price_per_night = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Price per night in USD"
    )
    
    property_type = models.CharField(
        max_length=20,
        choices=PROPERTY_TYPES,
        default='apartment',
        help_text="Type of property"
    )
    
    max_guests = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of guests allowed"
    )
    
    bedrooms = models.PositiveIntegerField(
        default=1,
        help_text="Number of bedrooms"
    )
    
    bathrooms = models.PositiveIntegerField(
        default=1,
        help_text="Number of bathrooms"
    )
    
    amenities = models.TextField(
        blank=True,
        help_text="List of amenities (comma-separated)"
    )
    
    available = models.BooleanField(
        default=True,
        help_text="Whether the listing is available for booking"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the listing was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the listing was last updated"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['location']),
            models.Index(fields=['property_type']),
            models.Index(fields=['price_per_night']),
            models.Index(fields=['available']),
        ]

    def __str__(self):
        return f"{self.name} - {self.location}"
    
    @property
    def average_rating(self):
        """Calculate average rating from reviews"""
        reviews = self.reviews.all()
        if reviews:
            return sum(review.rating for review in reviews) / len(reviews)
        return 0
    
    @property
    def total_reviews(self):
        """Get total number of reviews"""
        return self.reviews.count()


class Booking(models.Model):
    """
    Model representing a booking for a listing
    """
    BOOKING_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    
    booking_id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique identifier for the booking"
    )
    
    listing = models.ForeignKey(
        Listing, 
        on_delete=models.CASCADE, 
        related_name='bookings',
        help_text="The listing being booked"
    )
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='bookings',
        help_text="The user making the booking"
    )
    
    check_in_date = models.DateField(
        help_text="Check-in date"
    )
    
    check_out_date = models.DateField(
        help_text="Check-out date"
    )
    
    number_of_guests = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Number of guests for this booking"
    )
    
    total_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Total price for the booking"
    )
    
    status = models.CharField(
        max_length=20,
        choices=BOOKING_STATUS,
        default='pending',
        help_text="Current status of the booking"
    )
    
    special_requests = models.TextField(
        blank=True,
        help_text="Any special requests from the guest"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the booking was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the booking was last updated"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['check_in_date']),
            models.Index(fields=['check_out_date']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(check_out_date__gt=models.F('check_in_date')),
                name='check_out_after_check_in'
            ),
        ]

    def __str__(self):
        return f"Booking {self.booking_id} - {self.listing.name}"
    
    def clean(self):
        """Custom validation"""
        from django.core.exceptions import ValidationError
        
        if self.check_out_date <= self.check_in_date:
            raise ValidationError("Check-out date must be after check-in date")
        
        if self.number_of_guests > self.listing.max_guests:
            raise ValidationError(
                f"Number of guests ({self.number_of_guests}) exceeds maximum allowed ({self.listing.max_guests})"
            )
    
    @property
    def duration_nights(self):
        """Calculate number of nights for the booking"""
        return (self.check_out_date - self.check_in_date).days
    
    def calculate_total_price(self):
        """Calculate total price based on listing price and duration"""
        return self.listing.price_per_night * self.duration_nights


class Review(models.Model):
    """
    Model representing a review for a listing
    """
    review_id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique identifier for the review"
    )
    
    listing = models.ForeignKey(
        Listing, 
        on_delete=models.CASCADE, 
        related_name='reviews',
        help_text="The listing being reviewed"
    )
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='reviews',
        help_text="The user writing the review"
    )
    
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='review',
        null=True,
        blank=True,
        help_text="The booking this review is associated with"
    )
    
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    
    comment = models.TextField(
        help_text="Written review comment"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the review was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the review was last updated"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['rating']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['listing', 'user'],
                name='unique_user_listing_review'
            ),
        ]

    def __str__(self):
        return f"Review by {self.user.username} for {self.listing.name} - {self.rating} stars"
    
    def clean(self):
        """Custom validation"""
        from django.core.exceptions import ValidationError
        
        # Check if user has a completed booking for this listing
        if self.booking and self.booking.status != 'completed':
            raise ValidationError("Can only review completed bookings")
        
        if self.booking and self.booking.listing != self.listing:
            raise ValidationError("Booking must be for the same listing being reviewed")