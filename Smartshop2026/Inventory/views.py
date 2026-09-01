from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import Product, Invoice, InvoiceItem, StockMovement, Category, CustomerProfile, LedgerTransaction
from django.db.models import Q, Sum, F, DecimalField, ExpressionWrapper
from django.utils import timezone
import json
from datetime import timedelta
from django.db.models.functions import TruncDate
import os
from google.cloud import vision
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import ProtectedError

# તમારો GCP કી પાથ અહી સેટ કરો
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "path/to/your/credentials.json"

@login_required
def home(request):
    # 🛑 સિક્યુરિટી: જો સ્ટાફ હોય તો સીધા બિલિંગ (sales) પર મોકલો
    if getattr(request.user, 'is_shop_staff', False):
        return redirect('sales')

    # 🪄 જાદુઈ લાઈન: દુકાનદારનું ઓરિજિનલ એકાઉન્ટ લાવો (માલિક હોય કે સ્ટાફ, માલિકનું જ ખાતું આવશે)
    shop_owner = request.user.get_shop
    
    today = timezone.now().date()
    this_month_start = today.replace(day=1)

    # ==========================================
    # 💰 નફો (Profit) ગણવા માટેનું ફોર્મ્યુલા
    # ==========================================
    profit_calc = ExpressionWrapper(
        (F('selling_price') - F('product__purchase_price')) * F('quantity'),
        output_field=DecimalField()
    )

    # ૧. આજનો ડેટા (Today's Revenue & Profit)
    todays_invoices = Invoice.objects.filter(shop=shop_owner, date=today)
    todays_bills_count = todays_invoices.count()

    todays_data = InvoiceItem.objects.filter(invoice__shop=shop_owner, invoice__date=today).aggregate(
        total_revenue=Sum(F('quantity') * F('selling_price'), output_field=DecimalField()),
        total_profit=Sum(profit_calc)
    )
    todays_revenue = todays_data['total_revenue'] or 0
    todays_profit = todays_data['total_profit'] or 0

    # ૨. આ મહિનાનો ડેટા (Monthly Revenue & Profit)
    monthly_data = InvoiceItem.objects.filter(invoice__shop=shop_owner, invoice__date__gte=this_month_start).aggregate(
        total_revenue=Sum(F('quantity') * F('selling_price'), output_field=DecimalField()),
        total_profit=Sum(profit_calc)
    )
    monthly_revenue = monthly_data['total_revenue'] or 0
    monthly_profit = monthly_data['total_profit'] or 0

    # ૩. સૌથી વધુ વેચાતી પ્રોડક્ટ્સ (Top Selling Products - This Month)
    top_products = InvoiceItem.objects.filter(invoice__shop=shop_owner, invoice__date__gte=this_month_start)\
        .values('product__name')\
        .annotate(total_sold=Sum('quantity'))\
        .order_by('-total_sold')[:5]

    # ૪. કુલ પ્રોડક્ટ્સ અને Low Stock Alerts
    all_products = Product.objects.filter(shop=shop_owner)
    total_products = all_products.count()
    low_stock_list = [p for p in all_products if p.current_stock <= 5]
    low_stock_products = sorted(low_stock_list, key=lambda x: x.current_stock)[:5]

    # ૫. Recent Sales
    recent_sales = Invoice.objects.filter(shop=shop_owner).order_by('-date')[:5]

    # ૬. 📊 Chart.js માટે છેલ્લા 7 દિવસનો ડેટા
    last_7_days = today - timedelta(days=6)
    
    sales_data = InvoiceItem.objects.filter(
        invoice__shop=shop_owner, 
        invoice__date__gte=last_7_days
    ).values('invoice__date').annotate(
        daily_total=Sum(F('quantity') * F('selling_price'), output_field=DecimalField())
    ).order_by('invoice__date')

    chart_dates = []
    chart_revenues = []
    
    for i in range(7):
        current_d = last_7_days + timedelta(days=i)
        chart_dates.append(current_d.strftime('%d %b')) 
        
        daily_val = 0
        for data in sales_data:
            if data['invoice__date'] == current_d:
                daily_val = float(data['daily_total'])
                break
        chart_revenues.append(daily_val)

    context = {
        'todays_revenue': todays_revenue,
        'todays_profit': todays_profit,
        'monthly_revenue': monthly_revenue,
        'monthly_profit': monthly_profit,
        'todays_bills_count': todays_bills_count,
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'recent_sales': recent_sales,
        'top_products': top_products,
        'chart_dates': json.dumps(chart_dates),
        'chart_revenues': json.dumps(chart_revenues),
    }
    
    return render(request, 'home.html', context)


