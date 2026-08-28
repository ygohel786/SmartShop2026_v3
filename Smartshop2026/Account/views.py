from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from .models import ShopUser


def index(request):
    # જો યુઝર પહેલેથી લોગિન હોય તો સીધા ડેશબોર્ડ પર મોકલો
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        # Django જાતે જ પાસવર્ડ હેશ (Hash) કરીને ચેક કરશે
        user = authenticate(request, username=u, password=p)
        if user is not None:
            auth_login(request, user)
            messages.success(request, "Welcome back!")
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password.")
            
    return render(request, 'index.html')

def signup(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        email = request.POST.get('email')
        shop_name = request.POST.get('shop_name')
        phone = request.POST.get('contact_no')
        business_type = request.POST.get('business_type') # નવું ઉમેર્યું
        p = request.POST.get('password')
        cp = request.POST.get('confirm_password')

        if p != cp:
            messages.error(request, "Passwords do not match!")
            return redirect('signup')
            
        if ShopUser.objects.filter(username=u).exists():
            messages.error(request, "Username already exists! Choose another.")
            return redirect('signup')
            
        # નવો યુઝર બનાવો (business_type સાથે)
        user = ShopUser.objects.create_user(
            username=u, 
            email=email, 
            password=p, 
            shop_name=shop_name, 
            contact_no=phone,
            business_type=business_type # નવું ઉમેર્યું
        )
        user.save()
        messages.success(request, "Registration successful! Please login.")
        return redirect('index')
        
    return render(request, 'registration.html')

def logout_view(request):
    auth_logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('index')

@login_required
def home(request):
    return render(request, 'home.html')

@login_required
def profile_view(request):
    if request.method == 'POST':
        user = request.user
        # અહી માત્ર નામ અને ઈમેલ જ અપડેટ થશે, Business Type નહિ થાય.
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        messages.success(request, '✅ પ્રોફાઈલની માહિતી સફળતાપૂર્વક અપડેટ થઈ ગઈ છે!')
        return redirect('profile')

    password_form = PasswordChangeForm(request.user)
    return render(request, 'profile.html', {'password_form': password_form})

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # પાસવર્ડ બદલ્યા પછી યુઝર લોગઆઉટ ના થઈ જાય તે માટે:
            update_session_auth_hash(request, user) 
            messages.success(request, '🔒 તમારો પાસવર્ડ સફળતાપૂર્વક બદલાઈ ગયો છે!')
            return redirect('profile')
        else:
            for error in list(form.errors.values()):
                messages.error(request, error)
    return redirect('profile')