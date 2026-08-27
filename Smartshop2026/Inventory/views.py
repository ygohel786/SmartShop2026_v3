from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction  # નવું ઈમ્પોર્ટ કર્યું છે
from .models import Product, Invoice, InvoiceItem, StockMovement

@login_required
def inventory_view(request):
    return render(request, 'inventory.html')

@login_required
def sales(request):
    # બિલિંગ પેજ પર માત્ર લોગિન થયેલા યુઝરની જ પ્રોડક્ટ્સ બતાવો
    products = Product.objects.filter(shop=request.user)
    return render(request, 'sales.html', {'products': products})

@login_required
def hx_add_bill_item(request):
    # HTMX દ્વારા જ્યારે "Add Item" બટન દબાવાય ત્યારે આ ફંક્શન કોલ થશે
    product_id = request.POST.get('product_id')
    
    # જો quantity ખાલી આવે તો એરર ના આવે તે માટે ચેકિંગ
    qty_str = request.POST.get('quantity')
    quantity = int(qty_str) if qty_str and qty_str.isdigit() else 1
    
    if product_id:
        try:
            product = Product.objects.get(id=product_id, shop=request.user)
            
            # જો સ્ટોક પૂરતો ન હોય તો એરર બતાવો
            if product.current_stock < quantity:
                return HttpResponse(f"<tr><td colspan='6' class='text-red-600'><b>Error:</b> Not enough stock for {product.name} (Only {product.current_stock} left)</td></tr>")

            sub_total = product.selling_price * quantity
            context = {
                'product': product,
                'quantity': quantity,
                'sub_total': sub_total
            }
            # આ માત્ર એક ટેબલની <tr> રિટર્ન કરશે, આખું પેજ નહીં!
            return render(request, 'partials/bill_item_row.html', context)
        
        except Product.DoesNotExist:
            return HttpResponse("<tr><td colspan='6' class='text-red-600'><b>Error:</b> Product not found!</td></tr>")
            
    return HttpResponse("")

@login_required
def generate_bill(request):
    if request.method == 'POST':
        try:
            # transaction.atomic() થી જો વચ્ચે કોઈ પણ ભૂલ થાય તો આખું બિલ કેન્સલ થશે (ડેટા કરપ્ટ નહિ થાય)
            with transaction.atomic():
                customer_name = request.POST.get('customer_name')
                contact_number = request.POST.get('contact_number')
                gst_number = request.POST.get('gst_number')
                
                # ખાલી વેલ્યુને હેન્ડલ કરવા માટે
                sgst = float(request.POST.get('sgst') or 0)
                cgst = float(request.POST.get('cgst') or 0)
                grand_total = float(request.POST.get('grand_total') or 0)

                # ૧. ડેટાબેઝમાં નવું બિલ (Invoice) બનાવો
                invoice = Invoice.objects.create(
                    shop=request.user,
                    customer_name=customer_name,
                    contact_number=contact_number,
                    gst_number=gst_number,
                    sgst_percentage=sgst,
                    cgst_percentage=cgst,
                    grand_total=grand_total
                )

                # ૨. બિલમાં એડ થયેલી આઈટમ્સ ડેટાબેઝમાં સેવ કરો
                billed_items = request.POST.getlist('billed_items')
                for item in billed_items:
                    product_id, quantity = item.split('_')
                    
                    # shop=request.user એડ કર્યું જેથી કોઈ બીજા દુકાનદારની પ્રોડક્ટ ભૂલથી સિલેક્ટ ના થઈ જાય
                    product = Product.objects.get(id=product_id, shop=request.user) 
                    
                    # આ સેવ થતાં જ models.py માં લખેલા લોજિક મુજબ ઓટોમેટિક સ્ટોક માઈનસ થઈ જશે!
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        product=product,
                        quantity=int(quantity),
                        selling_price=product.selling_price
                    )
            
            messages.success(request, "Bill Generated & Saved Successfully!")
            
        except Exception as e:
            # જો કોઈ પણ એરર આવે તો યુઝરને મેસેજ બતાવશે
            messages.error(request, f"Error generating bill: {str(e)}")
            
        return redirect('sales')
    return redirect('sales')