@login_required
def inventory_view(request):
    shop_owner = request.user.get_shop
    products = Product.objects.filter(shop=shop_owner).order_by('-id')
    return render(request, 'inventory.html', {'products': products})


@login_required
def add_product(request):
    shop_owner = request.user.get_shop
    if request.method == 'POST':
        category_name = shop_owner.business_type or 'General'
        company_name = request.POST.get('company_name', '').strip()
        product_type = request.POST.get('product_type', '').strip()
        name = request.POST.get('name', '').strip()
        
        is_serialized = request.POST.get('is_serialized', 'true') == 'true'

        try:
            category, _ = Category.objects.get_or_create(name=category_name, shop=shop_owner)
            
            cat_char = category_name[0].upper() if category_name else 'X'
            comp_char = company_name[0].upper() if company_name else 'X'
            type_char = product_type[0].upper() if product_type else 'X'
            name_char = name[0].upper() if name else 'X'
            prefix = f"{cat_char}{comp_char}{type_char}{name_char}"

            if category_name in ['Electronics', 'Mobile', 'IT'] and is_serialized:
                margin_percentage = request.POST.get('margin_percentage', 0)
                imeis = request.POST.getlist('imei[]')
                storages = request.POST.getlist('storage[]')
                colors = request.POST.getlist('color[]')
                prices = request.POST.getlist('price[]')
                
                success_count = 0
                with transaction.atomic():
                    for i in range(len(imeis)):
                        imei = imeis[i].strip()
                        if not imei: 
                            continue 
                        
                        if Product.objects.filter(shop=shop_owner, serial_number__icontains=imei).exists():
                            messages.error(request, f"Skipped: IMEI/SN '{imei}' પહેલેથી હાજર છે!")
                            continue
                            
                        storage = storages[i].strip() if i < len(storages) else ''
                        color = colors[i].strip() if i < len(colors) else ''
                        price = float(prices[i].strip()) if i < len(prices) and prices[i].strip() else 0
                        
                        last_product = Product.objects.filter(serial_number__startswith=prefix, shop=shop_owner).order_by('-id').first()
                        new_number = 1
                        if last_product and last_product.serial_number:
                            try:
                                new_number = int(last_product.serial_number.split(' | ')[0][4:]) + 1
                            except ValueError:
                                pass
                        
                        uniq_code = f"{prefix}{new_number:06d}"
                        final_sn = f"{uniq_code} | SN: {imei}"
                        
                        prod = Product.objects.create(
                            shop=shop_owner, category=category, company_name=company_name,
                            product_type=product_type, name=name, storage=storage, color=color,
                            serial_number=final_sn, purchase_price=price, margin_percentage=margin_percentage
                        )
                        StockMovement.objects.create(product=prod, movement_type='IN', quantity=1, notes="Initial Stock")
                        success_count += 1
                        
                if success_count > 0:
                    messages.success(request, f"✅ {success_count} Serialized પ્રોડક્ટ્સ સફળતાપૂર્વક ઉમેરાઈ ગઈ!")
                return redirect('inventory')

            else:
                margin_percentage = request.POST.get('margin_percentage_ns', 0)
                ns_details = request.POST.get('ns_details', '').strip()
                expiry_date = request.POST.get('expiry_date') or None
                purchase_price = request.POST.get('purchase_price', 0)
                stock = int(request.POST.get('stock', 0))

                existing_product = Product.objects.filter(
                    shop=shop_owner, company_name__iexact=company_name, product_type__iexact=product_type,
                    name__iexact=name, weight__iexact=ns_details
                ).first()
                
                if existing_product:
                    if stock > 0:
                        StockMovement.objects.create(product=existing_product, movement_type='IN', quantity=stock, notes="Stock Added")
                        messages.success(request, f"✅ '{existing_product.name}' માં {stock} નો નવો જથ્થો (Stock) પ્લસ થઈ ગયો!")
                    return redirect('inventory')

                last_product = Product.objects.filter(serial_number__startswith=prefix, shop=shop_owner).order_by('-id').first()
                new_number = 1
                if last_product and last_product.serial_number:
                    try:
                        code_part = last_product.serial_number.split(' | ')[0]
                        new_number = int(code_part[4:]) + 1
                    except ValueError:
                        pass
                uniq_code = f"{prefix}{new_number:06d}"
                
                prod = Product.objects.create(
                    shop=shop_owner, category=category, company_name=company_name, product_type=product_type,
                    name=name, weight=ns_details, serial_number=uniq_code,
                    expiry_date=expiry_date, purchase_price=purchase_price, margin_percentage=margin_percentage
                )
                if stock > 0:
                    StockMovement.objects.create(product=prod, movement_type='IN', quantity=stock, notes="Initial Stock")
                messages.success(request, f"✅ '{name}' (Non-Serialized) ઉમેરાઈ ગયું! Code: {uniq_code}")
                
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            
    return redirect('inventory')


