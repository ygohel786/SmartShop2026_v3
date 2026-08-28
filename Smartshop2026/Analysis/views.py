from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, DecimalField
from django.utils import timezone
import datetime
import calendar
import pandas as pd
from sklearn.linear_model import LinearRegression

# Inventory માંથી ડેટા લાવવા
from Inventory.models import Product, Invoice, InvoiceItem

# ==========================================
# 1. Main Dashboard (Master Algorithm & Top 25)
# ==========================================
@login_required
def analysis(request):
    user = request.user
    today = timezone.now().date()
    
    # ---------------- તારીખોની ગણતરી ----------------
    last_30_days = today - datetime.timedelta(days=30)
    last_90_days = today - datetime.timedelta(days=90)
    start_of_current_year = today.replace(month=1, day=1)
    
    start_of_last_year = today.replace(year=today.year - 1, month=1, day=1)
    end_of_last_year = today.replace(year=today.year - 1, month=12, day=31)
    
    # Last Year Upcoming Month (દા.ત. અત્યારે ઓગસ્ટ હોય તો સપ્ટેમ્બર-ગયા વર્ષનો ડેટા)
    target_month = today.month + 1
    target_year = today.year - 1
    if target_month > 12:
        target_month = 1
        target_year = today.year
        
    start_upcoming_last_year = datetime.date(target_year, target_month, 1)
    last_day = calendar.monthrange(target_year, target_month)[1]
    end_upcoming_last_year = datetime.date(target_year, target_month, last_day)

    # ---------------- આવક અને નફો ----------------
    sales_data = InvoiceItem.objects.filter(invoice__shop=user).aggregate(
        total_revenue=Sum(F('quantity') * F('selling_price'), output_field=DecimalField()),
        total_cost=Sum(F('quantity') * F('product__purchase_price'), output_field=DecimalField())
    )
    total_revenue = sales_data['total_revenue'] or 0
    total_cost = sales_data['total_cost'] or 0
    total_profit = total_revenue - total_cost
    total_invoices = Invoice.objects.filter(shop=user).count()

    # ---------------- ડેટા કાઢવા માટેનું ફંક્શન ----------------
    def get_sales_data(start_date, end_date=None, limit=20):
        filters = {'invoice__shop': user, 'invoice__date__gte': start_date}
        if end_date:
            filters['invoice__date__lte'] = end_date
            
        return InvoiceItem.objects.filter(**filters).values(
            'product__id', 'product__name', 'product__company_name'
        ).annotate(total_sold=Sum('quantity')).order_by('-total_sold')[:limit]

    # 5 અલગ-અલગ રિપોર્ટ્સ (Top 20)
    top_last_month = get_sales_data(last_30_days)
    top_last_quarter = get_sales_data(last_90_days)
    top_current_year = get_sales_data(start_of_current_year)
    top_last_year = get_sales_data(start_of_last_year, end_of_last_year)
    top_upcoming_last_year = get_sales_data(start_upcoming_last_year, end_upcoming_last_year)

    # ---------------- Master Algorithm (Top 25) ----------------
    master_scores = {}
    def apply_weight(queryset, weight):
        for item in queryset:
            pid = item['product__id']
            if pid not in master_scores:
                master_scores[pid] = {
                    'name': item['product__name'],
                    'company': item['product__company_name'],
                    'score': 0,
                }
            master_scores[pid]['score'] += float(item['total_sold']) * weight

    # અલ્ગોરિધમના વજન (Weights)
    apply_weight(top_upcoming_last_year, 2.0)  # સીઝન (સૌથી વધુ મહત્વ)
    apply_weight(top_last_month, 1.5)          # કરંટ ટ્રેન્ડ
    apply_weight(top_last_quarter, 1.2)        # શોર્ટ ટર્મ ટ્રેન્ડ
    apply_weight(top_current_year, 1.0)        # આ વર્ષનો ટ્રેન્ડ
    apply_weight(top_last_year, 0.8)           # ગયા વર્ષનો ઇતિહાસ

    # પોઈન્ટ્સ સોર્ટ કરીને Top 25 કાઢો
    master_report = sorted(master_scores.values(), key=lambda x: x['score'], reverse=True)[:25]
    upcoming_month_name = start_upcoming_last_year.strftime('%B %Y')

    context = {
        'total_revenue': total_revenue,
        'total_profit': total_profit,
        'total_invoices': total_invoices,
        'top_last_month': top_last_month,
        'top_last_quarter': top_last_quarter,
        'top_current_year': top_current_year,
        'top_last_year': top_last_year,
        'top_upcoming_last_year': top_upcoming_last_year,
        'upcoming_month_name': upcoming_month_name,
        'master_report': master_report,
    }
    return render(request, 'analysis.html', context)


# ==========================================
# 2. Pandas & ML JSON API (તમારી જૂની સિસ્ટમ માટે)
# ==========================================
@login_required
def overall(request):
    items = InvoiceItem.objects.filter(invoice__shop=request.user).values(
        'product__name', 'product__category__name', 'quantity', 'selling_price', 'invoice__date'
    )
    data = pd.DataFrame(list(items))

    if data.empty:
        return JsonResponse({"error": "No sales data found. Please generate some bills first."}, status=404)

    data.rename(columns={
        'product__name': 'ProductName',
        'product__category__name': 'CategoryName',
        'selling_price': 'Selling Price',
        'quantity': 'Quantity',
        'invoice__date': 'Date'
    }, inplace=True)

    try:
        today = datetime.datetime.now()
        last_year = today - pd.DateOffset(months=12)
        data['Date'] = pd.to_datetime(data['Date'], errors='coerce')
        filtered_data = data[data['Date'] >= last_year]

        grouped_data = filtered_data.groupby('ProductName').agg({
            'Quantity': 'sum',
            'Selling Price': 'mean',
            'CategoryName': 'first'
        }).reset_index()

        grouped_data['Purchase Price'] = grouped_data['Selling Price'] / 1.1 

        X = grouped_data[['Quantity']]
        y = grouped_data['Quantity']
        model = LinearRegression()
        model.fit(X, y)
        
        grouped_data['Predicted_Next_Month_Sales'] = model.predict(X)
        grouped_data = grouped_data.sort_values(by='Predicted_Next_Month_Sales', ascending=False)

        buying_suggestions = []
        for _, row in grouped_data.iterrows():
            buying_suggestions.append({
                "ProductName": row['ProductName'],
                "CategoryName": row['CategoryName'],
                "Predicted_Next_Month_Sales": round(row['Predicted_Next_Month_Sales'], 2),
                "SellingPrice": round(row['Selling Price'], 2),
                "PurchasePrice": round(row['Purchase Price'], 2)
            })

        return JsonResponse({"buying_suggestions": buying_suggestions}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)