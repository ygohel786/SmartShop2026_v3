from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import Product, Invoice, InvoiceItem, StockMovement, Category
from django.db.models import Q, Sum, F, DecimalField
from django.utils import timezone

@login_required
def home(request):
    user = request.user
    today = timezone.now().date()

    # ૧. આજનું વેચાણ અને આજના બિલ
    todays_invoices = Invoice.objects.filter(shop=user, date__date=today)
    todays_bills_count = todays_invoices.count()

    # આજના વેચાણની કુલ રકમ (Total Revenue for Today)
    todays_sales = InvoiceItem.objects.filter(invoice__shop=user, invoice__date__date=today).aggregate(
        total=Sum(F('quantity') * F('selling_price'), output_field=DecimalField())
    )
    todays_revenue = todays_sales['total'] or 0

    # ૨. કુલ પ્રોડક્ટ્સ
    total_products = Product.objects.filter(shop=user).count()

    # ૩. Low Stock Alerts (જેનો સ્ટોક 5 કે તેનાથી ઓછો છે)
    low_stock_products = Product.objects.filter(shop=user, current_stock__lte=5).order_by('current_stock')[:10]

    # ૪. Recent Sales (છેલ્લા 5 બિલ)
    recent_sales = Invoice.objects.filter(shop=user).order_by('-date')[:5]

    context = {
        'todays_revenue': todays_revenue,
        'todays_bills_count': todays_bills_count,
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'recent_sales': recent_sales,
    }
    
    return render(request, 'home.html', context)

@login_required
def inventory_view(request):
    products = Product.objects.filter(shop=request.user).order_by('-id')
    return render(request, 'inventory.html', {'products': products})


@login_required
def add_product(request):
    if request.method == 'POST':
        category_name = request.user.business_type or 'General'
        company_name = request.POST.get('company_name', '').strip()
        product_type = request.POST.get('product_type', '').strip()
        name = request.POST.get('name', '').strip()
        
        # ચેક કરો કે રેડિયો બટનમાંથી કયું ઓપ્શન આવ્યું છે
        is_serialized = request.POST.get('is_serialized', 'true') == 'true'

        try:
            category, _ = Category.objects.get_or_create(name=category_name, shop=request.user)
            
            cat_char = category_name[0].upper() if category_name else 'X'
            comp_char = company_name[0].upper() if company_name else 'X'
            type_char = product_type[0].upper() if product_type else 'X'
            name_char = name[0].upper() if name else 'X'
            prefix = f"{cat_char}{comp_char}{type_char}{name_char}"

            # =========================================================
            # ૧. જો Electronics હોય અને 'SERIALIZED' પસંદ કર્યું હોય
            # =========================================================
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
                            continue # જો ભૂલથી ખાલી હોય તો જવા દો
                        
                        if Product.objects.filter(shop=request.user, serial_number__icontains=imei).exists():
                            messages.error(request, f"Skipped: IMEI/SN '{imei}' પહેલેથી હાજર છે!")
                            continue
                            
                        storage = storages[i].strip() if i < len(storages) else ''
                        color = colors[i].strip() if i < len(colors) else ''
                        price = float(prices[i].strip()) if i < len(prices) and prices[i].strip() else 0
                        
                        last_product = Product.objects.filter(serial_number__startswith=prefix, shop=request.user).order_by('-id').first()
                        new_number = 1
                        if last_product and last_product.serial_number:
                            try:
                                new_number = int(last_product.serial_number.split(' | ')[0][4:]) + 1
                            except ValueError:
                                pass
                        
                        uniq_code = f"{prefix}{new_number:06d}"
                        final_sn = f"{uniq_code} | SN: {imei}"
                        
                        prod = Product.objects.create(
                            shop=request.user, category=category, company_name=company_name,
                            product_type=product_type, name=name, storage=storage, color=color,
                            serial_number=final_sn, purchase_price=price, margin_percentage=margin_percentage
                        )
                        StockMovement.objects.create(product=prod, movement_type='IN', quantity=1, notes="Initial Stock")
                        success_count += 1
                        
                if success_count > 0:
                    messages.success(request, f"✅ {success_count} Serialized પ્રોડક્ટ્સ સફળતાપૂર્વક ઉમેરાઈ ગઈ!")
                return redirect('inventory')

            # =========================================================
            # ૨. જો NON-SERIALIZED પસંદ કર્યું હોય (અથવા બીજી કેટેગરી હોય)
            # =========================================================
            else:
                margin_percentage = request.POST.get('margin_percentage_ns', 0)
                ns_details = request.POST.get('ns_details', '').strip()
                expiry_date = request.POST.get('expiry_date') or None
                purchase_price = request.POST.get('purchase_price', 0)
                stock = int(request.POST.get('stock', 0))

                existing_product = Product.objects.filter(
                    shop=request.user, company_name__iexact=company_name, product_type__iexact=product_type,
                    name__iexact=name, weight__iexact=ns_details
                ).first()
                
                if existing_product:
                    if stock > 0:
                        StockMovement.objects.create(product=existing_product, movement_type='IN', quantity=stock, notes="Stock Added")
                        messages.success(request, f"✅ '{existing_product.name}' માં {stock} નો નવો જથ્થો (Stock) પ્લસ થઈ ગયો!")
                    return redirect('inventory')

                last_product = Product.objects.filter(serial_number__startswith=prefix, shop=request.user).order_by('-id').first()
                new_number = 1
                if last_product and last_product.serial_number:
                    try:
                        # સીરીયલ નંબર 'CODE | SN: ' ફોર્મેટમાં હોય કે માત્ર 'CODE' માં, બંને સાચવશે
                        code_part = last_product.serial_number.split(' | ')[0]
                        new_number = int(code_part[4:]) + 1
                    except ValueError:
                        pass
                uniq_code = f"{prefix}{new_number:06d}"
                
                prod = Product.objects.create(
                    shop=request.user, category=category, company_name=company_name, product_type=product_type,
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
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, shop=request.user)
    if request.method == 'POST':
        product.name = request.POST.get('name')
        product.company_name = request.POST.get('company_name')
        product.product_type = request.POST.get('product_type')
        product.purchase_price = request.POST.get('purchase_price')
        product.margin_percentage = request.POST.get('margin_percentage')
        
        # વેરાયટી ઓપ્શન્સ
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
    try:
        product = Product.objects.get(id=product_id, shop=request.user)
        product.delete()
        messages.success(request, f"{product.name} removed successfully.")
    except Exception as e:
        messages.error(request, "Error removing product.")
    return redirect('inventory')

