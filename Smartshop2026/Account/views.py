from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from .models import ShopUser

def index(request):
    # જો યુઝર પહેલેથી લોગિન હોય 
    if request.user.is_authenticated:
        # 🛑 સિક્યુરિટી: જો સ્ટાફ હોય તો સીધા બિલિંગ (sales) પર મોકલો
        if request.user.is_shop_staff:
            return redirect('sales')
        return redirect('home') # માલિક હોય તો ડેશબોર્ડ પર
        
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        # Django જાતે જ પાસવર્ડ હેશ (Hash) કરીને ચેક કરશે
        user = authenticate(request, username=u, password=p)
        if user is not None:
            auth_login(request, user)
            messages.success(request, "Welcome back!")
            
            # 🛑 સિક્યુરિટી: લોગીન થતા જ સ્ટાફને સેલ્સ પેજ પર ધકેલો
            if user.is_shop_staff:
                return redirect('sales')
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
        business_type = request.POST.get('business_type') 
        p = request.POST.get('password')
        cp = request.POST.get('confirm_password')

        if p != cp:
            messages.error(request, "Passwords do not match!")
            return redirect('signup')
            
        if ShopUser.objects.filter(username=u).exists():
            messages.error(request, "Username already exists! Choose another.")
            return redirect('signup')
            
        # નવો યુઝર બનાવો 
        user = ShopUser.objects.create_user(
            username=u, 
            email=email, 
            password=p, 
            shop_name=shop_name, 
            contact_no=phone,
            business_type=business_type 
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
        # અહી માત્ર નામ અને ઈમેલ જ અપડેટ થશે
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
            update_session_auth_hash(request, user) 
            messages.success(request, '🔒 તમારો પાસવર્ડ સફળતાપૂર્વક બદલાઈ ગયો છે!')
            return redirect('profile')
        else:
            for error in list(form.errors.values()):
                messages.error(request, error)
    return redirect('profile')

# ==========================================
# 👨‍💼 STAFF MANAGEMENT (નવું ઉમેરેલું ફંક્શન)
# ==========================================
@login_required
def staff_management(request):
    # 🛑 સિક્યુરિટી ચેક: સ્ટાફને આ પેજ જોવાની મંજૂરી નથી!
    if getattr(request.user, 'is_shop_staff', False):
        messages.error(request, "તમને આ પેજ જોવા માટેની મંજૂરી નથી!")
        return redirect('sales')

    if request.method == 'POST':
        username = request.POST.get('username').strip().lower()
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '').strip()

        # ચેક કરો કે આ યુઝરનેમ પહેલેથી કોઈ વાપરે છે કે નહિ
        if ShopUser.objects.filter(username=username).exists():
            messages.error(request, f"યુઝરનેમ '{username}' પહેલેથી વપરાયેલું છે. કૃપા કરીને બીજું નામ પસંદ કરો.")
        else:
            # નવો સ્ટાફ બનાવો
            staff = ShopUser.objects.create(
                username=username,
                first_name=first_name,
                password=make_password(password),
                is_shop_staff=True,
                parent_shop=request.user,
                shop_name=request.user.shop_name,
                business_type=request.user.business_type
            )
            messages.success(request, f"✅ સ્ટાફ '{first_name}' નું એકાઉન્ટ સફળતાપૂર્વક બની ગયું!")
            return redirect('staff_management')

    # માલિકના બધા સ્ટાફનું લિસ્ટ જોવા માટે
    staff_list = ShopUser.objects.filter(parent_shop=request.user, is_shop_staff=True).order_by('-date_joined')
    return render(request, 'staff_management.html', {'staff_list': staff_list})