from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
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
        p = request.POST.get('password')
        cp = request.POST.get('confirm_password')

        if p != cp:
            messages.error(request, "Passwords do not match!")
            return redirect('signup')
        
        if ShopUser.objects.filter(username=u).exists():
            messages.error(request, "Username already exists! Choose another.")
            return redirect('signup')
        
        # નવો સિક્યોર યુઝર બનાવો
        user = ShopUser.objects.create_user(
            username=u, 
            email=email, 
            password=p, 
            shop_name=shop_name, 
            contact_no=phone
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