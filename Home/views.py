from django.shortcuts import redirect, render
from django.contrib.auth.models import User
from django.contrib.auth import authenticate , login
from django.contrib import messages
from django.http import HttpResponseRedirect
from .models import (Amenities, Hotel, HotelBooking)
from django.db.models import Q
from django.core.mail import send_mail
from Lotus_Delights_Hotels_and_Dinings.settings import EMAIL_HOST_USER
import pandas as pd
from django.db.models import Count

# Create your views here.
def home(request):
    amenities_objs = Amenities.objects.all()
    hotels_objs = Hotel.objects.all()

    checkin = request.GET.get('checkin')
    checkout = request.GET.get('checkout')
    if checkin and checkout:
        res = check_booking_all(checkin , checkout)
        print(res.values())
        hotel_freq = pd.DataFrame(res.values('hotel_id').annotate(count=Count('hotel_id')).order_by('count').values('hotel_id', 'count'))
        # `hotel_freq` is a Pandas DataFrame containing the frequency of each hotel in `res`
        print("\n",hotel_freq)

        # Retrieve room count for each hotel
        hotels_df = pd.DataFrame(list(Hotel.objects.all().values('uid', 'room_count')))
        print("\n",hotels_df)
        a = list(hotels_df['uid'])
        print(a)

    
        # Merge the two dataframes based on the common column 'hotel_id'
        merged_df = pd.merge(hotels_df, hotel_freq, left_on='uid', right_on='hotel_id')
        # print("\n",merged_df)
        # merged_df = pd.merge(hotels_df, hotel_freq, left_on='uid', right_on='hotel_id')
        # merged_df = merged_df.drop('Hotel_Name', axis=1) # drop the redundant 'name' column

        # Filter out hotels whose frequency is less than their respective room count
        # merged_df = merged_df[merged_df['count'] < merged_df['room_count']]
        merged_df = merged_df[merged_df['count'] == merged_df['room_count']]
        print("\n",merged_df)

        # Retrieve the list of hotel names that meet the filter criteria
        # hotels = list(merged_df['hotel_id'])
        b = list(merged_df['hotel_id'])
        print("\n",b)
        # hotels_objs = Hotel.objects.filter(uid__in=hotels)

         # Drop the matching rows from `hotels_df`
        # merged_df = pd.merge(hotels_df, hotel_freq, how='outer', left_on='uid', right_on='hotel_id', indicator=True)
        # merged_df = merged_df[merged_df['_merge'] != 'both'].drop(['count', '_merge'], axis=1)
        # hotels_df = merged_df
        # print("\n",hotels_df)

        # hotels = list(hotels_df['uid'])
        # print("\n",hotels)

        for i in a:
            for j in b:
                if i==j:
                    a.remove(j)

        hotels_objs = Hotel.objects.filter(uid__in=a)


    sort_by = request.GET.get('sort_by')
    if sort_by:
        if sort_by == 'ASC':
            hotels_objs = hotels_objs.order_by('Hotel_Price')
        elif sort_by == 'DSC':
            hotels_objs = hotels_objs.order_by('-Hotel_Price')

    search = request.GET.get('search')
    if search:
        hotels_objs = hotels_objs.filter(
            Q(Hotel_Name__icontains = search) |
            Q(Hotel_Desc__icontains = search) |
            Q(location__icontains = search)
            )
    else:
        search = ""

    selected_amenities = request.GET.getlist('amenities')
    
    if selected_amenities:
            hotels_objs = filter_listings_by_amenities(hotels_objs, selected_amenities)

    context = {'amenities_objs' : amenities_objs , 'hotels_objs' : hotels_objs, 'sort_by' : sort_by, 'search' : search, 'amenities' : selected_amenities}
    return render(request,'home.html',context)

def check_booking_all(start_date , end_date):
    res = HotelBooking.objects.filter(
        start_date__lte = start_date ,
        end_date__gte = end_date
    )
    return res

def filter_listings_by_amenities(listings, amenities):
    """
    Filter hotel listings by a list of amenities.

    Args:
    listings (QuerySet): A queryset of Hotel objects.
    amenities (list): A list of amenities to filter by.

    Returns:
    QuerySet: A queryset of Hotel objects that have all the specified amenities.
    """
    filtered_listings = listings

    for amenity in amenities:
        filtered_listings = filtered_listings.filter(amenities__amenity_name=amenity)

    return filtered_listings.distinct()


def check_booking(start_date , end_date , uid , room_count):
    res = HotelBooking.objects.filter(
        start_date__lte = start_date ,
        end_date__gte = end_date ,
        hotel__uid = uid
    )
    if len(res) >= room_count:
        return False 
    
    return True

def hotel_detail(request,uid):
    hotels_obj = Hotel.objects.get(uid = uid)

    if request.method == 'POST':
        checkin = request.POST.get('checkin')
        checkout = request.POST.get('checkout')
        hotel = Hotel.objects.get(uid = uid)
        if not check_booking(checkin, checkout, uid, hotel.room_count) :
            messages.warning(request, 'Hotel is already booked on these dates')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        user=request.user
        booking = HotelBooking.objects.create(hotel=hotel, user=user, start_date=checkin, end_date=checkout, booking_type='Pre-Paid')
        booking_id = booking.uid
        booking_mail(user, hotel, checkin, checkout, booking_id)
        messages.success(request, 'Your Reservation has been saved')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    return render(request,'hotel_detail.html', {
        'hotels_obj' : hotels_obj,
        }
    )

def login_page(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user_obj = User.objects.filter(username = username)
        if not user_obj.exists():
            messages.warning(request, 'Account not found')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
        user_obj = authenticate(username = username, password = password)
        if not user_obj:
            messages.warning(request, 'Invalid Password')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        login(request, user_obj)
        return redirect('/')

    return render(request,'login.html')

def register_page(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        username = request.POST.get('username')
        password = request.POST.get('password')

        user_obj = User.objects.filter(email = email)
        if user_obj.exists():
            messages.warning(request, 'User already exists with this email.')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        else:
            user_obj = User.objects.filter(username = username)
            if user_obj.exists():
                messages.warning(request, 'User already exists with this username.')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            else:
                user = User.objects.create(email=email, username=username)
                user.set_password(password)
                user.save()
                print(password)
                # messages.success(request, 'Account created successfully!')

                # authenticate and login the user
                user_obj = authenticate(request, username=username, password=password)
                print(user_obj)
                login(request, user_obj)
                return redirect('/')
    
    return render(request,"register.html")

def booking_mail(user, hotel, checkin, checkout, booking_id):
    subject = 'Hotel Booking Confirmation'
    message = f'Dear {user.username},\n\n' \
              f'Thank you for booking {hotel.Hotel_Name}.\n\n' \
              f'Booking details:\n' \
              f'Check-in date: {checkin}\n' \
              f'Check-out date: {checkout}\n' \
              f'Booking ID: {booking_id}\n\n' \
              f'We hope you enjoy your stay at our hotel.\n\n' \
              f'Thanks and Regards,\n' \
              f'{hotel.Hotel_Name} Team'
    from_email = EMAIL_HOST_USER
    recipient_list = [user.email]
    send_mail(subject, message, from_email, recipient_list, fail_silently=False)