@login_required
def print_barcodes(request, product_id):
    shop_owner = request.user.get_shop
    product = get_object_or_404(Product, id=product_id, shop=shop_owner)
    
    qty = int(request.GET.get('qty', product.current_stock))
    if qty < 1:
        qty = 1
        
    context = {
        'product': product,
        'stickers': range(qty)
    }
    return render(request, 'print_barcodes.html', context)


@csrf_exempt
@login_required
def smart_invoice_scan(request):
    if request.method == 'POST' and request.FILES.get('invoice_image'):
        image_file = request.FILES['invoice_image']
        content = image_file.read()

        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=content)

        response = client.text_detection(image=image)
        texts = response.text_annotations

        if response.error.message:
            return JsonResponse({'error': response.error.message}, status=400)

        raw_text = texts[0].description if texts else ""
        extracted_lines = raw_text.split('\n')
        
        return JsonResponse({
            'success': True,
            'raw_text': raw_text,
            'lines': extracted_lines
        })
        
    return JsonResponse({'error': 'No image uploaded'}, status=400)


@login_required
def edit_product(request, product_id):
    shop_owner = request.user.get_shop
    product = get_object_or_404(Product, id=product_id, shop=shop_owner)
    
    if request.method == 'POST':
        product.name = request.POST.get('name')
        product.company_name = request.POST.get('company_name')
        product.product_type = request.POST.get('product_type')
        product.purchase_price = request.POST.get('purchase_price')
        product.margin_percentage = request.POST.get('margin_percentage')
        
        product.weight = request.POST.get('weight', '')
        product.size = request.POST.get('size', '')
        product.storage = request.POST.get('storage', '')
        product.color = request.POST.get('color', '')
        
        product.save()
        messages.success(request, f"'{product.name}' ની વિગતો અપડેટ થઈ ગઈ છે!")
        return redirect('inventory')
    
    return render(request, 'edit_product.html', {'product': product})


@login_required
def delete_product(request, product_id):
    shop_owner = request.user.get_shop
    try:
        product = Product.objects.get(id=product_id, shop=shop_owner)
        product.delete()
        messages.success(request, f"{product.name} removed successfully.")
    except ProtectedError:
        messages.error(request, "❌ આ પ્રોડક્ટના બિલ બની ગયા હોવાથી તેને ડિલીટ કરી શકાશે નહિ. (સ્ટોક 0 કરી શકો છો).")
    except Exception as e:
        messages.error(request, "Error removing product.")
    return redirect('inventory')


@login_required
def sales(request):
    shop_owner = request.user.get_shop
    products = Product.objects.filter(shop=shop_owner)
    return render(request, 'sales.html', {'products': products})


