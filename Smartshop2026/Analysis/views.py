from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
import pandas as pd
from datetime import datetime
from sklearn.linear_model import LinearRegression
from Inventory.models import InvoiceItem 

@login_required
def analysis(request):
    return render(request, 'analysis.html')

@login_required
def overall(request):
    # CSV ને બદલે સીધા ડેટાબેઝમાંથી ડેટા ખેંચો
    items = InvoiceItem.objects.filter(invoice__shop=request.user).values(
        'product__name', 
        'product__category__name', 
        'quantity', 
        'selling_price', 
        'invoice__date'
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
        today = datetime.now()
        last_year = today - pd.DateOffset(months=12)
        data['Date'] = pd.to_datetime(data['Date'], errors='coerce')
        filtered_data = data[data['Date'] >= last_year]

        grouped_data = filtered_data.groupby('ProductName').agg({
            'Quantity': 'sum',
            'Selling Price': 'mean',
            'CategoryName': 'first'
        }).reset_index()

        grouped_data['Purchase Price'] = grouped_data['Selling Price'] / 1.1 

        # ML Model (Linear Regression)
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