@login_required
def sales(request):
    products = Product.objects.filter(shop=request.user)
    return render(request, 'sales.html', {'products': products})

@login_required
def hx_add_bill_item(request):
    product_id = request.POST.get('product_id')
    qty_str = request.POST.get('quantity')
    quantity = int(qty_str) if qty_str and qty_str.isdigit() else 1
    
    if product_id:
        try:
            product = Product.objects.get(id=product_id, shop=request.user)
            if product.current_stock < quantity:
                return HttpResponse(f"<tr><td colspan='6' class='text-red-600'><b>Error:</b> Not enough stock!</td></tr>")

            sub_total = product.selling_price * quantity
            return render(request, 'partials/bill_item_row.html', {'product': product, 'quantity': quantity, 'sub_total': sub_total})
        except Product.DoesNotExist:
            return HttpResponse("<tr><td colspan='6' class='text-red-600'><b>Error:</b> Product not found!</td></tr>")
    return HttpResponse("")


@login_required
def generate_bill(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                customer_name = request.POST.get('customer_name')
                contact_number = request.POST.get('contact_number')
                gst_number = request.POST.get('gst_number')
                sgst = float(request.POST.get('sgst') or 0)
                cgst = float(request.POST.get('cgst') or 0)
                grand_total = float(request.POST.get('grand_total') or 0)

                invoice = Invoice.objects.create(
                    shop=request.user, customer_name=customer_name, contact_number=contact_number,
                    gst_number=gst_number, sgst_percentage=sgst, cgst_percentage=cgst, grand_total=grand_total
                )

                billed_items = request.POST.getlist('billed_items')
                for item in billed_items:
                    product_id, quantity = item.split('_')
                    product = Product.objects.get(id=product_id, shop=request.user) 
                    InvoiceItem.objects.create(
                        invoice=invoice, product=product, quantity=int(quantity), selling_price=product.selling_price
                    )
            
            messages.success(request, "Bill Generated Successfully!")
            # બિલ સેવ થતા જ સીધું પ્રિન્ટ પેજ પર જશે!
            return redirect('print_invoice', invoice_id=invoice.id)
            
        except Exception as e:
            messages.error(request, f"Error generating bill: {str(e)}")
            return redirect('sales')
    return redirect('sales')

# ==========================================
# નવા ફંક્શન: Sales History અને Print Bill
# ==========================================

@login_required
def sales_history(request):
    invoices = Invoice.objects.filter(shop=request.user).order_by('-id')
    
    # ફિલ્ટર માટેનો ડેટા પકડો
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    search_query = request.GET.get('search')
    
    if start_date:
        invoices = invoices.filter(date__gte=start_date)
    if end_date:
        invoices = invoices.filter(date__lte=end_date)
    if search_query:
        # ગ્રાહકનું નામ, બિલ નંબર અથવા પ્રોડક્ટના નામથી સર્ચ કરો
        invoices = invoices.filter(
            Q(customer_name__icontains=search_query) | 
            Q(id__icontains=search_query) |
            Q(items__product__name__icontains=search_query)
        ).distinct()
        
    return render(request, 'sales_history.html', {'invoices': invoices})

@login_required
def print_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id, shop=request.user)
    return render(request, 'print_invoice.html', {'invoice': invoice})