@login_required
def hx_add_bill_item(request):
    shop_owner = request.user.get_shop
    product_id = request.POST.get('product_id')
    qty_str = request.POST.get('quantity')
    quantity = int(qty_str) if qty_str and qty_str.isdigit() else 1
    
    if product_id:
        try:
            product = Product.objects.get(id=product_id, shop=shop_owner)
            if product.current_stock < quantity:
                return HttpResponse(f"<tr><td colspan='6' class='text-red-600'><b>Error:</b> Not enough stock!</td></tr>")

            sub_total = product.selling_price * quantity
            return render(request, 'partials/bill_item_row.html', {'product': product, 'quantity': quantity, 'sub_total': sub_total})
        except Product.DoesNotExist:
            return HttpResponse("<tr><td colspan='6' class='text-red-600'><b>Error:</b> Product not found!</td></tr>")
    return HttpResponse("")


@login_required
def generate_bill(request):
    shop_owner = request.user.get_shop
    if request.method == 'POST':
        try:
            with transaction.atomic():
                customer_name = request.POST.get('customer_name')
                contact_number = request.POST.get('contact_number')
                gst_number = request.POST.get('gst_number')
                sgst = float(request.POST.get('sgst') or 0)
                cgst = float(request.POST.get('cgst') or 0)
                grand_total = float(request.POST.get('grand_total') or 0)
                payment_mode = request.POST.get('payment_mode', 'CASH')

                invoice = Invoice.objects.create(
                    shop=shop_owner, customer_name=customer_name, contact_number=contact_number,
                    gst_number=gst_number, sgst_percentage=sgst, cgst_percentage=cgst, grand_total=grand_total, payment_mode=payment_mode
                )

                billed_items = request.POST.getlist('billed_items')
                for item in billed_items:
                    product_id, quantity = item.split('_')
                    product = Product.objects.get(id=product_id, shop=shop_owner) 
                    InvoiceItem.objects.create(
                        invoice=invoice, product=product, quantity=int(quantity), selling_price=product.selling_price
                    )
                
                # ==========================================
                # 🪄 SMART KHATA BOOK INTEGRATION
                # ==========================================
                if payment_mode == 'UNPAID':
                    customer_profile = CustomerProfile.objects.filter(shop=shop_owner, phone=contact_number).first()
                    
                    if not customer_profile:
                        customer_profile = CustomerProfile.objects.create(
                            shop=shop_owner,
                            name=customer_name,
                            phone=contact_number
                        )
                    
                    LedgerTransaction.objects.create(
                        customer=customer_profile,
                        transaction_type='GIVEN',
                        amount=invoice.grand_total,
                        description=f"Invoice #{invoice.id} (બિલ બાકી)"
                    )
                # ==========================================
            
            messages.success(request, "Bill Generated Successfully!")
            return redirect('print_invoice', invoice_id=invoice.id)
            
        except Exception as e:
            messages.error(request, f"Error generating bill: {str(e)}")
            return redirect('sales')
    return redirect('sales')


@login_required
def sales_history(request):
    shop_owner = request.user.get_shop
    invoices = Invoice.objects.filter(shop=shop_owner).order_by('-id')
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    search_query = request.GET.get('search')
    
    if start_date:
        invoices = invoices.filter(date__gte=start_date)
    if end_date:
        invoices = invoices.filter(date__lte=end_date)
    if search_query:
        invoices = invoices.filter(
            Q(customer_name__icontains=search_query) | 
            Q(id__icontains=search_query) |
            Q(items__product__name__icontains=search_query)
        ).distinct()
        
    return render(request, 'sales_history.html', {'invoices': invoices})


@login_required
def print_invoice(request, invoice_id):
    shop_owner = request.user.get_shop
    invoice = get_object_or_404(Invoice, id=invoice_id, shop=shop_owner)
    return render(request, 'print_invoice.html', {'invoice': invoice})


@login_required
def khata_dashboard(request):
    shop_owner = request.user.get_shop
    customers = CustomerProfile.objects.filter(shop=shop_owner).order_by('-created_at')
    
    total_market_outstanding = sum(c.total_balance for c in customers if c.total_balance > 0)
    
    context = {
        'customers': customers,
        'total_market_outstanding': total_market_outstanding
    }
    return render(request, 'khata.html', context)


