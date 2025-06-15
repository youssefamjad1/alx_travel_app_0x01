from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db.models import Q
from .models import Listing, Booking, Review
from .serializers import ListingSerializer, BookingSerializer, ReviewSerializer


class ListingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing travel listings.
    Provides CRUD operations for listings with additional filtering capabilities.
    """
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer
    lookup_field = 'listing_id'

    def get_queryset(self):
        """
        Optionally restricts the returned listings by filtering against
        query parameters in the URL.
        """
        queryset = Listing.objects.all()
        
        # Filter by location
        location = self.request.query_params.get('location', None)
        if location is not None:
            queryset = queryset.filter(location__icontains=location)
        
        # Filter by property type
        property_type = self.request.query_params.get('property_type', None)
        if property_type is not None:
            queryset = queryset.filter(property_type=property_type)
        
        # Filter by availability
        available = self.request.query_params.get('available', None)
        if available is not None:
            available_bool = available.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(available=available_bool)
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price', None)
        if min_price is not None:
            try:
                queryset = queryset.filter(price_per_night__gte=float(min_price))
            except ValueError:
                pass
        
        max_price = self.request.query_params.get('max_price', None)
        if max_price is not None:
            try:
                queryset = queryset.filter(price_per_night__lte=float(max_price))
            except ValueError:
                pass
        
        # Filter by number of guests
        guests = self.request.query_params.get('guests', None)
        if guests is not None:
            try:
                queryset = queryset.filter(max_guests__gte=int(guests))
            except ValueError:
                pass
        
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Set the host to the current user when creating a listing"""
        if self.request.user.is_authenticated:
            serializer.save(host=self.request.user)
        else:
            serializer.save()

    @swagger_auto_schema(
        method='get',
        manual_parameters=[
            openapi.Parameter('location', openapi.IN_QUERY, description="Filter by location", type=openapi.TYPE_STRING),
            openapi.Parameter('property_type', openapi.IN_QUERY, description="Filter by property type", type=openapi.TYPE_STRING),
            openapi.Parameter('available', openapi.IN_QUERY, description="Filter by availability", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('min_price', openapi.IN_QUERY, description="Minimum price per night", type=openapi.TYPE_NUMBER),
            openapi.Parameter('max_price', openapi.IN_QUERY, description="Maximum price per night", type=openapi.TYPE_NUMBER),
            openapi.Parameter('guests', openapi.IN_QUERY, description="Minimum number of guests", type=openapi.TYPE_INTEGER),
        ],
        responses={200: ListingSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Advanced search endpoint for listings with multiple filters
        """
        queryset = self.get_queryset()
        
        # Search in name and description
        search_query = request.query_params.get('search', None)
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(amenities__icontains=search_query)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        responses={200: ReviewSerializer(many=True)}
    )
    @action(detail=True, methods=['get'])
    def reviews(self, request, listing_id=None):
        """
        Get all reviews for a specific listing
        """
        listing = self.get_object()
        reviews = listing.reviews.all().order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        responses={200: BookingSerializer(many=True)}
    )
    @action(detail=True, methods=['get'])
    def bookings(self, request, listing_id=None):
        """
        Get all bookings for a specific listing (for hosts)
        """
        listing = self.get_object()
        bookings = listing.bookings.all().order_by('-created_at')
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)


class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing bookings.
    Provides CRUD operations for bookings with status management.
    """
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    lookup_field = 'booking_id'

    def get_queryset(self):
        """
        Filter bookings based on query parameters
        """
        queryset = Booking.objects.all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter is not None:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by user (for guests to see their bookings)
        user_id = self.request.query_params.get('user_id', None)
        if user_id is not None:
            try:
                queryset = queryset.filter(user_id=int(user_id))
            except ValueError:
                pass
        
        # Filter by listing (for hosts to see bookings for their listings)
        listing_id = self.request.query_params.get('listing_id', None)
        if listing_id is not None:
            queryset = queryset.filter(listing__listing_id=listing_id)
        
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Set the user to the current user when creating a booking"""
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    @swagger_auto_schema(
        method='patch',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'status': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['pending', 'confirmed', 'cancelled', 'completed'],
                    description='New booking status'
                )
            }
        ),
        responses={200: BookingSerializer}
    )
    @action(detail=True, methods=['patch'])
    def update_status(self, request, booking_id=None):
        """
        Update booking status
        """
        booking = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in ['pending', 'confirmed', 'cancelled', 'completed']:
            return Response(
                {'error': 'Invalid status. Must be one of: pending, confirmed, cancelled, completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = new_status
        booking.save()
        
        serializer = self.get_serializer(booking)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='post',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'status': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['cancelled'],
                    description='Cancel the booking'
                )
            }
        ),
        responses={200: BookingSerializer}
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, booking_id=None):
        """
        Cancel a booking
        """
        booking = self.get_object()
        
        if booking.status == 'completed':
            return Response(
                {'error': 'Cannot cancel a completed booking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if booking.status == 'cancelled':
            return Response(
                {'error': 'Booking is already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = 'cancelled'
        booking.save()
        
        serializer = self.get_serializer(booking)
        return Response(serializer.data)


class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing reviews.
    Provides CRUD operations for reviews.
    """
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    lookup_field = 'review_id'

    def get_queryset(self):
        """
        Filter reviews based on query parameters
        """
        queryset = Review.objects.all()
        
        # Filter by listing
        listing_id = self.request.query_params.get('listing_id', None)
        if listing_id is not None:
            queryset = queryset.filter(listing__listing_id=listing_id)
        
        # Filter by user
        user_id = self.request.query_params.get('user_id', None)
        if user_id is not None:
            try:
                queryset = queryset.filter(user_id=int(user_id))
            except ValueError:
                pass
        
        # Filter by rating
        min_rating = self.request.query_params.get('min_rating', None)
        if min_rating is not None:
            try:
                queryset = queryset.filter(rating__gte=int(min_rating))
            except ValueError:
                pass
        
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Set the user to the current user when creating a review"""
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()