@login_required
def add_khata_customer(request):
    shop_owner = request.user.get_shop
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address', '')
        
        CustomerProfile.objects.create(shop=shop_owner, name=name, phone=phone, address=address)
        messages.success(request, f"✅ ખાતાવહીમાં નવા ગ્રાહક '{name}' નું ખાતું ખૂલી ગયું છે!")
        
    return redirect('khata_dashboard')


@login_required
def khata_detail(request, customer_id):
    shop_owner = request.user.get_shop
    customer = get_object_or_404(CustomerProfile, id=customer_id, shop=shop_owner)
    transactions = customer.transactions.all().order_by('-date')
    
    context = {
        'customer': customer,
        'transactions': transactions
    }
    return render(request, 'khata_detail.html', context)


@login_required
def add_khata_transaction(request, customer_id):
    shop_owner = request.user.get_shop
    customer = get_object_or_404(CustomerProfile, id=customer_id, shop=shop_owner)
    
    if request.method == 'POST':
        transaction_type = request.POST.get('transaction_type')
        amount = request.POST.get('amount')
        description = request.POST.get('description')
        
        LedgerTransaction.objects.create(
            customer=customer,
            transaction_type=transaction_type,
            amount=amount,
            description=description
        )
        msg = "ઉધાર આપ્યા (બાકી)" if transaction_type == 'GIVEN' else "જમા લીધા (પેમેન્ટ)"
        messages.success(request, f"✅ ₹{amount} - {msg} સફળતાપૂર્વક નોંધાઈ ગયા!")
        
    return redirect('khata_detail', customer_id=customer.id)

@login_required
def gst_report_view(request):
    # 🛑 સિક્યુરિટી: સ્ટાફને ટેક્સ કે જીએસટી રિપોર્ટ જોવાની મંજૂરી નથી!
    if getattr(request.user, 'is_shop_staff', False):
        messages.error(request, "તમને જીએસટી રિપોર્ટ જોવાની મંજૂરી નથી!")
        return redirect('sales')

    shop_owner = request.user.get_shop
    invoices = Invoice.objects.filter(shop=shop_owner).order_by('-date')

    # ડેટ ફિલ્ટર (Start Date & End Date)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date:
        invoices = invoices.filter(date__gte=start_date)
    if end_date:
        invoices = invoices.filter(date__lte=end_date)

    # કુલ ટેબલ માટે ગણતરી
    total_taxable_amount = 0
    total_cgst_collected = 0
    total_sgst_collected = 0
    total_grand_total = 0

    report_data = []

    for inv in invoices:
        # બિલની ગ્રાન્ડ ટોટલમાંથી ટેક્સ બાદ કરીને ટેક્સેબલ અમાઉન્ટ કાઢવી
        # (જો grand_total માં ટેક્સ ઇન્ક્લુડેડ હોય અથવા અલગથી હોય)
        grand = float(inv.grand_total or 0)
        sgst_pct = float(inv.sgst_percentage or 0)
        cgst_pct = float(inv.cgst_percentage or 0)
        total_pct = sgst_pct + cgst_pct

        if total_pct > 0:
            taxable = grand / (1 + (total_pct / 100))
            tax_amount = grand - taxable
            cgst_amt = tax_amount / 2
            sgst_amt = tax_amount / 2
        else:
            taxable = grand
            cgst_amt = 0
            sgst_amt = 0

        total_taxable_amount += taxable
        total_cgst_collected += cgst_amt
        total_sgst_collected += sgst_amt
        total_grand_total += grand

        report_data.append({
            'invoice': inv,
            'taxable': taxable,
            'cgst': cgst_amt,
            'sgst': sgst_amt,
            'total': grand
        })

    context = {
        'report_data': report_data,
        'total_taxable_amount': total_taxable_amount,
        'total_cgst_collected': total_cgst_collected,
        'total_sgst_collected': total_sgst_collected,
        'total_grand_total': total_grand_total,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'gst_report.html', context)